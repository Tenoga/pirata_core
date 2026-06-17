import os
import json
import threading
import logging

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional, Any

from .config import CACHE_SCG_MANUAL, CACHE_SCG_NO_ENCONTRADAS

# 🔒 Lock en proceso para evitar condiciones de carrera
_IN_PROCESS_LOCK = threading.Lock()


# -------------------------------------------------
# Utilidades
# -------------------------------------------------

def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _atomic_write_json(path: Path, data: Any) -> None:
    """
    Escritura atómica usando archivo temporal en el mismo directorio.
    Previene corrupción de cache si el proceso se interrumpe.
    """
    _ensure_parent_dir(path)
    
    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=str(path.parent),
        prefix=".tmp_scg_",
        suffix=".json"
    ) as tf:
        json.dump(data, tf, ensure_ascii=False, indent=2)
        tmp_name = tf.name

    os.replace(tmp_name, path)


def _is_valid_cache_structure(data: Any, logger: logging.Logger) -> bool:
    """
    Valida que el cache tenga estructura:
    {
        scryfall_id: {
            finish: {
                url: str (http...),
                comentario?: str
            }
        }
    }
    """

    if not isinstance(data, dict):
        logger.error("La cache manual no es dict.")
        return False

    for scryfall_id, finishes in data.items():

        if not isinstance(scryfall_id, str):
            logger.warning(f"Clave raíz no es string: {scryfall_id!r}")
            return False

        if not isinstance(finishes, dict):
            logger.warning(f"Valor para {scryfall_id} no es dict: {type(finishes)}")
            return False

        for finish, payload in finishes.items():

            if not isinstance(finish, str):
                logger.warning(f"Finish no es string: {finish!r}")
                return False

            if not isinstance(payload, dict):
                logger.warning(f"Payload no es dict para {scryfall_id}/{finish}: {type(payload)}")
                return False

            url = payload.get("url")
            if not isinstance(url, str) or not url.startswith("http"):
                logger.warning(f"URL inválida para {scryfall_id}/{finish}: {url!r}")
                return False

            comentario = payload.get("comentario", None)
            if comentario is not None and not isinstance(comentario, str):
                logger.warning(
                    f"'comentario' no es string para {scryfall_id}/{finish}: {type(comentario)}"
                )
                return False

    return True


# -------------------------------------------------
# Cache manual (BASE + OVERLAY)
# -------------------------------------------------

def cargar_cache_scg_manual(
    ruta: Optional[str] = None,
    logger: Optional[logging.Logger] = None
) -> dict:

    path = Path(ruta or CACHE_SCG_MANUAL).expanduser().resolve()

    if logger:
        logger.info(f"Cargando cache SCG desde {path}")

    if not path.exists():

        if logger:
            logger.info("Cache SCG no existe. Se inicializa vacío.")

        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            if logger:
                logger.warning("Cache SCG corrupto. Se reinicia.")
            return {}

        if logger:
            logger.info(f"Cache_encontradas cargada | IDs={len(data)}")

        return data

    except Exception as e:

        if logger:
            logger.exception(f"Error leyendo cache SCG: {e}")

        return {}

def cargar_cache_scg_no_encontradas(
    ruta: Optional[str] = None,
    logger: Optional[logging.Logger] = None
) -> dict:

    path = Path(ruta or CACHE_SCG_NO_ENCONTRADAS).expanduser().resolve()

    if logger:
        logger.info(f"Cargando cache de NO encontradas desde {path}")

    if not path.exists():
        if logger:
            logger.info("Cache de no encontradas no existe aún. Se inicializa vacío.")
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            if logger:
                logger.warning("Cache de no encontradas corrupto (no es dict). Se reinicia.")
            return {}

        if logger:
            logger.info(f"Cache no_encontradas cargada | IDs={len(data)}")

        return data

    except Exception as e:
        if logger:
            logger.exception(f"Error leyendo cache de no encontradas: {e}")
        return {}

