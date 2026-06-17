"""
Procesa una carta: busca en SCG (via pirata_core.scg), compara contra el precio
de la tienda y decide si es oportunidad.

Migrado de core/processor.py (identico en los 4 bots salvo naming). Cambios:
  - Esquema neutral: `precio_tienda` en vez de `precio_<bot>`.
  - Los umbrales vienen de `config` (PirataConfig), no de constantes de modulo.
  - Consume SCG via el wrapper desacoplado (extraer_scry_minimo + reintentos).

Fidelidad: se conserva el flujo exacto del original (cache dedup, skip, registro
de no encontradas, clasificacion). El log "EVALUANDO" accede a `calculo` sin
guardarlo igual que el original (si `calculo` es None por precio<=0, cae al
except y devuelve "error" — comportamiento idéntico al de hoy).
"""

import threading

from .scg import buscar_precio_producto
from .cache import (
    registrar_no_encontrada_scg,
    actualizar_uso_cache_no_encontrada,
    eliminar_cache_no_encontrada_scg,
)
from .comparator import calcular_diferencia, es_oportunidad
from .oportunidades import construir_oportunidad, clasificar_oportunidad


def procesar_carta(carta, cache_encontradas, cache_no_encontradas, logger, config):
    try:
        foil = carta.get("foil")

        if isinstance(foil, bool):
            finish = "Foil" if foil else "Non-Foil"
        else:
            finish = foil

        scry = carta.get("scryfall_data")
        scryfall_id = carta.get("scryfall_id")
        titulo = carta.get("nombre", "SIN_TITULO")
        expansion = carta.get("expansion", "SIN_EXPANSION")
        collector_number = carta.get("collector_number", "SIN_COLLECTOR")

        context_id = f"{scryfall_id}-{finish}"

        def log(mensaje, level="info"):
            getattr(logger, level)(f"[{context_id}] {mensaje}")

        log(f"🧵 Thread: {threading.current_thread().name}")
        log(f"🃏 {titulo} | {expansion} | #{collector_number}")

        # Limpieza cache duplicado (mismo id+finish en encontradas y no encontradas)
        if (
            scryfall_id in cache_encontradas
            and scryfall_id in cache_no_encontradas
            and finish in cache_encontradas[scryfall_id]
            and finish in cache_no_encontradas[scryfall_id]
        ):
            log("⚠️ Duplicado en cache", "warning")
            eliminar_cache_no_encontrada_scg(
                scryfall_id, cache_no_encontradas, finish, logger
            )

        # Skip si ya esta registrada como no encontrada
        if (
            scryfall_id in cache_no_encontradas
            and finish in cache_no_encontradas[scryfall_id]
        ):
            log("⏭️ Skip por cache no encontrada")
            actualizar_uso_cache_no_encontrada(
                scryfall_id, finish, cache_no_encontradas, logger
            )
            return "skip", carta

        # Buscar SCG (wrapper desacoplado: extraer_scry_minimo + reintentos)
        try:
            log("🔎 Buscando en SCG...")
            resultado_scg = buscar_precio_producto(
                scry, finish, cache_encontradas, logger
            )
        except Exception as e:
            log(f"⚠️ Error SCG: {e}", "warning")
            return "error", carta

        # Extraer datos
        if isinstance(resultado_scg, dict):
            precioSCG = resultado_scg.get("precio")
            url_scg = resultado_scg.get("url")
            origen = resultado_scg.get("origen")
        else:
            precioSCG = None
            url_scg = None
            origen = None

        # NO ENCONTRADA
        if precioSCG in (None, 0, "No encontrada"):
            log(
                f"⚠️ SCG sin precio | Valor: {precioSCG} | Origen: {origen}",
                "warning",
            )

            if origen == "cache_historico":
                log("🚨 404 EN CACHE", "warning")

            registrar_no_encontrada_scg(
                scryfall_id=scryfall_id,
                urls_intentadas=resultado_scg.get("urls_intentadas", "SIN_URLS")
                if isinstance(resultado_scg, dict) else "SIN_URLS",
                titulo=titulo,
                expansion=expansion,
                collector_number=collector_number,
                finish=finish,
                cache=cache_no_encontradas,
                logger=logger,
            )

            return "no_encontrada", carta

        # MATCH -> calcular
        try:
            precio_scg = float(precioSCG)
        except Exception:
            log("❌ Precio SCG inválido", "warning")
            return "no_encontrada", carta

        precio_tienda = carta.get("precio_tienda", 0)
        calculo = calcular_diferencia(precio_tienda, precio_scg)

        log(
            f"💰 EVALUANDO | Tienda: {precio_tienda} | SCG: {calculo.get('precio_scg_raw')} | "
            f"%: {calculo.get('porcentaje')} | Diff: {calculo.get('diferencia')}"
        )

        if not es_oportunidad(
            calculo, config.porcentaje_minimo, config.diferencia_minima
        ):
            log(
                f"➖ Sin oportunidad | %: {calculo.get('porcentaje')} | "
                f"Diff: {calculo.get('diferencia')}"
            )
            return "match_sin_oportunidad", None

        clasificacion = clasificar_oportunidad(calculo)
        if not clasificacion:
            return "match_sin_oportunidad", None

        oportunidad = construir_oportunidad(carta, calculo, url_scg=url_scg)
        oportunidad["nivel"] = clasificacion["nivel"]
        oportunidad["prioridad"] = clasificacion["prioridad"]

        log(
            f"💎 OPORTUNIDAD | %: {calculo.get('porcentaje')} | "
            f"Diff: {calculo.get('diferencia')}"
        )

        return "oportunidad", oportunidad

    except Exception as e:
        logger.error(f"❌ Error procesando carta: {e}")
        return "error", carta
