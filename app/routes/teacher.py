from __future__ import annotations
from collections import defaultdict
from datetime import datetime, date, time, timedelta, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, has_request_context, \
    session
from ..security import admin_required , teacher_required
from flask_login import current_user,logout_user, login_required
from types import SimpleNamespace
from flask import render_template, request, redirect, url_for, flash, current_app
from datetime import datetime
from sqlalchemy import text
from werkzeug.security import generate_password_hash
from ..extensions import db
from ..emailer import send_email

teacher_bp = Blueprint("teacher", __name__, url_prefix="/teacher")

def _ns(d: dict) -> SimpleNamespace:
    return SimpleNamespace(**d)

def _ensure_teacher_role():
    roles = current_user.role or []
    active_role = session.get("active_role")

    if active_role == "teacher":
        return None

    if "teacher" in roles and len(roles) == 1:
        session["active_role"] = "teacher"
        return None

    flash("Teacher access required.", "danger")
    return redirect(url_for("student.choose_role"))





@teacher_bp.get("/todaysClasses")
@login_required
def todaysClasses():
    bookings_rows = db.session.execute(text("""
        SELECT
          b.id,
          b.status,
          b.created_at,
          b.availability_id,
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
        where b.teacher_id =12
        ORDER BY b.created_at DESC
        LIMIT 500
    """)
                                       #,{":id": 12}
                                       ).mappings().all()

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
    print(bookings_list)

    guard = _ensure_teacher_role()
    if guard is not None:
        return guard
    return render_template("teacher/todaysClasses.html", title="Today's Classes", todays_classes=bookings_list,now=datetime.now() )




@teacher_bp.post("/todaysClasses/<int:booking_id>/absent")
@login_required
def booking_absent(booking_id):
    # Cancel booking and free slot
    row = db.session.execute(text("""
        SELECT availability_id
        FROM booking
        WHERE id = :id AND status = 'BOOKED'
    """), {"id": booking_id}).mappings().first()

    if not row:
        flash("Booking not active or not found.", "warning")
        return redirect(url_for("teacher.todaysClasses"))

    db.session.execute(text("""
            UPDATE booking
            SET status = 'NO SHOW'
            WHERE id = :id
        """), {"id": booking_id})

    db.session.execute(text("""
            UPDATE teacher_availability
            SET is_booked = 0
            WHERE id = :aid
        """), {"aid": row["availability_id"]})
    db.session.commit()
    flash("Booking cancelled and slot freed.", "success")
    return redirect(url_for("teacher.todaysClasses"))


@teacher_bp.post("/bookings/<int:booking_id>/present")
@login_required
def booking_present(booking_id):
    # Cancel booking and free slot
    row = db.session.execute(text("""
        SELECT availability_id
        FROM booking
        WHERE id = :id AND status = 'BOOKED'
    """), {"id": booking_id}).mappings().first()

    if not row:
        flash("Booking not active or not found.", "warning")
        return redirect(url_for("teacher.todaysClasses"))

    db.session.execute(text("""
            UPDATE booking
            SET status = 'PRESENT'
            WHERE id = :id
        """), {"id": booking_id})

    db.session.commit()
    flash("Student Marked as PRESENT for this booking.", "success")
    return redirect(url_for("teacher.todaysClasses"))

