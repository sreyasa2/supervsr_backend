from datetime import datetime
from api import db

class RTSPStream(db.Model):
    __tablename__ = 'rtsp_stream'
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(255), nullable=False)
    rtsp_url     = db.Column(db.String(512), nullable=False, unique=True)
    location     = db.Column(db.String(255))
    description  = db.Column(db.Text)
    status       = db.Column(db.String(50), default='active')
    last_checked = db.Column(db.DateTime)
    is_accessible= db.Column(db.Boolean, default=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(
                      db.DateTime,
                      default=datetime.utcnow,
                      onupdate=datetime.utcnow
                   )

    screenshots = db.relationship(
        'Screenshot',
        backref='stream',
        lazy=True,
        cascade='all, delete-orphan'
    )

class Screenshot(db.Model):
    __tablename__ = 'screenshot'
    id           = db.Column(db.Integer, primary_key=True)
    stream_id    = db.Column(
                      db.Integer,
                      db.ForeignKey('rtsp_stream.id'),
                      nullable=False
                   )
    filename     = db.Column(db.String(255), nullable=False)
    file_path    = db.Column(db.String(255), nullable=False)
    capture_time = db.Column(db.DateTime, default=datetime.utcnow)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    analysis_results = db.relationship(
        'AnalysisResult',
        backref='screenshot',
        lazy=True,
        cascade='all, delete-orphan'
    )

class AnalysisResult(db.Model):
    __tablename__ = 'analysis_result'
    id             = db.Column(db.Integer, primary_key=True)
    screenshot_id  = db.Column(
                       db.Integer,
                       db.ForeignKey('screenshot.id'),
                       nullable=False
                    )
    analysis_text  = db.Column(db.Text)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
