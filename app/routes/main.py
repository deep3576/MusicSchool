from datetime import datetime
from types import SimpleNamespace

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash

from ..extensions import db
from ..forms import SignupForm, LoginForm
from ..auth_user import AppUser, get_user_by_id

main_bp = Blueprint("main", __name__)


def _ns(d: dict) -> SimpleNamespace:
    return SimpleNamespace(**d)


def _parse_fc_iso(s: str) -> datetime:
    s = (s or "").strip()
    if s.endswith("Z"):
        s = s[:-1]
    if "T" in s and len(s) >= 6 and s[-6] in ["+", "-"] and s[-3] == ":":
        s = s[:-6]
    if "+" in s:
        s = s.split("+", 1)[0]
    return datetime.fromisoformat(s)


@main_bp.get("/")
def index():
    return render_template("index.html", title="The Spirit School")


@main_bp.get("/book")
def book():
    return render_template("booking.html", title="Book a Class")


@main_bp.get("/api/availability")
def api_all_availability():
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return jsonify([])

    start_dt = _parse_fc_iso(start)
    end_dt = _parse_fc_iso(end)

    rows = db.session.execute(text("""
        SELECT ta.id, ta.start_at, ta.end_at
        FROM teacher_availability ta
        JOIN teacher t ON t.id = ta.teacher_id
        WHERE ta.is_booked = 0
          AND t.is_active = 1
          AND ta.start_at < :end_dt
          AND ta.end_at > :start_dt
        ORDER BY ta.start_at ASC
    """), {"start_dt": start_dt, "end_dt": end_dt}).mappings().all()

    return jsonify([{
        "id": r["id"],
        "title": "Available",
        "start": r["start_at"].isoformat(),
        "end": r["end_at"].isoformat(),
    } for r in rows])


@main_bp.post("/book/submit")
@login_required
def book_submit():
    availability_id = int(request.form.get("availability_id") or 0)
    if not availability_id:
        flash("Please select a slot.", "danger")
        return redirect(url_for("main.book"))

    try:
        with db.session.begin():
            slot = db.session.execute(text("""
                SELECT ta.id, ta.teacher_id, ta.venue_id, ta.start_at, ta.end_at, ta.is_booked,
                       t.default_venue_id
                FROM teacher_availability ta
                JOIN teacher t ON t.id = ta.teacher_id
                WHERE ta.id = :aid
                FOR UPDATE
            """), {"aid": availability_id}).mappings().first()

            if not slot:
                flash("Invalid slot selected.", "danger")
                return redirect(url_for("main.book"))

            if int(slot["is_booked"]) == 1:
                flash("That slot is no longer available.", "danger")
                return redirect(url_for("main.book"))

            updated = db.session.execute(text("""
                UPDATE teacher_availability
                SET is_booked = 1
                WHERE id = :aid AND is_booked = 0
            """), {"aid": availability_id}).rowcount

            if updated != 1:
                flash("That slot was just taken. Please try another.", "warning")
                return redirect(url_for("main.book"))

            venue_id = slot["venue_id"] or slot["default_venue_id"]

            db.session.execute(text("""
                INSERT INTO booking
                (teacher_id, availability_id, user_id,
                 student_name, student_email, student_phone,
                 class_level_id, venue_id, status, created_at)
                VALUES
                (:teacher_id, :availability_id, :user_id,
                 :student_name, :student_email, :student_phone,
                 NULL, :venue_id, 'BOOKED', NOW())
            """), {
                "teacher_id": slot["teacher_id"],
                "availability_id": availability_id,
                "user_id": current_user.id,
                "student_name": current_user.full_name,
                "student_email": current_user.email,
                "student_phone": getattr(current_user, "phone", None),
                "venue_id": venue_id,
            })

        flash("Booking confirmed!", "success")
        return redirect(url_for("main.my_bookings"))

    except Exception:
        db.session.rollback()
        current_app.logger.exception("book_submit failed")
        flash("Booking failed. Please try again.", "danger")
        return redirect(url_for("main.book"))


@main_bp.get("/my-bookings")
@login_required
def my_bookings():
    rows = db.session.execute(text("""
        SELECT
          b.id, b.status, b.created_at,
          t.name AS teacher_name,
          ta.start_at, ta.end_at,
          cl.code AS class_code, cl.title AS class_title,
          v.name AS venue_name
        FROM booking b
        JOIN teacher t ON t.id = b.teacher_id
        JOIN teacher_availability ta ON ta.id = b.availability_id
        LEFT JOIN class_level cl ON cl.id = b.class_level_id
        LEFT JOIN venue v ON v.id = b.venue_id
        WHERE b.user_id = :uid
        ORDER BY b.created_at DESC
        LIMIT 300
    """), {"uid": current_user.id}).mappings().all()

    items = [_ns({
        "id": r["id"],
        "status": r["status"],
        "created_at": r["created_at"],
        "teacher_name": r["teacher_name"],
        "start_at": r["start_at"],
        "end_at": r["end_at"],
        "class_label": (f"{r['class_code']} · {r['class_title']}" if r["class_code"] else None),
        "venue_name": r["venue_name"],
    }) for r in rows]

    return render_template("my_bookings.html", title="My Bookings", items=items)


@main_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("main.book"))

    form = SignupForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        exists = db.session.execute(text("SELECT id FROM user WHERE email = :email"), {"email": email}).first()
        if exists:
            flash("Email already registered. Please login.", "warning")
            return redirect(url_for("main.login"))

        pw_hash = generate_password_hash(form.password.data)

        db.session.execute(text("""
            INSERT INTO user
            (email, password_hash, role,
             first_name, last_name, phone,
             address_1, address_2, city, province, postal_code, country,
             created_at)
            VALUES
            (:email, :pw, 'customer',
             :fn, :ln, :phone,
             :a1, :a2, :city, :prov, :pc, :country,
             NOW())
        """), {
            "email": email,
            "pw": pw_hash,
            "fn": form.first_name.data.strip(),
            "ln": form.last_name.data.strip(),
            "phone": (form.phone.data or "").strip() or None,
            "a1": (form.address_1.data or "").strip() or None,
            "a2": (form.address_2.data or "").strip() or None,
            "city": (form.city.data or "").strip() or None,
            "prov": (form.province.data or "").strip() or None,
            "pc": (form.postal_code.data or "").strip() or None,
            "country": (form.country.data or "").strip() or None,
        })
        db.session.commit()

        new_id = db.session.execute(text("SELECT id FROM user WHERE email=:email"), {"email": email}).scalar()
        u = get_user_by_id(int(new_id))
        login_user(u)
        flash("Account created!", "success")
        return redirect(url_for("main.book"))

    return render_template("auth/signup.html", title="Sign Up", form=form)


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.book"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        row = db.session.execute(text("""
            SELECT id, password_hash, email, role, first_name, last_name, phone
            FROM user
            WHERE email = :email
            LIMIT 1
        """), {"email": email}).mappings().first()

        if row and check_password_hash(row["password_hash"], form.password.data):
            u = AppUser(
                id=int(row["id"]),
                email=row["email"],
                role=row["role"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                phone=row["phone"],
            )
            login_user(u)
            flash("Welcome!", "success")
            return redirect(url_for("admin.messages") if u.is_admin else url_for("main.book"))

        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html", title="Login", form=form)


@main_bp.get("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("main.index"))


@main_bp.get("/programs")
def programs():
    return render_template("programs.html", title="Programs")