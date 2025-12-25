from __future__ import annotations
from datetime import datetime, date, time, timedelta
from types import SimpleNamespace
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from sqlalchemy import text
from ..extensions import db
from ..security import admin_required
from flask_login import current_user,logout_user, login_required
from types import SimpleNamespace
from flask import render_template, request, redirect, url_for, flash, current_app
from sqlalchemy import text
from ..extensions import db


# Optional emailer
try:
    from ..emailer import send_email
except Exception:  # pragma: no cover
    send_email = None

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _ns(d: dict) -> SimpleNamespace:
    return SimpleNamespace(**d)


# -------------------- Messages --------------------

from types import SimpleNamespace
from flask import render_template, request, redirect, url_for, flash, current_app
from sqlalchemy import text
from ..extensions import db

def _ns(d: dict) -> SimpleNamespace:
    return SimpleNamespace(**d)

@admin_bp.get("/messages")
@admin_required
def messages():
    active_email = (request.args.get("email") or "").strip().lower() or None
    q = (request.args.get("q") or "").strip().lower()

    # LEFT: threads grouped by email
    if q:
        thread_rows = db.session.execute(text("""
            SELECT
              x.email,
              x.name,
              x.pending_count,
              x.last_at,
              cm.subject AS last_subject,
              cm.message AS last_message
            FROM (
              SELECT
                email,
                MAX(id) AS last_id,
                MAX(name) AS name,
                SUM(CASE WHEN (reply_body IS NULL OR replied_at IS NULL) THEN 1 ELSE 0 END) AS pending_count,
                MAX(created_at) AS last_at
              FROM contact_message
              WHERE LOWER(email) LIKE :q
                 OR LOWER(name) LIKE :q
              GROUP BY email
            ) x
            JOIN contact_message cm ON cm.id = x.last_id
            ORDER BY (x.pending_count > 0) DESC, x.pending_count DESC, x.last_at DESC
            LIMIT 500
        """), {"q": f"%{q}%"}).mappings().all()
    else:
        thread_rows = db.session.execute(text("""
            SELECT
              x.email,
              x.name,
              x.pending_count,
              x.last_at,
              cm.subject AS last_subject,
              cm.message AS last_message
            FROM (
              SELECT
                email,
                MAX(id) AS last_id,
                MAX(name) AS name,
                SUM(CASE WHEN (reply_body IS NULL OR replied_at IS NULL) THEN 1 ELSE 0 END) AS pending_count,
                MAX(created_at) AS last_at
              FROM contact_message
              GROUP BY email
            ) x
            JOIN contact_message cm ON cm.id = x.last_id
            ORDER BY (x.pending_count > 0) DESC, x.pending_count DESC, x.last_at DESC
            LIMIT 500
        """)).mappings().all()

    threads = [_ns({
        "email": r["email"],
        "name": r["name"] or r["email"],
        "pending": int(r["pending_count"] or 0),
        "last_at": r["last_at"],
        "last_subject": r["last_subject"] or "",
        "last_message": r["last_message"] or "",
    }) for r in thread_rows]

    # RIGHT: selected conversation
    convo = []
    contact_name = None
    pending_for_active = 0

    if active_email:
        meta = db.session.execute(text("""
            SELECT
              MAX(name) AS name,
              SUM(CASE WHEN (reply_body IS NULL OR replied_at IS NULL) THEN 1 ELSE 0 END) AS pending
            FROM contact_message
            WHERE email = :email
        """), {"email": active_email}).mappings().first()

        contact_name = (meta["name"] if meta else None) or active_email
        pending_for_active = int((meta["pending"] if meta else 0) or 0)

        convo_rows = db.session.execute(text("""
            SELECT
              id, created_at, subject, message,
              reply_subject, reply_body, replied_at
            FROM contact_message
            WHERE email = :email
            ORDER BY created_at ASC, id ASC
            LIMIT 2000
        """), {"email": active_email}).mappings().all()

        convo = [_ns({
            "id": r["id"],
            "created_at": r["created_at"],
            "subject": r["subject"],
            "message": r["message"] or "",
            "reply_subject": r["reply_subject"],
            "reply_body": r["reply_body"],
            "replied_at": r["replied_at"],
            "needs_reply": (not r["reply_body"]) or (not r["replied_at"]),
        }) for r in convo_rows]

    # Optional: bell count
    total_pending = db.session.execute(text("""
        SELECT COUNT(*)
        FROM contact_message
        WHERE (reply_body IS NULL OR replied_at IS NULL)
    """)).scalar() or 0

    return render_template(
        "admin/messages.html",
        title="Messages",
        threads=threads,
        active_email=active_email,
        contact_name=contact_name,
        convo=convo,
        pending_for_active=pending_for_active,
        total_pending=int(total_pending),
        q=q,
    )


