import os
import logging
import atexit
from api import tasks
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from sqlalchemy.orm import DeclarativeBase
from apscheduler.schedulers.background import BackgroundScheduler
from api.tasks.cron_jobs import register_cron_jobs  

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Only show WARNING and above
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize database
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
migrate = Migrate()

def start_scheduler(app):
    scheduler = BackgroundScheduler()
    register_cron_jobs(scheduler, app)
    scheduler.start()
    logger.warning("Scheduler started")  # Changed to warning level
    return scheduler

def create_app(test_config=None):
    """Create and configure the Flask application"""
    app = Flask(__name__, instance_relative_config=True)
    
    # Enable CORS
    CORS(app, resources={r"/*": {"origins": ["http://localhost:5173", "http://localhost:3000", "http://localhost:8080", "http://127.0.0.1:5173", "http://127.0.0.1:3000", "http://127.0.0.1:8080"]}}, supports_credentials=True)
    
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
    migrate.init_app(app, db)
    
    # Add connection pooling options for pgbouncer
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 10,
        "max_overflow": 20,
        "connect_args": {
            "application_name": "supervsr_backend",
            "options": "-c statement_timeout=60000"
        }
    }

    with app.app_context():
        from api.models import RTSPStream, SOP, AIModel, Analysis, Organization, User
        db.create_all()

    # Register routes
    from api.routes import video_bp, sop_bp, analysis_bp, model_bp
    app.register_blueprint(video_bp)
    app.register_blueprint(sop_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(model_bp)

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
                'streams': {
                    'list': '/api/streams',
                    'details': '/api/stream/<id>',
                    'check': '/api/stream/<id>/check',
                    'capture': '/api/stream/<id>/capture',
                    'screenshots': '/api/stream/<id>/screenshots'
                },
                'sops': {
                    'list': '/api/sops',
                    'details': '/api/sops/<id>',
                    'create': '/api/sops',
                    'update': '/api/sops/<id>',
                    'delete': '/api/sops/<id>'
                },
                'analysis': {
                    'list': '/api/analysis',
                    'details': '/api/analysis/<id>',
                    'create': '/api/analysis',
                    'update': '/api/analysis/<id>',
                    'delete': '/api/analysis/<id>'
                },
                'models': {
                    'list': '/api/models',
                    'details': '/api/models/<id>',
                    'create': '/api/models',
                    'update': '/api/models/<id>',
                    'delete': '/api/models/<id>'
                }
            }
        })

    logger.warning("Application initialized")  # Changed to warning level
    return app
