from __future__ import annotations
from collections import defaultdict
from datetime import datetime, date, time, timedelta, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, has_request_context, \
    session
from ..security import admin_required , teacher_required
from flask_login import current_user,logout_user, login_required
from types import SimpleNamespace
from flask import render_template, request, redirect, url_for, flash, current_app
from datetime import datetime
from sqlalchemy import text
from werkzeug.security import generate_password_hash
from ..extensions import db
from ..emailer import send_email

teacher_bp = Blueprint("teacher", __name__, url_prefix="/teacher")
def _ensure_teacher_role():
    roles = current_user.role or []
    active_role = session.get("active_role")

    if active_role == "teacher":
        return None

    if "teacher" in roles and len(roles) == 1:
        session["active_role"] = "teacher"
        return None

    flash("Teacher access required.", "danger")
    return redirect(url_for("student.choose_role"))


@teacher_bp.get("/dashboard")
@login_required
def dashboard():
    guard = _ensure_teacher_role()
    if guard is not None:
        return guard
    return render_template("teacher/dashboard.html", title="Teacher Dashboard")




