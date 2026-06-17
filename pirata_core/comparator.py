"""
Comparacion de precio de la tienda (COP) vs SCG (USD->COP) y decision de
oportunidad. Esquema neutral: `precio_tienda` en vez de `precio_<bot>`.

Los umbrales se reciben como parametros (vienen de PirataConfig / .env), no como
constantes de modulo: asi se elimina el bug #2 (Draco hardcodeaba 40/8500 e
ignoraba su .env). Hoy el .env de los 4 dice 40/8500, asi que el comportamiento
no cambia; queda consistente y configurable de verdad.
"""

from .precios import convertir_a_cop_usd


def calcular_diferencia(precio_tienda_cop, precio_scg_usd) -> dict | None:
    """
    Tienda viene en COP, SCG en USD; ambos se normalizan a COP.
    Devuelve None si algun precio es invalido o <= 0.
    """
    try:
        precio_tienda_raw = float(precio_tienda_cop)
        precio_scg_raw = float(convertir_a_cop_usd(precio_scg_usd))

        if precio_tienda_raw <= 0 or precio_scg_raw <= 0:
            return None

        diferencia_raw = precio_scg_raw - precio_tienda_raw
        porcentaje_raw = (diferencia_raw / precio_tienda_raw) * 100

        return {
            # valores reales (para decisiones)
            "precio_tienda_raw": precio_tienda_raw,
            "precio_scg_raw": precio_scg_raw,
            "diferencia_raw": diferencia_raw,
            "porcentaje_raw": porcentaje_raw,
            # valores redondeados (solo para mostrar)
            "precio_tienda": round(precio_tienda_raw, 2),
            "precio_scg": round(precio_scg_raw, 2),
            "diferencia": round(diferencia_raw, 2),
            "porcentaje": round(porcentaje_raw, 2),
        }

    except Exception:
        return None


def es_oportunidad(calculo: dict, porcentaje_minimo, diferencia_minima) -> bool:
    """Decide si el calculo representa una oportunidad real."""
    if not calculo:
        return False

    return (
        calculo["precio_tienda_raw"] < calculo["precio_scg_raw"]
        and calculo["porcentaje_raw"] >= porcentaje_minimo
        and calculo["diferencia_raw"] >= diferencia_minima
    )
