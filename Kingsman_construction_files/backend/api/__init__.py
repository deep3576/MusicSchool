from flask import Blueprint

api_bp = Blueprint("construction_api", __name__, url_prefix="/api/kingsman/v1")

from . import routes  # noqa: E402,F401
