"""
ui.py
------
Todos os elementos de interface (botões, formulário/modal e menus de
seleção) usados pelo bot, incluindo o comando administrativo /config,
ficam centralizados aqui.
"""

import asyncio
import io
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands

import config
import database
import utils


# ====================================================================
# Utilidades
# ====================================================================
def formatar_horas(horas: float) -> str:
    """Formata horas com uma casa decimal, sem zeros desnecessários."""
    if horas == int(horas):
        return f"{int(horas)}h"
    return f"{horas:.1f}h"


def barra_progresso(horas: float, meta: float, tamanho: int = 10) -> str:
    proporcao = min(horas / meta, 1.0) if meta > 0 else 0
    preenchido = round(proporcao * tamanho)
    return "🟩" * preenchido + "⬛" * (tamanho - preenchido)


# Ordem de exibição dos tiers: 4, 3, 2, 1 (do mais baixo para o mais alto)
ORDEM_TIERS = ["tier4", "tier3", "tier2", "tier1"]
NOME_TIPO = {"tier4": "Tier 4", "tier3": "Tier 3", "tier2": "Tier 2", "tier1": "Tier 1"}


async def determinar_tipo(interaction: discord.Interaction) -> str | None:
    """Descobre o tier do usuário (tier4, tier3, tier2 ou tier1) pelos cargos dele."""
    cargos_ids = [r.id for r in interaction.user.roles]
    for tier in ORDEM_TIERS:
        if utils.cargo_tier(tier) in cargos_ids:
            return tier
    return None


def eh_admin(member: discord.Member) -> bool:
    """Verifica se o membro tem algum dos cargos de administrador configurados."""
    if member.guild_permissions.administrator:
        return True
    cargos_ids = {r.id for r in member.roles}
    return any(cargo_id in cargos_ids for cargo_id in utils.cargo_admin_ids())


def eh_admin_servidor(member: discord.Member) -> bool:
    """Verifica se o membro tem a permissão de Administrador do servidor
    (mais restrito que eh_admin — usado em ações destrutivas como resetar o ranking)."""
    return member.guild_permissions.administrator


# ====================================================================
# Canal de log geral (todo comando/ação usado no bot é registrado aqui)
# ====================================================================
async def registrar_log(interaction: discord.Interaction, descricao: str) -> None:
    """Manda uma linha de log pro canal geral (utils.canal_log_comandos())
    com quem fez o quê."""
    canal_log = interaction.client.get_channel(utils.canal_log_comandos())
    if canal_log:
        canal_origem = f" em {interaction.channel.mention}" if interaction.channel else ""
        await canal_log.send(f"🔹 {interaction.user.mention} — {descricao}{canal_origem}")


