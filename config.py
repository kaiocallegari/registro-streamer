"""
Configurações do Bot de Registro de Metas — Alta RJ Criadores
--------------------------------------------------------------
Preencha os valores abaixo com os IDs do seu servidor antes de rodar o bot.

Como pegar um ID no Discord:
1. Ative o "Modo Desenvolvedor" em Configurações > Avançado.
2. Clique com o botão direito no canal/cargo/servidor e escolha "Copiar ID".
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------------
# TOKEN DO BOT
# Recomendado: definir a variável de ambiente DISCORD_TOKEN em vez de
# colocar o token direto aqui (mais seguro).
# ------------------------------------------------------------------
TOKEN = os.getenv("DISCORD_TOKEN")

# ------------------------------------------------------------------
# CARGOS (Roles) que definem o tier do criador
# ------------------------------------------------------------------
CARGO_TIER_4_ID = 1471198191046099140    # ID do cargo "Tier 4"
CARGO_TIER_3_ID = 1471198192094937251    # ID do cargo "Tier 3"
CARGO_TIER_2_ID = 1471198193248239637    # ID do cargo "Tier 2"
CARGO_TIER_1_ID = 1471198194401542244    # ID do cargo "Tier 1"

# Cargos que podem usar comandos administrativos (ex: /resetar_ranking, /enviar_painel)
# Coloque quantos cargos quiser nessa lista — todos eles contam como admin.
CARGO_ADMIN_IDS = [
    1465837667030925417,  # Cargo admin 1
    1471194086403997851,  # Cargo admin 2
    1465837667030925413,  # Cargo admin 3
]

# ------------------------------------------------------------------
# CANAIS DE LOG — um canal separado para cada tier
# ------------------------------------------------------------------
CANAL_LOG_TIER_4_ID = 1471278015584534754   # canal de log do Tier 4
CANAL_LOG_TIER_3_ID = 1471278255880278180   # canal de log do Tier 3
CANAL_LOG_TIER_2_ID = 1465837678002966704   # canal de log do Tier 2
CANAL_LOG_TIER_1_ID = 1465837677470552125   # canal de log do Tier 1

# ------------------------------------------------------------------
# REGRAS DE META
# ------------------------------------------------------------------
META_MINIMA_HORAS = 36        # Mínimo de horas exigido por ciclo (mensal)
META_MINIMA_HORAS_SEMANAL = 6  # Mínimo de horas exigido por semana

# Tempo (em segundos) que o bot espera o print comprovante após o formulário
TEMPO_ESPERA_PRINT = 300  # 5 minutos

# Quantas pessoas entram no ranking (a exibição é paginada, então isso
# só define o teto — suporta comunidades grandes, ex: 150-200 pessoas)
TAMANHO_RANKING = 200

# Quantas linhas aparecem por página quando o ranking é exibido
TAMANHO_PAGINA_RANKING = 15

# ------------------------------------------------------------------
# BANCO DE DADOS
# ------------------------------------------------------------------
DB_PATH = "metas.db"
