"""
database.py
------------
Toda a persistência dos registros de metas fica isolada aqui.
Usa SQLite (arquivo local, sem necessidade de servidor externo).
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import config

# O servidor (Railway) roda em UTC, mas os ciclos/semanas de meta devem
# seguir o horário de Brasília — senão registros feitos à noite (principalmente
# perto da virada do mês/semana) contam pro período errado.
FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")


def agora() -> datetime:
    return datetime.now(FUSO_HORARIO)


# ------------------------------------------------------------------
# Conexão
# ------------------------------------------------------------------
@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Cria a tabela de registros caso ainda não exista."""
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS registros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                tipo TEXT NOT NULL,        -- 'streamer' ou 'influencer'
                nome_rp TEXT NOT NULL,     -- nome RP informado no formulário
                id_rp TEXT NOT NULL,       -- ID RP informado no formulário
                dia TEXT NOT NULL,         -- dia da live informado no formulário
                horas_feitas REAL NOT NULL,-- horas feitas na live (float)
                print_url TEXT,            -- link do print comprovante
                ciclo TEXT NOT NULL,       -- formato MM/AAAA
                semana TEXT NOT NULL,      -- formato AAAA-Wnn (semana ISO)
                criado_em TEXT NOT NULL
            )
            """
        )


# ------------------------------------------------------------------
# Helpers de período
# ------------------------------------------------------------------
def ciclo_atual() -> str:
    return agora().strftime("%m/%Y")


def semana_atual() -> str:
    ano, semana, _ = agora().isocalendar()
    return f"{ano}-W{semana:02d}"


# ------------------------------------------------------------------
# Escrita
# ------------------------------------------------------------------
def registrar_meta(
    user_id: int,
    tipo: str,
    nome_rp: str,
    id_rp: str,
    dia: str,
    horas_feitas: float,
    print_url: str,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO registros
                (user_id, tipo, nome_rp, id_rp, dia, horas_feitas, print_url, ciclo, semana, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(user_id),
                tipo,
                nome_rp,
                id_rp,
                dia,
                horas_feitas,
                print_url,
                ciclo_atual(),
                semana_atual(),
                agora().isoformat(timespec="seconds"),
            ),
        )


# ------------------------------------------------------------------
# Leitura — progresso individual
# ------------------------------------------------------------------
def atualizar_print_url(user_id: int, dia: str, print_url: str) -> None:
    """
    Atualiza a URL do print para o registro mais recente desse usuário
    naquele dia (a URL definitiva só existe depois que a imagem é
    reenviada para o canal de log).
    """
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE registros
            SET print_url = ?
            WHERE id = (
                SELECT id FROM registros
                WHERE user_id = ? AND dia = ?
                ORDER BY id DESC
                LIMIT 1
            )
            """,
            (print_url, str(user_id), dia),
        )


def progresso_usuario(user_id: int, tipo: str, periodo: str = "ciclo") -> float:
    """Retorna a soma de horas do usuário no ciclo ou semana atual."""
    coluna = "ciclo" if periodo == "ciclo" else "semana"
    valor = ciclo_atual() if periodo == "ciclo" else semana_atual()

    with get_conn() as conn:
        row = conn.execute(
            f"""
            SELECT COALESCE(SUM(horas_feitas), 0) AS total
            FROM registros
            WHERE user_id = ? AND tipo = ? AND {coluna} = ?
            """,
            (str(user_id), tipo, valor),
        ).fetchone()
    return row["total"] or 0.0


# ------------------------------------------------------------------
# Leitura — ranking
# ------------------------------------------------------------------
def ranking(tipo: str, periodo: str = "ciclo", limite: int = None):
    """
    Retorna lista de tuplas (user_id, total_horas) ordenada da maior
    para a menor quantidade de horas, filtrando por tipo e período.
    """
    coluna = "ciclo" if periodo == "ciclo" else "semana"
    valor = ciclo_atual() if periodo == "ciclo" else semana_atual()
    limite = limite or config.TAMANHO_RANKING

    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT user_id, SUM(horas_feitas) AS total
            FROM registros
            WHERE tipo = ? AND {coluna} = ?
            GROUP BY user_id
            ORDER BY total DESC
            LIMIT ?
            """,
            (tipo, valor, limite),
        ).fetchall()

    return [(row["user_id"], row["total"]) for row in rows]


# ------------------------------------------------------------------
# Administração — reset manual
# ------------------------------------------------------------------
def resetar_periodo(tipo: str, periodo: str) -> int:
    """
    Apaga os registros do tipo e período informados (uso administrativo,
    ex: /resetar_ranking). Retorna quantas linhas foram apagadas.
    O reset "automático" mensal/semanal já acontece sozinho, pois o
    ranking é sempre calculado com base no ciclo/semana atual — este
    comando serve para forçar uma limpeza antecipada, se necessário.
    """
    coluna = "ciclo" if periodo == "ciclo" else "semana"
    valor = ciclo_atual() if periodo == "ciclo" else semana_atual()

    with get_conn() as conn:
        cur = conn.execute(
            f"DELETE FROM registros WHERE tipo = ? AND {coluna} = ?",
            (tipo, valor),
        )
        return cur.rowcount
