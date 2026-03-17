from __future__ import annotations

from datetime import datetime
from pathlib import Path
from functools import wraps

from flask import Blueprint, current_app, jsonify, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import text
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from ..auth_user import AppUser, get_user_by_id
from ..emailer import send_email
from ..extensions import db

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


# ----------------------------
# Helpers
# ----------------------------
def _json_error(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


def _to_iso(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _row_to_dict(row):
    out = {}
    for k, v in row.items():
        out[k] = _to_iso(v)
    return out


def _parse_json():
    return request.get_json(silent=True) or {}


def _parse_iso_datetime(value: str):
    s = (value or "").strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1]
    if "T" in s and len(s) >= 6 and s[-6] in ["+", "-"] and s[-3] == ":":
        s = s[:-6]
    if "+" in s:
        s = s.split("+", 1)[0]
    return datetime.fromisoformat(s)


def _serializer():
    return URLSafeTimedSerializer(current_app.config.get("SECRET_KEY", "dev-secret-change-me"))


def _roles_for_user(user_id: int) -> list[str]:
    rows = db.session.execute(text("""
        SELECT role
        FROM user_role
        WHERE user_id = :uid AND is_active = 1
    """), {"uid": user_id}).mappings().all()
    allowed = {"student", "teacher", "admin"}
    return sorted({(r["role"] or "").strip().lower() for r in rows} & allowed)


def _require_role(role: str):
    def deco(view):
        @wraps(view)
        @login_required
        def wrapper(*args, **kwargs):
            roles = set(getattr(current_user, "role", []) or [])
            if role not in roles:
                return _json_error(f"{role} role required", 403)
            return view(*args, **kwargs)

        return wrapper

    return deco


# ----------------------------
# Health
# ----------------------------
@api_bp.get("/health")
def health():
    return jsonify({"ok": True, "service": "music-school-api", "version": "v1"})


# ----------------------------
# Auth
# ----------------------------
@api_bp.post("/auth/signup")
def auth_signup():
    data = _parse_json()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()

    if not email or not password or not first_name or not last_name:
        return _json_error("email, password, first_name and last_name are required", 422)

    exists = db.session.execute(text("SELECT id FROM user WHERE email = :email LIMIT 1"), {"email": email}).scalar()
    if exists:
        return _json_error("Email already registered", 409)

    db.session.execute(text("""
        INSERT INTO user
          (email, password_hash, first_name, last_name, phone,
           address_1, address_2, city, province, postal_code, country,
           assigned_class_id, created_at)
        VALUES
          (:email, :pw, :fn, :ln, :phone,
           :a1, :a2, :city, :province, :postal_code, :country,
           :assigned_class_id, NOW())
    """), {
        "email": email,
        "pw": generate_password_hash(password),
        "fn": first_name,
        "ln": last_name,
        "phone": (data.get("phone") or "").strip() or None,
        "a1": (data.get("address_1") or "").strip() or None,
        "a2": (data.get("address_2") or "").strip() or None,
        "city": (data.get("city") or "").strip() or None,
        "province": (data.get("province") or "").strip() or None,
        "postal_code": (data.get("postal_code") or "").strip() or None,
        "country": (data.get("country") or "").strip() or None,
        "assigned_class_id": int(data.get("assigned_class_id") or 11),
    })
    user_id = int(db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar())
    db.session.execute(text("INSERT INTO user_role (user_id, role, assigned_at) VALUES (:uid, 'student', NOW())"), {"uid": user_id})
    db.session.commit()

    user = get_user_by_id(user_id)
    login_user(user)
    session["active_role"] = "student"
    return jsonify({"ok": True, "user": {"id": user.id, "email": user.email, "roles": user.role}}), 201


@api_bp.post("/auth/login")
def auth_login():
    data = _parse_json()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return _json_error("email and password are required", 422)

    row = db.session.execute(text("""
        SELECT id, email, password_hash, first_name, last_name, phone, available_credits
        FROM user
        WHERE email = :email
        LIMIT 1
    """), {"email": email}).mappings().first()

    if not row or not check_password_hash(row["password_hash"], password):
        return _json_error("Invalid email or password", 401)

    roles = _roles_for_user(int(row["id"]))
    if not roles:
        return _json_error("No active roles assigned", 403)

    session.pop("active_role", None)
    if len(roles) == 1:
        session["active_role"] = roles[0]

    u = AppUser(
        id=int(row["id"]),
        email=row["email"],
        role=roles,
        first_name=row["first_name"],
        last_name=row["last_name"],
        phone=row["phone"],
        available_credits=int(row["available_credits"] or 0),
    )
    login_user(u)

    return jsonify({
        "ok": True,
        "user": {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "roles": u.role,
            "active_role": session.get("active_role"),
            "available_credits": u.available_credits,
        },
    })


@api_bp.post("/auth/logout")
@login_required
def auth_logout():
    logout_user()
    session.pop("active_role", None)
    return jsonify({"ok": True})


@api_bp.get("/auth/me")
@login_required
def auth_me():
    return jsonify({
        "ok": True,
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "roles": current_user.role,
            "active_role": session.get("active_role"),
            "available_credits": int(getattr(current_user, "available_credits", 0) or 0),
        },
    })


@api_bp.post("/auth/select-role")
@login_required
def auth_select_role():
    data = _parse_json()
    role = (data.get("role") or "").strip().lower()
    roles = set(getattr(current_user, "role", []) or [])
    if role not in roles:
        return _json_error("Invalid role", 422)
    session["active_role"] = role
    return jsonify({"ok": True, "active_role": role})


