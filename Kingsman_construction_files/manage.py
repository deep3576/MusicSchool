from werkzeug.security import generate_password_hash
from app import create_app
from extensions import db
from models import User
import click

app = create_app()

@app.cli.command("create-admin")
@click.argument("email")
@click.argument("password")
@click.argument("first_name")
@click.argument("last_name")
def create_admin(email, password, first_name, last_name):
    """Create an admin user."""
    with app.app_context():
        if db.session.scalar(db.select(User).where(User.email==email)):
            click.echo("User already exists"); return
        u = User(role="admin", email=email, password_hash=generate_password_hash(password),
                 first_name=first_name, last_name=last_name, is_active=True)
        db.session.add(u); db.session.commit()
        click.echo(f"Created admin {email}")
