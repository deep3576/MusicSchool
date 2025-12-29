from __future__ import annotations

from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(20), nullable=False, default="student", index=True)

    first_name = db.Column(db.String(80), nullable=True)
    last_name = db.Column(db.String(80), nullable=True)
    phone = db.Column(db.String(60), nullable=True)

    address_1 = db.Column(db.String(200), nullable=True)
    address_2 = db.Column(db.String(200), nullable=True)
    city = db.Column(db.String(120), nullable=True)
    province = db.Column(db.String(120), nullable=True)
    postal_code = db.Column(db.String(30), nullable=True)
    country = db.Column(db.String(80), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self) -> str:
        fn = (self.first_name or "").strip()
        ln = (self.last_name or "").strip()
        return (fn + " " + ln).strip() or self.email

    @property
    def is_admin(self) -> bool:
        return (self.role or "").lower() == "admin"


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


class ContactMessage(db.Model):
    __tablename__ = "contact_message"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(60), nullable=True)

    subject = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    reply_subject = db.Column(db.String(255), nullable=True)
    reply_body = db.Column(db.Text, nullable=True)
    replied_at = db.Column(db.DateTime, nullable=True)


class Venue(db.Model):
    __tablename__ = "venue"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Teacher(db.Model):
    __tablename__ = "teacher"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.Text, nullable=True)

    class_duration_min = db.Column(db.Integer, nullable=False, default=45)

    is_active = db.Column(db.Boolean, default=True, nullable=False)

    default_venue_id = db.Column(db.Integer, db.ForeignKey("venue.id"), nullable=True)
    default_venue = db.relationship("Venue", foreign_keys=[default_venue_id])


class TeacherAvailability(db.Model):
    __tablename__ = "teacher_availability"

    id = db.Column(db.Integer, primary_key=True)

    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False, index=True)
    teacher = db.relationship("Teacher")

    start_at = db.Column(db.DateTime, nullable=False, index=True)
    end_at = db.Column(db.DateTime, nullable=False, index=True)

    venue_id = db.Column(db.Integer, db.ForeignKey("venue.id"), nullable=True)
    venue = db.relationship("Venue")

    is_booked = db.Column(db.Boolean, default=False, nullable=False, index=True)


class ClassLevel(db.Model):
    __tablename__ = "class_level"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)   # 1M ... 10M
    title = db.Column(db.String(140), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class SyllabusItem(db.Model):
    __tablename__ = "syllabus_item"

    id = db.Column(db.Integer, primary_key=True)

    class_level_id = db.Column(db.Integer, db.ForeignKey("class_level.id"), nullable=False, index=True)
    class_level = db.relationship("ClassLevel")

    unit_no = db.Column(db.Integer, nullable=True)
    topic = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text, nullable=True)
    resource_link = db.Column(db.String(600), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Booking(db.Model):
    __tablename__ = "booking"

    id = db.Column(db.Integer, primary_key=True)

    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=False, index=True)
    availability_id = db.Column(db.Integer, db.ForeignKey("teacher_availability.id"), nullable=False, unique=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)

    student_name = db.Column(db.String(120), nullable=False)
    student_email = db.Column(db.String(255), nullable=False)
    student_phone = db.Column(db.String(60), nullable=True)

    class_level_id = db.Column(db.Integer, db.ForeignKey("class_level.id"), nullable=True)
    venue_id = db.Column(db.Integer, db.ForeignKey("venue.id"), nullable=True)

    status = db.Column(db.String(20), default="BOOKED", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships (optional; routes can use raw SQL)
    user = db.relationship("User")
    teacher = db.relationship("Teacher")
    availability = db.relationship("TeacherAvailability")
    class_level = db.relationship("ClassLevel")
    venue = db.relationship("Venue")