@admin_bp.post("/messages/send")
@admin_required
def messages_send():
    email = (request.form.get("email") or "").strip().lower()
    message_id_raw = (request.form.get("message_id") or "").strip()
    reply_subject = (request.form.get("reply_subject") or "").strip() or None
    reply_body = (request.form.get("reply_body") or "").strip()

    if not email or not reply_body:
        flash("Reply cannot be empty.", "danger")
        return redirect(url_for("admin.messages", email=email) if email else url_for("admin.messages"))

    # If message_id not provided, reply to latest unreplied for that email
    message_id = int(message_id_raw) if message_id_raw.isdigit() else None
    if not message_id:
        row = db.session.execute(text("""
            SELECT id
            FROM contact_message
            WHERE email = :email
              AND (reply_body IS NULL OR replied_at IS NULL)
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        """), {"email": email}).mappings().first()
        message_id = int(row["id"]) if row else None

    if not message_id:
        flash("No pending message found to reply.", "warning")
        return redirect(url_for("admin.messages", email=email))

    try:
        # Prevent double reply: only update if still unreplied
        updated = db.session.execute(text("""
            UPDATE contact_message
            SET reply_subject = :reply_subject,
                reply_body = :reply_body,
                replied_at = NOW()
            WHERE id = :id
              AND email = :email
              AND (reply_body IS NULL OR replied_at IS NULL)
            LIMIT 1
        """), {
            "reply_subject": reply_subject,
            "reply_body": reply_body,
            "id": message_id,
            "email": email,
        }).rowcount

        if updated != 1:
            db.session.rollback()
            flash("That message was already replied. Refresh the thread.", "warning")
            return redirect(url_for("admin.messages", email=email))

        db.session.commit()
        flash("Reply saved.", "success")
        return redirect(url_for("admin.messages", email=email))

    except Exception:
        db.session.rollback()
        current_app.logger.exception("messages_send failed")
        flash("Could not save reply. Check logs.", "danger")
        return redirect(url_for("admin.messages", email=email))


@admin_bp.post("/messages/<int:msg_id>/reply")
@admin_required
def reply_message(msg_id):
    reply_subject = (request.form.get("reply_subject") or "").strip()
    reply_body = (request.form.get("reply_body") or "").strip()
    if not reply_subject or not reply_body:
        flash("Reply subject/body required.", "danger")
        return redirect(url_for("admin.messages"))

    msg = db.session.execute(text("""
        SELECT id, email
        FROM contact_message
        WHERE id = :id
    """), {"id": msg_id}).mappings().first()

    if not msg:
        flash("Message not found.", "danger")
        return redirect(url_for("admin.messages"))

    if send_email:
        try:
            send_email(msg["email"], reply_subject, reply_body)
        except Exception:
            flash("Reply saved, but email sending failed.", "warning")
            # Still save reply

    db.session.execute(text("""
        UPDATE contact_message
        SET reply_subject = :sub,
            reply_body = :body,
            replied_at = NOW()
        WHERE id = :id
    """), {"sub": reply_subject, "body": reply_body, "id": msg_id})
    db.session.commit()

    flash("Reply saved.", "success")
    return redirect(url_for("admin.messages"))




@admin_bp.get("/login")
def login():
    # Admin login is the same as normal login
    if current_user.is_authenticated:
        # If user is already logged in, send them to admin or book page
        if getattr(current_user, "is_admin", False):
            return redirect(url_for("admin.messages"))
        return redirect(url_for("main.book"))
    return redirect(url_for("main.login"))




@admin_bp.get("/logout")
@login_required
def logout():
    # same logout behavior as main.logout
    logout_user()
    return redirect(url_for("main.logout"))







# -------------------- Teachers --------------------

@admin_bp.get("/teachers")
@admin_required
def teachers():
    teachers_rows = db.session.execute(text("""
        SELECT
          t.id, t.name, t.email, t.bio, t.is_active, t.class_duration_min,
          t.default_venue_id,
          v.name AS default_venue_name
        FROM teacher t
        LEFT JOIN venue v ON v.id = t.default_venue_id
        ORDER BY t.name ASC
    """)).mappings().all()

    venues_rows = db.session.execute(text("""
        SELECT id, name
        FROM venue
        WHERE is_active = 1
        ORDER BY name ASC
    """)).mappings().all()

    teachers = []
    for r in teachers_rows:
        teachers.append(_ns({
            "id": r["id"],
            "name": r["name"],
            "email": r["email"],
            "bio": r["bio"],
            "is_active": bool(r["is_active"]),
            "class_duration_min": int(r["class_duration_min"] or 45),
            "default_venue_id": r["default_venue_id"],
            "default_venue": (_ns({"id": r["default_venue_id"], "name": r["default_venue_name"]})
                              if r["default_venue_id"] else None)
        }))

    venues = [_ns({"id": v["id"], "name": v["name"]}) for v in venues_rows]

    return render_template("admin/teachers.html", title="Teachers", teachers=teachers, venues=venues)