# ----------------------------
# Student APIs
# ----------------------------
@api_bp.get("/student/availability")
@_require_role("student")
def student_availability():
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return jsonify({"ok": True, "items": []})

    start_dt = _parse_iso_datetime(start)
    end_dt = _parse_iso_datetime(end)
    if not start_dt or not end_dt:
        return _json_error("start and end must be ISO datetime", 422)

    rows = db.session.execute(text("""
        SELECT
          ta.id,
          ta.start_at,
          ta.end_at,
          ta.teacher_id,
          CONCAT(t.first_name, ' ', t.last_name) AS teacher_name,
          COALESCE(ta.venue_id, t.default_venue_id) AS venue_id,
          v.name AS venue_name
        FROM teacher_availability ta
        JOIN teacher t ON t.id = ta.teacher_id
        JOIN teacher_class_level tcl
          ON tcl.teacher_id = t.id
         AND tcl.class_level_id = (SELECT assigned_class_id FROM user WHERE id = :user_id)
         AND tcl.is_active = 1
        LEFT JOIN venue v ON v.id = COALESCE(ta.venue_id, t.default_venue_id)
        WHERE t.is_active = 1
          AND ta.teacher_id <> :user_id
          AND ta.is_booked = 0
          AND ta.start_at < :end_dt
          AND ta.end_at > :start_dt
          AND ta.start_at > (SELECT CURRENT_TIMESTAMP() - INTERVAL 5 HOUR)
        ORDER BY ta.start_at ASC
    """), {"start_dt": start_dt, "end_dt": end_dt, "user_id": current_user.id}).mappings().all()

    return jsonify({"ok": True, "items": [_row_to_dict(r) for r in rows]})


@api_bp.get("/student/availability/summary")
@_require_role("student")
def student_availability_summary():
    start = request.args.get("start")
    end = request.args.get("end")
    start_dt = _parse_iso_datetime(start)
    end_dt = _parse_iso_datetime(end)
    if not start_dt or not end_dt:
        return _json_error("start and end must be ISO datetime", 422)

    rows = db.session.execute(text("""
        SELECT
          DATE(ta.start_at) AS date,
          COUNT(*) AS total_slots,
          SUM(CASE WHEN ta.is_booked = 0 THEN 1 ELSE 0 END) AS available_slots
        FROM teacher_availability ta
        JOIN teacher t ON t.id = ta.teacher_id
        JOIN teacher_class_level tcl
          ON tcl.teacher_id = t.id
         AND tcl.class_level_id = (SELECT assigned_class_id FROM user WHERE id = :user_id)
         AND tcl.is_active = 1
        WHERE t.is_active = 1
          AND ta.teacher_id <> :user_id
          AND ta.is_booked = 0
          AND ta.start_at < :end_dt
          AND ta.end_at > :start_dt
          AND ta.start_at > (SELECT CURRENT_TIMESTAMP() - INTERVAL 5 HOUR)
        GROUP BY DATE(ta.start_at)
        ORDER BY DATE(ta.start_at)
    """), {"start_dt": start_dt, "end_dt": end_dt, "user_id": current_user.id}).mappings().all()
    return jsonify({"ok": True, "items": [_row_to_dict(r) for r in rows]})


@api_bp.post("/student/bookings")
@_require_role("student")
def student_create_booking():
    data = _parse_json()
    availability_id = int(data.get("availability_id") or 0)
    if not availability_id:
        return _json_error("availability_id is required", 422)

    try:
        updated = db.session.execute(text("""
            UPDATE teacher_availability ta
            JOIN teacher t ON t.id = ta.teacher_id
            JOIN teacher_class_level tcl
              ON tcl.teacher_id = t.id
             AND tcl.class_level_id = (SELECT assigned_class_id FROM user WHERE id = :user_id)
             AND tcl.is_active = 1
            SET ta.is_booked = 1
            WHERE ta.id = :aid
              AND ta.is_booked = 0
              AND t.is_active = 1
              AND ta.teacher_id <> :user_id
        """), {"aid": availability_id, "user_id": current_user.id}).rowcount

        if updated != 1:
            db.session.rollback()
            return _json_error("Slot is no longer available", 409)

        slot = db.session.execute(text("""
            SELECT ta.id, ta.teacher_id, ta.start_at, ta.end_at,
                   COALESCE(ta.venue_id, t.default_venue_id) AS venue_id,
                   t.email AS teacher_email,
                   u.assigned_class_id,
                   u.first_name,
                   u.last_name,
                   u.email AS student_email,
                   u.phone AS student_phone
            FROM teacher_availability ta
            JOIN teacher t ON t.id = ta.teacher_id
            JOIN user u ON u.id = :user_id
            WHERE ta.id = :aid
            LIMIT 1
        """), {"aid": availability_id, "user_id": current_user.id}).mappings().first()
        if not slot:
            db.session.rollback()
            return _json_error("Invalid slot", 404)

        db.session.execute(text("""
            INSERT INTO booking
              (teacher_id, availability_id, user_id,
               student_name, student_email, student_phone,
               class_level_id, venue_id, status, created_at)
            VALUES
              (:teacher_id, :availability_id, :user_id,
               :student_name, :student_email, :student_phone,
               :class_level_id, :venue_id, 'BOOKED', NOW())
        """), {
            "teacher_id": slot["teacher_id"],
            "availability_id": slot["id"],
            "user_id": current_user.id,
            "student_name": f"{slot.get('first_name') or ''} {slot.get('last_name') or ''}".strip() or current_user.full_name,
            "student_email": slot["student_email"],
            "student_phone": slot["student_phone"],
            "class_level_id": slot["assigned_class_id"],
            "venue_id": slot["venue_id"],
        })

        booking_id = int(db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar())
        db.session.commit()
        return jsonify({"ok": True, "booking_id": booking_id}), 201
    except Exception:
        db.session.rollback()
        raise


@api_bp.get("/student/bookings")
@_require_role("student")
def student_bookings():
    rows = db.session.execute(text("""
        SELECT
          b.id, b.status, b.created_at,
          CONCAT(t.first_name, ' ', t.last_name) AS teacher_name,
          ta.start_at, ta.end_at,
          cl.code AS class_code, cl.title AS class_title,
          v.name AS venue_name,
          b.google_meet_link
        FROM booking b
        JOIN teacher t ON t.id = b.teacher_id
        JOIN teacher_availability ta ON ta.id = b.availability_id
        LEFT JOIN user u ON u.id = b.user_id
        LEFT JOIN class_level cl ON cl.id = u.assigned_class_id
        LEFT JOIN venue v ON v.id = b.venue_id
        WHERE b.user_id = :uid
        ORDER BY b.created_at DESC
        LIMIT 500
    """), {"uid": current_user.id}).mappings().all()
    return jsonify({"ok": True, "items": [_row_to_dict(r) for r in rows]})


