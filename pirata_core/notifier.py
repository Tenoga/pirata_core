"""
Notificaciones Telegram: foto+caption y documento Excel. Identico en los 4 bots.
Rutea a CHAT_PIRATA (oportunidad/resumen) o CHAT_ERRORES (resto) segun el
contenido del mensaje. Credenciales desde el entorno.
"""

import logging
import os

import requests

_LOGO = "https://cdn.shopify.com/s/files/1/0710/0029/3568/files/TheVaultBot.png?v=1776461063"


def enviar_mensaje_telegram(image_url, mensaje):
    if image_url is None:
        image_url = _LOGO

    if "Oportunidad detectada" in mensaje or "Resumen del botín" in mensaje:
        chat_id = os.getenv("CHAT_PIRATA")
    else:
        chat_id = os.getenv("CHAT_ERRORES")

    token = os.getenv("TELEGRAM_TOKEN")
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": image_url,
        "caption": mensaje,
        "parse_mode": "HTML",
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        logging.error(f"⚠️ Error enviando mensaje a Telegram: {e}")


def enviar_excel_telegram(ruta_archivo, caption=None):
    """Envia un archivo Excel por Telegram al chat de oportunidades."""
    if not os.path.exists(ruta_archivo):
        raise FileNotFoundError(f"No existe el archivo: {ruta_archivo}")

    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_PIRATA")
    url = f"https://api.telegram.org/bot{token}/sendDocument"

    with open(ruta_archivo, "rb") as f:
        files = {"document": f}
        data = {"chat_id": chat_id, "caption": caption or "📊 Reporte de oportunidades"}
        resp = requests.post(url, data=data, files=files, timeout=30)

    if not resp.ok:
        raise RuntimeError(f"Error enviando Excel a Telegram: {resp.text}")