@admin_bp.post("/teachers/create")
@admin_required
def teacher_create():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Teacher name required.", "danger")
        return redirect(url_for("admin.teachers"))

    email = (request.form.get("email") or "").strip() or None
    bio = (request.form.get("bio") or "").strip() or None
    is_active = 1 if (request.form.get("is_active") == "1") else 0
    default_venue_id = request.form.get("default_venue_id")
    default_venue_id = int(default_venue_id) if default_venue_id else None
    shift_start_time = request.form.get("shift_start_time")
    shift_end_time = request.form.get("shift_end_time")
    break_start_time = request.form.get("break_start_time")
    break_end_time = request.form.get("break_end_time")
    duration = int(request.form.get("class_duration_min") or 45)
    duration = max(15, min(duration, 240))

    db.session.execute(text("""
        INSERT INTO teacher
        (name, email, bio, class_duration_min, is_active, default_venue_id,shift_start_time,shift_end_time,break_start_time,break_end_time)
        VALUES
        (:name, :email, :bio, :duration, :is_active, :default_venue_id,:shift_start_time,:shift_end_time,:break_start_time,:break_end_time)
    """), {
        "name": name,
        "email": email,
        "bio": bio,
        "duration": duration,
        "is_active": is_active,
        "default_venue_id": default_venue_id,
    "shift_start_time": shift_start_time,
    "shift_end_time": shift_end_time,
    "break_start_time" : break_start_time,
    "break_end_time" : break_end_time
    })
    db.session.commit()

    shift_start_time
    shift_end_time
    break_start_time
    break_end_time



    flash("Teacher created.", "success")
    return redirect(url_for("admin.teachers"))



@admin_bp.post("/teachers/<int:teacher_id>/update")
@admin_required
def teacher_update(teacher_id):
    duration = int(request.form.get("class_duration_min") or 45)
    duration = max(15, min(duration, 240))
    default_venue_id = request.form.get("default_venue_id")
    default_venue_id = int(default_venue_id) if default_venue_id else None

    db.session.execute(text("""
        UPDATE teacher
        SET class_duration_min = :duration,
            default_venue_id = :default_venue_id
        WHERE id = :id
    """), {"duration": duration, "default_venue_id": default_venue_id, "id": teacher_id})
    db.session.commit()

    flash("Teacher updated.", "success")
    return redirect(url_for("admin.teachers"))


@admin_bp.post("/teachers/<int:teacher_id>/toggle")
@admin_required
def teacher_toggle(teacher_id):
    db.session.execute(text("""
        UPDATE teacher
        SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
        WHERE id = :id
    """), {"id": teacher_id})
    db.session.commit()
    flash("Teacher status updated.", "success")
    return redirect(url_for("admin.teachers"))


@admin_bp.post("/teachers/<int:teacher_id>/delete")
@admin_required
def teacher_delete(teacher_id):
    try:
        db.session.execute(text("DELETE FROM teacher WHERE id = :id"), {"id": teacher_id})
        db.session.commit()
        flash("Teacher deleted.", "success")
    except Exception:
        db.session.rollback()
        flash("Delete failed (teacher may have availability/bookings). Deactivate instead.", "danger")
    return redirect(url_for("admin.teachers"))


# -------------------- Teacher Availability --------------------

@admin_bp.get("/teachers/<int:teacher_id>/availability")
@admin_required
def teacher_availability(teacher_id):
    teacher = db.session.execute(text("""
        SELECT
          t.id, t.name, t.class_duration_min, t.default_venue_id,
          v.name AS default_venue_name
        FROM teacher t
        LEFT JOIN venue v ON v.id = t.default_venue_id
        WHERE t.id = :id
    """), {"id": teacher_id}).mappings().first()

    if not teacher:
        flash("Teacher not found.", "danger")
        return redirect(url_for("admin.teachers"))

    venues_rows = db.session.execute(text("""
        SELECT id, name
        FROM venue
        WHERE is_active = 1
        ORDER BY name ASC
    """)).mappings().all()

    slots_rows = db.session.execute(text("""
        SELECT
          ta.id, ta.teacher_id, ta.start_at, ta.end_at, ta.venue_id, ta.is_booked,
          v.name AS venue_name
        FROM teacher_availability ta
        LEFT JOIN venue v ON v.id = ta.venue_id
        WHERE ta.teacher_id = :tid
        and ta.is_booked=1
        ORDER BY ta.start_at ASC
        LIMIT 200
    """), {"tid": teacher_id}).mappings().all()

    teacher_obj = _ns({
        "id": teacher["id"],
        "name": teacher["name"],
        "class_duration_min": int(teacher["class_duration_min"] or 45),
        "default_venue_id": teacher["default_venue_id"],
        "default_venue": (_ns({"id": teacher["default_venue_id"], "name": teacher["default_venue_name"]})
                          if teacher["default_venue_id"] else None)
    })

    venues = [_ns({"id": v["id"], "name": v["name"]}) for v in venues_rows]

    slots = []
    for s in slots_rows:
        slots.append(_ns({
            "id": s["id"],
            "start_at": s["start_at"],
            "end_at": s["end_at"],
            "is_booked": bool(s["is_booked"]),
            "venue_id": s["venue_id"],
            "venue": (_ns({"id": s["venue_id"], "name": s["venue_name"]}) if s["venue_id"] else None)
        }))

    return render_template("admin/teacher_availability.html",
                           title="Availability",
                           teacher=teacher_obj, venues=venues, slots=slots)



