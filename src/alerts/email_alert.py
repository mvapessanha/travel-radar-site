"""Alerta via e-mail (SMTP).

Setup pro Gmail (você faz, eu não posso gerar isso por você):
1. Ative a verificação em 2 etapas na sua conta Google.
2. Gere uma "Senha de app" em https://myaccount.google.com/apppasswords
3. Use SMTP_HOST=smtp.gmail.com, SMTP_PORT=587, SMTP_USER=seu email,
   SMTP_PASSWORD=a senha de app gerada (não é a senha normal da conta).
"""
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText


def send_email_alert(subject: str, body: str) -> bool:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    to_addr = os.getenv("ALERT_EMAIL_TO", user)

    if not (host and user and password):
        print("[email] SMTP_HOST/SMTP_USER/SMTP_PASSWORD não configurados, pulando alerta.")
        return False

    # os textos das mensagens usam \n pra quebra de linha (é o que o Telegram
    # entende); e-mail HTML precisa de <br> pra quebrar visualmente também.
    msg = MIMEText(body.replace("\n", "<br>"), "html")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(user, [to_addr], msg.as_string())
    return True
