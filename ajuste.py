# ajuste.py — rodar uma vez e depois apagar
import sqlite3
import config

ID_RP = "1017"   # Lucas Castro
HORAS = 3        # quanto somar

conn = sqlite3.connect(config.DB_PATH)
conn.row_factory = sqlite3.Row

antes = conn.execute(
    "SELECT COALESCE(SUM(horas_feitas),0) t FROM registros WHERE id_rp=?",
    (ID_RP,)).fetchone()["t"]

conn.execute(
    """UPDATE registros SET horas_feitas = horas_feitas + ?
       WHERE id = (SELECT id FROM registros WHERE id_rp=? ORDER BY id DESC LIMIT 1)""",
    (HORAS, ID_RP),
)
conn.commit()

depois = conn.execute(
    "SELECT COALESCE(SUM(horas_feitas),0) t FROM registros WHERE id_rp=?",
    (ID_RP,)).fetchone()["t"]

conn.close()
print(f"id_rp {ID_RP}: {antes:.1f}h -> {depois:.1f}h")