@api_bp.post("/contact-messages")
def contact_create():
    data = _parse_json()
    required = ["name", "email", "subject", "message"]
    if any(not (data.get(k) or "").strip() for k in required):
        return _json_error("name, email, subject, message are required", 422)

    db.session.execute(text("""
        INSERT INTO contact_message (name, email, phone, subject, message, created_at)
        VALUES (:name, :email, :phone, :subject, :message, NOW())
    """), {
        "name": data["name"].strip(),
        "email": data["email"].strip().lower(),
        "phone": (data.get("phone") or "").strip() or None,
        "subject": data["subject"].strip(),
        "message": data["message"].strip(),
    })
    db.session.commit()
    return jsonify({"ok": True}), 201


# ----------------------------
# Teacher APIs
# ----------------------------
@api_bp.get("/teacher/bookings")
@_require_role("teacher")
def teacher_bookings():
    rows = db.session.execute(text("""
        SELECT
          b.id, b.status, b.created_at, b.user_id,
          b.student_name, b.student_email, b.student_phone,
          b.class_level_id, cl.code AS class_code, cl.title AS class_title,
          b.venue_id, v.name AS venue_name,
          ta.start_at, ta.end_at,
          b.google_meet_link
        FROM booking b
        JOIN teacher_availability ta ON ta.id = b.availability_id
        LEFT JOIN class_level cl ON cl.id = b.class_level_id
        LEFT JOIN venue v ON v.id = b.venue_id
        WHERE b.teacher_id = :teacher_id
        ORDER BY b.created_at DESC
        LIMIT 500
    """), {"teacher_id": current_user.id}).mappings().all()
    return jsonify({"ok": True, "items": [_row_to_dict(r) for r in rows]})


@api_bp.get("/teacher/students")
@_require_role("teacher")
def teacher_students():
    rows = db.session.execute(text("""
        SELECT DISTINCT
          u.id,
          u.email,
          CONCAT(u.first_name, ' ', u.last_name) AS full_name,
          u.phone,
          u.created_at,
          cl.title AS class_title
        FROM user u
        JOIN user_role ur ON ur.user_id = u.id AND ur.role = 'student' AND ur.is_active = 1
        JOIN teacher_class_level tcl ON tcl.class_level_id = u.assigned_class_id
          AND tcl.teacher_id = :teacher_id
          AND tcl.is_active = 1
        LEFT JOIN class_level cl ON cl.id = u.assigned_class_id
        ORDER BY u.created_at DESC
        LIMIT 500
    """), {"teacher_id": current_user.id}).mappings().all()
    return jsonify({"ok": True, "items": [_row_to_dict(r) for r in rows]})


@api_bp.patch("/teacher/bookings/<int:booking_id>/status")
@_require_role("teacher")
def teacher_update_booking_status(booking_id: int):
    data = _parse_json()
    status = (data.get("status") or "").strip().upper()
    if status not in {"PRESENT", "ABSENT", "CANCELLED", "BOOKED"}:
        return _json_error("Invalid status", 422)

    result = db.session.execute(text("""
        UPDATE booking
        SET status = :status
        WHERE id = :bid AND teacher_id = :teacher_id
    """), {"status": status, "bid": booking_id, "teacher_id": current_user.id})
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Booking not found", 404)
    return jsonify({"ok": True})


# ----------------------------
# Admin APIs
# ----------------------------
@api_bp.get("/admin/messages")
@_require_role("admin")
def admin_messages():
    email = (request.args.get("email") or "").strip().lower()
    rows = db.session.execute(text("""
        SELECT id, name, email, phone, subject, message,
               reply_subject, reply_body, created_at, replied_at
        FROM contact_message
        WHERE (:email = '' OR email = :email)
        ORDER BY created_at DESC, id DESC
        LIMIT 1000
    """), {"email": email}).mappings().all()
    return jsonify({"ok": True, "items": [_row_to_dict(r) for r in rows]})


@api_bp.patch("/admin/messages/<int:message_id>/reply")
@_require_role("admin")
def admin_reply_message(message_id: int):
    data = _parse_json()
    reply_subject = (data.get("reply_subject") or "").strip() or None
    reply_body = (data.get("reply_body") or "").strip()
    if not reply_body:
        return _json_error("reply_body is required", 422)

    result = db.session.execute(text("""
        UPDATE contact_message
        SET reply_subject = :reply_subject,
            reply_body = :reply_body,
            replied_at = NOW()
        WHERE id = :id
    """), {"reply_subject": reply_subject, "reply_body": reply_body, "id": message_id})
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Message not found", 404)
    return jsonify({"ok": True})


@api_bp.get("/admin/teachers")
@_require_role("admin")
def admin_teachers():
    rows = db.session.execute(text("""
        SELECT t.id, t.first_name, t.last_name, t.email, t.bio,
               t.is_active, t.class_duration_min, t.default_venue_id,
               t.shift_start_time, t.shift_end_time, t.break_start_time, t.break_end_time,
               v.name AS default_venue_name
        FROM teacher t
        LEFT JOIN venue v ON v.id = t.default_venue_id
        ORDER BY t.first_name, t.last_name
    """), {}).mappings().all()
    return jsonify({"ok": True, "items": [_row_to_dict(r) for r in rows]})


@api_bp.post("/admin/teachers")
@_require_role("admin")
def admin_create_teacher():
    data = _parse_json()
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    if not first_name or not last_name:
        return _json_error("first_name and last_name are required", 422)

    db.session.execute(text("""
        INSERT INTO teacher
          (first_name, last_name, email, bio, class_duration_min,
           is_active, default_venue_id, shift_start_time, shift_end_time,
           break_start_time, break_end_time)
        VALUES
          (:first_name, :last_name, :email, :bio, :duration,
           :is_active, :default_venue_id, :shift_start_time, :shift_end_time,
           :break_start_time, :break_end_time)
    """), {
        "first_name": first_name,
        "last_name": last_name,
        "email": email or None,
        "bio": (data.get("bio") or "").strip() or None,
        "duration": int(data.get("class_duration_min") or 45),
        "is_active": 1 if data.get("is_active", True) else 0,
        "default_venue_id": data.get("default_venue_id"),
        "shift_start_time": data.get("shift_start_time"),
        "shift_end_time": data.get("shift_end_time"),
        "break_start_time": data.get("break_start_time"),
        "break_end_time": data.get("break_end_time"),
    })
    teacher_id = int(db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar())
    db.session.commit()
    return jsonify({"ok": True, "teacher_id": teacher_id}), 201


