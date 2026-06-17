"""
Conversion de precio USD -> COP. Migrado de utils/helper.py (duplicado en los 4
bots, bug #7); identico a precios_core. MAGIC_DOLAR/TAX_PAGE se leen del entorno
en tiempo de ejecucion.
"""

import math
import os
import re


def redondear_arriba(valor):
    """Redondea hacia arriba al siguiente multiplo de 100."""
    return math.ceil(valor / 100) * 100


def convertir_a_cop_usd(precioSCG):
    """
    Convierte un precio en USD (string) a COP redondeado hacia arriba.
    Devuelve None si el precio es vacio o no numerico.
    """
    if not precioSCG:
        return None

    precio_limpio = re.sub(r'[^\d.]', '', str(precioSCG))
    if precio_limpio == '':
        return None

    try:
        valor_float = float(precio_limpio)
    except ValueError:
        return None

    try:
        tipo_cambio = float(os.getenv("MAGIC_DOLAR", 5000))
        impuesto = float(os.getenv("TAX_PAGE", 0))
    except ValueError:
        tipo_cambio = 5000
        impuesto = 0

    valor_neto = valor_float * tipo_cambio + impuesto
    return f"{redondear_arriba(valor_neto):.2f}"
