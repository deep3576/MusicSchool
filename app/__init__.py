# app/__init__.py
import os
import configparser
from flask import Flask

from .extensions import db, login_manager


def _read_config():
    cfg = configparser.ConfigParser()

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config_path = os.path.join(base_dir, "instance/config.ini")

    read_files = cfg.read(config_path)
    if not read_files:
        raise RuntimeError(f"config.ini not found at: {config_path}")

    # Accept mysql section names flexibly (in case your file uses a different name)
    section = None
    for candidate in ["mysql", "db", "database"]:
        if cfg.has_section(candidate):
            section = candidate
            break
    if not section:
        raise RuntimeError(
            f"No [mysql] section found in {config_path}. "
            f"Expected one of: [mysql] / [db] / [database]."
        )

    if not cfg.has_section("flask"):
        raise RuntimeError(f"No [flask] section found in {config_path}.")

    return cfg, section


def create_app() -> Flask:
    app = Flask(__name__)

    cfg, db_section = _read_config()

    app.config["SECRET_KEY"] = cfg.get("flask", "secret_key", fallback="dev-secret-change-me")

    host = cfg.get(db_section, "host")
    port = cfg.get(db_section, "port", fallback="3306")
    user = cfg.get(db_section, "user")
    password = cfg.get(db_section, "password")
    database = cfg.get(db_section, "database")

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    # SQL-only user loader (no ORM models)
    from .auth_user import register_user_loader
    register_user_loader(login_manager)

    # Register your existing blueprints (keep as-is)
    from .routes.main import main_bp
    from .routes.admin import admin_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    return app