@api_bp.patch("/admin/teachers/<int:teacher_id>")
@_require_role("admin")
def admin_update_teacher(teacher_id: int):
    data = _parse_json()
    result = db.session.execute(text("""
        UPDATE teacher
        SET first_name = COALESCE(:first_name, first_name),
            last_name = COALESCE(:last_name, last_name),
            email = COALESCE(:email, email),
            bio = COALESCE(:bio, bio),
            class_duration_min = COALESCE(:duration, class_duration_min),
            is_active = COALESCE(:is_active, is_active),
            default_venue_id = COALESCE(:default_venue_id, default_venue_id),
            shift_start_time = COALESCE(:shift_start_time, shift_start_time),
            shift_end_time = COALESCE(:shift_end_time, shift_end_time),
            break_start_time = COALESCE(:break_start_time, break_start_time),
            break_end_time = COALESCE(:break_end_time, break_end_time)
        WHERE id = :id
    """), {
        "id": teacher_id,
        "first_name": data.get("first_name"),
        "last_name": data.get("last_name"),
        "email": data.get("email"),
        "bio": data.get("bio"),
        "duration": data.get("class_duration_min"),
        "is_active": data.get("is_active"),
        "default_venue_id": data.get("default_venue_id"),
        "shift_start_time": data.get("shift_start_time"),
        "shift_end_time": data.get("shift_end_time"),
        "break_start_time": data.get("break_start_time"),
        "break_end_time": data.get("break_end_time"),
    })
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Teacher not found", 404)
    return jsonify({"ok": True})


@api_bp.get("/admin/venues")
@_require_role("admin")
def admin_venues():
    rows = db.session.execute(text("SELECT id, name, address, notes, is_active FROM venue ORDER BY name")).mappings().all()
    return jsonify({"ok": True, "items": [_row_to_dict(r) for r in rows]})


@api_bp.post("/admin/venues")
@_require_role("admin")
def admin_create_venue():
    data = _parse_json()
    name = (data.get("name") or "").strip()
    if not name:
        return _json_error("name is required", 422)
    db.session.execute(text("""
        INSERT INTO venue (name, address, notes, is_active)
        VALUES (:name, :address, :notes, :is_active)
    """), {
        "name": name,
        "address": (data.get("address") or "").strip() or None,
        "notes": (data.get("notes") or "").strip() or None,
        "is_active": 1 if data.get("is_active", True) else 0,
    })
    venue_id = int(db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar())
    db.session.commit()
    return jsonify({"ok": True, "venue_id": venue_id}), 201


@api_bp.patch("/admin/venues/<int:venue_id>")
@_require_role("admin")
def admin_update_venue(venue_id: int):
    data = _parse_json()
    result = db.session.execute(text("""
        UPDATE venue
        SET name = COALESCE(:name, name),
            address = COALESCE(:address, address),
            notes = COALESCE(:notes, notes),
            is_active = COALESCE(:is_active, is_active)
        WHERE id = :id
    """), {
        "id": venue_id,
        "name": data.get("name"),
        "address": data.get("address"),
        "notes": data.get("notes"),
        "is_active": data.get("is_active"),
    })
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Venue not found", 404)
    return jsonify({"ok": True})


@api_bp.get("/admin/syllabus")
@_require_role("admin")
def admin_syllabus():
    rows = db.session.execute(text("""
        SELECT id, class_level_id, unit_no, topic, details, resource_link, created_at
        FROM syllabus_item
        ORDER BY class_level_id, unit_no, id
    """)).mappings().all()
    return jsonify({"ok": True, "items": [_row_to_dict(r) for r in rows]})


@api_bp.post("/admin/syllabus")
@_require_role("admin")
def admin_create_syllabus_item():
    data = _parse_json()
    if not data.get("class_level_id") or not (data.get("topic") or "").strip():
        return _json_error("class_level_id and topic are required", 422)
    db.session.execute(text("""
        INSERT INTO syllabus_item (class_level_id, unit_no, topic, details, resource_link, created_at)
        VALUES (:class_level_id, :unit_no, :topic, :details, :resource_link, NOW())
    """), {
        "class_level_id": data.get("class_level_id"),
        "unit_no": data.get("unit_no"),
        "topic": data.get("topic"),
        "details": data.get("details"),
        "resource_link": data.get("resource_link"),
    })
    item_id = int(db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar())
    db.session.commit()
    return jsonify({"ok": True, "item_id": item_id}), 201


@api_bp.delete("/admin/syllabus/<int:item_id>")
@_require_role("admin")
def admin_delete_syllabus_item(item_id: int):
    result = db.session.execute(text("DELETE FROM syllabus_item WHERE id = :id"), {"id": item_id})
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Syllabus item not found", 404)
    return jsonify({"ok": True})


@api_bp.get("/admin/bookings")
@_require_role("admin")
def admin_bookings():
    rows = db.session.execute(text("""
        SELECT
          b.id, b.user_id, b.teacher_id, b.status, b.created_at,
          b.student_name, b.student_email, b.student_phone,
          b.class_level_id, cl.code AS class_code, cl.title AS class_title,
          b.venue_id, v.name AS venue_name,
          ta.start_at, ta.end_at, b.google_meet_link
        FROM booking b
        JOIN teacher_availability ta ON ta.id = b.availability_id
        LEFT JOIN class_level cl ON cl.id = b.class_level_id
        LEFT JOIN venue v ON v.id = b.venue_id
        ORDER BY b.created_at DESC
        LIMIT 1000
    """)).mappings().all()
    return jsonify({"ok": True, "items": [_row_to_dict(r) for r in rows]})


@api_bp.patch("/admin/bookings/<int:booking_id>")
@_require_role("admin")
def admin_update_booking(booking_id: int):
    data = _parse_json()
    result = db.session.execute(text("""
        UPDATE booking
        SET status = COALESCE(:status, status),
            class_level_id = COALESCE(:class_level_id, class_level_id),
            venue_id = COALESCE(:venue_id, venue_id)
        WHERE id = :id
    """), {
        "id": booking_id,
        "status": data.get("status"),
        "class_level_id": data.get("class_level_id"),
        "venue_id": data.get("venue_id"),
    })
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Booking not found", 404)
    return jsonify({"ok": True})


