from pathlib import Path
from configparser import ConfigParser

BASE_DIR = Path(__file__).resolve().parent

def _read_ini():
    ini_path = BASE_DIR / "instance" / "config.ini"
    parser = ConfigParser()
    if ini_path.exists():
        parser.read(ini_path)
    return parser

_ini = _read_ini()

def _ini_get(section: str, key: str, fallback=None):
    try:
        return _ini.get(section, key, fallback=fallback)
    except Exception:
        return fallback

def _ini_getint(section: str, key: str, fallback: int):
    try:
        return _ini.getint(section, key, fallback=fallback)
    except Exception:
        return fallback

class Config:
    # Flask
    SECRET_KEY = _ini_get("flask", "secret_key", "dev-secret-change-me")
    ENV = _ini_get("flask", "env", "production")
    DEBUG = _ini_get("flask", "debug", "false").lower() == "true"

    # MySQL
    MYSQL_HOST = _ini_get("mysql", "host", "localhost")
    MYSQL_PORT = _ini_getint("mysql", "port", 3306)
    MYSQL_USER = _ini_get("mysql", "user", "root")
    MYSQL_PASSWORD = _ini_get("mysql", "password", "")
    MYSQL_DB = _ini_get("mysql", "database", "")
    MYSQL_CHARSET = _ini_get("mysql", "charset", "utf8mb4")

    # SQLAlchemy URI (PyMySQL)
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset={MYSQL_CHARSET}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SMTP_HOST = _ini_get("email", "smtp_host", "")
    SMTP_PORT = _ini_getint("email", "smtp_port", 587)
    SMTP_USER = _ini_get("email", "smtp_user", "")
    SMTP_PASSWORD = _ini_get("email", "smtp_password", "")
    MAIL_FROM = _ini_get("email", "from_email", SMTP_USER)
    ADMIN_NOTIFY = _ini_get("email", "admin_notify", "")