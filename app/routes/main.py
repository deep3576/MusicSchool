from types import SimpleNamespace
from datetime import datetime, timedelta, time
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




def _time_to_hms(v) -> str:
    """MySQL TIME may come as datetime.time OR datetime.timedelta."""
    if v is None:
        return "00:00:00"
    if isinstance(v, time):
        return v.strftime("%H:%M:%S")
    if isinstance(v, timedelta):
        total = int(v.total_seconds()) % (24 * 3600)
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    # fallback (string etc.)
    return str(v)

@main_bp.get("/book")
def book():
    # NOTE: no ta.is_booked filter -> includes both Available + Booked windows
    row = db.session.execute(text("""
        SELECT
          MIN(ta.start_at) AS min_start_dt,
          MAX(ta.end_at)   AS max_end_dt,
          MIN(TIME(ta.start_at)) AS min_time_day,
          MAX(TIME(ta.end_at))   AS max_time_day
        FROM teacher_availability ta
        JOIN teacher t ON t.id = ta.teacher_id
        WHERE t.is_active = 1
          AND ta.start_at >= NOW()
    """)).mappings().first()

    bounds = None
    if row and row["min_start_dt"] and row["max_end_dt"]:
        min_start_dt = row["min_start_dt"]
        max_end_dt   = row["max_end_dt"]

        bounds = {
            "min_date": min_start_dt.date().isoformat(),         # YYYY-MM-DD
            "max_date": max_end_dt.date().isoformat(),           # YYYY-MM-DD

            # IMPORTANT: use time-of-day min/max across ALL slots
            "min_time": _time_to_hms(row["min_time_day"]),       # HH:MM:SS
            "max_time": _time_to_hms(row["max_time_day"]),       # HH:MM:SS
        }

    return render_template("book.html", bounds=bounds, title="Book")


from ..forms import ContactForm
@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    form = ContactForm()

    if form.validate_on_submit():
        try:
            db.session.execute(text("""
                INSERT INTO contact_message
                  (name, email, phone, subject, message, created_at)
                VALUES
                  (:name, :email, :phone, :subject, :message, NOW())
            """), {
                "name": (form.name.data or "").strip(),
                "email": (form.email.data or "").strip().lower(),
                "phone": (form.phone.data or "").strip() or None,
                "subject": (form.subject.data or "").strip(),
                "message": (form.message.data or "").strip(),
            })
            db.session.commit()

            flash("Message sent! We’ll reply soon.", "success")
            return redirect(url_for("main.contact"))

        except Exception:
            db.session.rollback()
            current_app.logger.exception("contact submit failed")
            flash("Could not send message. Please try again.", "danger")

    return render_template("contact.html", title="Contact", form=form)


@main_bp.get("/api/availability")
def api_all_availability():
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return jsonify([])

    start_dt = _parse_fc_iso(start)
    end_dt = _parse_fc_iso(end)

    rows = db.session.execute(text("""
        SELECT
          ta.start_at,
          ta.end_at,
          SUM(CASE WHEN ta.is_booked = 0 THEN 1 ELSE 0 END) AS available_count,
          COUNT(*) AS total_count
        FROM teacher_availability ta
        JOIN teacher t ON t.id = ta.teacher_id
        WHERE t.is_active = 1
          AND ta.start_at < :end_dt
          AND ta.end_at > :start_dt
          and ta.start_at > (SELECT CURRENT_TIMESTAMP() - INTERVAL 5 HOUR)
        GROUP BY ta.start_at, ta.end_at
        ORDER BY ta.start_at ASC
    """), {"start_dt": start_dt, "end_dt": end_dt}).mappings().all()

    events = []
    for r in rows:
        available_count = int(r["available_count"] or 0)
        total_count = int(r["total_count"] or 0)
        is_available = available_count > 0

        events.append({
            "id": f"{r['start_at'].isoformat()}__{r['end_at'].isoformat()}",
            "title": "Available" if is_available else "Booked",
            "start": r["start_at"].isoformat(),
            "end": r["end_at"].isoformat(),
            "extendedProps": {
                "is_available": is_available,
                "available_count": available_count,
                "total_count": total_count
            },
            "classNames": ["slot-available" if is_available else "slot-booked"]
        })

    return jsonify(events)


