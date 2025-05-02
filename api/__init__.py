import os
import logging
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

def create_app(test_config=None):
    """Create and configure the Flask application"""
    # Create app instance
    app = Flask(__name__, instance_relative_config=True)
    
    # Load configuration
    if test_config is None:
        # Load the config based on environment
        from api.config import get_config
        app.config.from_object(get_config())
    else:
        # Load the test config
        app.config.from_mapping(test_config)
    
    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass
    
    # Ensure uploads folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'screenshots'), exist_ok=True)
    
    # Initialize database with app
    db.init_app(app)
    
    # Add connection pooling options for cloud database
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 10,
        "max_overflow": 20
    }
    
    with app.app_context():
        # Import models to ensure they're registered with SQLAlchemy
        from api.models import RTSPStream, Screenshot, AnalysisResult
        
        # Create database tables
        db.create_all()
    
    # Register routes
    from api.routes import video_bp
    app.register_blueprint(video_bp)
    
    # Create a basic route for health checks
    @app.route('/health')
    def health_check():
        return {'status': 'ok'}
        
    # Root route with API information
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