@admin_bp.post("/teachers/<int:teacher_id>/availability/create")
@admin_required
def availability_create(teacher_id):
    # ---------- Debug helper ----------
    def dbg(msg: str):
        print(f"[availability_create] {msg}")
        try:
            current_app.logger.info(f"[availability_create] {msg}")
        except Exception:
            pass

    # ---------- Convert MySQL TIME values (often returned as timedelta) ----------
    def to_time(v):
        """
        Accepts datetime.time | datetime.timedelta | 'HH:MM[:SS]' | None -> datetime.time | None
        PyMySQL commonly returns MySQL TIME columns as datetime.timedelta.
        """
        if v is None:
            return None

        if isinstance(v, time):
            return v

        if isinstance(v, timedelta):
            total_seconds = int(v.total_seconds())
            total_seconds = total_seconds % (24 * 3600)
            h = total_seconds // 3600
            m = (total_seconds % 3600) // 60
            s = total_seconds % 60
            return time(hour=h, minute=m, second=s)

        if isinstance(v, str):
            parts = v.strip().split(":")
            h = int(parts[0]) if len(parts) > 0 else 0
            m = int(parts[1]) if len(parts) > 1 else 0
            s = int(parts[2]) if len(parts) > 2 else 0
            return time(hour=h, minute=m, second=s)

        raise TypeError(f"Unsupported time type: {type(v)} -> {v}")

    # ---------- Config (can be made dynamic via form inputs later) ----------
    start_date = date.today() + timedelta(days=1)   # tomorrow
    days = 7                                       # generate next 7 days
    default_duration = 45

    venue_id = request.form.get("venue_id")
    venue_id = int(venue_id) if venue_id else None

    dbg(f"START teacher_id={teacher_id}, start_date={start_date}, days={days}, venue_id={venue_id}")

    # ---------- Load teacher config in ONE query ----------
    teacher = db.session.execute(text("""
        SELECT
            id,
            class_duration_min,
            shift_start_time,
            shift_end_time,
            break_start_time,
            break_end_time
        FROM teacher
        WHERE id = :id
        LIMIT 1
    """), {"id": teacher_id}).mappings().first()

    if not teacher:
        flash("Teacher not found.", "danger")
        dbg("Teacher not found.")
        return redirect(url_for("admin.teachers"))

    # Duration
    duration = int((teacher["class_duration_min"] or default_duration) or default_duration)
    duration = max(15, min(duration, 240))
    step = timedelta(minutes=duration)

    # Normalize TIME values
    raw_s = teacher["shift_start_time"]
    raw_e = teacher["shift_end_time"]
    raw_bs = teacher["break_start_time"]
    raw_be = teacher["break_end_time"]

    s_time = to_time(raw_s)
    e_time = to_time(raw_e)
    b_s = to_time(raw_bs)
    b_e = to_time(raw_be)

    dbg(f"RAW types: shift_start={type(raw_s)}, shift_end={type(raw_e)}, "
        f"break_start={type(raw_bs)}, break_end={type(raw_be)}")
    dbg(f"Normalized: duration={duration}, shift=({s_time} -> {e_time}), break=({b_s} -> {b_e})")

    if not s_time or not e_time:
        flash("Please set teacher shift start and end time first.", "danger")
        dbg("Missing shift_start_time or shift_end_time.")
        return redirect(url_for("admin.teacher_availability", teacher_id=teacher_id))

    # ---------- Helpers for window building ----------
    def build_window(d: date, start_t: time, end_t: time):
        """Return (start_dt, end_dt) for a date, supporting overnight end."""
        start_dt = datetime.combine(d, start_t)
        end_dt = datetime.combine(d, end_t)
        if end_dt <= start_dt:
            # Overnight shift (e.g. 20:00 -> 02:00 next day)
            end_dt = datetime.combine(d + timedelta(days=1), end_t)
        return start_dt, end_dt

    def build_break(d: date, bs: time | None, be: time | None,
                    shift_start_dt: datetime, shift_end_dt: datetime):
        """
        Build break window. Supports overnight breaks too.
        Returns (break_start_dt, break_end_dt) or (None, None).
        Clamps break inside shift.
        """
        if not bs or not be:
            return None, None

        br_s = datetime.combine(d, bs)
        br_e = datetime.combine(d, be)
        if br_e <= br_s:
            br_e = datetime.combine(d + timedelta(days=1), be)

        # Clamp within shift bounds
        br_s = max(br_s, shift_start_dt)
        br_e = min(br_e, shift_end_dt)
        if br_e <= br_s:
            return None, None

        return br_s, br_e

    # ---------- Slot generation ----------
    rows_to_insert = []
    created = 0

    for i in range(days):
        businessdate = start_date + timedelta(days=i)

        shift_start_dt, shift_end_dt = build_window(businessdate, s_time, e_time)
        break_start_dt, break_end_dt = build_break(
            businessdate, b_s, b_e, shift_start_dt, shift_end_dt
        )

        dbg(f"Day {businessdate}: shift {shift_start_dt} -> {shift_end_dt}, "
            f"break {break_start_dt} -> {break_end_dt}")

        cur = shift_start_dt
        day_slots = 0

        # Safety guard (should never hit unless config is broken)
        max_iters = 10000
        iters = 0

        while cur + step <= shift_end_dt:
            iters += 1
            if iters > max_iters:
                dbg(f"SAFETY BREAK: too many iterations on {businessdate}")
                break

            nxt = cur + step

            # Skip overlap with break
            if break_start_dt and break_end_dt:
                overlaps_break = not (nxt <= break_start_dt or cur >= break_end_dt)
                if overlaps_break:
                    dbg(f"Skipping slot overlapping break: {cur} -> {nxt}; jump to {break_end_dt}")
                    cur = break_end_dt
                    continue

            rows_to_insert.append({
                "teacher_id": teacher_id,
                "start_at": cur,
                "end_at": nxt,
                "venue_id": venue_id,
                "businessdate": businessdate
            })

            created += 1
            day_slots += 1
            cur = nxt

        dbg(f"Day {businessdate}: generated {day_slots} slots")

    if created == 0:
        flash("No slots generated (check teacher shift times / duration).", "warning")
        dbg("No slots generated.")
        return redirect(url_for("admin.teacher_availability", teacher_id=teacher_id))

    dbg(f"Prepared total rows_to_insert={len(rows_to_insert)}")

    # ---------- Bulk insert ----------
    insert_sql = text("""
        INSERT INTO teacher_availability
            (teacher_id, start_at, end_at, venue_id, is_booked, businessdate)
        VALUES
            (:teacher_id, :start_at, :end_at, :venue_id, 0, :businessdate)
    """)

    try:
        # Debug without in_transaction()
        dbg(f"db.session type={type(db.session)}")
        try:
            real_sess = db.session()  # underlying Session
            dbg(f"real session type={type(real_sess)}")
            dbg(f"real session in_transaction={real_sess.in_transaction()}")
        except Exception as _e:
            dbg(f"could not inspect real session state: {repr(_e)}")

        dbg(f"bulk insert rows={len(rows_to_insert)}")
        db.session.execute(insert_sql, rows_to_insert)

        dbg("executed insert; committing...")
        db.session.commit()
        dbg("commit OK")

        flash(f"Created {created} slot(s) of {duration} minutes for next {days} day(s).", "success")

    except Exception as e:
        dbg(f"INSERT ERROR: {repr(e)} -> rolling back")
        db.session.rollback()
        flash("Could not create slots (some may already exist). Check logs.", "danger")

    return redirect(url_for("admin.teacher_availability", teacher_id=teacher_id))


