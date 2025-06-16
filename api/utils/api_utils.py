from flask import current_app

def get_api_url(endpoint):
    """Get the full API URL for an endpoint"""
    base_url = current_app.config.get('API_BASE_URL', 'http://localhost:8000')
    return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}" 