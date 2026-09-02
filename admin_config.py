"""
admin_config.py
-----------------
Comando /config — painel de configuração administrativa do bot.
Só aparece pra quem tem permissão de Administrador no servidor (o próprio
Discord já esconde o comando de quem não tem essa permissão).
"""

from typing import Optional

import discord
from discord import app_commands

import config_runtime
from ui_components import NOME_TIPO, ORDEM_TIERS, eh_admin_servidor, registrar_log

OPCOES_TIER = [app_commands.Choice(name=NOME_TIPO[t], value=t) for t in ORDEM_TIERS]


def _construir_embed_config() -> discord.Embed:
    """Embed com o resumo de tudo que está configurado — usado tanto pelo
    /config ver quanto pelo painel visual /config painel."""
    embed = discord.Embed(title="⚙️ Central de Configuração", color=discord.Color.blurple())

    linhas_tier = []
    for tier in ORDEM_TIERS:
        cargo_id = config_runtime.cargo_tier(tier)
        canal_id = config_runtime.canal_log_tier(tier)
        linhas_tier.append(f"**{NOME_TIPO[tier]}** — cargo <@&{cargo_id}> • log <#{canal_id}>")
    embed.add_field(name="🏷️ Tiers", value="\n".join(linhas_tier), inline=False)

    admins = config_runtime.cargo_admin_ids()
    embed.add_field(
        name="🛡️ Cargos admin extra",
        value="\n".join(f"<@&{cargo_id}>" for cargo_id in admins) if admins else "Nenhum",
        inline=False,
    )

    embed.add_field(
        name="📋 Canal de log geral",
        value=f"<#{config_runtime.canal_log_comandos()}>",
        inline=False,
    )

    embed.add_field(
        name="🎯 Meta mínima",
        value=(
            f"{config_runtime.meta_minima_horas():g}h mensal • "
            f"{config_runtime.meta_minima_horas_semanal():g}h semanal"
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
        antigo = config_runtime.cargo_tier(self.tier)
        config_runtime.definir_cargo_tier(self.tier, cargo.id)

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
        antigos = set(config_runtime.cargo_admin_ids())
        novos = {cargo.id for cargo in select.values}
        config_runtime.definir_cargo_admin_ids(list(novos))

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
            antigo = config_runtime.canal_log_comandos()
            config_runtime.definir_canal_log_comandos(canal.id)
            descricao_antigo = f"<#{antigo}>"
            rotulo = "log geral"
        else:
            antigo = config_runtime.canal_log_tier(self.destino)
            config_runtime.definir_canal_log_tier(self.destino, canal.id)
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

        antigo_mensal = config_runtime.meta_minima_horas()
        antigo_semanal = config_runtime.meta_minima_horas_semanal()
        config_runtime.definir_meta_minima_horas(novo_mensal)
        config_runtime.definir_meta_minima_horas_semanal(novo_semanal)

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
        modal.mensal.default = f"{config_runtime.meta_minima_horas():g}"
        modal.semanal.default = f"{config_runtime.meta_minima_horas_semanal():g}"
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


@app_commands.default_permissions(administrator=True)
class ConfigGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="config", description="Configurações administrativas do bot.")

    async def _checar_admin(self, interaction: discord.Interaction) -> bool:
        if not eh_admin_servidor(interaction.user):
            await interaction.response.send_message(
                "❌ Só administradores do servidor podem usar isso.", ephemeral=True
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

        antigo = config_runtime.cargo_tier(tier.value)
        config_runtime.definir_cargo_tier(tier.value, cargo.id)

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

        antigo = config_runtime.canal_log_tier(tier.value)
        config_runtime.definir_canal_log_tier(tier.value, canal.id)

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

        antigo = config_runtime.canal_log_comandos()
        config_runtime.definir_canal_log_comandos(canal.id)

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

        config_runtime.adicionar_cargo_admin(cargo.id)

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

        config_runtime.remover_cargo_admin(cargo.id)

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
            antigo = config_runtime.meta_minima_horas()
            config_runtime.definir_meta_minima_horas(mensal)
            partes.append(f"mensal de {antigo:g}h para {mensal:g}h")
        if semanal is not None:
            antigo = config_runtime.meta_minima_horas_semanal()
            config_runtime.definir_meta_minima_horas_semanal(semanal)
            partes.append(f"semanal de {antigo:g}h para {semanal:g}h")

        await interaction.response.send_message(f"✅ Meta atualizada ({' e '.join(partes)}).", ephemeral=True)
        await registrar_log(interaction, f"mudou a meta mínima: {' e '.join(partes)}")
