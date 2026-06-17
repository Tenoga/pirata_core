"""
Orquestacion compartida de los bots piratas: el main() de cada bot,
parametrizado. Toma un frontend per-bot que emite lotes de cartas neutrales y
hace TODO lo demas (dedup, proceso paralelo contra SCG, cache, Telegram, Excel,
resumen).

Mirror de precios_core.escanear_precios: devuelve un resumen serializable y
acepta on_progress / should_cancel / notificar -> deja lista la Fase 2 (disparar
desde el backend + panel de oportunidades + cancelacion).

Contrato del frontend per-bot:
    generar_cartas(config, logger) -> Iterator[list[carta]]
donde cada `carta` es un dict con esquema neutral ya enriquecido con Scryfall:
    {scryfall_id, nombre, expansion, set_code, collector_number, scryfall_data,
     foil(bool), precio_tienda(float COP), url_tienda, image_url, full_art?}
Draco emite muchos lotes (uno por pagina, streaming); los bots API emiten uno
solo (todo de golpe). ejecutar funciona igual para ambos.
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .cache import (
    cargar_cache_scg_manual,
    cargar_cache_scg_no_encontradas,
    guardar_cache_scg_manual,
    guardar_cache_scg_no_encontradas,
    limpiar_cache_antiguo,
)
from .processor import procesar_carta
from .notifier import enviar_mensaje_telegram
from .reporte import generar_reporte_excel


def _formatear_tiempo(segundos: float) -> str:
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = int(segundos % 60)
    return f"{h}h {m}m {s}s" if h else (f"{m}m {s}s" if m else f"{s}s")


def _barra_progreso(idx, total, inicio, prefijo, ancho=30):
    progreso = idx / total if total else 1
    relleno = int(ancho * progreso)
    barra = f"[{'#' * relleno}{'-' * (ancho - relleno)}]"
    elapsed = time.time() - inicio
    eta = int((elapsed / idx) * (total - idx)) if idx else 0
    mins, secs = divmod(eta, 60)
    print(
        f"\r{prefijo} {barra} {progreso*100:5.1f}% ({idx}/{total}) | ETA {mins:02d}m {secs:02d}s",
        end="",
    )
    sys.stdout.flush()


def _key(c):
    return (c.get("scryfall_id"), "Foil" if c.get("foil") else "Non-Foil")


def ejecutar(generar_cartas, config, logger, *, notificar=True, generar_excel=True,
             on_progress=None, should_cancel=None) -> dict:
    logger.info(
        f"======================= INICIANDO {config.nombre} ======================="
    )
    inicio = time.time()

    # ---- Cache SCG (compartido con botPrecios) ----
    cache_encontradas = cargar_cache_scg_manual(logger=logger)
    cache_no_encontradas = cargar_cache_scg_no_encontradas(logger=logger)

    elim_e = limpiar_cache_antiguo(cache_encontradas, config.cache_encontrada_dias, logger)
    elim_ne = limpiar_cache_antiguo(cache_no_encontradas, config.cache_no_encontrada_dias, logger)
    logger.info(f"🧹 Limpieza cache SCG | encontradas: {elim_e} | no encontradas: {elim_ne}")

    oportunidades_unicas = {}
    no_encontradas = []
    total_productos = 0
    procesados = 0
    cancelado = False

    try:
        for lote in generar_cartas(config, logger):
            if should_cancel and should_cancel():
                cancelado = True
                logger.warning("⏹️ Cancelacion solicitada; cortando.")
                break

            total_productos += len(lote)

            # dedup dentro del lote por (scryfall_id, finish)
            lote = list({_key(c): c for c in lote}.values())

            inicio_lote = time.time()
            idx = 0

            with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
                futures = [
                    executor.submit(
                        procesar_carta, c, cache_encontradas, cache_no_encontradas, logger, config
                    )
                    for c in lote
                ]

                for future in as_completed(futures):
                    estado, resultado = "error", None
                    try:
                        estado, resultado = future.result()
                        if estado == "oportunidad":
                            oportunidades_unicas[_key(resultado)] = resultado
                        elif estado in ("no_encontrada", "error"):
                            no_encontradas.append(resultado)
                    except Exception as e:
                        logger.error(f"💥 Error en thread: {e}")

                    idx += 1
                    procesados += 1
                    _barra_progreso(idx, len(lote), inicio_lote, f"💰 {config.nombre}")
                    if on_progress:
                        on_progress(procesados, total_productos, {"estado": estado, "carta": resultado})

            print()
    finally:
        logger.info("💾 Guardando caches en disco...")
        guardar_cache_scg_manual(cache_encontradas, logger=logger)
        guardar_cache_scg_no_encontradas(cache_no_encontradas, logger=logger)
        logger.info("✅ Caches guardados correctamente")

    oportunidades = sorted(
        oportunidades_unicas.values(),
        key=lambda op: (op["prioridad"], -op["porcentaje"], -op["diferencia"]),
    )

    logger.info(
        f"✅ Comparación SCG finalizada → "
        f"{len(oportunidades)} oportunidades / {len(no_encontradas)} no encontradas"
    )

    if notificar and not cancelado:
        _enviar_oportunidades(oportunidades, logger)
        _enviar_no_encontradas(no_encontradas, config, logger)
        _enviar_resumen(config, total_productos, no_encontradas, oportunidades, inicio, logger)

    if generar_excel and not cancelado:
        generar_reporte_excel(oportunidades, logger, enviar_telegram=notificar)

    return {
        "nombre": config.nombre,
        "total_evaluadas": total_productos,
        "encontradas": total_productos - len(no_encontradas),
        "no_encontradas": len(no_encontradas),
        "oportunidades": len(oportunidades),
        "oportunidades_detalle": oportunidades,
        "cancelado": cancelado,
        "tiempo": _formatear_tiempo(time.time() - inicio),
    }


# =====================================================
# Telegram (mismos textos del main original, parametrizados por config)
# =====================================================

def _enviar_oportunidades(oportunidades, logger):
    logger.info(f"📨 Enviando {len(oportunidades)} oportunidades a Telegram")
    total = len(oportunidades)
    inicio = time.time()
    for idx, op in enumerate(oportunidades, start=1):
        mensaje = (
            f"💎 <b>Oportunidad detectada</b>\n"
            f"─────────────\n"
            f"🏷️ Oportunidad: {op.get('nivel','')}\n"
            f"🃏 <b>Carta:</b> {op.get('nombre', 'DESCONOCIDO')}\n"
            f"📦 <b>Expansion:</b> {op.get('expansion', '')}\n"
            f"✨ <b>Finishing:</b> {'Foil' if op.get('foil') else 'No Foil'}\n\n"
            f"📦 <b>Full Art:</b> {op.get('full_art', 'No tiene')}\n"
            f"💰 Tienda: ${int(op.get('precio_tienda',0)):,} COP\n"
            f"🏷️ Precio Venta: ${int(op.get('precio_scg',0)):,} COP\n"
            f"📊 Ganancia: ${int(op.get('diferencia',0)):,} COP\n\n"
            f"📈 % de Ganancia: {op.get('porcentaje',0)}%\n"
            f"─────────────\n"
            f"🆔 ScryfallID: {op.get('scryfall_id','No tiene')}\n"
            f"🔗 URL Tienda: {op.get('url_tienda','')}\n"
            f"⭐ URL SCG: {op.get('url_scg','')}\n"
        )
        enviar_mensaje_telegram(op.get("image_url"), mensaje)
        time.sleep(0.3)
        _barra_progreso(idx, total, inicio, "📤 Telegram Oportunidades")
    print()


def _enviar_no_encontradas(no_encontradas, config, logger):
    logger.info(f"📨 Enviando {len(no_encontradas)} cartas no encontradas a Telegram")
    total = len(no_encontradas)
    inicio = time.time()
    for idx, carta in enumerate(no_encontradas, start=1):
        mensaje = (
            f"❌ <b>Carta no encontrada</b> ❌\n"
            f"─────────────\n"
            f"{config.emoji} <b>Origen:</b> {config.nombre}\n"
            f"🃏 <b>Carta:</b> {carta.get('nombre', 'DESCONOCIDO')}\n"
            f"📦 <b>Expansion:</b> {carta.get('expansion', '')}\n"
            f"✨ <b>Finishing:</b> {'Foil' if carta.get('foil') else 'No Foil'}\n\n"
            f"📦 <b>Full Art:</b> {carta.get('full_art', 'No tiene')}\n"
            f"🆔 <b>ScryfallID:</b> {carta.get('scryfall_id', 'No tiene')}\n"
        )
        enviar_mensaje_telegram(carta.get("image_url"), mensaje)
        time.sleep(0.3)
        _barra_progreso(idx, total, inicio, "📤 Telegram No encontradas")
    print()


def _enviar_resumen(config, total_productos, no_encontradas, oportunidades, inicio, logger):
    tiempo = _formatear_tiempo(time.time() - inicio)
    no_match = len(no_encontradas)
    match = total_productos - no_match
    mensaje = (
        "🏴‍☠️ <b>Resumen del botín</b>\n"
        "─────────────\n"
        f"⏱️ <b>Tiempo total:</b> {tiempo}\n\n"
        f"📊 <b>Porcentaje mínimo usado:</b> {config.porcentaje_minimo}%\n"
        f"💰 <b>Diferencia mínima:</b> ${config.diferencia_minima:,.0f}\n\n"
        f"📦 <b>Cartas evaluadas:</b> {total_productos}\n"
        f"✅ <b>Encontradas en SCG:</b> {match}\n"
        f"❌ <b>No encontradas:</b> {no_match}\n\n"
        f"💎 <b>Oportunidades detectadas:</b> {len(oportunidades)}"
    )
    enviar_mensaje_telegram(None, mensaje)
    logger.info("✅ Resumen enviado a Telegram")
