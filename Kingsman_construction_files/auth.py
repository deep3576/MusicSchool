# auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import select
from datetime import datetime
from models import db, User, LoginAudit

auth_bp = Blueprint("auth", __name__)

def login_manager_init(app):
    lm = LoginManager()
    lm.login_view = "auth.login"
    lm.init_app(app)

    @lm.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

def _audit(user_id, action, success=True):
    try:
        rec = LoginAudit(
            user_id=user_id,
            action=action,
            success=success,
            ip_address=request.headers.get("X-Forwarded-For", request.remote_addr),
            user_agent=request.headers.get("User-Agent")
        )
        db.session.add(rec); db.session.commit()
    except Exception:
        db.session.rollback()

@auth_bp.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        pw = request.form.get("password","")
        user = db.session.scalar(select(User).where(User.email==email, User.is_active==True))
        if user and check_password_hash(user.password_hash, pw):
            login_user(user, remember=True)
            user.last_login_at = datetime.utcnow()
            db.session.commit()
            _audit(user.id, "login", True)
            flash("Welcome back!", "success")
            next_url = request.args.get("next") or url_for("portal.dashboard")
            return redirect(next_url)
        _audit(user.id if user else 0, "login", False)
        flash("Invalid email or password.", "error")
    return render_template("login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    _audit(current_user.id, "logout", True)
    logout_user()
    flash("You’ve been logged out.", "success")
    return redirect(url_for("auth.login"))

# Optional: simple admin-only user creation route (disable in production, use CLI instead)