def actualizar_uso_cache_no_encontrada(
    scryfall_id: str,
    finish: str,
    cache: dict,
    logger=None
) -> bool:

    if scryfall_id not in cache:
        return False

    if finish not in cache[scryfall_id]:
        return False

    cache[scryfall_id][finish]["ultima_vez_usado"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if logger:
        logger.debug(f"🔄 Cache no encontrada actualizado: {scryfall_id} ({finish})")

    return True

def guardar_cache_scg_manual(
    data: dict,
    ruta_overlay: Optional[str] = None,
    logger: Optional[logging.Logger] = None
) -> bool:
    """
    Guarda SOLO overlay (nunca escribe base empaquetada).

    Usa escritura atómica + lock para evitar corrupción concurrente.
    """

    if not isinstance(data, dict):
        logger.error("`data` debe ser dict.")
        return False

    if not _is_valid_cache_structure(data, logger):
        logger.error("Estructura de cache inválida; no se escribirá.")
        return False

    overlay_path = Path(ruta_overlay or CACHE_SCG_MANUAL).expanduser().resolve()

    if overlay_path is None:
        logger.error("No existe ruta overlay para guardar cache.")
        return False

    with _IN_PROCESS_LOCK:
        try:
            _atomic_write_json(overlay_path, data)
            logger.info(f"Overlay guardado en {overlay_path}")
            return True

        except Exception as e:
            logger.exception(f"Error guardando overlay en {overlay_path}: {e}")
            return False

def guardar_cache_scg_no_encontradas(data, logger=None):

    path = Path(CACHE_SCG_NO_ENCONTRADAS)

    try:
        _atomic_write_json(path, data)

        if logger:
            logger.info(f"Cache NO encontradas guardado | IDs={len(data)}")

        return True

    except Exception as e:

        if logger:
            logger.exception(f"Error guardando cache no_encontradas: {e}")

        return False



def registrar_uso_cache_scg_manual(
    scryfall_id: str,
    titulo: str,
    finish: str,
    url: str,
    cache: dict,
    comentario: Optional[str] = None,
    logger: Optional[logging.Logger] = None
) -> bool:

    if not scryfall_id or not finish or not url:
        if logger:
            logger.error("Datos insuficientes para registrar cache.")
        return False

    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    finish = finish.strip()

    if scryfall_id not in cache:
        cache[scryfall_id] = {}

    accion = None

    if finish not in cache[scryfall_id]:

        cache[scryfall_id][finish] = {
            "titulo": titulo,
            "url": url,
            "comentario": comentario or "",
            "ultima_vez_usado": fecha_hora
        }

        accion = "creado"

    else:

        cache[scryfall_id][finish]["ultima_vez_usado"] = fecha_hora
        accion = "actualizado"

    if logger:
        if accion == "creado":
            logger.info(f"🆕 Cache creado (RAM): {scryfall_id} | {finish}")
        else:
            logger.debug(f"🔄 Cache actualizado (RAM): {scryfall_id} | {finish}")

    return True



def registrar_no_encontrada_scg(
    scryfall_id: str,
    urls_intentadas: list,
    titulo: str,
    expansion: str,
    collector_number: str,
    finish: str,
    cache: dict,
    logger: Optional[logging.Logger] = None
) -> bool:

    if not scryfall_id:
        if logger:
            logger.error("No se puede registrar no encontrada sin scryfall_id.")
        return False

    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    finish = finish.strip()

    if scryfall_id not in cache:
        cache[scryfall_id] = {}

    if finish in cache[scryfall_id]:
        if logger:
            logger.debug(f"⚠ Ya registrada como no encontrada: {scryfall_id} | {finish}")
        return True

    cache[scryfall_id][finish] = {
        "titulo": titulo,
        "urls_intentadas": urls_intentadas,
        "comentario": f"No encontrada automáticamente | {titulo} | {expansion} | {collector_number}",
        "ultima_vez_usado": fecha_hora
    }

    if logger:
        logger.info(f"🚫 Registrada como NO encontrada (RAM): {scryfall_id} | {finish}")

    return True



def eliminar_cache_encontrada_scg(
    scryfall_id: str,
    cache: dict,
    finish: str | None = None,
    logger=None
) -> bool:
    """
    Elimina registros del cache de cartas encontradas.

    - Si finish=None → elimina todo el scryfall_id
    - Si finish="Foil"/"Non-Foil" → elimina solo esa versión
    """

    if scryfall_id not in cache:
        logger.warning(f"⚠️ ScryfallID no existe en cache encontradas: {scryfall_id}")
        return False

    # eliminar todo el ID
    if finish is None:
        del cache[scryfall_id]
        logger.info(f"🗑️ Eliminado cache SCG completo: {scryfall_id}")
        return True

    entry = cache[scryfall_id]

    if finish in entry:
        del entry[finish]
        logger.info(f"🗑️ Eliminado cache SCG: {scryfall_id} | finish={finish}")

        # si ya no quedan finishes eliminar el ID
        if not entry:
            del cache[scryfall_id]
            logger.info(f"🧹 Eliminado ScryfallID vacío del cache: {scryfall_id}")

        return True

    logger.warning(
        f"⚠️ Finish no encontrado en cache SCG: {scryfall_id} | finish={finish}"
    )
    return False


def eliminar_cache_no_encontrada_scg(
    scryfall_id: str,
    cache: dict,
    finish: str | None = None,
    logger=None
) -> bool:
    """
    Elimina registros del cache de NO encontradas.
    """

    if scryfall_id not in cache:
        logger.warning(f"⚠️ ScryfallID no existe en cache no_encontradas: {scryfall_id}")
        return False

    if finish is None:
        del cache[scryfall_id]
        logger.info(f"🗑️ Eliminado NO encontrada completo: {scryfall_id}")
        return True

    entry = cache[scryfall_id]

    if finish in entry:
        del entry[finish]
        logger.info(f"🗑️ Eliminado NO encontrada: {scryfall_id} | finish={finish}")

        if not entry:
            del cache[scryfall_id]
            logger.info(f"🧹 Eliminado ScryfallID vacío del cache no_encontradas")

        return True

    logger.warning(
        f"⚠️ Finish no encontrado en cache no_encontradas: {scryfall_id} | finish={finish}"
    )
    return False


def limpiar_cache_antiguo(
    cache: dict,
    dias_expiracion: int,
    logger
) -> int:

    dias_expiracion = int(dias_expiracion)
    ahora = datetime.now()
    eliminados = 0

    # Lista para evitar modificar dict mientras se recorre
    scryfall_ids = list(cache.keys())

    for scryfall_id in scryfall_ids:

        finishes = list(cache[scryfall_id].keys())

        for finish in finishes:

            data = cache[scryfall_id][finish]
            fecha_str = data.get("ultima_vez_usado")

            # 🧹 Si no tiene fecha → eliminar
            if not fecha_str:

                del cache[scryfall_id][finish]
                eliminados += 1

                logger.debug(
                    f"🧹 Eliminado cache sin fecha: {scryfall_id} | {finish}"
                )

                continue

            try:
                fecha = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                logger.warning(
                    f"⚠️ Fecha inválida en cache: {scryfall_id} | {finish}"
                )
                continue

            if ahora - fecha > timedelta(days=dias_expiracion):

                del cache[scryfall_id][finish]
                eliminados += 1

                logger.debug(
                    f"🧹 Eliminado cache expirado: {scryfall_id} | {finish}"
                )

        # si ya no quedan finishes eliminar el scryfall_id
        if not cache[scryfall_id]:
            del cache[scryfall_id]

    return eliminados