# ====================================================================
# Formulário (Modal) de Registro de Meta
# ====================================================================
class RegistrarMetaModal(discord.ui.Modal, title="Registro de Meta"):
    nome_rp = discord.ui.TextInput(
        label="NOME RP",
        style=discord.TextStyle.short,
        placeholder="ex: skyler",
        max_length=50,
        required=True,
    )
    id_rp = discord.ui.TextInput(
        label="ID RP",
        style=discord.TextStyle.short,
        placeholder="ex: 158",
        max_length=20,
        required=True,
    )
    dia = discord.ui.TextInput(
        label="DIA DA LIVE",
        style=discord.TextStyle.short,
        placeholder="ex: 01/08",
        max_length=10,
        required=True,
    )
    horas_feitas = discord.ui.TextInput(
        label="HORAS FEITAS",
        style=discord.TextStyle.short,
        placeholder="ex: 3.40",
        max_length=6,
        required=True,
    )

    def __init__(self, tipo: str):
        super().__init__()
        self.tipo = tipo

    async def on_submit(self, interaction: discord.Interaction):
        # Valida o campo de horas
        texto_horas = self.horas_feitas.value.strip().replace(",", ".")
        try:
            horas = float(texto_horas)
            if horas <= 0 or horas > 24:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ O campo **Horas Feitas** precisa ser um número válido de horas "
                "(entre 0 e 24). Tente novamente clicando em **Registrar Meta**.",
                ephemeral=True,
            )
            return

        # Painel de instruções (mais bonito que uma mensagem de texto simples)
        embed_aguardando = discord.Embed(
            title="📎 Falta só uma coisa!",
            description=(
                "Formulário recebido com sucesso.\n\n"
                "Agora **anexe uma imagem aqui neste canal** com o print "
                "comprovante da sua live (é só mandar a imagem numa mensagem normal)."
            ),
            color=discord.Color.blurple(),
        )
        embed_aguardando.add_field(
            name="⏳ Tempo limite",
            value=f"{config.TEMPO_ESPERA_PRINT // 60} minutos",
        )
        embed_aguardando.set_footer(text="Só você pode ver esta mensagem")
        await interaction.response.send_message(embed=embed_aguardando, ephemeral=True)

        def checar_print(m: discord.Message) -> bool:
            return (
                m.author.id == interaction.user.id
                and m.channel.id == interaction.channel.id
                and len(m.attachments) > 0
            )

        try:
            mensagem_print = await interaction.client.wait_for(
                "message", timeout=config.TEMPO_ESPERA_PRINT, check=checar_print
            )
        except asyncio.TimeoutError:
            await interaction.followup.send(
                "⌛ Tempo esgotado esperando o print comprovante. "
                "Clique novamente em **Registrar Meta** para tentar de novo.",
                ephemeral=True,
            )
            return

        # Baixa os bytes da imagem e reenvia como anexo próprio do bot.
        # Isso é necessário porque, se a mensagem original for apagada depois,
        # o link do anexo do Discord para de funcionar e a imagem some dos embeds.
        anexo = mensagem_print.attachments[0]
        dados_imagem = await anexo.read()
        nome_arquivo = anexo.filename

        database.registrar_meta(
            user_id=interaction.user.id,
            tipo=self.tipo,
            nome_rp=self.nome_rp.value.strip(),
            id_rp=self.id_rp.value.strip(),
            dia=self.dia.value.strip(),
            horas_feitas=horas,
            print_url="",  # preenchido abaixo, depois que o Discord gera a URL definitiva
        )

        def montar_embed(titulo: str, cor: discord.Color) -> discord.Embed:
            embed = discord.Embed(title=titulo, color=cor, timestamp=datetime.now())
            embed.set_author(
                name=str(interaction.user), icon_url=interaction.user.display_avatar.url
            )
            embed.add_field(name="👤 Criador", value=interaction.user.mention, inline=True)
            embed.add_field(name="🏷️ Tier", value=NOME_TIPO[self.tipo], inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=True)
            embed.add_field(name="📝 Nome RP", value=self.nome_rp.value.strip(), inline=True)
            embed.add_field(name="🆔 ID RP", value=self.id_rp.value.strip(), inline=True)
            embed.add_field(name="📅 Dia da Live", value=self.dia.value.strip(), inline=True)
            embed.add_field(name="⏱️ Horas Feitas", value=formatar_horas(horas), inline=True)
            embed.set_image(url=f"attachment://{nome_arquivo}")
            return embed

        # Confirmação para o usuário (ephemeral)
        embed_usuario = montar_embed("✅ Meta registrada com sucesso!", discord.Color.green())
        arquivo_usuario = discord.File(io.BytesIO(dados_imagem), filename=nome_arquivo)
        await interaction.followup.send(embed=embed_usuario, file=arquivo_usuario, ephemeral=True)

        # Log no canal do tier correspondente, com a imagem já embutida no embed
        canal_log = interaction.client.get_channel(utils.canal_log_tier(self.tipo))
        if canal_log:
            embed_log = montar_embed("📋 Nova Meta Registrada", discord.Color.blurple())
            arquivo_log = discord.File(io.BytesIO(dados_imagem), filename=nome_arquivo)
            mensagem_log = await canal_log.send(embed=embed_log, file=arquivo_log)

            # Guarda a URL definitiva do print (útil para consultas futuras)
            if mensagem_log.attachments:
                database.atualizar_print_url(
                    interaction.user.id, self.dia.value.strip(), mensagem_log.attachments[0].url
                )

        # Apaga a mensagem original do print no canal público para manter o chat limpo
        try:
            await mensagem_print.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        await registrar_log(
            interaction,
            f"registrou uma meta (**{NOME_TIPO[self.tipo]}**, {formatar_horas(horas)}, dia {self.dia.value.strip()})",
        )


# ====================================================================
# Seletor de tipo (usado só se o usuário não tiver nenhum cargo de tier)
# ====================================================================
class SelecionarTipoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.select(
        placeholder="Qual é o seu tier?",
        options=[
            discord.SelectOption(label="Tier 4", value="tier4", emoji="4️⃣"),
            discord.SelectOption(label="Tier 3", value="tier3", emoji="3️⃣"),
            discord.SelectOption(label="Tier 2", value="tier2", emoji="2️⃣"),
            discord.SelectOption(label="Tier 1", value="tier1", emoji="1️⃣"),
        ],
    )
    async def selecionar(self, interaction: discord.Interaction, select: discord.ui.Select):
        tipo = select.values[0]
        await interaction.response.send_modal(RegistrarMetaModal(tipo=tipo))


