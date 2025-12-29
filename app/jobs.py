# app/jobs.py
from datetime import date
from sqlalchemy import text
from .extensions import db
from .routes.admin import availability_auto_create


def scheduling():
    print("Scheduler Start . . . . .")
    rows = db.session.execute(
        text("SELECT id FROM teacher WHERE is_active = 1")
    ).mappings().all()

    for r in rows:
        availability_auto_create(r["id"])  # or availability_auto_create(r["id"])

    print("Scheduler End . . . . .")