@main_bp.get("/api/availability/summary")
def api_availability_summary():
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return jsonify([])

    start_dt = _parse_fc_iso(start)
    end_dt = _parse_fc_iso(end)

    rows = db.session.execute(text("""
        SELECT
          DATE(ta.start_at) AS d,
          COUNT(*) AS total_slots,
          SUM(CASE WHEN ta.is_booked = 0 THEN 1 ELSE 0 END) AS available_slots
        FROM teacher_availability ta
        JOIN teacher t ON t.id = ta.teacher_id
        WHERE t.is_active = 1
          AND ta.start_at < :end_dt
          AND ta.end_at > :start_dt
          AND ta.start_at > (SELECT CURRENT_TIMESTAMP() - INTERVAL 5 HOUR)
        GROUP BY DATE(ta.start_at)
        ORDER BY d ASC
    """), {"start_dt": start_dt, "end_dt": end_dt}).mappings().all()

    return jsonify([{
        "date": r["d"].isoformat() if hasattr(r["d"], "isoformat") else str(r["d"]),
        "total": int(r["total_slots"] or 0),
        "available": int(r["available_slots"] or 0),
    } for r in rows])



@main_bp.post("/book/submit")
@login_required
def book_submit():
    raw_aid = (request.form.get("availability_id") or "").strip()
    start_s = (request.form.get("start_at") or "").strip()
    end_s = (request.form.get("end_at") or "").strip()

    availability_id = int(raw_aid) if raw_aid.isdigit() else 0

    def dbg(msg: str):
        try:
            current_app.logger.info(f"[book_submit] {msg}")
        except Exception:
            pass
        print(f"[book_submit] {msg}")

    if not availability_id and (not start_s or not end_s):
        flash("Please select a slot.", "danger")
        return redirect(url_for("main.book"))

    try:
        # ------------------------------------------------------------
        # A) Booking by specific availability_id (direct)
        # ------------------------------------------------------------
        if availability_id:
            dbg(f"booking by availability_id={availability_id}")

            # Claim it atomically
            updated = db.session.execute(text("""
                UPDATE teacher_availability ta
                JOIN teacher t ON t.id = ta.teacher_id
                join user 
                SET ta.is_booked = 1
                WHERE ta.id = :aid
                  AND ta.is_booked = 0
                  AND t.is_active = 1
            """), {"aid": availability_id}).rowcount

            if updated != 1:
                db.session.rollback()
                flash("That slot is no longer available. Please pick another.", "warning")
                return redirect(url_for("main.book"))

            # Fetch details for booking insert
            slot = db.session.execute(text("""
                SELECT ta.id, ta.teacher_id,
                       COALESCE(ta.venue_id, t.default_venue_id) AS venue_id
                FROM teacher_availability ta
                JOIN teacher t ON t.id = ta.teacher_id
                WHERE ta.id = :aid
                LIMIT 1
            """), {"aid": availability_id}).mappings().first()

            if not slot:
                db.session.rollback()
                flash("Invalid slot selected.", "danger")
                return redirect(url_for("main.book"))

        # ------------------------------------------------------------
        # B) Booking by time-window (start_at/end_at) => pick any teacher
        # ------------------------------------------------------------
        else:
            start_dt = _parse_fc_iso(start_s).replace(microsecond=0)
            end_dt = _parse_fc_iso(end_s).replace(microsecond=0)
            dbg(f"booking by window start={start_dt} end={end_dt}")

            # Pick ONE available slot and lock it (this prevents double-booking)
            slot = db.session.execute(text("""
                SELECT ta.id, ta.teacher_id,
                       COALESCE(ta.venue_id, t.default_venue_id) AS venue_id
                FROM teacher_availability ta
                JOIN teacher t ON t.id = ta.teacher_id
                WHERE ta.is_booked = 0
                  AND t.is_active = 1
                  AND ta.start_at = :start_at
                  AND ta.end_at   = :end_at
                ORDER BY ta.id ASC
                LIMIT 1
                FOR UPDATE
            """), {"start_at": start_dt, "end_at": end_dt}).mappings().first()

            if not slot:
                db.session.rollback()
                flash("Not available for that time. Please choose another slot.", "warning")
                return redirect(url_for("main.book"))

            # Now claim it by id (simple single-table UPDATE; no ORDER BY)
            updated = db.session.execute(text("""
                UPDATE teacher_availability
                SET is_booked = 1
                WHERE id = :id AND is_booked = 0
            """), {"id": slot["id"]}).rowcount

            if updated != 1:
                db.session.rollback()
                flash("That slot was just taken. Please try another.", "warning")
                return redirect(url_for("main.book"))

        # Insert booking row
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
            "availability_id": slot["id"],
            "user_id": current_user.id,
            "student_name": current_user.full_name,
            "student_email": current_user.email,
            "student_phone": getattr(current_user, "phone", None),
            "venue_id": slot["venue_id"],
        })

        db.session.commit()
        flash("Booking confirmed!", "success")
        return redirect(url_for("main.my_bookings"))

    except Exception as e:
        db.session.rollback()
        dbg(f"ERROR: {repr(e)}")
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