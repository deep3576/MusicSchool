from types import SimpleNamespace
from datetime import datetime, timedelta, time
from flask import Blueprint, request, current_app, jsonify, make_response, redirect, url_for, flash, render_template, \
    session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from ..emailer import send_email
from ..create_meeting import create_google_meet
from ..extensions import db
from ..forms import SignupForm, LoginForm, ForgotPasswordForm, ResetPasswordForm
from ..auth_user import AppUser
from sqlalchemy import text
from itsdangerous import BadSignature, SignatureExpired ,URLSafeTimedSerializer
from weasyprint import HTML
from ..forms import ContactForm


main_bp = Blueprint("student", __name__)


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
    return render_template("index.html", title="The Rhythm School")




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



@main_bp.get("/about")
def about():
    return render_template("about.html", title="About")


@main_bp.get("/admissions")
def admissions():
    return render_template("admissions.html", title="Admissions")


@main_bp.get("/careers/teacher-exam")
def teacher_exam():
    return render_template("teacher_exam.html", title="Teacher Hiring Exam")


@main_bp.get("/auth/login")
def auth_login_alias():
    return redirect(url_for("student.login"))


@main_bp.route("/auth/signup", methods=["GET", "POST"])
def auth_signup_alias():
    return signup()


@main_bp.get("/student")
@login_required
def student_home_alias():
    return redirect(url_for("student.book"))


@main_bp.get("/booking")
@login_required
def booking_alias():
    return redirect(url_for("student.book"))


@main_bp.get("/my_bookings")
@login_required
def my_bookings_alias():
    return redirect(url_for("student.my_bookings"))

@main_bp.route(
    "/book",
    methods=["get"],
    endpoint="book"
)
@login_required
def book():
    row = db.session.execute(text("""
        SELECT
          MIN(ta.start_at) AS min_start_dt,
          MAX(ta.end_at)   AS max_end_dt,
          MIN(TIME(ta.start_at)) AS min_time_day,
          MAX(TIME(ta.end_at))   AS max_time_day
        FROM teacher_availability ta
        JOIN teacher t ON t.id = ta.teacher_id AND t.is_active = 1
        JOIN teacher_class_level tcl
          ON tcl.teacher_id = t.id
         AND tcl.class_level_id = (SELECT assigned_class_id FROM `user` WHERE id = :user_id)
         AND tcl.is_active = 1
        WHERE ta.start_at >= NOW()
          AND ta.is_booked = 0
          AND ta.teacher_id <> :user_id
    """),{"user_id":current_user.id}).mappings().first()



    bounds = None
    if row and row["min_start_dt"] and row["max_end_dt"]:
        min_start_dt = row["min_start_dt"]
        max_end_dt = row["max_end_dt"]

        bounds = {
            "min_date": min_start_dt.date().isoformat(),  # YYYY-MM-DD
            "max_date": max_end_dt.date().isoformat(),  # YYYY-MM-DD

            # IMPORTANT: use time-of-day min/max across ALL slots
            "min_time": _time_to_hms(row["min_time_day"]),  # HH:MM:SS
            "max_time": _time_to_hms(row["max_time_day"]),  # HH:MM:SS
        }

    return render_template("book.html", bounds=bounds, title="Book")


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
            return redirect(url_for("student.contact"))

        except Exception:
            db.session.rollback()
            current_app.logger.exception("contact submit failed")
            flash("Could not send message. Please try again.", "danger")

    return render_template("contact.html", title="Contact", form=form)


