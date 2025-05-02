import os
import logging

logger = logging.getLogger(__name__)

class Config:
    """Base configuration class"""
    DEBUG = True
    TESTING = False
    SECRET_KEY = os.environ.get("SESSION_SECRET", "dev_secret_key")
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload settings
    UPLOAD_FOLDER = "uploads"
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'wmv', 'mkv'}
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    
    # Gemini AI settings
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL_NAME = "gemini-pro-vision"
    
    # Video processing settings
    SCREENSHOT_INTERVAL = 5  # Take a screenshot every 5 seconds
    MAX_SCREENSHOTS_PER_VIDEO = 20  # Maximum number of screenshots to process per video


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    UPLOAD_FOLDER = "test_uploads"


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    # In production, ensure a proper secret key is set
    SECRET_KEY = os.environ.get("SESSION_SECRET")
    # Consider more restrictive settings for production
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB


def get_config():
    """Return the active configuration"""
    env = os.environ.get("FLASK_ENV", "development").lower()
    
    if env == "production":
        logger.info("Loading production configuration")
        return ProductionConfig
    elif env == "testing":
        logger.info("Loading testing configuration")
        return TestingConfig
    else:
        logger.info("Loading development configuration")
        return DevelopmentConfig