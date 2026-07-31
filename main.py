"""
main.py
--------
Ponto de entrada do bot. Rode com:  python main.py
"""

import discord
from discord.ext import commands

import config
import database
from ui_components import PainelMetasView, ResetarRankingView, eh_admin

# ------------------------------------------------------------------
# Intents necessárias
# ------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True  # necessário para capturar o print comprovante
intents.members = True          # necessário para ler os cargos do usuário

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    database.init_db()
    # Registra a view do painel como persistente (funciona após reiniciar o bot)
    bot.add_view(PainelMetasView())
    await bot.tree.sync()
    print(f"✅ Bot conectado como {bot.user} (ID: {bot.user.id})")


# ------------------------------------------------------------------
# /enviar_painel — publica o painel com os 3 botões no canal atual
# ------------------------------------------------------------------
@bot.tree.command(
    name="enviar_painel",
    description="Publica o painel de Registro de Metas neste canal (uso administrativo).",
)
async def enviar_painel(interaction: discord.Interaction):
    if not eh_admin(interaction.user):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar isso.", ephemeral=True
        )
        return

    embed = discord.Embed(
        title="📊 Registro de Metas — Lisboa Criadores",
        description=(
            "🔄 O ranking reseta mensalmente via `/resetar_ranking`.\n\n"
            "📊 **Registrar Meta** — envie o registro da sua live.\n"
            "📈 **Meu Progresso** — veja quantas horas você já fez neste ciclo.\n"
            "🏆 **Ver Ranking** — veja a classificação de horas de todos os criadores."
        ),
        color=discord.Color.blurple(),
    )
    await interaction.channel.send(embed=embed, view=PainelMetasView())
    await interaction.response.send_message("✅ Painel publicado!", ephemeral=True)


# ------------------------------------------------------------------
# /resetar_ranking — comando administrativo
# ------------------------------------------------------------------
@bot.tree.command(
    name="resetar_ranking",
    description="Reseta o ranking de um período/tipo específico (uso administrativo).",
)
async def resetar_ranking(interaction: discord.Interaction):
    if not eh_admin(interaction.user):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar isso.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        "Selecione o que deseja resetar:",
        view=ResetarRankingView(),
        ephemeral=True,
    )


if __name__ == "__main__":
    bot.run(config.TOKEN)
