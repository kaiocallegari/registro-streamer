"""
config_runtime.py
-------------------
Resolve as configurações administráveis pelo comando /config: um valor
salvo no banco (editado pelo painel administrativo) tem prioridade; se
não houver override, cai no padrão definido em config.py.
"""

import json

import config
import database

PADRAO_CARGO_TIER = {
    "tier4": config.CARGO_TIER_4_ID,
    "tier3": config.CARGO_TIER_3_ID,
    "tier2": config.CARGO_TIER_2_ID,
    "tier1": config.CARGO_TIER_1_ID,
}
PADRAO_CANAL_LOG_TIER = {
    "tier4": config.CANAL_LOG_TIER_4_ID,
    "tier3": config.CANAL_LOG_TIER_3_ID,
    "tier2": config.CANAL_LOG_TIER_2_ID,
    "tier1": config.CANAL_LOG_TIER_1_ID,
}


def _chave_cargo_tier(tier: str) -> str:
    return f"cargo_{tier}"


def _chave_canal_log_tier(tier: str) -> str:
    return f"canal_log_{tier}"


def cargo_tier(tier: str) -> int:
    valor = database.get_config(_chave_cargo_tier(tier))
    return int(valor) if valor else PADRAO_CARGO_TIER[tier]


def definir_cargo_tier(tier: str, cargo_id: int) -> None:
    database.set_config(_chave_cargo_tier(tier), str(cargo_id))


def canal_log_tier(tier: str) -> int:
    valor = database.get_config(_chave_canal_log_tier(tier))
    return int(valor) if valor else PADRAO_CANAL_LOG_TIER[tier]


def definir_canal_log_tier(tier: str, canal_id: int) -> None:
    database.set_config(_chave_canal_log_tier(tier), str(canal_id))


def canal_log_comandos() -> int:
    valor = database.get_config("canal_log_comandos")
    return int(valor) if valor else config.CANAL_LOG_COMANDOS_ID


def definir_canal_log_comandos(canal_id: int) -> None:
    database.set_config("canal_log_comandos", str(canal_id))


def cargo_admin_ids() -> list[int]:
    valor = database.get_config("cargo_admin_ids")
    if valor is None:
        return list(config.CARGO_ADMIN_IDS)
    return json.loads(valor)


def adicionar_cargo_admin(cargo_id: int) -> list[int]:
    atuais = cargo_admin_ids()
    if cargo_id not in atuais:
        atuais.append(cargo_id)
        database.set_config("cargo_admin_ids", json.dumps(atuais))
    return atuais


def remover_cargo_admin(cargo_id: int) -> list[int]:
    atuais = cargo_admin_ids()
    if cargo_id in atuais:
        atuais.remove(cargo_id)
        database.set_config("cargo_admin_ids", json.dumps(atuais))
    return atuais


def definir_cargo_admin_ids(ids: list[int]) -> None:
    database.set_config("cargo_admin_ids", json.dumps(ids))


def meta_minima_horas() -> float:
    valor = database.get_config("meta_minima_horas")
    return float(valor) if valor else config.META_MINIMA_HORAS


def definir_meta_minima_horas(horas: float) -> None:
    database.set_config("meta_minima_horas", str(horas))


def meta_minima_horas_semanal() -> float:
    valor = database.get_config("meta_minima_horas_semanal")
    return float(valor) if valor else config.META_MINIMA_HORAS_SEMANAL


def definir_meta_minima_horas_semanal(horas: float) -> None:
    database.set_config("meta_minima_horas_semanal", str(horas))
