"""
Utilidades de scraping compartidas. Lo unico vivo que sobrevive del viejo
utils/helper.py de los bots: la extraccion del scryfall_id desde la URL de
imagen (la usa el scraper Playwright de Draco).
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