@api_bp.get("/admin/users")
@_require_role("admin")
def admin_users():
    rows = db.session.execute(text("""
        SELECT
          u.id, u.email, u.first_name, u.last_name, u.phone,
          u.assigned_class_id, u.available_credits, u.created_at,
          COALESCE(GROUP_CONCAT(ur.role ORDER BY ur.role SEPARATOR ','), '') AS roles
        FROM user u
        LEFT JOIN user_role ur ON ur.user_id = u.id AND ur.is_active = 1
        GROUP BY u.id
        ORDER BY u.created_at DESC
        LIMIT 2000
    """)).mappings().all()

    items = []
    for r in rows:
        d = _row_to_dict(r)
        d["roles"] = [x for x in (d.get("roles") or "").split(",") if x]
        items.append(d)

    return jsonify({"ok": True, "items": items})


@api_bp.post("/admin/users")
@_require_role("admin")
def admin_create_user():
    data = _parse_json()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    if not email or not password:
        return _json_error("email and password are required", 422)

    db.session.execute(text("""
        INSERT INTO user
          (email, password_hash, first_name, last_name, phone,
           assigned_class_id, available_credits, created_at)
        VALUES
          (:email, :pw, :first_name, :last_name, :phone,
           :assigned_class_id, :available_credits, NOW())
    """), {
        "email": email,
        "pw": generate_password_hash(password),
        "first_name": first_name or None,
        "last_name": last_name or None,
        "phone": (data.get("phone") or "").strip() or None,
        "assigned_class_id": data.get("assigned_class_id"),
        "available_credits": int(data.get("available_credits") or 0),
    })
    user_id = int(db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar())

    roles = data.get("roles") or ["student"]
    for role in roles:
        role_clean = (role or "").strip().lower()
        if role_clean in {"student", "teacher", "admin"}:
            db.session.execute(text("""
                INSERT INTO user_role (user_id, role, is_active, assigned_at)
                VALUES (:uid, :role, 1, NOW())
                ON DUPLICATE KEY UPDATE is_active = 1
            """), {"uid": user_id, "role": role_clean})
    db.session.commit()
    return jsonify({"ok": True, "user_id": user_id}), 201


@api_bp.patch("/admin/users/<int:user_id>")
@_require_role("admin")
def admin_update_user(user_id: int):
    data = _parse_json()
    result = db.session.execute(text("""
        UPDATE user
        SET first_name = COALESCE(:first_name, first_name),
            last_name = COALESCE(:last_name, last_name),
            phone = COALESCE(:phone, phone),
            assigned_class_id = COALESCE(:assigned_class_id, assigned_class_id),
            available_credits = COALESCE(:available_credits, available_credits)
        WHERE id = :id
    """), {
        "id": user_id,
        "first_name": data.get("first_name"),
        "last_name": data.get("last_name"),
        "phone": data.get("phone"),
        "assigned_class_id": data.get("assigned_class_id"),
        "available_credits": data.get("available_credits"),
    })
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("User not found", 404)
    return jsonify({"ok": True})


@api_bp.put("/admin/users/<int:user_id>/roles")
@_require_role("admin")
def admin_set_user_roles(user_id: int):
    data = _parse_json()
    roles = data.get("roles") or []
    roles = {(r or "").strip().lower() for r in roles}
    roles = roles & {"student", "teacher", "admin"}
    if not roles:
        return _json_error("At least one valid role is required", 422)

    db.session.execute(text("UPDATE user_role SET is_active = 0 WHERE user_id = :uid"), {"uid": user_id})
    for role in roles:
        db.session.execute(text("""
            INSERT INTO user_role (user_id, role, is_active, assigned_at)
            VALUES (:uid, :role, 1, NOW())
            ON DUPLICATE KEY UPDATE is_active = 1
        """), {"uid": user_id, "role": role})
    db.session.commit()
    return jsonify({"ok": True, "roles": sorted(list(roles))})


@api_bp.post("/admin/users/<int:user_id>/credits")
@_require_role("admin")
def admin_add_credits(user_id: int):
    data = _parse_json()
    credits = int(data.get("credits") or 0)
    if credits <= 0:
        return _json_error("credits must be > 0", 422)

    user_row = db.session.execute(text("SELECT available_credits FROM user WHERE id = :uid LIMIT 1"), {"uid": user_id}).mappings().first()
    if not user_row:
        return _json_error("User not found", 404)

    before = int(user_row["available_credits"] or 0)
    after = before + credits

    db.session.execute(text("UPDATE user SET available_credits = :after WHERE id = :uid"), {"after": after, "uid": user_id})

    db.session.execute(text("""
        INSERT INTO transactions
          (teacher_id, type_of_transaction, mode_of_payment,
           student_id, action_performer_user_id,
           balance_before_this_transaction, balance_after_this_transaction,
           amount_added, credits_added, total_available_credits, created_at)
        VALUES
          (0, 'credit', :mode,
           :student_id, :actor,
           :before, :after,
           :amount_added, :credits_added, :total_available_credits, NOW())
    """), {
        "mode": (data.get("mode_of_payment") or "online"),
        "student_id": user_id,
        "actor": current_user.id,
        "before": before,
        "after": after,
        "amount_added": data.get("amount_added"),
        "credits_added": credits,
        "total_available_credits": after,
    })

    db.session.commit()
    return jsonify({"ok": True, "before": before, "after": after})

# ----------------------------
# Auth: password reset flow
# ----------------------------
@api_bp.post("/auth/forgot-password")
def auth_forgot_password():
    data = _parse_json()
    email = (data.get("email") or "").strip().lower()
    if not email:
        return _json_error("email is required", 422)

    row = db.session.execute(text("SELECT id FROM user WHERE email = :email LIMIT 1"), {"email": email}).mappings().first()
    if row:
        token = _serializer().dumps({"uid": int(row["id"])}, salt="reset-password")
        reset_url = url_for("student.reset_password", token=token, _external=True)
        send_email(email, subject="Reset your password", body=reset_url, html=f"<p>Reset link: <a href='{reset_url}'>{reset_url}</a></p>")

    # Don't leak whether account exists
    return jsonify({"ok": True, "message": "If the email exists, a reset link has been sent."})


