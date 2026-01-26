# app/security.py
from functools import wraps
from flask import redirect, url_for, flash, request
from flask_login import current_user


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("student.login", next=request.path))
        if not getattr(current_user, "is_admin", False):
            flash("Admin access required.", "danger")
            return redirect(url_for("student.index"))
        return view(*args, **kwargs)
    return wrapper


def teacher_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("student.login", next=request.path))
        if not getattr(current_user, "is_teacher", False):
            flash("Teacher access required.", "danger")
            return redirect(url_for("student.index"))
        return view(*args, **kwargs)
    return wrapper