@main_bp.get("/api/availability")
@login_required
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
        JOIN teacher_class_level tcl
          ON tcl.teacher_id = t.id
         AND tcl.class_level_id = (SELECT assigned_class_id FROM `user` WHERE id = :user_id)
         AND tcl.is_active = 1
        WHERE t.is_active = 1
          AND ta.teacher_id <> :user_id
          AND ta.is_booked = 0
          AND ta.start_at < :end_dt
          AND ta.end_at > :start_dt
          and ta.start_at > (SELECT CURRENT_TIMESTAMP() - INTERVAL 5 HOUR)
        GROUP BY ta.start_at, ta.end_at
        ORDER BY ta.start_at ASC
    """), {"start_dt": start_dt, "end_dt": end_dt, "user_id": current_user.id}).mappings().all()

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
@login_required
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
        JOIN teacher_class_level tcl
          ON tcl.teacher_id = t.id
         AND tcl.class_level_id = (SELECT assigned_class_id FROM `user` WHERE id = :user_id)
         AND tcl.is_active = 1
        WHERE t.is_active = 1
          AND ta.teacher_id <> :user_id
          AND ta.is_booked = 0
          AND ta.start_at < :end_dt
          AND ta.end_at > :start_dt
          AND ta.start_at > (SELECT CURRENT_TIMESTAMP() - INTERVAL 5 HOUR)
        GROUP BY DATE(ta.start_at)
        ORDER BY d ASC
    """), {"start_dt": start_dt, "end_dt": end_dt, "user_id": current_user.id}).mappings().all()

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
        return redirect(url_for("student.book"))

    if not getattr(current_user, "is_student", False):
        flash("Only students can book classes.", "danger")
        return redirect(url_for("student.book"))

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
                JOIN teacher_class_level tcl
                  ON tcl.teacher_id = t.id
                 AND tcl.class_level_id = (SELECT assigned_class_id FROM `user` WHERE id = :user_id)
                 AND tcl.is_active = 1
                SET ta.is_booked = 1
                WHERE ta.id = :aid
                  AND ta.is_booked = 0
                  AND t.is_active = 1
                  AND ta.teacher_id <> :user_id
            """), {"aid": availability_id, "user_id": current_user.id}).rowcount

            if updated != 1:
                db.session.rollback()
                flash("That slot is no longer available. Please pick another.", "warning")
                return redirect(url_for("student.book"))

            # Fetch details for booking insert
            slot = db.session.execute(text("""
                SELECT ta.id, ta.teacher_id,
                       ta.start_at, ta.end_at,
                       t.email AS teacher_email,
                       COALESCE(ta.venue_id, t.default_venue_id) AS venue_id
                FROM teacher_availability ta
                JOIN teacher t ON t.id = ta.teacher_id
                JOIN teacher_class_level tcl
                  ON tcl.teacher_id = t.id
                 AND tcl.class_level_id = (SELECT assigned_class_id FROM `user` WHERE id = :user_id)
                 AND tcl.is_active = 1
                WHERE ta.id = :aid
                  AND ta.teacher_id <> :user_id
                LIMIT 1
            """), {"aid": availability_id, "user_id": current_user.id}).mappings().first()

            if not slot:
                db.session.rollback()
                flash("Invalid slot selected.", "danger")
                return redirect(url_for("student.book"))

        # ------------------------------------------------------------
        # B) Booking by time-window (start_at/end_at) => pick any teacher
        # ------------------------------------------------------------
        else:
            start_dt = _parse_fc_iso(start_s).replace(microsecond=0)
            end_dt = _parse_fc_iso(end_s).replace(microsecond=0)
            dbg(f"booking by window start={start_dt} end={end_dt}")

            # Pick ONE available slot and lock it (this prevents double-booking)
            slot = db.session.execute(text("""
                SELECT ta.id, ta.teacher_id,ta.start_at,ta.end_at,
                       t.email AS teacher_email,
                       COALESCE(ta.venue_id, t.default_venue_id) AS venue_id
                FROM teacher_availability ta
                JOIN teacher t ON t.id = ta.teacher_id
                JOIN teacher_class_level tcl
                  ON tcl.teacher_id = t.id
                 AND tcl.class_level_id = (SELECT assigned_class_id FROM `user` WHERE id = :user_id)
                 AND tcl.is_active = 1
                WHERE ta.is_booked = 0
                  AND t.is_active = 1
                  AND ta.teacher_id <> :user_id
                  AND ta.start_at = :start_at
                  AND ta.end_at   = :end_at
                ORDER BY ta.id ASC
                LIMIT 1
                FOR UPDATE
            """), {"start_at": start_dt, "end_at": end_dt, "user_id": current_user.id}).mappings().first()

            if not slot:
                db.session.rollback()
                flash("Not available for that time. Please choose another slot.", "warning")
                return redirect(url_for("student.book"))

            # Now claim it by id (simple single-table UPDATE; no ORDER BY)
            updated = db.session.execute(text("""
                UPDATE teacher_availability
                SET is_booked = 1
                WHERE id = :id AND is_booked = 0
            """), {"id": slot["id"]}).rowcount

            if updated != 1:
                db.session.rollback()
                flash("That slot was just taken. Please try another.", "warning")
                return redirect(url_for("student.book"))




        row=db.session.execute(text(""" Select assigned_class_id, available_credits from user where id=:id FOR UPDATE """),{"id":current_user.id}).mappings().first()
        assigned_class_id = row["assigned_class_id"] if row else None
        available_credits = int((row or {}).get("available_credits") or 0)
        if available_credits < 1:
            db.session.rollback()
            flash("You do not have enough credits to book this class. Add Credits to your Account.", "warning")
            return redirect(url_for("student.book"))

        # Safety guard: a student must never be booked with themselves as teacher.
        if int(slot["teacher_id"]) == int(current_user.id):
            db.session.rollback()
            flash("Invalid booking: teacher cannot be the current user.", "danger")
            return redirect(url_for("student.book"))

        updated_credits = db.session.execute(text("""
            UPDATE `user`
            SET available_credits = available_credits - 1
            WHERE id = :uid AND available_credits > 0
        """), {"uid": current_user.id}).rowcount

        if updated_credits != 1:
            db.session.rollback()
            flash("You do not have enough credits to book this class.", "warning")
            return redirect(url_for("student.book"))

        balance_after = available_credits - 1

        try:
            meet_info = create_google_meet(
                start_time=slot["start_at"],
                end_time=slot["end_at"],
                student_email=current_user.email,
                teacher_email=slot.get("teacher_email"),
                description=f"Booking for student {current_user.full_name}.",
            )
        except Exception:
            current_app.logger.exception("create_google_meet failed")
            meet_info = {"meet_link": None, "event_id": None}
        meet_link = meet_info.get("meet_link")

        booking_cols = {
            (r["Field"] or "").lower()
            for r in db.session.execute(text("SHOW COLUMNS FROM booking")).mappings().all()
        }

        booking_columns = [
            "teacher_id", "availability_id", "user_id",
            "student_name", "student_email", "student_phone",
            "class_level_id", "venue_id", "status", "created_at", "last_update_timestamp", "last_update_by"
        ]
        booking_values = [
            ":teacher_id", ":availability_id", ":user_id",
            ":student_name", ":student_email", ":student_phone",
            ":class_level_id", ":venue_id", "'BOOKED'", "NOW()", "NOW()", "'System'"
        ]
        booking_params = {
            "teacher_id": slot["teacher_id"],
            "availability_id": slot["id"],
            "user_id": current_user.id,
            "student_name": current_user.full_name,
            "student_email": current_user.email,
            "student_phone": getattr(current_user, "phone", None),
            "class_level_id": assigned_class_id,
            "venue_id": slot["venue_id"],
        }

        if "google_meet_link" in booking_cols:
            booking_columns.append("google_meet_link")
            booking_values.append(":google_meet_link")
            booking_params["google_meet_link"] = meet_link

        db.session.execute(text(f"""
            INSERT INTO booking ({", ".join(booking_columns)})
            VALUES ({", ".join(booking_values)})
        """), booking_params)

        booking_id = db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar()

        tx_cols = {
            (r["Field"] or "").lower()
            for r in db.session.execute(text("SHOW COLUMNS FROM transactions")).mappings().all()
        }

        tx_params = {
            "teacher_id": int(slot["teacher_id"] or 0),
            "student_id": int(current_user.id),
            "actor_id": int(current_user.id),
            "before": int(available_credits),
            "after": int(balance_after),
            "credits_added": -1,
            "total": int(balance_after),
        }
        tx_columns = [
            "teacher_id",
            "type_of_transaction",
            "mode_of_payment",
            "student_id",
            "action_performer_user_id",
            "balance_before_this_transaction",
            "balance_after_this_transaction",
            "amount_added",
            "credits_added",
            "total_available_credits",
            "created_at",
        ]
        tx_values = [
            ":teacher_id",
            "'debit'",
            "NULL",
            ":student_id",
            ":actor_id",
            ":before",
            ":after",
            "NULL",
            ":credits_added",
            ":total",
            "NOW()",
        ]

        if "availability_id" in tx_cols:
            tx_columns.append("availability_id")
            tx_values.append(":availability_id")
            tx_params["availability_id"] = int(slot["id"])

        if "booking_id" in tx_cols and booking_id:
            tx_columns.append("booking_id")
            tx_values.append(":booking_id")
            tx_params["booking_id"] = int(booking_id)

        db.session.execute(text(f"""
            INSERT INTO transactions ({", ".join(tx_columns)})
            VALUES ({", ".join(tx_values)})
        """), tx_params)

        db.session.commit()
 # Ensure start/end always come from DB slot
        start_val = slot.get("start_at")
        end_val = slot.get("end_at")

        plain = f"""Your class is booked.

        Start: {start_val}
        End: {end_val}
        Google Meet: {meet_link or 'Will be shared shortly'}

        Regards,
        The Rhythm School
        """

        html = f"""
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Booking Confirmation</title>
          </head>
          <body style="margin:0;padding:0;background:#f5f7fb;font-family:Arial,Helvetica,sans-serif;color:#111827;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f5f7fb;padding:24px 0;">
              <tr>
                <td align="center" style="padding:0 16px;">
                  <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 10px 25px rgba(17,24,39,0.08);">
                    <!-- Header -->
                    <tr>
                      <td style="padding:22px 26px;background:linear-gradient(135deg,#111827,#2563eb);">
                        <div style="font-size:16px;font-weight:700;letter-spacing:0.2px;color:#ffffff;">
                          The Rhythm School
                        </div>
                        <div style="margin-top:4px;font-size:13px;color:rgba(255,255,255,0.85);">
                          Booking Confirmation
                        </div>
                      </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                      <td style="padding:26px;">
                        <div style="font-size:20px;font-weight:700;line-height:1.3;margin:0 0 10px 0;">
                          Your class is booked 🎶
                        </div>

                        <div style="font-size:14px;line-height:1.6;color:#374151;margin:0 0 16px 0;">
                          Thanks! Your booking is confirmed. Here are your class details:
                        </div>

                        <!-- Details table -->
                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
                               style="border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
                          <tr>
                            <td style="padding:12px 14px;background:#f9fafb;border-bottom:1px solid #e5e7eb;width:140px;font-size:13px;font-weight:700;color:#111827;">
                              Start
                            </td>
                            <td style="padding:12px 14px;background:#ffffff;border-bottom:1px solid #e5e7eb;font-size:13px;color:#111827;">
                              {start_val}
                            </td>
                          </tr>
                          <tr>
                            <td style="padding:12px 14px;background:#f9fafb;width:140px;font-size:13px;font-weight:700;color:#111827;">
                              End
                            </td>
                            <td style="padding:12px 14px;background:#ffffff;font-size:13px;color:#111827;">
                              {end_val}
                            </td>
                          </tr>
                          <tr>
                            <td style="padding:12px 14px;background:#f9fafb;width:140px;font-size:13px;font-weight:700;color:#111827;">
                              Google Meet
                            </td>
                            <td style="padding:12px 14px;background:#ffffff;font-size:13px;color:#111827;">
                              <a href="{meet_link}" target="_blank" rel="noopener">Join Class</a>
                            </td>
                          </tr>
                        </table>

                        <div style="margin-top:16px;font-size:13px;line-height:1.6;color:#6b7280;">
                          If you need to reschedule, reply to this email and we’ll help you.
                        </div>

                        <div style="margin-top:18px;padding-top:16px;border-top:1px solid #e5e7eb;font-size:13px;line-height:1.6;color:#374151;">
                          Regards,<br>
                          <span style="font-weight:700;color:#111827;">The Rhythm School</span>
                        </div>
                      </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                      <td style="padding:18px 26px;background:#f9fafb;border-top:1px solid #eef2f7;">
                        <div style="font-size:12px;color:#9ca3af;line-height:1.6;">
                          Please do not share this email publicly. If you did not make this booking, reply to this message.
                        </div>
                      </td>
                    </tr>
                  </table>

                  <div style="max-width:600px;margin:12px auto 0 auto;font-size:11px;color:#9ca3af;line-height:1.5;padding:0 10px;">
                    © {__import__("datetime").datetime.now().year} The Rhythm School
                  </div>
                </td>
              </tr>
            </table>
          </body>
        </html>
        """

        send_email(
            current_user.email,
            "Booking Confirmation - The Rhythm School",
            plain,
            html
        )
        if slot.get("teacher_email"):
            send_email(
                slot["teacher_email"],
                "New Class Booking - The Rhythm School",
                plain,
                html
            )
        send_email(
            "therythmschool@gmail.com",
            "Booking Notification - The Rhythm School",
            plain,
            html
        )

        flash("Booking confirmed!", "success")
        return redirect(url_for("student.my_bookings"))

    except Exception as e:
        db.session.rollback()
        dbg(f"ERROR: {repr(e)}")
        current_app.logger.exception("book_submit failed")
        flash("Booking failed. Please try again.", "danger")
        return redirect(url_for("student.book"))


@main_bp.get("/my-bookings")
@login_required
def my_bookings():
    rows = db.session.execute(text("""
        SELECT
          b.id, b.status, b.created_at,
          concat(t.first_name ,' ',t.last_name) AS teacher_name,
          ta.start_at, ta.end_at,
          cl.code AS class_code, cl.title AS class_title,
          v.name AS venue_name,
          b.google_meet_link
        FROM booking b
        JOIN teacher t ON t.id = b.teacher_id
        JOIN teacher_availability ta ON ta.id = b.availability_id
        LEFT JOIN user u on u.id=b.user_id
        LEFT JOIN class_level cl ON cl.id = u.assigned_class_id
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
        "google_meet_link": r.get("google_meet_link"),
    }) for r in rows]

    return render_template("my_bookings.html", title="My Bookings", items=items)


