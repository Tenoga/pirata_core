"""
Config compartida de pirata_core: rutas del cache SCG, credenciales (via env) y
el dataclass PirataConfig con los parametros por bot.

El cache SCG es el MISMO que usa botPrecios (Projects/SCG_Cache/scg_cache). Con
install EDITABLE, __file__ vive en el arbol fuente real
(automation/pirata_core/pirata_core/config.py), asi que parents[3] resuelve a
Projects correctamente (a diferencia de precios_core, que al instalarse no-
editable caia en el venv). Aun asi se permite override por env PIRATA_CACHE_DIR.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Cada bot corre desde su propia carpeta; carga su .env (umbrales, dolar, chats).
load_dotenv()


def _default_cache_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "SCG_Cache" / "scg_cache"


CACHE_DIR = Path(os.getenv("PIRATA_CACHE_DIR") or _default_cache_dir())
CACHE_SCG_MANUAL = CACHE_DIR / "cache_scg_manual.json"
CACHE_SCG_NO_ENCONTRADAS = CACHE_DIR / "scg_no_encontradas.json"


def _int_env(nombre: str, default: int) -> int:
    """Lee un entero del entorno tolerando espacios/comentarios sueltos."""
    valor = os.getenv(nombre)
    if valor is None:
        return default
    try:
        return int(str(valor).split("#")[0].strip())
    except (TypeError, ValueError):
        return default


@dataclass
class PirataConfig:
    """Parametros por bot. Lo unico que cambia entre los 4 (mas su scraper)."""

    nombre: str                       # nombre display, ej. "BotPirataDraco"
    emoji: str = ""                   # emoji del bot para Telegram, ej. "🐲"
    url_base: str = ""                # url del sitio (la usa el scraper per-bot)
    total_paginas: int | None = None  # tope de paginas (Draco); None en API bots
    max_workers: int = 8
    porcentaje_minimo: int = field(
        default_factory=lambda: _int_env("PORCENTAJE_MINIMO", 40)
    )
    diferencia_minima: int = field(
        default_factory=lambda: _int_env("DIFERENCIA_MINIMA", 8500)
    )
    cache_encontrada_dias: int = field(
        default_factory=lambda: _int_env("CACHE_ENCONTRADA_EXPIRA_DIAS", 7)
    )
    cache_no_encontrada_dias: int = field(
        default_factory=lambda: _int_env("CACHE_NO_ENCONTRADA_EXPIRA_DIAS", 7)
    )
