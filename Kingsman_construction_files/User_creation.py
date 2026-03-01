from sqlalchemy import create_engine, text
from config import Config

# pooled engine
engine = create_engine(
    Config.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    future=True,
)

def ensure_schema():
    User_content="insert into Users "
with app.app_context():
    u = User(email="harpreet@kingsmanrenovations.ca", password_hash=generate_password_hash("admin123") , role="admin")
    db.session.add(u)
    db.session.commit()
    print("User created:", u.email)