@main_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("student.book"))

    form = SignupForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        exists = db.session.execute(text("SELECT id FROM user WHERE email = :email"), {"email": email}).first()
        if exists:
            flash("Email already registered. Please login.", "warning")
            return redirect(url_for("student.login"))

        pw_hash = generate_password_hash(form.password.data)

        # Insert user
        db.session.execute(text("""
            INSERT INTO user
            (email, password_hash, 
             first_name, last_name, phone,
             address_1, address_2, city, province, postal_code, country, assigned_class_id,
             created_at)
            VALUES
            (:email, :pw,
             :fn, :ln, :phone,
             :a1, :a2, :city, :prov, :pc, :country, 11,
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

        # Get the ID of the row we just inserted (MySQL)
        user_id = db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar()

        # Insert role for THAT user
        db.session.execute(text("""
            INSERT INTO user_role (user_id, role, assigned_at)
            VALUES (:uid, 'student', NOW())
        """), {"uid": user_id})

        db.session.commit()

        # Now login
        u = get_user_by_id(int(user_id))
        login_user(u)

        new_id = db.session.execute(text("SELECT id FROM user WHERE email=:email"), {"email": email}).scalar()
        u = get_user_by_id(int(new_id))
        login_user(u)
        flash("Account created!", "success")
        return redirect(url_for("student.book"))

    return render_template("auth/signup.html", title="Sign Up", form=form)



# -----------------------------
# Helpers
# -----------------------------
def get_roles_for_user(user_id: int) -> list[str]:
    rows = db.session.execute(text("""
        SELECT ur.role
        FROM user_role ur
        WHERE ur.user_id = :uid
          AND ur.is_active = 1
    """), {"uid": user_id}).mappings().all()

    allowed = {"student", "teacher", "admin"}
    roles = sorted({
        (r["role"] or "").strip().lower()
        for r in rows
        if (r["role"] or "").strip()
    } & allowed)

    return roles


def get_user_by_id(user_id: int):
    row = db.session.execute(text("""
        SELECT id, email, first_name, last_name, phone,available_credits
        FROM `user`
        WHERE id = :id
        LIMIT 1
    """), {"id": user_id}).mappings().first()

    if not row:
        return None

    roles = get_roles_for_user(int(row["id"]))

    return AppUser(
        id=int(row["id"]),
        email=row["email"],
        role=roles,  # keep field name "role" if your AppUser uses it
        first_name=row["first_name"],
        last_name=row["last_name"],
        phone=row["phone"],
        available_credits=row["available_credits"]
    )

def get_active_role(user):
    # if already chosen and still valid, use it
    chosen = session.get("active_role")
    if chosen and chosen in (user.role or []):
        return chosen

    # if only one role, auto use it
    roles = user.role or []
    if len(roles) == 1:
        session["active_role"] = roles[0]
        return roles[0]

    return None  # multiple roles, not chosen yet
# -----------------------------
# Login Route
# -----------------------------


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    # If already logged in, route based on active role / choose role
    if current_user.is_authenticated:
        # if multiple roles and not chosen -> choose page
        roles = current_user.role or []
        print(current_user.role)

        active = session.get("active_role")
        print(active)
        if len(roles) > 1 and active not in roles:
            return redirect(url_for("student.choose_role"))
        return redirect(url_for("student.after_login_redirect"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        row = db.session.execute(text("""
            SELECT u.id, u.password_hash, u.email, u.first_name, u.last_name, u.phone, u.available_credits
            FROM `user` u
            WHERE u.email = :email
            LIMIT 1
        """), {"email": email}).mappings().first()

        if not row or not check_password_hash(row["password_hash"], form.password.data):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html", title="Login", form=form)

        roles = get_roles_for_user(int(row["id"]))  # must return list[str] active roles
        if not roles:
            flash("No active roles assigned to this account.", "danger")
            return render_template("auth/login.html", title="Login", form=form)

        # IMPORTANT: clear any previous role selection (user might switch accounts)
        session.pop("active_role", None)

        u = AppUser(
            id=int(row["id"]),
            email=row["email"],
            role=roles,  # list[str]
            first_name=row["first_name"],
            last_name=row["last_name"],
            phone=row["phone"],
            available_credits=int(row["available_credits"] or 0),
        )

        login_user(u)
        flash("Welcome!", "success")

        # ✅ Multi-role routing
        if len(roles) > 1:
            return redirect(url_for("student.choose_role"))

        # Only one role -> auto set it
        session["active_role"] = roles[0]
        return redirect(url_for("student.after_login_redirect"))

    return render_template("auth/login.html", title="Login", form=form)



@main_bp.get("/choose-role")
@login_required
def choose_role():
    roles = current_user.role or []
    if not roles:
        flash("No roles assigned. Contact admin.", "danger")
        return redirect(url_for("student.logout"))  # or safe page

    if len(roles) == 1:
        session["active_role"] = roles[0]
        return redirect(url_for("student.after_login_redirect"))

    return render_template("auth/choose_role.html", roles=roles)


@main_bp.post("/choose-role")
@login_required
def choose_role_post():
    role = (request.form.get("role") or "").strip().lower()
    roles = current_user.role or []

    if role not in roles:
        flash("Invalid role selection.", "danger")
        return redirect(url_for("student.choose_role"))

    session["active_role"] = role
    return redirect(url_for("student.after_login_redirect"))

@main_bp.get("/after-login")
@login_required
def after_login_redirect():
    role = session.get("active_role")
    roles = current_user.role or []

    # if multiple roles but not chosen yet
    if len(roles) > 1 and (not role or role not in roles):
        return redirect(url_for("student.choose_role"))

    # if single role, role may be missing, set it
    if len(roles) == 1 and (not role or role not in roles):
        session["active_role"] = roles[0]
        role = roles[0]

    # Now redirect based on selected role
    if role == "admin":
        return redirect(url_for("admin.messages"))  # change to your route
    if role == "teacher":
        return redirect(url_for("teacher.todaysClasses"))
    return redirect(url_for("student.book"))  # student default




@main_bp.get("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("student.index"))


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])



@main_bp.route("/forgotpassword", methods=["GET", "POST"])
def forgotpassword():
    form = ForgotPasswordForm()  # contains only email
    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        # Always respond same way (prevents email enumeration)
        flash("If that email exists, we sent a reset link.", "success")

        # Check if user exists
        row = db.session.execute(
            text("SELECT id FROM user WHERE email=:email"),
            {"email": email}
        ).mappings().first()

        if row:
            s = _serializer()
            token = s.dumps({"uid": row["id"]}, salt="reset-password")

            reset_url = url_for("student.reset_password", token=token, _external=True)

            html = f"""
            <!doctype html>
            <html>
              <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>Reset your password</title>
              </head>
              <body style="margin:0;padding:0;background:#f5f7fb;font-family:Arial,Helvetica,sans-serif;color:#111827;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f5f7fb;padding:24px 0;">
                  <tr>
                    <td align="center" style="padding:0 16px;">
                      <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 10px 25px rgba(17,24,39,0.08);">
                        <!-- Header -->
                        <tr>
                          <td style="padding:22px 26px;background:linear-gradient(135deg,#111827,#2563eb);">
                            <div style="font-size:16px;font-weight:700;letter-spacing:0.2px;color:#ffffff;">
                              The Rhythm School
                            </div>
                            <div style="margin-top:4px;font-size:13px;color:rgba(255,255,255,0.85);">
                              Secure account access
                            </div>
                          </td>
                        </tr>

                        <!-- Body -->
                        <tr>
                          <td style="padding:26px;">
                            <div style="font-size:20px;font-weight:700;line-height:1.3;margin:0 0 10px 0;">
                              Reset your password
                            </div>

                            <div style="font-size:14px;line-height:1.6;color:#374151;margin:0 0 16px 0;">
                              We received a request to reset your password. Click the button below to choose a new password.
                            </div>

                            <!-- Button -->
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:18px 0 18px 0;">
                              <tr>
                                <td align="center" bgcolor="#2563eb" style="border-radius:12px;">
                                  <a href="{reset_url}"
                                     style="display:inline-block;padding:12px 18px;font-size:14px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:12px;">
                                    Reset Password
                                  </a>
                                </td>
                              </tr>
                            </table>

                            <div style="font-size:13px;line-height:1.6;color:#6b7280;margin:0 0 12px 0;">
                              If the button doesn’t work, copy and paste this link into your browser:
                            </div>

                            <div style="font-size:12px;line-height:1.6;word-break:break-all;background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:12px;color:#111827;">
                              <a href="{reset_url}" style="color:#2563eb;text-decoration:underline;">{reset_url}</a>
                            </div>

                            <div style="font-size:13px;line-height:1.6;color:#6b7280;margin:16px 0 0 0;">
                              If you didn’t request this, you can safely ignore this email—your password won’t change.
                            </div>

                            <div style="margin-top:16px;padding-top:16px;border-top:1px solid #e5e7eb;font-size:12px;line-height:1.6;color:#9ca3af;">
                              For security, this link may expire after a short time.
                            </div>
                          </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                          <td style="padding:18px 26px;background:#f9fafb;border-top:1px solid #eef2f7;">
                            <div style="font-size:12px;color:#9ca3af;line-height:1.6;">
                              © {__import__("datetime").datetime.now().year} The Rhythm School. All rights reserved.
                            </div>
                          </td>
                        </tr>
                      </table>

                      <div style="max-width:600px;margin:12px auto 0 auto;font-size:11px;color:#9ca3af;line-height:1.5;padding:0 10px;">
                        Tip: If you have trouble resetting your password, reply to this email and we’ll help you out.
                      </div>
                    </td>
                  </tr>
                </table>
              </body>
            </html>
            """

            send_email(email, subject="Reset your password", body=reset_url ,html=html)
            print("RESET LINK:", reset_url)  # for testing

        return redirect(url_for("student.login"))

    return render_template("auth/forgotpassword.html", form=form)




@main_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    form = ResetPasswordForm()
    current_app.logger.info("Form fields: %s", list(form._fields.keys()))

    try:
        data = _serializer().loads(token, salt="reset-password", max_age=60 * 30)
        uid = int(data["uid"])
    except SignatureExpired:
        flash("Reset link expired. Please request again.", "danger")
        return redirect(url_for("student.forgotpassword"))
    except BadSignature:
        flash("Invalid reset link.", "danger")
        return redirect(url_for("student.forgotpassword"))

    # ✅ IMPORTANT: use your real table name: "user"
    row = db.session.execute(
        text('SELECT id, email FROM `user` WHERE id = :uid'),   # SQLite quoting
        {"uid": uid}
    ).mappings().first()

    if not row:
        flash("Invalid reset link (user not found).", "danger")
        return redirect(url_for("student.forgotpassword"))

    email = row["email"]

    if request.method == "POST":
        if not form.validate_on_submit():
            current_app.logger.info("Reset form errors: %s", form.errors)
            for field, errs in form.errors.items():
                for err in errs:
                    flash(err, "danger")
            return render_template("auth/reset_password.html", form=form, title="Reset Password", email=email)

        new_hash = generate_password_hash(form.password.data)

        result = db.session.execute(
            text('UPDATE `user` SET password_hash = :h WHERE id = :uid'),
            {"h": new_hash, "uid": uid}
        )

        if result.rowcount != 1:
            db.session.rollback()
            flash("Password was not updated. Please try again.", "danger")
            return render_template("auth/reset_password.html", form=form, title="Reset Password", email=email)

        db.session.commit()
        flash("Password updated. Please login.", "success")
        return redirect(url_for("student.login"))

    return render_template("auth/reset_password.html", form=form, title="Reset Password", email=email)





@main_bp.get("/programs")
def programs():
    return render_template("programs.html", title="Programs")




@main_bp.get("/certificate/<int:student_id>/pdf")
def certificate_pdf(student_id):

    data = {
        "certificate_id": f"TRS-{student_id:05d}",
        "issue_date": "2025-12-28",
        "student_name": "Inderdeep Singh",
        "course_name": "Vocal Training (Indian Classical)",
        "level_name": "Level 1",
        "duration_text": "8 Weeks",
        "instructor_name": "Harjeet Singh",
        "director_name": "Harjeet Singh",
    }

    html = render_template("certificates/certificate.html", **data)

    # base_url is important so WeasyPrint can load /static/... assets (logo, css, etc.)
    pdf_bytes = HTML(string=html, base_url=request.root_url).write_pdf()

    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'inline; filename="{data["certificate_id"]}.pdf"'
    return resp
