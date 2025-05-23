# Route blueprint imports
from api.routes.video_routes import video_bp
from api.routes.sop_routes import sop_bp
from api.routes.analysis_routes import analysis_bp
from api.routes.model_routes import model_bp

__all__ = ['video_bp', 'sop_bp', 'analysis_bp', 'model_bp']