@admin_bp.post("/teachers/<int:teacher_id>/availability/bulk")
@admin_required
def availability_bulk(teacher_id):
    start_date_s = request.form.get("start_date")
    end_date_s = request.form.get("end_date")
    start_time_s = request.form.get("start_time")
    end_time_s = request.form.get("end_time")
    venue_id = request.form.get("venue_id")
    venue_id = int(venue_id) if venue_id else None

    dows = request.form.getlist("dow")  # 0=Mon ... 6=Sun
    dows = set(int(x) for x in dows)

    if not start_date_s or not end_date_s or not start_time_s or not end_time_s or not dows:
        flash("Fill date range, start/end time, and select days.", "danger")
        return redirect(url_for("admin.teacher_availability", teacher_id=teacher_id))

    start_d = date.fromisoformat(start_date_s)
    end_d = date.fromisoformat(end_date_s)
    if end_d < start_d:
        flash("End date must be after start date.", "danger")
        return redirect(url_for("admin.teacher_availability", teacher_id=teacher_id))

    st = time.fromisoformat(start_time_s)
    et = time.fromisoformat(end_time_s)
    if et <= st:
        flash("End time must be after start time.", "danger")
        return redirect(url_for("admin.teacher_availability", teacher_id=teacher_id))

    t = db.session.execute(text("""
        SELECT class_duration_min
        FROM teacher
        WHERE id = :id
    """), {"id": teacher_id}).mappings().first()

    duration = int((t["class_duration_min"] if t else 45) or 45)
    duration = max(15, min(duration, 240))
    step = timedelta(minutes=duration)

    created = 0
    cur_day = start_d

    try:
        with db.session.begin():
            while cur_day <= end_d:
                if cur_day.weekday() in dows:
                    window_start = datetime.combine(cur_day, st)
                    window_end = datetime.combine(cur_day, et)

                    cur = window_start
                    while cur + step <= window_end:
                        db.session.execute(text("""
                            INSERT INTO teacher_availability
                            (teacher_id, start_at, end_at, venue_id, is_booked)
                            VALUES
                            (:teacher_id, :start_at, :end_at, :venue_id, 0)
                        """), {
                            "teacher_id": teacher_id,
                            "start_at": cur,
                            "end_at": cur + step,
                            "venue_id": venue_id
                        })
                        created += 1
                        cur = cur + step

                cur_day += timedelta(days=1)

        flash(f"Created {created} slot(s) of {duration} minutes.", "success")
    except Exception:
        db.session.rollback()
        flash("Could not create slots (duplicates may exist).", "danger")

    return redirect(url_for("admin.teacher_availability", teacher_id=teacher_id))


