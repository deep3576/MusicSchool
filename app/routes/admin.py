from __future__ import annotations
from datetime import datetime, date, time, timedelta
from types import SimpleNamespace
from flask import Blueprint, render_template, redirect, url_for, flash, request
from sqlalchemy import text
from ..extensions import db
from ..security import admin_required
from flask_login import current_user,logout_user, login_required


# Optional emailer
try:
    from ..emailer import send_email
except Exception:  # pragma: no cover
    send_email = None

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _ns(d: dict) -> SimpleNamespace:
    return SimpleNamespace(**d)


# -------------------- Messages --------------------

@admin_bp.get("/messages")
@admin_required
def messages():
    rows = db.session.execute(text("""
        SELECT id, name, email, phone, subject, message, created_at,
               reply_subject, reply_body, replied_at
        FROM contact_message
        ORDER BY created_at DESC
        LIMIT 300
    """)).mappings().all()

    items = []
    for r in rows:
        items.append(_ns({
            "id": r["id"],
            "name": r["name"],
            "email": r["email"],
            "phone": r["phone"],
            "subject": r["subject"],
            "message": r["message"],
            "created_at": r["created_at"],
            "reply_subject": r["reply_subject"],
            "reply_body": r["reply_body"],
            "replied_at": r["replied_at"],
            "is_replied": True if r["replied_at"] else False
        }))

    return render_template("admin/messages.html", title="Messages", items=items)



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

    duration = int(request.form.get("class_duration_min") or 45)
    duration = max(15, min(duration, 240))

    db.session.execute(text("""
        INSERT INTO teacher
        (name, email, bio, class_duration_min, is_active, default_venue_id)
        VALUES
        (:name, :email, :bio, :duration, :is_active, :default_venue_id)
    """), {
        "name": name,
        "email": email,
        "bio": bio,
        "duration": duration,
        "is_active": is_active,
        "default_venue_id": default_venue_id
    })
    db.session.commit()

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
        ORDER BY ta.start_at ASC
        LIMIT 2000
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
    start_s = request.form.get("start_at")
    end_s = request.form.get("end_at")
    if not start_s or not end_s:
        flash("Start and end required.", "danger")
        return redirect(url_for("admin.teacher_availability", teacher_id=teacher_id))

    window_start = datetime.fromisoformat(start_s)
    window_end = datetime.fromisoformat(end_s)
    if window_end <= window_start:
        flash("End must be after start.", "danger")
        return redirect(url_for("admin.teacher_availability", teacher_id=teacher_id))

    venue_id = request.form.get("venue_id")
    venue_id = int(venue_id) if venue_id else None

    t = db.session.execute(text("""
        SELECT class_duration_min
        FROM teacher
        WHERE id = :id
    """), {"id": teacher_id}).mappings().first()

    duration = int((t["class_duration_min"] if t else 45) or 45)
    duration = max(15, min(duration, 240))
    step = timedelta(minutes=duration)

    created = 0
    cur = window_start

    try:
        with db.session.begin():
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

        flash(f"Created {created} slot(s) of {duration} minutes.", "success")
    except Exception:
        db.session.rollback()
        flash("Could not create slots (some may already exist).", "danger")

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

    with db.session.begin():
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
