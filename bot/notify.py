import requests
from . import config


def send(text):
    print(text, flush=True)
    if not (config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
    except Exception:
        pass