@admin_bp.post("/teachers/<int:teacher_id>/availability/<int:slot_id>/delete")
@admin_required
def availability_delete(teacher_id, slot_id):
    row = db.session.execute(text("""
        SELECT is_booked
        FROM teacher_availability
        WHERE id = :id AND teacher_id = :tid
    """), {"id": slot_id, "tid": teacher_id}).mappings().first()

    if not row:
        flash("Slot not found.", "danger")
        return redirect(url_for("admin.teacher_availability", teacher_id=teacher_id))

    if int(row["is_booked"]) == 1:
        flash("Cannot delete a booked slot.", "danger")
        return redirect(url_for("admin.teacher_availability", teacher_id=teacher_id))

    db.session.execute(text("""
        DELETE FROM teacher_availability
        WHERE id = :id AND teacher_id = :tid
    """), {"id": slot_id, "tid": teacher_id})
    db.session.commit()

    flash("Slot deleted.", "success")
    return redirect(url_for("admin.teacher_availability", teacher_id=teacher_id))


# -------------------- Venues --------------------

@admin_bp.get("/venues")
@admin_required
def venues():
    rows = db.session.execute(text("""
        SELECT id, name, address, notes, is_active
        FROM venue
        ORDER BY name ASC
    """)).mappings().all()

    venues_list = [_ns({
        "id": r["id"],
        "name": r["name"],
        "address": r["address"],
        "notes": r["notes"],
        "is_active": bool(r["is_active"]),
    }) for r in rows]

    return render_template("admin/venues.html", title="Venues", venues=venues_list)


@admin_bp.post("/venues/create")
@admin_required
def venue_create():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Venue name required.", "danger")
        return redirect(url_for("admin.venues"))

    address = (request.form.get("address") or "").strip() or None
    notes = (request.form.get("notes") or "").strip() or None
    is_active = 1 if (request.form.get("is_active") == "1") else 0

    db.session.execute(text("""
        INSERT INTO venue (name, address, notes, is_active)
        VALUES (:name, :address, :notes, :is_active)
    """), {"name": name, "address": address, "notes": notes, "is_active": is_active})
    db.session.commit()

    flash("Venue created.", "success")
    return redirect(url_for("admin.venues"))


@admin_bp.post("/venues/<int:venue_id>/toggle")
@admin_required
def venue_toggle(venue_id):
    db.session.execute(text("""
        UPDATE venue
        SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
        WHERE id = :id
    """), {"id": venue_id})
    db.session.commit()

    flash("Venue status updated.", "success")
    return redirect(url_for("admin.venues"))


@admin_bp.post("/venues/<int:venue_id>/delete")
@admin_required
def venue_delete(venue_id):
    try:
        db.session.execute(text("DELETE FROM venue WHERE id = :id"), {"id": venue_id})
        db.session.commit()
        flash("Venue deleted.", "success")
    except Exception:
        db.session.rollback()
        flash("Delete failed (venue may be referenced). Deactivate instead.", "danger")

    return redirect(url_for("admin.venues"))


# -------------------- Syllabus --------------------

@admin_bp.get("/syllabus")
@admin_required
def syllabus():
    levels_rows = db.session.execute(text("""
        SELECT id, code, title, is_active
        FROM class_level
        ORDER BY id ASC
    """)).mappings().all()

    levels = [_ns({"id": r["id"], "code": r["code"], "title": r["title"], "is_active": bool(r["is_active"])})
              for r in levels_rows]

    if not levels:
        flash("No class levels found.", "danger")
        return render_template("admin/syllabus.html", title="Syllabus", levels=[], selected_level=None, items=[])

    selected_id = request.args.get("class_level_id")
    selected_level = None
    if selected_id:
        for lv in levels:
            if lv.id == int(selected_id):
                selected_level = lv
                break
    if not selected_level:
        selected_level = levels[0]

    items_rows = db.session.execute(text("""
        SELECT id, class_level_id, unit_no, topic, details, resource_link, created_at
        FROM syllabus_item
        WHERE class_level_id = :clid
        ORDER BY (unit_no IS NULL) ASC, unit_no ASC, id ASC
    """), {"clid": selected_level.id}).mappings().all()

    items = [_ns({
        "id": r["id"],
        "class_level_id": r["class_level_id"],
        "unit_no": r["unit_no"],
        "topic": r["topic"],
        "details": r["details"],
        "resource_link": r["resource_link"],
        "created_at": r["created_at"],
    }) for r in items_rows]

    return render_template("admin/syllabus.html", title="Syllabus",
                           levels=levels, selected_level=selected_level, items=items)


@admin_bp.post("/syllabus/add")
@admin_required
def syllabus_add():
    class_level_id = int(request.form.get("class_level_id") or 0)
    topic = (request.form.get("topic") or "").strip()
    if not class_level_id or not topic:
        flash("Class level and topic are required.", "danger")
        return redirect(url_for("admin.syllabus"))

    unit_no = request.form.get("unit_no")
    unit_no = int(unit_no) if unit_no else None

    details = (request.form.get("details") or "").strip() or None
    resource_link = (request.form.get("resource_link") or "").strip() or None

    db.session.execute(text("""
        INSERT INTO syllabus_item
        (class_level_id, unit_no, topic, details, resource_link, created_at)
        VALUES
        (:clid, :unit_no, :topic, :details, :link, NOW())
    """), {"clid": class_level_id, "unit_no": unit_no, "topic": topic, "details": details, "link": resource_link})
    db.session.commit()

    flash("Syllabus item added.", "success")
    return redirect(url_for("admin.syllabus", class_level_id=class_level_id))


