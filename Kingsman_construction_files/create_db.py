# Create tables using raw SQL (no ORM)
from app import create_app
from db import ensure_schema

app = create_app()
with app.app_context():
    ensure_schema()
    print("✅ Schema ensured with raw SQL (IF NOT EXISTS).")
