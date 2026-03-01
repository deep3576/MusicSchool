from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from sqlalchemy import select
from extensions import db, login_manager
from models import User, LoginAudit
from .forms import LoginForm
from datetime import datetime

auth_bp = Blueprint("auth", __name__)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@login_manager.unauthorized_handler
def _unauth():
    return redirect(url_for("auth.login"))

def _audit(user_id, action, success):
    try:
        rec = LoginAudit(user_id=user_id, action=action, success=success,
                         ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
                         user_agent=request.headers.get("User-Agent"))
        db.session.add(rec); db.session.commit()
    except Exception:
        db.session.rollback()

@auth_bp.route("/login", methods=["GET","POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("portal.dashboard"))
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        pw = form.password.data
        user = db.session.scalar(select(User).where(User.email==email, User.is_active==True))
        if user and check_password_hash(user.password_hash, pw):
            login_user(user, remember=True)
            user.last_login_at = datetime.utcnow()
            db.session.commit()
            _audit(user.id, "login", True)
            flash("Welcome back!", "success")
            return redirect(url_for("portal.dashboard"))
        _audit(user.id if user else 0, "login", False)
        flash("Invalid email or password.", "error")
    return render_template("login.html", form=form)

@auth_bp.route("/logout")
@login_required
def logout():
    _audit(current_user.id, "logout", True)
    logout_user()
    flash("You’ve been logged out.", "success")
    return redirect(url_for("auth.login"))