@admin_bp.post("/syllabus/<int:item_id>/delete")
@admin_required
def syllabus_delete(item_id):
    row = db.session.execute(text("""
        SELECT class_level_id
        FROM syllabus_item
        WHERE id = :id
    """), {"id": item_id}).mappings().first()

    if not row:
        flash("Syllabus item not found.", "danger")
        return redirect(url_for("admin.syllabus"))

    db.session.execute(text("DELETE FROM syllabus_item WHERE id = :id"), {"id": item_id})
    db.session.commit()

    flash("Syllabus item deleted.", "success")
    return redirect(url_for("admin.syllabus", class_level_id=row["class_level_id"]))


# -------------------- Bookings (Admin assigns class) --------------------

@admin_bp.get("/bookings")
@admin_required
def bookings():
    bookings_rows = db.session.execute(text("""
        SELECT
          b.id,
          b.status,
          b.created_at,
          b.teacher_id,
          t.name AS teacher_name,
          b.user_id,
          b.student_name,
          b.student_email,
          b.student_phone,
          b.class_level_id,
          cl.code AS class_code,
          cl.title AS class_title,
          b.venue_id,
          v.name AS venue_name,
          ta.start_at,
          ta.end_at
        FROM booking b
        JOIN teacher t ON t.id = b.teacher_id
        JOIN teacher_availability ta ON ta.id = b.availability_id
        LEFT JOIN class_level cl ON cl.id = b.class_level_id
        LEFT JOIN venue v ON v.id = b.venue_id
        ORDER BY b.created_at DESC
        LIMIT 500
    """)).mappings().all()

    levels_rows = db.session.execute(text("""
        SELECT id, code, title
        FROM class_level
        WHERE is_active = 1
        ORDER BY id ASC
    """)).mappings().all()

    levels = [_ns({"id": r["id"], "code": r["code"], "title": r["title"]}) for r in levels_rows]

    bookings_list = []
    for r in bookings_rows:
        bookings_list.append(_ns({
            "id": r["id"],
            "status": r["status"],
            "created_at": r["created_at"],
            "student_name": r["student_name"],
            "student_email": r["student_email"],
            "student_phone": r["student_phone"],
            "teacher": _ns({"id": r["teacher_id"], "name": r["teacher_name"]}),
            "availability": _ns({"start_at": r["start_at"], "end_at": r["end_at"]}),
            "class_level_id": r["class_level_id"],
            "class_level": (_ns({"id": r["class_level_id"], "code": r["class_code"], "title": r["class_title"]})
                            if r["class_level_id"] else None),
            "venue": (_ns({"id": r["venue_id"], "name": r["venue_name"]})
                      if r["venue_id"] else None),
        }))

    return render_template("admin/bookings.html", title="Bookings", bookings=bookings_list, levels=levels)


@admin_bp.post("/bookings/<int:booking_id>/set-class")
@admin_required
def booking_set_class(booking_id):
    class_level_id = request.form.get("class_level_id")
    class_level_id = int(class_level_id) if class_level_id else None

    db.session.execute(text("""
        UPDATE booking
        SET class_level_id = :clid
        WHERE id = :bid
    """), {"clid": class_level_id, "bid": booking_id})
    db.session.commit()

    flash("Class updated for booking.", "success")
    return redirect(url_for("admin.bookings"))


@admin_bp.post("/bookings/<int:booking_id>/cancel")
@admin_required
def booking_cancel(booking_id):
    # Cancel booking and free slot
    row = db.session.execute(text("""
        SELECT availability_id
        FROM booking
        WHERE id = :id AND status = 'BOOKED'
    """), {"id": booking_id}).mappings().first()

    if not row:
        flash("Booking not active or not found.", "warning")
        return redirect(url_for("admin.bookings"))

    db.session.execute(text("""
            UPDATE booking
            SET status = 'CANCELLED'
            WHERE id = :id
        """), {"id": booking_id})

    db.session.execute(text("""
            UPDATE teacher_availability
            SET is_booked = 0
            WHERE id = :aid
        """), {"aid": row["availability_id"]})
    db.session.commit()
    flash("Booking cancelled and slot freed.", "success")
    return redirect(url_for("admin.bookings"))


# -------------------- Users (Admin) --------------------

@admin_bp.get("/users")
@admin_required
def users():
    rows = db.session.execute(text("""
        SELECT id, email, role, first_name, last_name, phone, created_at
        FROM user
        ORDER BY created_at DESC
        LIMIT 500
    """)).mappings().all()

    items = []
    for r in rows:
        full_name = ((r["first_name"] or "").strip() + " " + (r["last_name"] or "").strip()).strip() or r["email"]
        items.append(_ns({
            "id": r["id"],
            "email": r["email"],
            "role": r["role"],
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "phone": r["phone"],
            "created_at": r["created_at"],
            "full_name": full_name
        }))

    return render_template("admin/users.html", title="Users", items=items)


def _ns(d: dict) -> SimpleNamespace:
    return SimpleNamespace(**d)




