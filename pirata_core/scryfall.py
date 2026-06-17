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


def get_scryfall_data(logger, scryfall_id: str, max_reintentos: int = 3):
    """
    Obtiene datos de Scryfall directamente desde la API (sin cache persistente).
    Devuelve el dict de Scryfall o None.
    """
    if not scryfall_id:
        return None

    url = SCRYFALL_API + scryfall_id

    for intento in range(max_reintentos):
        try:
            res = requests.get(url, headers=_HEADERS, timeout=15)

            if res.status_code == 200:
                return res.json()

            elif res.status_code == 429:
                wait = 1.5 * (intento + 1)
                logger.warning(
                    f"⚠️ Scryfall 429 | ID {scryfall_id} "
                    f"| intento {intento + 1}/{max_reintentos} "
                    f"| esperando {wait:.1f}s"
                )
                time.sleep(wait)
                continue

            else:
                logger.warning(
                    f"⚠️ Scryfall respondió {res.status_code} para ID {scryfall_id}"
                )
                return None

        except Exception as e:
            logger.warning(f"❌ Error consultando Scryfall ({scryfall_id}): {e}")
            time.sleep(1)

    logger.error(f"🚫 Scryfall falló tras {max_reintentos} intentos | ID {scryfall_id}")
    return None
