import os, secrets
from flask import Blueprint, render_template, abort, current_app, request, redirect, url_for, flash, send_from_directory
from flask_login import login_required, current_user
from sqlalchemy import select
from werkzeug.utils import secure_filename
from extensions import db
from models import Job, JobUpdate, JobAttachment
from .forms import UploadForm

portal_bp = Blueprint("portal", __name__, url_prefix="/portal")

@portal_bp.route("/")
@login_required
def dashboard():
    if current_user.role == "customer":
        jobs = db.session.scalars(select(Job).where(Job.customer_user_id==current_user.id).order_by(Job.created_at.desc())).all()
    elif current_user.role == "contractor":
        jobs = db.session.scalars(select(Job).where(Job.assigned_contractor_user_id==current_user.id).order_by(Job.created_at.desc())).all()
    else:
        jobs = db.session.scalars(select(Job).order_by(Job.created_at.desc())).all()
    return render_template("portal_dashboard.html", jobs=jobs)

@portal_bp.route("/jobs/<job_uid>", methods=["GET","POST"])
@login_required
def job_detail(job_uid):
    job = db.session.scalar(select(Job).where(Job.job_uid==job_uid))
    if not job: abort(404)
    if current_user.role == "customer" and job.customer_user_id != current_user.id: abort(403)
    if current_user.role == "contractor" and job.assigned_contractor_user_id != current_user.id: abort(403)

    form = UploadForm()
    if form.validate_on_submit():
        if current_user.role not in ("contractor","admin"):
            abort(403)
        f = form.file.data
        filename = secure_filename(f.filename)
        filename = f"{secrets.token_hex(4)}_{filename}"
        dest_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], job.job_uid)
        os.makedirs(dest_dir, exist_ok=True)
        path = os.path.join(dest_dir, filename)
        f.save(path)
        att = JobAttachment(
            job_id=job.id,
            uploaded_by_user_id=current_user.id,
            category=form.category.data,
            file_name=filename,
            mime_type=f.mimetype,
            storage_url=path,  # local path; swap to S3 URL if needed
            size_bytes=os.path.getsize(path),
            is_visible_to_customer=True
        )
        db.session.add(att); db.session.commit()
        flash("File uploaded.", "success")
        return redirect(url_for("portal.job_detail", job_uid=job_uid))

    updates = db.session.scalars(select(JobUpdate).where(JobUpdate.job_id==job.id).order_by(JobUpdate.created_at.desc())).all()
    attachments = db.session.scalars(select(JobAttachment).where(JobAttachment.job_id==job.id).order_by(JobAttachment.created_at.desc())).all()
    return render_template("portal_job_detail.html", job=job, updates=updates, attachments=attachments, form=form)
