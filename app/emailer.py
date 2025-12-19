import smtplib
from email.message import EmailMessage
from flask import current_app

def send_email(to_email: str, subject: str, body: str) -> None:
    cfg = current_app.config

    host = cfg.get("SMTP_HOST")
    port = int(cfg.get("SMTP_PORT", 587))
    user = cfg.get("SMTP_USER")
    pwd  = cfg.get("SMTP_PASSWORD")
    from_email = cfg.get("MAIL_FROM") or user

    if not host or not user or not pwd:
        # Email not configured; fail silently (or raise if you prefer)
        return

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(host, port, timeout=20) as s:
        s.ehlo()
        s.starttls()
        s.login(user, pwd)
        s.send_message(msg)
