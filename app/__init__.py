# app/__init__.py
import os
import configparser
import importlib
import importlib.util

from flask import Flask, jsonify, redirect, request, session, url_for
from flask_login import current_user
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


def _build_mysql_uri_with_database(cfg: configparser.ConfigParser, section: str, database: str) -> str:
    host = cfg.get(section, "host")
    port = cfg.get(section, "port", fallback="3306")
    user = cfg.get(section, "user")
    password = cfg.get(section, "password")
    charset = cfg.get(section, "charset", fallback="utf8mb4")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset={charset}"


def _build_mysql_uri(cfg: configparser.ConfigParser, section: str) -> str:
    return _build_mysql_uri_with_database(cfg, section, cfg.get(section, "database"))


def _get_optional_kingsman_section(cfg: configparser.ConfigParser, primary_section: str) -> str | None:
    for section in ("mysql_kingsman", "kingsman_mysql", "kingsman_db"):
        if cfg.has_section(section):
            return section

    if cfg.has_option(primary_section, "kingsman_database"):
        return primary_section

    return None


def _register_optional_blueprint(app: Flask, module_name: str, blueprint_attr: str):
    if importlib.util.find_spec(module_name) is None:
        return

    module = importlib.import_module(module_name)
    blueprint = getattr(module, blueprint_attr, None)
    if blueprint is not None:
        app.register_blueprint(blueprint)


def create_app() -> Flask:
    app = Flask(__name__)

    cfg, db_section = _read_config()
    app.config["SECRET_KEY"] = cfg.get("flask", "secret_key", fallback="dev-secret-change-me")

    app.config["SQLALCHEMY_DATABASE_URI"] = _build_mysql_uri(cfg, db_section)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["MUSIC_SCHOOL_SCHEMA"] = cfg.get(db_section, "database")
    app.config["ALLOW_HIRING_EXAM_DEV_BYPASS"] = cfg.getboolean(
        "features",
        "allow_hiring_exam_dev_bypass",
        fallback=os.getenv("ALLOW_HIRING_EXAM_DEV_BYPASS", "").strip().lower() in {"1", "true", "yes", "on"},
    )

    kingsman_section = _get_optional_kingsman_section(cfg, db_section)
    if kingsman_section:
        kingsman_schema = cfg.get(kingsman_section, "kingsman_database", fallback=None)
        if not kingsman_schema:
            kingsman_schema = cfg.get(kingsman_section, "database", fallback=None)

        if kingsman_schema:
            app.config["KINGSMAN_SCHEMA"] = kingsman_schema
            app.config["SQLALCHEMY_BINDS"] = {
                "kingsman": _build_mysql_uri_with_database(cfg, kingsman_section, kingsman_schema)
            }

        app.config["KINGSMAN_CORS_ORIGINS"] = cfg.get(
            kingsman_section,
            "cors_origins",
            fallback="",
        )

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.unauthorized_handler
    def _handle_unauthorized():
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "Authentication required"}), 401

        return redirect(url_for("student.auth_login_alias", next=request.url))

    # SQL-only user loader (no ORM models)
    from .auth_user import register_user_loader
    register_user_loader(login_manager)

    # ✅ Inject active_role into all templates (used to show clean admin/student UI)
    @app.context_processor
    def inject_active_role():
        roles = getattr(current_user, "role", None) or []
        chosen = session.get("active_role")

        if chosen and chosen in roles:
            ar = chosen
        elif len(roles) == 1:
            session["active_role"] = roles[0]
            ar = roles[0]
        else:
            ar = None  # multiple roles and not chosen yet

        return {"active_role": ar}

    # Blueprints
    from .routes.student import main_bp
    from .routes.admin import admin_bp
    from .routes.teacher import teacher_bp
    from .routes.api import api_bp
    from .routes.API_kingsman import api_kingsman_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(api_kingsman_bp)

    _register_optional_blueprint(app, "app.routes.kingsman_api", "kingsman_api_bp")
    _register_optional_blueprint(app, "app.routes.kingsman", "kingsman_bp")
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
        hour=23,               # midnight
        minute=30,
        replace_existing=True,
        timezone="America/Toronto",
    )

    scheduler.start()
    return app
