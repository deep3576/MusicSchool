from __future__ import annotations
from collections import defaultdict
from datetime import datetime, date, time, timedelta, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, has_request_context
from ..security import admin_required , teacher_required
from flask_login import current_user,logout_user, login_required
from types import SimpleNamespace
from flask import render_template, request, redirect, url_for, flash, current_app
from datetime import datetime
from sqlalchemy import text
from werkzeug.security import generate_password_hash
from ..extensions import db
from ..emailer import send_email

teacher_bp = Blueprint("teacher", __name__, url_prefix="/admin")
def _ns(d: dict) -> SimpleNamespace:
    return SimpleNamespace(**d)

@teacher_bp.get("/dashboard")
@login_required
@teacher_required
def messages():
    return render_template(
        "teacher/Dashboard.html",
        title="Teacher Dashboard",
    )




