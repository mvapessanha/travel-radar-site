"""Alerta via bot do Telegram (grátis).

Setup (você faz, eu não posso criar contas por você):
1. No Telegram, fale com @BotFather -> /newbot -> siga o assistente -> copie o TOKEN.
2. Mande qualquer mensagem pro seu bot recém-criado (ex: "oi").
3. Acesse https://api.telegram.org/bot<TOKEN>/getUpdates no navegador e pegue o
   "chat":{"id": ...} da resposta -> esse é o seu TELEGRAM_CHAT_ID.
4. Cole os dois valores no .env.
"""
from __future__ import annotations

import os

import requests

API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram_alert(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[telegram] TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID não configurados, pulando alerta.")
        return False
    resp = requests.post(
        API_URL.format(token=token),
        data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=15,
    )
    return resp.status_code == 200
