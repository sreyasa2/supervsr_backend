from datetime import datetime
from api import db


class RTSPStream(db.Model):
    __tablename__   = 'rtsp_stream'

    id              = db.Column(db.Integer, primary_key=True)
    rtsp_url        = db.Column(db.String(255), nullable=False)
    description     = db.Column(db.Text)
    name            = db.Column(db.String(255))
    coco_link       = db.Column(db.String(255))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    sops            = db.relationship('SOP', secondary='rtsp_sop_association', back_populates='rtsp_streams')
    analysis        = db.relationship('Analysis', backref='rtsp_stream', lazy=True, cascade='all, delete-orphan')


class SOP(db.Model):
    __tablename__   = 'sop'

    id              = db.Column(db.Integer, primary_key=True)
    model_id        = db.Column(db.Integer, db.ForeignKey('ai_model.id'), nullable=True)
    name            = db.Column(db.String(255))
    description     = db.Column(db.Text)
    prompt          = db.Column(db.Text)
    frequency       = db.Column(db.Integer, default=10, nullable=False)  # Frequency in seconds

    model           = db.relationship('AIModel', backref='sop', lazy=True)
    analysis        = db.relationship('Analysis', backref='sop', lazy=True, cascade='all, delete-orphan')
    rtsp_streams    = db.relationship('RTSPStream', secondary='rtsp_sop_association', back_populates='sops')


class AIModel(db.Model):
    __tablename__   = 'ai_model'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(255), nullable=False)
    description     = db.Column(db.Text)
    link            = db.Column(db.String(255))
    model_type      = db.Column(db.String(255))


class Analysis(db.Model):
    __tablename__   = 'analysis'

    id              = db.Column(db.Integer, primary_key=True)
    rtsp_id         = db.Column(db.Integer, db.ForeignKey('rtsp_stream.id'), nullable=False)
    sop_id          = db.Column(db.Integer, db.ForeignKey('sop.id'), nullable=False)
    timestamp       = db.Column(db.DateTime, nullable=False)
    output          = db.Column(db.Text)


class Organization(db.Model):
    __tablename__   = 'organization'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(255), nullable=False)
    description     = db.Column(db.Text)

    users           = db.relationship('User', backref='organization', lazy=True)


class User(db.Model):
    __tablename__   = 'user'

    id              = db.Column(db.Integer, primary_key=True)
    org_id          = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    name            = db.Column(db.String(255), nullable=False)
    password        = db.Column(db.String(255), nullable=False)
    email           = db.Column(db.String(255), unique=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)


rtsp_sop_association = db.Table(
    'rtsp_sop_association',
    db.Column('rtsp_id', db.Integer, db.ForeignKey('rtsp_stream.id'), primary_key=True),
    db.Column('sop_id', db.Integer, db.ForeignKey('sop.id'), primary_key=True)
)
