"""
Utilidades de scraping compartidas. Lo unico vivo que sobrevive del viejo
utils/helper.py de los bots: la extraccion del scryfall_id desde la URL de
imagen (la usa el scraper Playwright de Draco), mas la extraccion de
set+collector desde el slug del producto (fuente primaria de Draco desde que
dracostore cambio su CDN de imagenes ~2026-06 y el UUID de la img dejo de ser
el scryfall_id).
"""

import re
from urllib.parse import urlparse, parse_qs, unquote


def extraer_scryfall_id_desde_img(img_url):
    if not img_url:
        return None

    try:
        parsed = urlparse(img_url)
        query = parse_qs(parsed.query)

        if "url" not in query:
            return None

        real_url = unquote(query["url"][0])

        # buscar UUID
        match = re.search(
            r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',
            real_url
        )

        if match:
            return match.group(1)

    except Exception:
        return None

    return None


def extraer_set_cn_desde_url(url):
    """
    Extrae (set_code, collector_number) del slug de una URL de producto tipo
    dracostore: /carta/<nombre-slug>-<set>-<collector>. Con eso Scryfall se
    consulta por /cards/{set}/{cn} sin depender de la URL de la imagen.

    Devuelve la tupla en minusculas o None si el slug no calza con el patron
    (el caller puede caer al fallback por imagen).
    """
    if not url:
        return None

    try:
        slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
        partes = [p for p in slug.lower().split("-") if p]

        # minimo nombre + set + collector
        if len(partes) < 3:
            return None

        set_code, cn = partes[-2], partes[-1]

        # set: 2-6 alfanumerico con al menos una letra (mh3, dsc, som...)
        if not re.fullmatch(r"[0-9a-z]{2,6}", set_code) or set_code.isdigit():
            return None

        # collector: alfanumerico con al menos un digito (25, 224b...)
        if not re.fullmatch(r"[0-9a-z]{1,7}", cn) or not any(c.isdigit() for c in cn):
            return None

        return set_code, cn

    except Exception:
        return None
