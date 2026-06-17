"""
Construccion y clasificacion de oportunidades (esquema neutral: `precio_tienda`/
`url_tienda` en vez de `precio_<bot>`/`url_<bot>`).
"""


def construir_oportunidad(carta: dict, calculo: dict, url_scg: str | None = None) -> dict:
    foil_raw = carta.get("foil", False)

    # Normalizacion robusta a boolean
    if isinstance(foil_raw, bool):
        foil = foil_raw
    elif isinstance(foil_raw, str):
        foil = foil_raw.strip().lower() in ("foil", "yes", "true", "1")
    else:
        foil = False

    return {
        "scryfall_id": carta["scryfall_id"],
        "nombre": carta["nombre"],
        "expansion": carta["expansion"],
        "foil": foil,
        "full_art": carta.get("full_art", False),
        "precio_tienda": calculo["precio_tienda"],
        "precio_scg": calculo["precio_scg"],
        "diferencia": calculo["diferencia"],
        "porcentaje": calculo["porcentaje"],
        "image_url": carta.get("image_url"),
        "url_tienda": carta.get("url_tienda"),
        "url_scg": url_scg,
    }


def clasificar_oportunidad(calculo):
    """
    Devuelve nivel y prioridad (prioridad mas baja = menos interesante).
    Las bandas (40/60/80) son las del original; se mantienen fieles.
    """
    pct = calculo["porcentaje"]

    if pct >= 80:
        return {"nivel": "🔥 ALTA", "prioridad": 3}
    elif pct >= 60:
        return {"nivel": "✅ MEDIA", "prioridad": 2}
    elif pct >= 40:
        return {"nivel": "🟡 BAJA", "prioridad": 1}

    return None
