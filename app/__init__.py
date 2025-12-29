# app/__init__.py
import os
import configparser
from datetime import date
from flask import Flask
from flask_apscheduler import APScheduler
from .extensions import db, login_manager
from .jobs import scheduling  # make sure jobs.py exists

scheduler = APScheduler()

class Config:
    SCHEDULER_API_ENABLED = True


def _read_config():
    cfg = configparser.ConfigParser()

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config_path = os.path.join(base_dir, "instance/config.ini")

    read_files = cfg.read(config_path)
    if not read_files:
        raise RuntimeError(f"config.ini not found at: {config_path}")

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

    # Blueprints
    from .routes.main import main_bp
    from .routes.admin import admin_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    # Scheduler
    app.config.from_object(Config)
    scheduler.init_app(app)

    def run_midnight_job():
        # run inside app context so db.session works
        with app.app_context():
            scheduling()

    scheduler.add_job(
        id="daily_scheduling_midnight",
        func=run_midnight_job,
        trigger="cron",
        hour=0,                # midnight
        minute=0,
        replace_existing=True,
        timezone="America/Toronto",
    )

    scheduler.start()
    return app
