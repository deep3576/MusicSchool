# app/security.py
from functools import wraps
from flask import redirect, url_for, flash, request
from flask_login import current_user


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("main.login", next=request.path))
        if not getattr(current_user, "is_admin", False):
            flash("Admin access required.", "danger")
            return redirect(url_for("main.index"))
        return view(*args, **kwargs)
    return wrapper
