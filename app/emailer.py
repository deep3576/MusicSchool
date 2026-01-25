# app/email.py
import os
import configparser
import smtplib
from email.message import EmailMessage
from pathlib import Path
from threading import Thread

from flask import current_app


def _resolve_config_path() -> Path:
    """
    Resolve the absolute path to instance/config.ini reliably.

    - When running inside Flask (request/app context), use current_app.instance_path.
    - When running as a standalone script, resolve relative to this file location.
    """
    try:
        # Flask context available
        return Path(current_app.instance_path) / "config.ini"
    except Exception:
        # Standalone execution (no Flask app context)
        # This assumes project layout:
        # project-root/
        #   instance/config.ini
        #   app/email.py
        return (Path(__file__).resolve().parent.parent / "instance" / "config.ini").resolve()


def _load_email_config() -> tuple[str, int, str, str, str]:
    """
    Returns: (smtp_host, smtp_port, smtp_user, smtp_password, from_email)
    """
    config_path = _resolve_config_path()
    config = configparser.ConfigParser()

    loaded = config.read(str(config_path))
    if not loaded:
        raise FileNotFoundError(f"config.ini not found or not readable at: {config_path}")

    if not config.has_section("email"):
        raise RuntimeError(f"Missing [email] section in config: {config_path}")

    host = config.get("email", "smtp_host")
    port = config.getint("email", "smtp_port")
    user = config.get("email", "smtp_user")
    pwd = config.get("email", "smtp_password")
    from_email = config.get("email", "from_email")

    return host, port, user, pwd, from_email


def send_email_actual(to_email: str, subject: str, body: str, html: str | None = None) -> None:
    host, port, user, pwd, from_email = _load_email_config()

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject

    # Always include a plain-text fallback (important)
    msg.set_content(body)

    # If html provided, add it as an alternative part
    if html:
        msg.add_alternative(html, subtype="html")

    try:
        print(f"Connecting to {host}:{port} ...")
        server = smtplib.SMTP(host, port, timeout=20)
        server.ehlo()
        server.starttls()
        server.ehlo()

        print("Logging in...")
        server.login(user, pwd)

        print("Sending email...")
        server.send_message(msg)

        print("✅ SUCCESS: Email sent successfully!")
        server.quit()

    except Exception as e:
        print(f"❌ FAILED: {e}")
        raise  # important so your app logs it too


def send_email_bg(app, to, subject, body, html):
    # Need app context because thread runs outside request context
    with app.app_context():
        try:
            send_email_actual(to, subject=subject, body=body, html=html)
        except Exception:
            app.logger.exception("Background email failed")

def send_email(to, subject, body, html:str | None = None):
    app = current_app._get_current_object()
    Thread(
        target=send_email_bg,
        args=(app, to, subject, body, html),
        daemon=True
    ).start()



