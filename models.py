from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    credits = db.Column(db.Integer, default=0)
    videos = db.relationship('Video', backref='user', lazy=True)
    batches = db.relationship('BatchJob', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200))
    topic = db.Column(db.String(200))
    character = db.Column(db.String(100))
    s3_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BatchJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    csv_filename = db.Column(db.String(200))
    total = db.Column(db.Integer)
    completed = db.Column(db.Integer, default=0)
    failed = db.Column(db.Integer, default=0)
    zip_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='PENDING')  # PENDING, PROCESSING, COMPLETED, FAILED

class BatchVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch_job.id'), nullable=False)
    row_index = db.Column(db.Integer)
    topic = db.Column(db.String(200))
    character = db.Column(db.String(100))
    video_url = db.Column(db.String(500))
    status = db.Column(db.String(20), default='PENDING')
    error = db.Column(db.Text, nullable=True)
