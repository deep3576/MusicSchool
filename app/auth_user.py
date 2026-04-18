# app/auth_user.py
from dataclasses import dataclass
from flask_login import UserMixin
from sqlalchemy import text
from .extensions import db

@dataclass
class AppUser(UserMixin):
    id: int
    email: str
    role: list[str]   # active roles list
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    available_credits: int = 0

    @property
    def full_name(self) -> str:
        fn = (self.first_name or "").strip()
        ln = (self.last_name or "").strip()
        name = (fn + " " + ln).strip()
        return name or self.email

    @property
    def is_admin(self) -> bool:
        return "admin" in (self.role or [])

    @property
    def is_teacher(self) -> bool:
        return "teacher" in (self.role or [])

    @property
    def is_student(self) -> bool:
        return "student" in (self.role or [])


def get_user_by_id(user_id: int) -> AppUser | None:
    # ✅ user table WITHOUT role
    row = db.session.execute(text("""
        SELECT id, email, first_name, last_name, phone, available_credits
        FROM `user`
        WHERE id = :id
        LIMIT 1
    """), {"id": user_id}).mappings().first()

    if not row:
        return None

    # ✅ roles from user_role table (only active)
    roles = db.session.execute(text("""
        SELECT role
        FROM user_role
        WHERE user_id = :id AND is_active = 1
    """), {"id": user_id}).scalars().all()   # returns list[str]

    # roles loaded from user_role table
    return AppUser(
        id=int(row["id"]),
        email=row["email"],
        role=list(roles),   # ✅ list
        first_name=row["first_name"],
        last_name=row["last_name"],
        phone=row["phone"],
        available_credits=int(row["available_credits"] or 0),
    )


def register_user_loader(login_manager):
    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return get_user_by_id(int(user_id))
        except Exception:
            import logging
            logging.getLogger(__name__).exception("user_loader failed for user_id=%s", user_id)
            return None
