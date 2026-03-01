from pathlib import Path
from configparser import ConfigParser

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)


def load_ini() -> ConfigParser:
    parser = ConfigParser()
    for candidate in [INSTANCE_DIR / "config.ini", BASE_DIR / "config.ini"]:
        if candidate.exists():
            parser.read(candidate)
            return parser
    return parser


def ini_get(parser: ConfigParser, section: str, option: str, default=None):
    try:
        return parser.get(section, option)
    except Exception:
        return default


def build_mysql_uri(parser: ConfigParser) -> str | None:
    # MySQL only (no SQLite support)
    engine = (ini_get(parser, "database", "engine", "mysql") or "").strip().lower()
    if engine != "mysql":
        return None
    user = ini_get(parser, "database", "user")
    pwd  = ini_get(parser, "database", "password")
    host = ini_get(parser, "database", "host")
    port = ini_get(parser, "database", "port", "3306")
    name = ini_get(parser, "database", "name")
    driver = ini_get(parser, "database", "driver", "pymysql")
    charset = ini_get(parser, "database", "charset", "utf8mb4")
    if all([user, pwd, host, port, name]):
        return f"mysql+{driver}://{user}:{pwd}@{host}:{port}/{name}?charset={charset}"
    return None


class Config:
    _ini = load_ini()

    # App / brand
    APP_ENV = ini_get(_ini, "app", "env", "production")
    SECRET_KEY = ini_get(_ini, "app", "secret_key", "dev-key-change-me")
    COMPANY_NAME = ini_get(_ini, "app", "company_name", "Kingsman Construction & Renovations Inc.")
    COMPANY_DOMAIN = ini_get(_ini, "app", "company_domain", "kingsmanrenovations.ca")
    PRIMARY_COLOR = ini_get(_ini, "app", "primary_color", "#0f172a")
    ACCENT_COLOR  = ini_get(_ini, "app", "accent_color",  "#dc2626")
    LOGO_PATH     = ini_get(_ini, "app", "logo_path", "img/Kingsman_logo.png")
    FAVICON_PATH  = ini_get(_ini, "app", "favicon_path", "img/favicon.ico")

    # Database (MySQL only)
    SQLALCHEMY_DATABASE_URI = build_mysql_uri(_ini)
    if not SQLALCHEMY_DATABASE_URI:
        raise RuntimeError(
            "Missing or invalid MySQL settings in instance/config.ini. "
            "Required [database] keys: engine=mysql, user, password, host, port, name."
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    @staticmethod
    def debug_print():
        print("[Config] env:", Config.APP_ENV)
        print("[Config] db uri:", Config.SQLALCHEMY_DATABASE_URI)