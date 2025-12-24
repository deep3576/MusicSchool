# app/auth_user.py
from dataclasses import dataclass
from flask_login import UserMixin
from sqlalchemy import text
from .extensions import db


@dataclass
class AppUser(UserMixin):
    id: int
    email: str
    role: str
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None

    @property
    def full_name(self) -> str:
        fn = (self.first_name or "").strip()
        ln = (self.last_name or "").strip()
        name = (fn + " " + ln).strip()
        return name or self.email

    @property
    def is_admin(self) -> bool:
        return (self.role or "").lower() == "admin"

    @property
    def is_customer(self) -> bool:
        return (self.role or "").lower() == "customer"


def get_user_by_id(user_id: int) -> AppUser | None:
    row = db.session.execute(text("""
        SELECT id, email, role, first_name, last_name, phone
        FROM `user`
        WHERE id = :id
        LIMIT 1
    """), {"id": user_id}).mappings().first()

    if not row:
        return None

    return AppUser(
        id=int(row["id"]),
        email=row["email"],
        role=row["role"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        phone=row["phone"],
    )


def register_user_loader(login_manager):
    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return get_user_by_id(int(user_id))
        except Exception:
            return None