@api_bp.post("/auth/reset-password")
def auth_reset_password():
    data = _parse_json()
    token = (data.get("token") or "").strip()
    password = data.get("password") or ""
    if not token or not password:
        return _json_error("token and password are required", 422)

    try:
        payload = _serializer().loads(token, salt="reset-password", max_age=60 * 30)
        uid = int(payload["uid"])
    except SignatureExpired:
        return _json_error("Reset link expired", 400)
    except BadSignature:
        return _json_error("Invalid reset token", 400)

    result = db.session.execute(text("UPDATE user SET password_hash = :h WHERE id = :uid"), {
        "h": generate_password_hash(password),
        "uid": uid,
    })
    if result.rowcount != 1:
        db.session.rollback()
        return _json_error("User not found", 404)
    db.session.commit()
    return jsonify({"ok": True})


# ----------------------------
# Additional parity endpoints
# ----------------------------
@api_bp.get("/meta/programs")
def api_programs_meta():
    return jsonify({"ok": True, "programs_page": "/programs"})


@api_bp.get("/teacher/students/<int:user_id>")
@_require_role("teacher")
def teacher_student_detail(user_id: int):
    row = db.session.execute(text("""
        SELECT
          u.id, u.email, u.first_name, u.last_name, u.phone,
          u.address_1, u.address_2, u.city, u.province, u.postal_code, u.country,
          u.assigned_class_id, cl.title AS class_title
        FROM user u
        LEFT JOIN class_level cl ON cl.id = u.assigned_class_id
        WHERE u.id = :id
        LIMIT 1
    """), {"id": user_id}).mappings().first()
    if not row:
        return _json_error("Student not found", 404)
    return jsonify({"ok": True, "item": _row_to_dict(row)})


@api_bp.patch("/teacher/students/<int:user_id>")
@_require_role("teacher")
def teacher_student_update(user_id: int):
    data = _parse_json()
    result = db.session.execute(text("""
        UPDATE user
        SET first_name = COALESCE(:first_name, first_name),
            last_name = COALESCE(:last_name, last_name),
            phone = COALESCE(:phone, phone),
            address_1 = COALESCE(:address_1, address_1),
            address_2 = COALESCE(:address_2, address_2),
            city = COALESCE(:city, city),
            province = COALESCE(:province, province),
            postal_code = COALESCE(:postal_code, postal_code),
            country = COALESCE(:country, country),
            assigned_class_id = COALESCE(:assigned_class_id, assigned_class_id)
        WHERE id = :id
    """), {
        "id": user_id,
        "first_name": data.get("first_name"),
        "last_name": data.get("last_name"),
        "phone": data.get("phone"),
        "address_1": data.get("address_1"),
        "address_2": data.get("address_2"),
        "city": data.get("city"),
        "province": data.get("province"),
        "postal_code": data.get("postal_code"),
        "country": data.get("country"),
        "assigned_class_id": data.get("assigned_class_id"),
    })
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Student not found", 404)
    return jsonify({"ok": True})


@api_bp.get("/admin/students")
@_require_role("admin")
def admin_students():
    rows = db.session.execute(text("""
        SELECT u.id, u.email, u.first_name, u.last_name, u.phone, u.assigned_class_id, u.created_at
        FROM user u
        JOIN user_role ur ON ur.user_id = u.id AND ur.role = 'student' AND ur.is_active = 1
        ORDER BY u.created_at DESC
        LIMIT 2000
    """)).mappings().all()
    return jsonify({"ok": True, "items": [_row_to_dict(r) for r in rows]})


@api_bp.put("/admin/teachers/<int:teacher_id>/classes")
@_require_role("admin")
def admin_teacher_set_classes(teacher_id: int):
    data = _parse_json()
    class_level_ids = [int(x) for x in (data.get("class_level_ids") or []) if str(x).isdigit()]
    if not class_level_ids:
        return _json_error("class_level_ids is required", 422)

    db.session.execute(text("UPDATE teacher_class_level SET is_active = 0 WHERE teacher_id = :teacher_id"), {"teacher_id": teacher_id})
    now = datetime.utcnow()
    for class_level_id in class_level_ids:
        db.session.execute(text("""
            INSERT INTO teacher_class_level (teacher_id, class_level_id, is_active, assigned_at)
            VALUES (:teacher_id, :class_level_id, 1, :assigned_at)
            ON DUPLICATE KEY UPDATE is_active = 1, assigned_at = VALUES(assigned_at)
        """), {
            "teacher_id": teacher_id,
            "class_level_id": class_level_id,
            "assigned_at": now,
        })
    db.session.commit()
    return jsonify({"ok": True, "class_level_ids": class_level_ids})


@api_bp.post("/admin/teachers/<int:teacher_id>/toggle")
@_require_role("admin")
def admin_teacher_toggle(teacher_id: int):
    result = db.session.execute(text("""
        UPDATE teacher
        SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
        WHERE id = :id
    """), {"id": teacher_id})
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Teacher not found", 404)
    row = db.session.execute(text("SELECT is_active FROM teacher WHERE id = :id"), {"id": teacher_id}).mappings().first()
    return jsonify({"ok": True, "is_active": int(row["is_active"]) if row else None})


@api_bp.delete("/admin/teachers/<int:teacher_id>")
@_require_role("admin")
def admin_teacher_delete(teacher_id: int):
    result = db.session.execute(text("DELETE FROM teacher WHERE id = :id"), {"id": teacher_id})
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Teacher not found", 404)
    return jsonify({"ok": True})


@api_bp.get("/admin/teachers/<int:teacher_id>/availability")
@_require_role("admin")
def admin_teacher_availability(teacher_id: int):
    rows = db.session.execute(text("""
        SELECT id, teacher_id, start_at, end_at, venue_id, is_booked, created_at
        FROM teacher_availability
        WHERE teacher_id = :teacher_id
        ORDER BY start_at ASC
        LIMIT 5000
    """), {"teacher_id": teacher_id}).mappings().all()
    return jsonify({"ok": True, "items": [_row_to_dict(r) for r in rows]})


