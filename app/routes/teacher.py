from __future__ import annotations
from collections import defaultdict
from datetime import datetime, date, time, timedelta, timezone
from pathlib import Path

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
    has_request_context,
    session,
    make_response,
    send_file,
)
from weasyprint import HTML

from ..security import admin_required, teacher_required
from flask_login import current_user, logout_user, login_required
from types import SimpleNamespace
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


def _certificates_base_dir() -> Path:
    cert_dir = Path(current_app.instance_path) / "certificates"
    cert_dir.mkdir(parents=True, exist_ok=True)
    return cert_dir


def _student_certificate_dir(student_id: int) -> Path:
    path = _certificates_base_dir() / str(student_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _certificate_public_link(student_id: int, filename: str) -> str:
    return url_for("teacher.download_certificate", student_id=student_id, filename=filename, _external=True)


@teacher_bp.get("/todaysClasses")
@login_required
def todaysClasses():
    print(current_user.id)
    bookings_rows = db.session.execute(text("""
        SELECT
          b.id,
          b.status,
          b.created_at,
          b.availability_id,
          b.teacher_id,
          concat(t.first_name,t.last_name) AS teacher_name,
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
        WHERE b.teacher_id = :teacher_id
        ORDER BY b.created_at DESC
        LIMIT 500
    """), {"teacher_id": current_user.id}).mappings().all()

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
    return render_template("teacher/todaysClasses.html", title="Today's Classes", todays_classes=bookings_list,
                           now=datetime.now())


@teacher_bp.get("/students")
@login_required
def students():
    rows = db.session.execute(text("""
        SELECT DISTINCT
          u.id,
          u.email,
          CONCAT(u.first_name,' ', u.last_name) AS full_name,
          u.phone,
          u.created_at,
          cl.title
        FROM user u
        JOIN user_role ur
          ON ur.user_id = u.id AND ur.role = 'student' AND ur.is_active = 1
        JOIN teacher_class_level tcl
          ON tcl.class_level_id = u.assigned_class_id
         AND tcl.teacher_id = :teacher_id
         AND tcl.is_active = 1
        LEFT JOIN class_level cl ON cl.id = u.assigned_class_id
        WHERE u.id <> :teacher_id
        ORDER BY u.created_at DESC
        LIMIT 500
    """), {'id': current_user.id}).mappings().all()

    items = []
    for r in rows:
        items.append(_ns({
            "id": r["id"],
            "email": r["email"],
            "full_name": r["full_name"],
            "phone": r["phone"],
            "created_at": r["created_at"],
            "assigned_class_id": r["title"]
        }))

    return render_template("teacher/students.html", title="Students", items=items)


@teacher_bp.route("/studentProfile/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def studentProfile(user_id: int):
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
          u.id,cl.title, u.email,
          u.first_name, u.last_name, u.phone,
          u.address_1, u.address_2, u.city, u.province, u.postal_code, u.country,
          u.assigned_class_id
        FROM `user` u
        left join class_level cl 
        on u.assigned_class_id = cl.id 
        WHERE u.id = :id
        LIMIT 1
    """), {"id": user_id}).mappings().first()

    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("teacher.students"))

    cert_files = []
    for path in sorted(_student_certificate_dir(user_id).glob("*.pdf"), reverse=True):
        cert_files.append(_ns({
            "name": path.name,
            "created_at": datetime.fromtimestamp(path.stat().st_mtime),
            "download_url": url_for("teacher.download_certificate", student_id=user_id, filename=path.name),
        }))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        roles = request.form.getlist("roles")
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

        dual_teacher_conflict = db.session.execute(text("""
            SELECT 1
            FROM user_role ur
            JOIN teacher_class_level tcl
              ON tcl.teacher_id = ur.user_id
             AND tcl.class_level_id = :class_id
             AND tcl.is_active = 1
            WHERE ur.user_id = :user_id
              AND ur.role = 'teacher'
              AND ur.is_active = 1
            LIMIT 1
        """), {"user_id": user_id, "class_id": assigned_class_id}).first() if assigned_class_id else None
        if dual_teacher_conflict:
            flash("This user is also a teacher for the selected class and cannot be assigned to the same class as a student.", "danger")
            return redirect(url_for("teacher.studentProfile", user_id=user_id))

        if not email:
            flash("Email is required.", "danger")
            return redirect(url_for("teacher.studentProfile", user_id=user_id))

        exists = db.session.execute(text("""
            SELECT id FROM `user`
            WHERE email = :email AND id <> :id
            LIMIT 1
        """), {"email": email, "id": user_id}).first()

        if exists:
            flash("That email is already used by another user.", "danger")
            return redirect(url_for("teacher.studentProfile", user_id=user_id))

        check1 = db.session.execute(text("""
            Select * from 
            teacher where id =:id and email=:email
                        """), {
            "email": email,
            "id": user_id,
        }).first()
        if check1:
            db.session.execute(text("""
                        Delete  from 
                        teacher where id =:id and email=:email
                                    """), {
                "email": email,
                "id": user_id,
            })
            db.session.commit()

        if 'teacher' in roles:
            db.session.execute(text("""
            INSERT
            INTO
            teacher(id, first_name,last_name, email, is_active)
            VALUES(:id,:first_name , :last_name, :email, 0)
                        """), {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "id": user_id,
            })

        try:
            db.session.execute(text("""
                UPDATE `user`
                SET email = :email,
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

            roles = [r.strip().lower() for r in request.form.getlist("roles")]
            allowed = {"admin", "student", "teacher"}
            roles = [r for r in roles if r in allowed]
            roles = list(dict.fromkeys(roles))

            if not roles:
                flash("Select at least one role.", "danger")
                return redirect(url_for("teacher.studentProfile", user_id=user_id))

            existing_rows = db.session.execute(text("""
                SELECT role, is_active
                FROM user_role
                WHERE user_id = :id
                ORDER BY role
            """), {"id": user_id}).mappings().all()

            existing = {row["role"]: int(row["is_active"]) for row in existing_rows}

            for r in roles:
                if r in existing:
                    db.session.execute(text("""
                        UPDATE user_role
                        SET is_active = 1
                        WHERE user_id = :id AND role = :role
                        LIMIT 1
                    """), {"id": user_id, "role": r})
                else:
                    db.session.execute(text("""
                        INSERT INTO user_role (user_id, role, is_active, assigned_at)
                        VALUES (:id, :role, 1, NOW())
                    """), {"id": user_id, "role": r})

            for r in existing.keys():
                if r not in roles:
                    db.session.execute(text("""
                        UPDATE user_role
                        SET is_active = 0
                        WHERE user_id = :id AND role = :role
                        LIMIT 1
                    """), {"id": user_id, "role": r})

            db.session.commit()
            flash("User updated successfully.", "success")
            return redirect(url_for("teacher.students"))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("[teacher.studentProfile] update failed")
            flash("Could not update user. Check logs.", "danger")
            return redirect(url_for("teacher.studentProfile", user_id=user_id))

    item = _ns({
        **user,
        "full_name": (f"{user['first_name'] or ''} {user['last_name'] or ''}".strip() or "—")
    })

    return render_template(
        "teacher/studentProfile.html",
        title="Student Profile",
        u=item,
        classes=classes,
        certificates=cert_files,
    )


@teacher_bp.get("/certificate/<int:student_id>/pdf")
def certificate_pdf(student_id):
    student = db.session.execute(text("""
            SELECT
              u.id,cl.title, u.email,
              concat(u.first_name, ' ', u.last_name) as name,
              u.assigned_class_id,cl.description
            FROM `user` u
            left join class_level cl
            on u.assigned_class_id = cl.id
            WHERE u.id = :id
            LIMIT 1"""), {'id': student_id}).first()

    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("teacher.students"))

    if student[4] == 11:
        level = 0
        next_class_id = 1
    else:
        level = student[4]
        next_class_id = int(student[4]) + 1
    try:
        db.session.execute(text("""
        UPDATE `user` Set assigned_class_id = :assigned_class_id
                    WHERE id = :id
                    LIMIT 1"""), {'id': student_id, 'assigned_class_id': next_class_id})
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("[admin.user_edit] update failed")
        flash("Could not update user. Check logs.", "danger")
        return redirect(url_for("teacher.studentProfile", user_id=student_id))
    data = {
        "certificate_id": f"TRS-{student_id:05d}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "issue_date": datetime.now(),
        "student_name": student[3],
        "course_name": student[5],
        "level_name": f"Level - {level}",
        "duration_text": "8 Weeks",
        "instructor_name": current_user.first_name + ' ' + current_user.last_name,
        "director_name": "Harjeet Singh",
    }

    html = render_template("certificates/certificate.html", **data)

    pdf_bytes = HTML(string=html, base_url=request.root_url).write_pdf()

    cert_filename = f"{data['certificate_id']}.pdf"
    cert_path = _student_certificate_dir(student_id) / cert_filename
    cert_path.write_bytes(pdf_bytes)

    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'inline; filename="{cert_filename}"'
    return resp


@teacher_bp.get("/certificate/<int:student_id>/files/<path:filename>")
@login_required
def download_certificate(student_id: int, filename: str):
    file_path = (_student_certificate_dir(student_id) / filename).resolve()
    student_dir = _student_certificate_dir(student_id).resolve()

    if student_dir not in file_path.parents:
        flash("Invalid certificate path.", "danger")
        return redirect(url_for("teacher.studentProfile", user_id=student_id))

    if not file_path.exists() or not file_path.is_file():
        flash("Certificate not found.", "warning")
        return redirect(url_for("teacher.studentProfile", user_id=student_id))

    return send_file(file_path, as_attachment=True, download_name=file_path.name)


@teacher_bp.post("/certificate/<int:student_id>/email-latest")
@login_required
def email_latest_certificate(student_id: int):
    student = db.session.execute(text("""
        SELECT id, email, concat(first_name, ' ', last_name) as full_name
        FROM `user`
        WHERE id = :id
        LIMIT 1
    """), {"id": student_id}).mappings().first()

    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("teacher.students"))

    cert_files = sorted(_student_certificate_dir(student_id).glob("*.pdf"), reverse=True)
    if not cert_files:
        flash("No saved certificate found for this student.", "warning")
        return redirect(url_for("teacher.studentProfile", user_id=student_id))

    latest = cert_files[0]
    download_link = _certificate_public_link(student_id, latest.name)

    subject = "Your Certificate is Ready"
    body = (
        f"Hello {student['full_name']},\n\n"
        f"Your certificate is attached.\n"
        f"You can also download it from this link: {download_link}\n\n"
        "Regards,\nMusic School"
    )
    html = f"""
    <p>Hello {student['full_name']},</p>
    <p>Your certificate is attached to this email.</p>
    <p>You can also download it using this secure link:</p>
    <p><a href=\"{download_link}\">Download Certificate</a></p>
    <p>Regards,<br>Music School</p>
    """

    send_email(student["email"], subject=subject, body=body, html=html, attachments=[str(latest)])
    flash("Certificate emailed to student.", "success")
    return redirect(url_for("teacher.studentProfile", user_id=student_id))


@teacher_bp.post("/todaysClasses/<int:booking_id>/absent")
@login_required
def booking_absent(booking_id):
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
