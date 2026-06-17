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
from .scryfall import get_scryfall_data
from .scrape_utils import extraer_scryfall_id_desde_img
from .ejecutar import ejecutar

__all__ = [
    "PirataConfig",
    "buscar_precio_producto",
    "get_scryfall_data",
    "extraer_scryfall_id_desde_img",
    "ejecutar",
]