@api_bp.post("/admin/teachers/<int:teacher_id>/availability")
@_require_role("admin")
def admin_teacher_availability_create(teacher_id: int):
    data = _parse_json()
    start_at = _parse_iso_datetime(data.get("start_at") or "")
    end_at = _parse_iso_datetime(data.get("end_at") or "")
    if not start_at or not end_at or end_at <= start_at:
        return _json_error("Valid start_at and end_at are required", 422)

    db.session.execute(text("""
        INSERT INTO teacher_availability (teacher_id, start_at, end_at, venue_id, is_booked, created_at)
        VALUES (:teacher_id, :start_at, :end_at, :venue_id, 0, NOW())
    """), {
        "teacher_id": teacher_id,
        "start_at": start_at,
        "end_at": end_at,
        "venue_id": data.get("venue_id"),
    })
    slot_id = int(db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar())
    db.session.commit()
    return jsonify({"ok": True, "slot_id": slot_id}), 201


@api_bp.delete("/admin/teachers/<int:teacher_id>/availability/<int:slot_id>")
@_require_role("admin")
def admin_teacher_availability_delete(teacher_id: int, slot_id: int):
    result = db.session.execute(text("""
        DELETE FROM teacher_availability
        WHERE id = :slot_id AND teacher_id = :teacher_id
    """), {"slot_id": slot_id, "teacher_id": teacher_id})
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Availability slot not found", 404)
    return jsonify({"ok": True})


@api_bp.post("/admin/venues/<int:venue_id>/toggle")
@_require_role("admin")
def admin_venue_toggle(venue_id: int):
    result = db.session.execute(text("""
        UPDATE venue
        SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
        WHERE id = :id
    """), {"id": venue_id})
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Venue not found", 404)
    row = db.session.execute(text("SELECT is_active FROM venue WHERE id = :id"), {"id": venue_id}).mappings().first()
    return jsonify({"ok": True, "is_active": int(row["is_active"]) if row else None})


@api_bp.delete("/admin/venues/<int:venue_id>")
@_require_role("admin")
def admin_venue_delete(venue_id: int):
    result = db.session.execute(text("DELETE FROM venue WHERE id = :id"), {"id": venue_id})
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Venue not found", 404)
    return jsonify({"ok": True})


@api_bp.post("/admin/bookings/<int:booking_id>/cancel")
@_require_role("admin")
def admin_booking_cancel(booking_id: int):
    result = db.session.execute(text("UPDATE booking SET status = 'CANCELLED' WHERE id = :id"), {"id": booking_id})
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Booking not found", 404)
    return jsonify({"ok": True})


@api_bp.post("/admin/bookings/<int:booking_id>/present")
@_require_role("admin")
def admin_booking_present(booking_id: int):
    result = db.session.execute(text("UPDATE booking SET status = 'PRESENT' WHERE id = :id"), {"id": booking_id})
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Booking not found", 404)
    return jsonify({"ok": True})


@api_bp.post("/admin/bookings/<int:booking_id>/absent")
@_require_role("admin")
def admin_booking_absent(booking_id: int):
    result = db.session.execute(text("UPDATE booking SET status = 'ABSENT' WHERE id = :id"), {"id": booking_id})
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Booking not found", 404)
    return jsonify({"ok": True})


@api_bp.post("/admin/bookings/<int:booking_id>/set-class")
@_require_role("admin")
def admin_booking_set_class(booking_id: int):
    data = _parse_json()
    class_level_id = data.get("class_level_id")
    result = db.session.execute(text("UPDATE booking SET class_level_id = :class_level_id WHERE id = :id"), {
        "class_level_id": class_level_id,
        "id": booking_id,
    })
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Booking not found", 404)
    return jsonify({"ok": True})


@api_bp.post("/teacher/bookings/<int:booking_id>/present")
@_require_role("teacher")
def teacher_booking_present(booking_id: int):
    result = db.session.execute(text("UPDATE booking SET status = 'PRESENT' WHERE id = :id AND teacher_id = :teacher_id"), {
        "id": booking_id,
        "teacher_id": current_user.id,
    })
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Booking not found", 404)
    return jsonify({"ok": True})


@api_bp.post("/teacher/bookings/<int:booking_id>/absent")
@_require_role("teacher")
def teacher_booking_absent(booking_id: int):
    result = db.session.execute(text("UPDATE booking SET status = 'ABSENT' WHERE id = :id AND teacher_id = :teacher_id"), {
        "id": booking_id,
        "teacher_id": current_user.id,
    })
    db.session.commit()
    if result.rowcount != 1:
        return _json_error("Booking not found", 404)
    return jsonify({"ok": True})

def _certificates_base_dir() -> Path:
    base = Path(current_app.root_path).parent / "instance" / "certificates"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _student_certificate_dir(student_id: int) -> Path:
    path = _certificates_base_dir() / str(student_id)
    path.mkdir(parents=True, exist_ok=True)
    return path




def _normalize_exam_questions(questions_raw):
    if not isinstance(questions_raw, list):
        return None

    normalized = []
    for idx, q in enumerate(questions_raw, start=1):
        if not isinstance(q, dict):
            return None

        prompt = (q.get("prompt") or "").strip()
        options = q.get("options") or []
        question_type = (q.get("type") or "single_choice").strip().lower()

        if not prompt or not isinstance(options, list) or len(options) < 2:
            return None

        clean_options = [str(opt).strip() for opt in options if str(opt).strip()]
        if len(clean_options) < 2:
            return None

        normalized.append({
            "id": int(q.get("id") or idx),
            "type": question_type,
            "prompt": prompt,
            "options": clean_options,
            "required": bool(q.get("required", True)),
        })

    return normalized if normalized else None


@api_bp.get("/admin/teacher-hiring-exam")
@_require_role("admin")
def admin_teacher_hiring_exam_get():
    row = db.session.execute(text("""
        SELECT id, title, description, instructions, duration_min, questions_json, is_active, created_at, updated_at
        FROM teacher_hiring_exam
        WHERE is_active = 1
        ORDER BY id DESC
        LIMIT 1
    """)).mappings().first()

    if not row:
        return jsonify({"ok": True, "exam": None})

    return jsonify({
        "ok": True,
        "exam": {
            "id": int(row["id"]),
            "title": row["title"],
            "description": row["description"],
            "instructions": row["instructions"],
            "duration_min": int(row["duration_min"] or 45),
            "questions": row["questions_json"] or [],
            "is_active": bool(row["is_active"]),
            "created_at": _to_iso(row["created_at"]),
            "updated_at": _to_iso(row["updated_at"]),
        },
    })