# ====================================================================
# Painel principal — Registrar Meta / Meu Progresso / Ver Ranking
# ====================================================================
class PainelMetasView(discord.ui.View):
    """View persistente: precisa dos mesmos custom_id sempre que o bot reiniciar."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Registrar Meta",
        emoji="📊",
        style=discord.ButtonStyle.primary,
        custom_id="painel_registrar_meta",
    )
    async def registrar_meta(self, interaction: discord.Interaction, button: discord.ui.Button):
        tipo = await determinar_tipo(interaction)
        if tipo is None:
            await interaction.response.send_message(
                "Antes de continuar, me diga qual é o seu tier:",
                view=SelecionarTipoView(),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(RegistrarMetaModal(tipo=tipo))
        await registrar_log(interaction, "clicou em **Registrar Meta**")

    @discord.ui.button(
        label="Meu Progresso",
        emoji="📈",
        style=discord.ButtonStyle.secondary,
        custom_id="painel_meu_progresso",
    )
    async def meu_progresso(self, interaction: discord.Interaction, button: discord.ui.Button):
        tipo = await determinar_tipo(interaction)
        if tipo is None:
            await interaction.response.send_message(
                "Você ainda não possui nenhum cargo de tier, então não há progresso para mostrar.",
                ephemeral=True,
            )
            return

        horas_ciclo = database.progresso_usuario(interaction.user.id, tipo, "ciclo")
        meta = utils.meta_minima_horas()
        falta = max(meta - horas_ciclo, 0)
        atingida = horas_ciclo >= meta
        proporcao = min(horas_ciclo / meta, 1.0) if meta > 0 else 0

        embed = discord.Embed(
            title=f"📊 Seu progresso este mês ({database.ciclo_atual()})",
            color=discord.Color.green() if atingida else discord.Color.blurple(),
        )
        embed.add_field(name="🏷️ Tier", value=NOME_TIPO[tipo], inline=False)
        embed.add_field(
            name="🕒 Horas feitas",
            value=f"{formatar_horas(horas_ciclo)} de {formatar_horas(meta)}",
            inline=False,
        )
        embed.add_field(name="📈 Progresso", value=f"{proporcao * 100:.0f}%", inline=True)
        embed.add_field(name="⚡ Falta", value=formatar_horas(falta), inline=True)
        embed.add_field(
            name="\u200b",
            value=barra_progresso(horas_ciclo, meta),
            inline=False,
        )
        embed.add_field(
            name="\u200b",
            value="✅ Meta atingida! Parabéns!" if atingida else "🔸 Continue registrando suas lives!",
            inline=False,
        )
        embed.set_footer(text="Só você pode ver esta mensagem")

        await interaction.response.send_message(embed=embed, ephemeral=True)
        await registrar_log(interaction, "consultou **Meu Progresso**")

    @discord.ui.button(
        label="Ver Ranking",
        emoji="🏆",
        style=discord.ButtonStyle.success,
        custom_id="painel_ver_ranking",
    )
    async def ver_ranking(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Escolha o tipo de ranking:",
            view=SelecionarRankingView(),
            ephemeral=True,
        )
        await registrar_log(interaction, "abriu **Ver Ranking**")


def _opcoes_ranking(emoji_ciclo: str, emoji_semana: str):
    """Gera as 8 opções (ciclo/semana x tier4..tier1) na ordem 4, 3, 2, 1."""
    opcoes = []
    for periodo, emoji in (("ciclo", emoji_ciclo), ("semana", emoji_semana)):
        rotulo_periodo = "Ciclo Mensal" if periodo == "ciclo" else "Semanal"
        for tier in ORDEM_TIERS:
            opcoes.append(
                discord.SelectOption(
                    label=f"{rotulo_periodo} — {NOME_TIPO[tier]}",
                    value=f"{periodo}:{tier}",
                    emoji=emoji,
                )
            )
    return opcoes


class RankingPaginatorView(discord.ui.View):
    """Pagina o ranking em blocos de N pessoas para aguentar comunidades grandes
    (ex: 150-200 criadores) sem estourar o limite de caracteres do Discord."""

    def __init__(self, dados: list, tipo: str, periodo: str, ciclo: str = None):
        super().__init__(timeout=180)
        self.dados = dados
        self.tipo = tipo
        self.periodo = periodo
        self.ciclo = ciclo  # ciclo específico (usado pelo /historico); None = ciclo atual
        self.pagina = 0
        self.tamanho_pagina = config.TAMANHO_PAGINA_RANKING
        self.total_paginas = max(1, -(-len(dados) // self.tamanho_pagina))  # ceil
        self._atualizar_botoes()

    def _atualizar_botoes(self):
        self.anterior.disabled = self.pagina == 0
        self.proxima.disabled = self.pagina >= self.total_paginas - 1

    def montar_embed(self) -> discord.Embed:
        rotulo_periodo = (
            f"Ciclo {self.ciclo or database.ciclo_atual()}"
            if self.periodo == "ciclo"
            else f"Semana {database.semana_atual()}"
        )
        embed = discord.Embed(
            title=f"🏆 Ranking {NOME_TIPO[self.tipo]} — {rotulo_periodo}",
            color=discord.Color.gold(),
        )

        if not self.dados:
            embed.description = "Ainda não há registros para este período."
            return embed

        medalhas = ["🥇", "🥈", "🥉"]
        inicio = self.pagina * self.tamanho_pagina
        fim = inicio + self.tamanho_pagina
        linhas = []
        for posicao, (user_id, total_horas) in enumerate(self.dados[inicio:fim], start=inicio + 1):
            prefixo = medalhas[posicao - 1] if posicao <= 3 else f"{posicao}."
            linhas.append(f"{prefixo} <@{user_id}> — {formatar_horas(total_horas)}")

        embed.description = "\n".join(linhas)
        embed.set_footer(
            text=f"Página {self.pagina + 1}/{self.total_paginas} • {len(self.dados)} criadores no total"
        )
        return embed

    @discord.ui.button(label="◀️ Anterior", style=discord.ButtonStyle.secondary)
    async def anterior(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina = max(0, self.pagina - 1)
        self._atualizar_botoes()
        await interaction.response.edit_message(embed=self.montar_embed(), view=self)

    @discord.ui.button(label="Próxima ▶️", style=discord.ButtonStyle.secondary)
    async def proxima(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.pagina = min(self.total_paginas - 1, self.pagina + 1)
        self._atualizar_botoes()
        await interaction.response.edit_message(embed=self.montar_embed(), view=self)


# ====================================================================
# Seletor de ranking (Ciclo/Semanal x Tier 4/3/2/1)
# ====================================================================
class SelecionarRankingView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.select(
        placeholder="Escolha o tipo de ranking",
        options=_opcoes_ranking("🏆", "📊"),
    )
    async def selecionar(self, interaction: discord.Interaction, select: discord.ui.Select):
        periodo, tipo = select.values[0].split(":")
        dados = database.ranking(tipo, periodo, limite=config.TAMANHO_RANKING)

        paginador = RankingPaginatorView(dados, tipo, periodo)
        embed = paginador.montar_embed()
        embed.set_footer(
            text=(embed.footer.text + " • " if embed.footer.text else "")
            + "Só você pode ver esta mensagem"
        )
        await interaction.response.edit_message(content=None, embed=embed, view=paginador)

        rotulo_periodo = "Ciclo Mensal" if periodo == "ciclo" else "Semanal"
        await registrar_log(interaction, f"visualizou o ranking **{rotulo_periodo} — {NOME_TIPO[tipo]}**")


# ====================================================================
# Confirmação usada antes de apagar de fato os registros
# ====================================================================
class ConfirmarResetView(discord.ui.View):
    def __init__(self, tipo: str, periodo: str):
        super().__init__(timeout=60)
        self.tipo = tipo
        self.periodo = periodo

    @discord.ui.button(label="✅ Confirmar reset", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not eh_admin_servidor(interaction.user):
            await interaction.response.send_message(
                "❌ Você não tem permissão para usar isso.", ephemeral=True
            )
            return

        apagados = database.resetar_periodo(self.tipo, self.periodo)
        await interaction.response.edit_message(
            content=f"✅ Ranking resetado! ({apagados} registros removidos)",
            view=None,
        )

        rotulo_periodo = "Ciclo Mensal" if self.periodo == "ciclo" else "Semanal"
        await registrar_log(
            interaction,
            f"⚠️ **RESETOU** o ranking **{rotulo_periodo} — {NOME_TIPO[self.tipo]}** "
            f"({apagados} registros apagados)",
        )

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not eh_admin_servidor(interaction.user):
            await interaction.response.send_message(
                "❌ Você não tem permissão para usar isso.", ephemeral=True
            )
            return

        await interaction.response.edit_message(content="🚫 Reset cancelado.", view=None)

        rotulo_periodo = "Ciclo Mensal" if self.periodo == "ciclo" else "Semanal"
        await registrar_log(
            interaction, f"cancelou o reset de **{rotulo_periodo} — {NOME_TIPO[self.tipo]}**"
        )


# ====================================================================
# Seletor usado pelo comando administrativo /resetar_ranking
# ====================================================================
class ResetarRankingView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.select(
        placeholder="O que deseja resetar?",
        options=_opcoes_ranking("🔄", "🔄"),
    )
    async def selecionar(self, interaction: discord.Interaction, select: discord.ui.Select):
        if not eh_admin_servidor(interaction.user):
            await interaction.response.send_message(
                "❌ Só administradores do servidor podem usar isso.", ephemeral=True
            )
            return

        periodo, tipo = select.values[0].split(":")
        rotulo_periodo = "Ciclo Mensal" if periodo == "ciclo" else "Semanal"
        await interaction.response.edit_message(
            content=(
                f"⚠️ Tem certeza que quer resetar **{rotulo_periodo} — {NOME_TIPO[tipo]}**?\n"
                "Essa ação apaga os registros permanentemente e não pode ser desfeita."
            ),
            view=ConfirmarResetView(tipo, periodo),
        )
        await registrar_log(
            interaction,
            f"selecionou resetar **{rotulo_periodo} — {NOME_TIPO[tipo]}** (aguardando confirmação)",
        )


# ====================================================================
# Fluxo do comando administrativo /historico (consulta de meses anteriores)
# ====================================================================
class SelecionarTierHistoricoView(discord.ui.View):
    """Segundo passo do /historico: depois de escolher o mês, escolhe o tier."""

    def __init__(self, ciclo: str):
        super().__init__(timeout=120)
        self.ciclo = ciclo

    @discord.ui.select(
        placeholder="Escolha o tier",
        options=[discord.SelectOption(label=NOME_TIPO[tier], value=tier) for tier in ORDEM_TIERS],
    )
    async def selecionar(self, interaction: discord.Interaction, select: discord.ui.Select):
        tipo = select.values[0]
        dados = database.ranking_por_ciclo(tipo, self.ciclo, limite=config.TAMANHO_RANKING)

        paginador = RankingPaginatorView(dados, tipo, "ciclo", ciclo=self.ciclo)
        embed = paginador.montar_embed()
        embed.set_footer(
            text=(embed.footer.text + " • " if embed.footer.text else "")
            + "Só você pode ver esta mensagem"
        )
        await interaction.response.edit_message(content=None, embed=embed, view=paginador)

        await registrar_log(
            interaction, f"consultou o histórico **{self.ciclo} — {NOME_TIPO[tipo]}**"
        )


class SelecionarCicloHistoricoView(discord.ui.View):
    """Primeiro passo do /historico: escolhe o mês/ano (ciclo) a consultar,
    a partir dos ciclos que realmente existem no banco."""

    def __init__(self, ciclos: list[str]):
        super().__init__(timeout=120)
        # Opções montadas em runtime (o Discord permite no máximo 25 por menu)
        self.selecionar.options = [
            discord.SelectOption(label=ciclo, value=ciclo, emoji="🗓️") for ciclo in ciclos[:25]
        ]

    @discord.ui.select(placeholder="Escolha o mês/ano")
    async def selecionar(self, interaction: discord.Interaction, select: discord.ui.Select):
        ciclo = select.values[0]
        await interaction.response.edit_message(
            content=f"Mês selecionado: **{ciclo}**. Agora escolha o tier:",
            view=SelecionarTierHistoricoView(ciclo),
        )
        await registrar_log(interaction, f"selecionou o mês **{ciclo}** no histórico")


# ====================================================================
# Comando /config — painel de configuração administrativa do bot.
# Liberado pra quem tem permissão de Administrador do servidor OU um dos
# cargos admin extra configurados (mesma regra usada em /enviar_painel).
# ====================================================================
OPCOES_TIER = [app_commands.Choice(name=NOME_TIPO[t], value=t) for t in ORDEM_TIERS]


def _construir_embed_config() -> discord.Embed:
    """Embed com o resumo de tudo que está configurado — usado tanto pelo
    /config ver quanto pelo painel visual /config painel."""
    embed = discord.Embed(title="⚙️ Central de Configuração", color=discord.Color.blurple())

    linhas_tier = []
    for tier in ORDEM_TIERS:
        cargo_id = utils.cargo_tier(tier)
        canal_id = utils.canal_log_tier(tier)
        linhas_tier.append(f"**{NOME_TIPO[tier]}** — cargo <@&{cargo_id}> • log <#{canal_id}>")
    embed.add_field(name="🏷️ Tiers", value="\n".join(linhas_tier), inline=False)

    admins = utils.cargo_admin_ids()
    embed.add_field(
        name="🛡️ Cargos admin extra",
        value="\n".join(f"<@&{cargo_id}>" for cargo_id in admins) if admins else "Nenhum",
        inline=False,
    )

    embed.add_field(
        name="📋 Canal de log geral",
        value=f"<#{utils.canal_log_comandos()}>",
        inline=False,
    )

    embed.add_field(
        name="🎯 Meta mínima",
        value=(
            f"{utils.meta_minima_horas():g}h mensal • "
            f"{utils.meta_minima_horas_semanal():g}h semanal"
        ),
        inline=False,
    )
    embed.set_footer(text="Só você pode ver esta mensagem")
    return embed


# ====================================================================
# Painel visual (/config painel) — alternativa em botões/menus ao
# /config <subcomando>, pra quem prefere não digitar.
# ====================================================================
class VoltarButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="◀️ Voltar", style=discord.ButtonStyle.secondary, row=4)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=_construir_embed_config(), view=CentralConfigView())


class EscolherCargoTierView(discord.ui.View):
    def __init__(self, tier: str):
        super().__init__(timeout=180)
        self.tier = tier
        self.select_cargo.placeholder = f"Novo cargo para {NOME_TIPO[tier]}"
        self.add_item(VoltarButton())

    @discord.ui.select(cls=discord.ui.RoleSelect, min_values=1, max_values=1)
    async def select_cargo(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        cargo = select.values[0]
        antigo = utils.cargo_tier(self.tier)
        utils.definir_cargo_tier(self.tier, cargo.id)

        await interaction.response.edit_message(embed=_construir_embed_config(), view=CargosAreaView())
        await registrar_log(
            interaction, f"mudou o cargo do **{NOME_TIPO[self.tier]}** de <@&{antigo}> para {cargo.mention}"
        )


class AdminExtraRoleSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(VoltarButton())

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Selecione os cargos admin (substitui a lista atual)",
        min_values=0,
        max_values=25,
    )
    async def select_cargos(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        antigos = set(utils.cargo_admin_ids())
        novos = {cargo.id for cargo in select.values}
        utils.definir_cargo_admin_ids(list(novos))

        await interaction.response.edit_message(embed=_construir_embed_config(), view=CargosAreaView())

        adicionados = novos - antigos
        removidos = antigos - novos
        if adicionados or removidos:
            partes = []
            if adicionados:
                partes.append("adicionou " + ", ".join(f"<@&{c}>" for c in adicionados))
            if removidos:
                partes.append("removeu " + ", ".join(f"<@&{c}>" for c in removidos))
            await registrar_log(interaction, f"mudou os cargos admin: {' e '.join(partes)}")


class CargosAreaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(VoltarButton())

    @discord.ui.select(
        placeholder="Qual cargo você quer configurar?",
        options=(
            [
                discord.SelectOption(label=NOME_TIPO[t], value=t, description=f"Cargo do {NOME_TIPO[t]}")
                for t in ORDEM_TIERS
            ]
            + [
                discord.SelectOption(
                    label="Admin extra", value="admin_extra", description="Cargos com acesso administrativo"
                )
            ]
        ),
    )
    async def selecionar(self, interaction: discord.Interaction, select: discord.ui.Select):
        escolha = select.values[0]
        if escolha == "admin_extra":
            await interaction.response.edit_message(embed=_construir_embed_config(), view=AdminExtraRoleSelectView())
        else:
            await interaction.response.edit_message(
                embed=_construir_embed_config(), view=EscolherCargoTierView(escolha)
            )


class EscolherCanalView(discord.ui.View):
    def __init__(self, destino: str, rotulo: str):
        super().__init__(timeout=180)
        self.destino = destino
        self.select_canal.placeholder = f"Novo canal para {rotulo}"
        self.add_item(VoltarButton())

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], min_values=1, max_values=1)
    async def select_canal(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        canal = select.values[0]

        if self.destino == "geral":
            antigo = utils.canal_log_comandos()
            utils.definir_canal_log_comandos(canal.id)
            descricao_antigo = f"<#{antigo}>"
            rotulo = "log geral"
        else:
            antigo = utils.canal_log_tier(self.destino)
            utils.definir_canal_log_tier(self.destino, canal.id)
            descricao_antigo = f"<#{antigo}>"
            rotulo = f"log do {NOME_TIPO[self.destino]}"

        await interaction.response.edit_message(embed=_construir_embed_config(), view=CanaisAreaView())
        await registrar_log(interaction, f"mudou o canal de {rotulo} de {descricao_antigo} para {canal.mention}")


class CanaisAreaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(VoltarButton())

    @discord.ui.select(
        placeholder="Qual canal você quer configurar?",
        options=(
            [
                discord.SelectOption(
                    label=f"Log {NOME_TIPO[t]}", value=t, description=f"Canal de log do {NOME_TIPO[t]}"
                )
                for t in ORDEM_TIERS
            ]
            + [
                discord.SelectOption(
                    label="Log geral", value="geral", description="Canal de log de todo comando/ação do bot"
                )
            ]
        ),
    )
    async def selecionar(self, interaction: discord.Interaction, select: discord.ui.Select):
        destino = select.values[0]
        rotulo = "log geral" if destino == "geral" else f"log do {NOME_TIPO[destino]}"
        await interaction.response.edit_message(
            embed=_construir_embed_config(), view=EscolherCanalView(destino, rotulo)
        )


class MetaHorasModal(discord.ui.Modal, title="Meta mínima de horas"):
    mensal = discord.ui.TextInput(label="Meta mensal (horas)", style=discord.TextStyle.short, max_length=6)
    semanal = discord.ui.TextInput(label="Meta semanal (horas)", style=discord.TextStyle.short, max_length=6)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            novo_mensal = float(self.mensal.value.strip().replace(",", "."))
            novo_semanal = float(self.semanal.value.strip().replace(",", "."))
        except ValueError:
            await interaction.response.send_message(
                "❌ Os dois campos precisam ser números válidos. Tente novamente.", ephemeral=True
            )
            return

        antigo_mensal = utils.meta_minima_horas()
        antigo_semanal = utils.meta_minima_horas_semanal()
        utils.definir_meta_minima_horas(novo_mensal)
        utils.definir_meta_minima_horas_semanal(novo_semanal)

        await interaction.response.edit_message(embed=_construir_embed_config(), view=MetasAreaView())
        await registrar_log(
            interaction,
            f"mudou a meta mínima: mensal {antigo_mensal:g}h→{novo_mensal:g}h, "
            f"semanal {antigo_semanal:g}h→{novo_semanal:g}h",
        )


class MetasAreaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(VoltarButton())

    @discord.ui.button(label="✏️ Editar metas", style=discord.ButtonStyle.primary, row=0)
    async def editar(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MetaHorasModal()
        modal.mensal.default = f"{utils.meta_minima_horas():g}"
        modal.semanal.default = f"{utils.meta_minima_horas_semanal():g}"
        await interaction.response.send_modal(modal)


class CentralConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.select(
        placeholder="Escolha uma área",
        options=[
            discord.SelectOption(label="Cargos", emoji="🏷️", value="cargos", description="Cargos de tier e admin extra"),
            discord.SelectOption(label="Canais", emoji="📋", value="canais", description="Canais de log"),
            discord.SelectOption(label="Metas", emoji="🎯", value="metas", description="Meta mínima de horas"),
            discord.SelectOption(label="Ver Config", emoji="📄", value="ver", description="Atualizar esta tela"),
        ],
    )
    async def escolher(self, interaction: discord.Interaction, select: discord.ui.Select):
        area = select.values[0]
        vistas = {
            "cargos": CargosAreaView,
            "canais": CanaisAreaView,
            "metas": MetasAreaView,
            "ver": CentralConfigView,
        }
        await interaction.response.edit_message(embed=_construir_embed_config(), view=vistas[area]())


class ConfigGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="config", description="Configurações administrativas do bot.")

    async def _checar_admin(self, interaction: discord.Interaction) -> bool:
        if not eh_admin(interaction.user):
            await interaction.response.send_message(
                "❌ Você não tem permissão para usar isso.", ephemeral=True
            )
            return False
        return True

    @app_commands.command(name="ver", description="Mostra a configuração atual do bot.")
    async def ver(self, interaction: discord.Interaction):
        if not await self._checar_admin(interaction):
            return
        await interaction.response.send_message(embed=_construir_embed_config(), ephemeral=True)

    @app_commands.command(name="painel", description="Abre o painel visual de configuração do bot.")
    async def painel(self, interaction: discord.Interaction):
        if not await self._checar_admin(interaction):
            return
        await interaction.response.send_message(
            embed=_construir_embed_config(), view=CentralConfigView(), ephemeral=True
        )

    @app_commands.command(name="cargo-tier", description="Define qual cargo representa um tier.")
    @app_commands.describe(tier="Qual tier", cargo="Cargo do Discord")
    @app_commands.choices(tier=OPCOES_TIER)
    async def cargo_tier(
        self, interaction: discord.Interaction, tier: app_commands.Choice[str], cargo: discord.Role
    ):
        if not await self._checar_admin(interaction):
            return

        antigo = utils.cargo_tier(tier.value)
        utils.definir_cargo_tier(tier.value, cargo.id)

        await interaction.response.send_message(
            f"✅ Cargo do **{NOME_TIPO[tier.value]}** agora é {cargo.mention}.", ephemeral=True
        )
        await registrar_log(
            interaction,
            f"mudou o cargo do **{NOME_TIPO[tier.value]}** de <@&{antigo}> para {cargo.mention}",
        )

    @app_commands.command(name="canal-log-tier", description="Define o canal de log de um tier.")
    @app_commands.describe(tier="Qual tier", canal="Canal de texto")
    @app_commands.choices(tier=OPCOES_TIER)
    async def canal_log_tier(
        self,
        interaction: discord.Interaction,
        tier: app_commands.Choice[str],
        canal: discord.TextChannel,
    ):
        if not await self._checar_admin(interaction):
            return

        antigo = utils.canal_log_tier(tier.value)
        utils.definir_canal_log_tier(tier.value, canal.id)

        await interaction.response.send_message(
            f"✅ Canal de log do **{NOME_TIPO[tier.value]}** agora é {canal.mention}.",
            ephemeral=True,
        )
        await registrar_log(
            interaction,
            f"mudou o canal de log do **{NOME_TIPO[tier.value]}** de <#{antigo}> para {canal.mention}",
        )

    @app_commands.command(name="canal-logs", description="Define o canal de log geral do bot.")
    @app_commands.describe(canal="Canal de texto")
    async def canal_logs(self, interaction: discord.Interaction, canal: discord.TextChannel):
        if not await self._checar_admin(interaction):
            return

        antigo = utils.canal_log_comandos()
        utils.definir_canal_log_comandos(canal.id)

        await interaction.response.send_message(
            f"✅ Canal de log geral agora é {canal.mention}.", ephemeral=True
        )
        await registrar_log(interaction, f"mudou o canal de log geral de <#{antigo}> para {canal.mention}")

    @app_commands.command(
        name="cargo-admin-adicionar", description="Autoriza um cargo a usar comandos administrativos."
    )
    @app_commands.describe(cargo="Cargo do Discord")
    async def cargo_admin_adicionar(self, interaction: discord.Interaction, cargo: discord.Role):
        if not await self._checar_admin(interaction):
            return

        utils.adicionar_cargo_admin(cargo.id)

        await interaction.response.send_message(
            f"✅ {cargo.mention} agora pode usar comandos administrativos.", ephemeral=True
        )
        await registrar_log(interaction, f"adicionou {cargo.mention} como cargo admin")

    @app_commands.command(
        name="cargo-admin-remover", description="Remove a autorização administrativa de um cargo."
    )
    @app_commands.describe(cargo="Cargo do Discord")
    async def cargo_admin_remover(self, interaction: discord.Interaction, cargo: discord.Role):
        if not await self._checar_admin(interaction):
            return

        utils.remover_cargo_admin(cargo.id)

        await interaction.response.send_message(
            f"✅ {cargo.mention} não é mais um cargo admin.", ephemeral=True
        )
        await registrar_log(interaction, f"removeu {cargo.mention} como cargo admin")

    @app_commands.command(
        name="meta-horas", description="Define a meta mínima de horas mensal e/ou semanal."
    )
    @app_commands.describe(
        mensal="Nova meta mensal em horas (deixe vazio pra não mudar)",
        semanal="Nova meta semanal em horas (deixe vazio pra não mudar)",
    )
    async def meta_horas(
        self,
        interaction: discord.Interaction,
        mensal: Optional[float] = None,
        semanal: Optional[float] = None,
    ):
        if not await self._checar_admin(interaction):
            return

        if mensal is None and semanal is None:
            await interaction.response.send_message(
                "❌ Informe ao menos um valor (mensal ou semanal).", ephemeral=True
            )
            return

        partes = []
        if mensal is not None:
            antigo = utils.meta_minima_horas()
            utils.definir_meta_minima_horas(mensal)
            partes.append(f"mensal de {antigo:g}h para {mensal:g}h")
        if semanal is not None:
            antigo = utils.meta_minima_horas_semanal()
            utils.definir_meta_minima_horas_semanal(semanal)
            partes.append(f"semanal de {antigo:g}h para {semanal:g}h")

        await interaction.response.send_message(f"✅ Meta atualizada ({' e '.join(partes)}).", ephemeral=True)
        await registrar_log(interaction, f"mudou a meta mínima: {' e '.join(partes)}")
