# portal.py
from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from sqlalchemy import select
from models import db, Job

portal_bp = Blueprint("portal", __name__, url_prefix="/portal")

@portal_bp.route("/")
@login_required
def dashboard():
    if current_user.role == "customer":
        jobs = db.session.scalars(select(Job).where(Job.customer_user_id==current_user.id).order_by(Job.created_at.desc())).all()
    elif current_user.role == "contractor":
        jobs = db.session.scalars(select(Job).where(Job.assigned_contractor_user_id==current_user.id).order_by(Job.created_at.desc())).all()
    else:  # admin
        jobs = db.session.scalars(select(Job).order_by(Job.created_at.desc())).all()
    return render_template("portal_dashboard.html", jobs=jobs)

@portal_bp.route("/jobs/<job_uid>")
@login_required
def job_detail(job_uid):
    job = db.session.scalar(select(Job).where(Job.job_uid==job_uid))
    if not job:
        abort(404)
    # Access control
    if current_user.role == "customer" and job.customer_user_id != current_user.id:
        abort(403)
    if current_user.role == "contractor" and job.assigned_contractor_user_id != current_user.id:
        abort(403)
    return render_template("portal_job_detail.html", job=job)
