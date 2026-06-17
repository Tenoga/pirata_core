"""
Precio desde SCG para los bots piratas: wrapper desacoplado de
Buscador_SCG.buscar_scg.

Por que existe (la diferencia a corregir): hoy los 4 bots piratas hacen
`from Buscador_SCG import buscar_scg` y lo llaman EN CRUDO desde
core/processor.py, pasandole el objeto Scryfall COMPLETO (scryfall_data, traido
de la API de Scryfall) y sin reintentos. Este wrapper centraliza el consumo
"como se debe", igual que precios_core/scg.py.

Diferencias deliberadas vs precios_core/scg.py (NO es copia ciega; se verifico
contra el codigo real de buscar_scg):
  - precios_core extrae el scry del metafield de Shopify y deduce el foil desde
    el variant_title. Aqui NO: el bot pirata ya tiene el objeto Scryfall (dict)
    y el finish ya calculado ("Foil"/"Non-Foil"), asi que se reciben directos.
  - El finish se pasa SIN transformar. buscar_scg ya hace normalizar_foil()
    internamente; pasar el mismo valor que hoy mantiene el match byte-identico
    (no se adopta el "No-Foil" de precios_core para no alterar las keys de cache).
  - buscar_scg SIEMPRE devuelve un dict (incluso "no encontrada", con
    urls_intentadas/origen), NUNCA None. El processor depende de ese dict para
    registrar_no_encontrada_scg. Por eso este wrapper devuelve el dict TAL CUAL
    (a diferencia de precios_core, que devuelve None en el no-exito). Si se
    agotan los reintentos por una EXCEPCION real (red/SCG caido), RE-LANZA para
    conservar el camino "error" del processor (un fallo transitorio no debe
    quedar cacheado como carta inexistente).

Lo que aporta sobre el uso crudo:
  - extraer_scry_minimo(): recorta el objeto Scryfall completo al subconjunto
    que buscar_scg realmente usa (consumidores recortan en origen).
  - reintentos ante excepcion.
  - logger inyectado (no globals).
"""

import logging
import time

from Buscador_SCG import buscar_scg, extraer_scry_minimo

logger_default = logging.getLogger(__name__)


def buscar_precio_producto(scry, esFoil, cache, logger=None, reintentos=3):
    """
    Busca el precio de una carta en SCG via Buscador_SCG.buscar_scg.

    Parametros:
        scry (dict): objeto Scryfall, completo o ya recortado. Se recorta
            defensivamente con extraer_scry_minimo antes de buscar (buscar_scg
            funciona igual con el completo o el subconjunto).
        esFoil (str): finish tal como lo calcula el bot ("Foil" / "Non-Foil").
            Se pasa sin transformar; buscar_scg lo normaliza internamente.
        cache (dict): cache manual de SCG (encontradas). Si es None se usa {}.
        logger (logging.Logger, opcional): logger inyectado; si es None usa el
            del modulo.
        reintentos (int): intentos ante excepcion (red/SCG). Debe ser >= 1.

    Retorna:
        dict: el resultado de buscar_scg (encontrada o no encontrada), sin
        alterar.

    Lanza:
        la ultima excepcion si se agotan los reintentos por error real.
    """
    if logger is None:
        logger = logger_default

    if cache is None:
        cache = {}

    # Recorte defensivo en origen: el scry pirata viene completo de la API de
    # Scryfall (~75 claves) y buscar_scg solo usa CAMPOS_SCRY_MINIMO.
    scry_min = extraer_scry_minimo(scry)

    for intento in range(1, reintentos + 1):
        try:
            return buscar_scg(
                scry=scry_min,
                esFoil=esFoil,
                cache=cache,
                logger=logger,
            )
        except Exception as e:
            logger.error(
                f"Error buscando en SCG (intento {intento}/{reintentos}): {e}"
            )
            if intento >= reintentos:
                # Agotados los reintentos: propagar para que el processor lo
                # trate como "error" (distinto de "no encontrada").
                raise
            time.sleep(1)
