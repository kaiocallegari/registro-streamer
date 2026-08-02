"""
ui_components.py
------------------
Todos os elementos de interface (botões, formulário/modal e menus de
seleção) usados pelo bot ficam centralizados aqui.
"""

import asyncio
import io
from datetime import datetime

import discord

import config
import database


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
CARGO_POR_TIER = {
    "tier4": config.CARGO_TIER_4_ID,
    "tier3": config.CARGO_TIER_3_ID,
    "tier2": config.CARGO_TIER_2_ID,
    "tier1": config.CARGO_TIER_1_ID,
}
CANAL_LOG_POR_TIER = {
    "tier4": config.CANAL_LOG_TIER_4_ID,
    "tier3": config.CANAL_LOG_TIER_3_ID,
    "tier2": config.CANAL_LOG_TIER_2_ID,
    "tier1": config.CANAL_LOG_TIER_1_ID,
}


async def determinar_tipo(interaction: discord.Interaction) -> str | None:
    """Descobre o tier do usuário (tier4, tier3, tier2 ou tier1) pelos cargos dele."""
    cargos_ids = [r.id for r in interaction.user.roles]
    for tier in ORDEM_TIERS:
        if CARGO_POR_TIER[tier] in cargos_ids:
            return tier
    return None


def eh_admin(member: discord.Member) -> bool:
    """Verifica se o membro tem algum dos cargos de administrador configurados."""
    if member.guild_permissions.administrator:
        return True
    cargos_ids = {r.id for r in member.roles}
    return any(cargo_id in cargos_ids for cargo_id in config.CARGO_ADMIN_IDS)


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
        canal_log = interaction.client.get_channel(CANAL_LOG_POR_TIER[self.tipo])
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
        meta = config.META_MINIMA_HORAS
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

    def __init__(self, dados: list, tipo: str, periodo: str):
        super().__init__(timeout=180)
        self.dados = dados
        self.tipo = tipo
        self.periodo = periodo
        self.pagina = 0
        self.tamanho_pagina = config.TAMANHO_PAGINA_RANKING
        self.total_paginas = max(1, -(-len(dados) // self.tamanho_pagina))  # ceil
        self._atualizar_botoes()

    def _atualizar_botoes(self):
        self.anterior.disabled = self.pagina == 0
        self.proxima.disabled = self.pagina >= self.total_paginas - 1

    def montar_embed(self) -> discord.Embed:
        rotulo_periodo = (
            f"Ciclo {database.ciclo_atual()}"
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
        if not eh_admin(interaction.user):
            await interaction.response.send_message(
                "❌ Você não tem permissão para usar isso.", ephemeral=True
            )
            return

        periodo, tipo = select.values[0].split(":")
        apagados = database.resetar_periodo(tipo, periodo)
        await interaction.response.edit_message(
            content=f"✅ Ranking resetado! ({apagados} registros removidos)",
            view=None,
        )
