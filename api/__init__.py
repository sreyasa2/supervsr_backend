import os
import logging
import atexit
from api import tasks
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from apscheduler.schedulers.background import BackgroundScheduler
from api.tasks.cron_jobs import register_cron_jobs  

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

def start_scheduler(app):
    scheduler = BackgroundScheduler()
    register_cron_jobs(scheduler, app)
    scheduler.start()
    logger.info("APScheduler with RTSP job and stream manager started.")
    return scheduler

def create_app(test_config=None):
    """Create and configure the Flask application"""
    app = Flask(__name__, instance_relative_config=True)
    
    # Load configuration
    if test_config is None:
        from api.config import get_config
        app.config.from_object(get_config())
    else:
        app.config.from_mapping(test_config)
    
    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass
    
    # Ensure uploads folders exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'screenshots'), exist_ok=True)
    
    # Initialize database with app
    db.init_app(app)
    
    # Add connection pooling options
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 10,
        "max_overflow": 20
    }

    with app.app_context():
        from api.models import RTSPStream, Screenshot, AnalysisResult
        db.create_all()

    # Register routes
    from api.routes import video_bp
    app.register_blueprint(video_bp)

    # Start scheduler
    scheduler = start_scheduler(app)
    atexit.register(lambda: scheduler.shutdown())

    # Health check route
    @app.route('/health')
    def health_check():
        return {'status': 'ok'}

    # API index route
    @app.route('/')
    def index():
        return jsonify({
            'name': 'CCTV Analysis API',
            'version': '1.0.0',
            'description': 'Backend API for analyzing RTSP streams with Gemini AI',
            'endpoints': {
                'health': '/health',
                'streams': '/api/streams',
                'stream_details': '/api/stream/<id>',
                'check_stream': '/api/stream/<id>/check',
                'capture': '/api/stream/<id>/capture',
                'screenshots': '/api/stream/<id>/screenshots',
                'analyze': '/api/screenshot/<id>/analyze',
                'analysis': '/api/screenshot/<id>/analysis'
            }
        })

    logger.info("Application initialized successfully")
    return app
