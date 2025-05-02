from datetime import datetime
from api import db

class RTSPStream(db.Model):
    """Model for storing RTSP stream links"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    rtsp_url = db.Column(db.String(512), nullable=False, unique=True)
    location = db.Column(db.String(255), nullable=True)  # Physical location of the camera
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default='active')  # active, inactive, error
    last_checked = db.Column(db.DateTime, nullable=True)  # Last time the stream was checked
    is_accessible = db.Column(db.Boolean, default=False)  # Is the stream currently accessible
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    screenshots = db.relationship('Screenshot', backref='stream', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<RTSPStream {self.name} - {self.rtsp_url}>"

class Screenshot(db.Model):
    """Model for storing screenshots extracted from RTSP streams"""
    id = db.Column(db.Integer, primary_key=True)
    stream_id = db.Column(db.Integer, db.ForeignKey('rtsp_stream.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    capture_time = db.Column(db.DateTime, default=datetime.utcnow)  # When the screenshot was taken
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    analysis_results = db.relationship('AnalysisResult', backref='screenshot', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Screenshot {self.filename} taken at {self.capture_time}>"

class AnalysisResult(db.Model):
    """Model for storing Gemini analysis results"""
    id = db.Column(db.Integer, primary_key=True)
    screenshot_id = db.Column(db.Integer, db.ForeignKey('screenshot.id'), nullable=False)
    analysis_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<AnalysisResult for Screenshot {self.screenshot_id}>"