@api_bp.post("/admin/teacher-hiring-exam")
@_require_role("admin")
def admin_teacher_hiring_exam_upsert():
    data = _parse_json()
    title = (data.get("title") or "Teacher Hiring Assessment").strip()
    description = (data.get("description") or "").strip()
    instructions = (data.get("instructions") or "").strip()
    raw_duration_min = data.get("duration_min")
    try:
        duration_min = int(raw_duration_min or 45)
    except (TypeError, ValueError):
        return _json_error("duration_min must be a number", 422)
    questions = _normalize_exam_questions(data.get("questions"))

    if not questions:
        return _json_error("questions must be a list with at least one valid question", 422)

    if duration_min < 5 or duration_min > 300:
        return _json_error("duration_min must be between 5 and 300", 422)

    db.session.execute(text("UPDATE teacher_hiring_exam SET is_active = 0 WHERE is_active = 1"))

    db.session.execute(text("""
        INSERT INTO teacher_hiring_exam
          (title, description, instructions, duration_min, questions_json, is_active, created_by_user_id, created_at, updated_at)
        VALUES
          (:title, :description, :instructions, :duration_min, :questions_json, 1, :created_by_user_id, NOW(), NOW())
    """), {
        "title": title,
        "description": description or None,
        "instructions": instructions or None,
        "duration_min": duration_min,
        "questions_json": questions,
        "created_by_user_id": current_user.id,
    })
    exam_id = int(db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar())
    db.session.commit()

    return jsonify({"ok": True, "exam_id": exam_id}), 201


@api_bp.get("/public/teacher-hiring-exam")
def public_teacher_hiring_exam_get():
    row = db.session.execute(text("""
        SELECT id, title, description, instructions, duration_min, questions_json
        FROM teacher_hiring_exam
        WHERE is_active = 1
        ORDER BY id DESC
        LIMIT 1
    """)).mappings().first()

    if not row:
        return _json_error("No active teacher hiring exam found", 404)

    return jsonify({
        "ok": True,
        "exam": {
            "id": int(row["id"]),
            "title": row["title"],
            "description": row["description"],
            "instructions": row["instructions"],
            "duration_min": int(row["duration_min"] or 45),
            "questions": row["questions_json"] or [],
        },
    })


@api_bp.post("/public/teacher-hiring-exam/attempts")
def public_teacher_hiring_exam_submit():
    data = _parse_json()

    try:
        exam_id = int(data.get("exam_id") or 0)
    except (TypeError, ValueError):
        return _json_error("exam_id must be a number", 422)

    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip()
    answers = data.get("answers") or {}

    if not exam_id or not full_name or not email:
        return _json_error("exam_id, full_name and email are required", 422)

    if "@" not in email or "." not in email.split("@")[-1]:
        return _json_error("email must be valid", 422)

    if not isinstance(answers, dict) or not answers:
        return _json_error("answers must be a non-empty object", 422)

    exam = db.session.execute(text("""
        SELECT id
        FROM teacher_hiring_exam
        WHERE id = :exam_id AND is_active = 1
        LIMIT 1
    """), {"exam_id": exam_id}).mappings().first()

    if not exam:
        return _json_error("Exam is not active or does not exist", 404)

    linked_user_id = db.session.execute(text("""
        SELECT id
        FROM user
        WHERE email = :email
        LIMIT 1
    """), {"email": email}).scalar()

    db.session.execute(text("""
        INSERT INTO teacher_hiring_exam_attempt
          (exam_id, full_name, email, phone, answers_json, existing_user_id, submitted_at, status)
        VALUES
          (:exam_id, :full_name, :email, :phone, :answers_json, :existing_user_id, NOW(), 'SUBMITTED')
    """), {
        "exam_id": exam_id,
        "full_name": full_name,
        "email": email,
        "phone": phone or None,
        "answers_json": answers,
        "existing_user_id": int(linked_user_id) if linked_user_id else None,
    })
    attempt_id = int(db.session.execute(text("SELECT LAST_INSERT_ID()")).scalar())
    db.session.commit()

    return jsonify({
        "ok": True,
        "attempt_id": attempt_id,
        "linked_existing_user": bool(linked_user_id),
        "message": "Exam submitted successfully",
    }), 201

@api_bp.get("/teacher/students/<int:student_id>/certificates")
@_require_role("teacher")
def teacher_student_certificates(student_id: int):
    items = []
    for path in sorted(_student_certificate_dir(student_id).glob("*.pdf"), reverse=True):
        items.append({
            "name": path.name,
            "created_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
            "download_path": f"/teacher/certificate/{student_id}/files/{path.name}",
        })
    return jsonify({"ok": True, "items": items})


@api_bp.post("/teacher/students/<int:student_id>/certificates/email-latest")
@_require_role("teacher")
def teacher_student_certificate_email_latest(student_id: int):
    row = db.session.execute(text("SELECT email FROM user WHERE id = :id LIMIT 1"), {"id": student_id}).mappings().first()
    if not row or not row.get("email"):
        return _json_error("Student email not found", 404)

    files = sorted(_student_certificate_dir(student_id).glob("*.pdf"), reverse=True)
    if not files:
        return _json_error("No certificate found", 404)

    latest = files[0]
    link = f"/teacher/certificate/{student_id}/files/{latest.name}"
    send_email(row["email"], subject="Your certificate", body=f"Download: {link}", html=f"<p>Download: <a href='{link}'>{link}</a></p>")
    return jsonify({"ok": True, "file": latest.name})


@api_bp.post("/admin/teachers/<int:teacher_id>/mark-sick-today")
@_require_role("admin")
def admin_teacher_mark_sick_today(teacher_id: int):
    today = datetime.utcnow().date()
    db.session.execute(text("""
        UPDATE teacher_availability
        SET is_booked = 1
        WHERE teacher_id = :teacher_id
          AND DATE(start_at) = :today
          AND is_booked = 0
    """), {"teacher_id": teacher_id, "today": today})

    result = db.session.execute(text("""
        UPDATE booking b
        JOIN teacher_availability ta ON ta.id = b.availability_id
        SET b.status = 'CANCELLED'
        WHERE b.teacher_id = :teacher_id
          AND b.status = 'BOOKED'
          AND DATE(ta.start_at) = :today
    """), {"teacher_id": teacher_id, "today": today})
    db.session.commit()
    return jsonify({"ok": True, "cancelled_bookings": int(result.rowcount or 0)})
