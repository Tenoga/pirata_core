"""
pirata_core - logica reutilizable de los bots piratas de The Vault
(botPirataDraco / botPirataElBulk / botPirataRohan / botPirataTopCard).

Cada bot queda con solo su scraper/frontend (generar_cartas) + config; toda la
logica compartida (SCG, cache, comparador, oportunidades, processor, notifier,
reporte y la orquestacion) vive aqui. Esquema neutral: `precio_tienda`/
`url_tienda` (no `precio_<bot>`).
"""

from .config import PirataConfig
from .scg import buscar_precio_producto
from .scryfall import get_scryfall_data, get_scryfall_data_por_set_cn
from .scrape_utils import extraer_scryfall_id_desde_img, extraer_set_cn_desde_url
from .ejecutar import ejecutar, CorridaAbortada

__all__ = [
    "PirataConfig",
    "buscar_precio_producto",
    "get_scryfall_data",
    "get_scryfall_data_por_set_cn",
    "extraer_scryfall_id_desde_img",
    "extraer_set_cn_desde_url",
    "ejecutar",
    "CorridaAbortada",
]