@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def user_edit(user_id: int):
    # classes for dropdown
    class_rows = db.session.execute(text("""
        SELECT id, code, title
        FROM class_level
        ORDER BY id ASC
    """)).mappings().all()

    classes = [_ns({
        "id": r["id"],
        "label": f"{r['code']} · {r['title']}"
    }) for r in class_rows]

    user = db.session.execute(text("""
        SELECT
          id, email, role,
          first_name, last_name, phone,
          address_1, address_2, city, province, postal_code, country,
          assigned_class_id
        FROM `user`
        WHERE id = :id
        LIMIT 1
    """), {"id": user_id}).mappings().first()

    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("admin.users"))

    if request.method == "POST":
        # Read form
        email = (request.form.get("email") or "").strip().lower()
        role = (request.form.get("role") or "customer").strip().lower()
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        phone = (request.form.get("phone") or "").strip() or None

        address_1 = (request.form.get("address_1") or "").strip() or None
        address_2 = (request.form.get("address_2") or "").strip() or None
        city = (request.form.get("city") or "").strip() or None
        province = (request.form.get("province") or "").strip() or None
        postal_code = (request.form.get("postal_code") or "").strip() or None
        country = (request.form.get("country") or "").strip() or None

        assigned_class_id_raw = (request.form.get("assigned_class_id") or "").strip()
        assigned_class_id = int(assigned_class_id_raw) if assigned_class_id_raw.isdigit() else None

        # Basic validations
        if not email:
            flash("Email is required.", "danger")
            return redirect(url_for("admin.user_edit", user_id=user_id))

        if role not in ("admin", "customer"):
            role = "customer"

        # Email uniqueness check if changed
        exists = db.session.execute(text("""
            SELECT id FROM `user`
            WHERE email = :email AND id <> :id
            LIMIT 1
        """), {"email": email, "id": user_id}).first()

        if exists:
            flash("That email is already used by another user.", "danger")
            return redirect(url_for("admin.user_edit", user_id=user_id))

        try:
            db.session.execute(text("""
                UPDATE `user`
                SET email = :email,
                    role = :role,
                    first_name = :first_name,
                    last_name = :last_name,
                    phone = :phone,
                    address_1 = :address_1,
                    address_2 = :address_2,
                    city = :city,
                    province = :province,
                    postal_code = :postal_code,
                    country = :country,
                    assigned_class_id = :assigned_class_id
                WHERE id = :id
                LIMIT 1
            """), {
                "email": email,
                "role": role,
                "first_name": first_name,
                "last_name": last_name,
                "phone": phone,
                "address_1": address_1,
                "address_2": address_2,
                "city": city,
                "province": province,
                "postal_code": postal_code,
                "country": country,
                "assigned_class_id": assigned_class_id,
                "id": user_id,
            })
            db.session.commit()
            flash("User updated successfully.", "success")
            return redirect(url_for("admin.users"))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("[admin.user_edit] update failed")
            flash("Could not update user. Check logs.", "danger")
            return redirect(url_for("admin.user_edit", user_id=user_id))

    # GET render
    item = _ns({
        **user,
        "full_name": (f"{user['first_name'] or ''} {user['last_name'] or ''}".strip() or "—")
    })
    return render_template("admin/user_edit.html", title="Edit User", u=item, classes=classes)


@admin_bp.post("/users/create")
@admin_required
def user_create():
    email = (request.form.get("email") or "").strip().lower()
    password = (request.form.get("password") or "").strip()
    role = (request.form.get("role") or "customer").strip().lower()
    if role not in ["admin", "customer"]:
        role = "customer"

    if not email or not password:
        flash("Email and password required.", "danger")
        return redirect(url_for("admin.users"))

    exists = db.session.execute(text("SELECT id FROM user WHERE email = :email"), {"email": email}).first()
    if exists:
        flash("User already exists.", "warning")
        return redirect(url_for("admin.users"))

    from werkzeug.security import generate_password_hash
    pw_hash = generate_password_hash(password)

    db.session.execute(text("""
        INSERT INTO user (email, password_hash, role, created_at)
        VALUES (:email, :pw, :role, NOW())
    """), {"email": email, "pw": pw_hash, "role": role})
    db.session.commit()

    flash("User created.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.post("/users/<int:user_id>/role")
@admin_required
def user_set_role(user_id):
    role = (request.form.get("role") or "customer").strip().lower()
    if role not in ["admin", "customer"]:
        role = "customer"

    db.session.execute(text("""
        UPDATE user
        SET role = :role
        WHERE id = :id
    """), {"role": role, "id": user_id})
    db.session.commit()

    flash("Role updated.", "success")
    return redirect(url_for("admin.users"))



@admin_bp.app_context_processor
def inject_admin_message_badge():
    """
    Provides admin_unreplied_count to templates on /admin/* pages only.
    Hides bell when count == 0.
    """
    count = 0
    try:
        if current_user.is_authenticated and getattr(current_user, "is_admin", False):
            # Try both table names (some projects use contact_message, some contact_messages)
            try:
                count = db.session.execute(
                    text("SELECT COUNT(*) FROM contact_message WHERE replied_at IS NULL")
                ).scalar() or 0
            except Exception:
                count = db.session.execute(
                    text("SELECT COUNT(*) FROM contact_messages WHERE replied_at IS NULL")
                ).scalar() or 0
    except Exception:
        count = 0

    return {"admin_unreplied_count": int(count)}
