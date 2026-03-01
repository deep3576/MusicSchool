from flask import Flask

from config import Config
from db import ensure_schema
from .api import api_bp


def create_backend_app(config_override: dict | None = None) -> Flask:
    """Factory for the construction backend REST API."""
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_override:
        app.config.update(config_override)

    with app.app_context():
        ensure_schema()

    app.register_blueprint(api_bp)

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

    return app
