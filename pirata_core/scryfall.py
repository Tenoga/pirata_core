"""
Fetch de datos de Scryfall por id, con retry/backoff ante 429.

Unifica los dos scryfall_manager divergentes de los bots (bug #3): se toma la
version robusta de los bots API (get_scryfall_data con backoff 429); Draco usaba
una sin retry. Se agrega User-Agent identificable (Scryfall lo pide).
"""

import time

import requests

SCRYFALL_API = "https://api.scryfall.com/cards/"
_HEADERS = {"User-Agent": "TheVault-pirata/1.0", "Accept": "application/json"}


def _fetch_scryfall(logger, url: str, contexto: str, max_reintentos: int):
    for intento in range(max_reintentos):
        try:
            res = requests.get(url, headers=_HEADERS, timeout=15)

            if res.status_code == 200:
                return res.json()

            elif res.status_code == 429:
                wait = 1.5 * (intento + 1)
                logger.warning(
                    f"⚠️ Scryfall 429 | {contexto} "
                    f"| intento {intento + 1}/{max_reintentos} "
                    f"| esperando {wait:.1f}s"
                )
                time.sleep(wait)
                continue

            else:
                logger.warning(
                    f"⚠️ Scryfall respondió {res.status_code} para {contexto}"
                )
                return None

        except Exception as e:
            logger.warning(f"❌ Error consultando Scryfall ({contexto}): {e}")
            time.sleep(1)

    logger.error(f"🚫 Scryfall falló tras {max_reintentos} intentos | {contexto}")
    return None


def get_scryfall_data(logger, scryfall_id: str, max_reintentos: int = 3):
    """
    Obtiene datos de Scryfall directamente desde la API (sin cache persistente).
    Devuelve el dict de Scryfall o None.
    """
    if not scryfall_id:
        return None

    return _fetch_scryfall(
        logger, SCRYFALL_API + scryfall_id, f"ID {scryfall_id}", max_reintentos
    )


def get_scryfall_data_por_set_cn(
    logger, set_code: str, collector_number: str, max_reintentos: int = 3
):
    """
    Obtiene datos de Scryfall por set + collector number (/cards/{set}/{cn}).
    Devuelve el dict de Scryfall o None.
    """
    if not set_code or not collector_number:
        return None

    return _fetch_scryfall(
        logger,
        f"{SCRYFALL_API}{set_code}/{collector_number}",
        f"set/cn {set_code}/{collector_number}",
        max_reintentos,
    )
