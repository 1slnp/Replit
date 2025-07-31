from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy import func

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    tokens = db.Column(db.Integer, default=2)  # Starter tokens
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class CoverArt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    artist_name = db.Column(db.String(100), nullable=False)
    album_title = db.Column(db.String(100), nullable=False)
    genre = db.Column(db.String(50), nullable=False)
    explicit_content = db.Column(db.Boolean, default=False)
    ai_prompt = db.Column(db.Text)
    image_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class VocalMaster(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    track_title = db.Column(db.String(100), nullable=False)
    original_file = db.Column(db.String(255), nullable=False)
    mastered_file = db.Column(db.String(255))
    template = db.Column(db.String(50), nullable=False)
    eq_settings = db.Column(db.JSON)
    status = db.Column(db.String(20), default='processing')  # processing, completed, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class VideoGeneration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    track_title = db.Column(db.String(100), nullable=False)
    audio_file = db.Column(db.String(255), nullable=False)
    visual_style = db.Column(db.String(50), nullable=False)
    scene_prompt = db.Column(db.Text)
    duration = db.Column(db.String(10), nullable=False)  # 15s, 30s, 1min
    resolution = db.Column(db.String(10), nullable=False)  # 720p, 1080p, 4K
    video_file = db.Column(db.String(255))
    status = db.Column(db.String(20), default='processing')  # processing, completed, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
