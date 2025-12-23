# app/email.py
import os
import configparser
import smtplib
from email.message import EmailMessage
from pathlib import Path

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


def send_email(to_email: str, subject: str, body: str) -> None:
    """
    Sends an email using SMTP credentials stored in instance/config.ini under [email].

    Keeps your original SMTP logic:
    - SMTP(host, port)
    - starttls()
    - login()
    - send_message()
    """
    host, port, user, pwd, from_email = _load_email_config()

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        print(f"Connecting to {host}:{port} ...")
        server = smtplib.SMTP(host, port, timeout=20)
        server.starttls()  # Secure the connection

        print("Logging in...")
        server.login(user, pwd)

        print("Sending email...")
        server.send_message(msg)

        print("✅ SUCCESS: Email sent successfully!")
        server.quit()

    except Exception as e:
        print(f"❌ FAILED: {e}")



