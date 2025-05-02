# Project Dependencies

This document lists the required dependencies for the CCTV Analysis backend.

## Python Packages

- **flask**: Web framework
- **flask-sqlalchemy**: ORM for database integration
- **gunicorn**: WSGI HTTP server
- **opencv-python**: Computer vision library for video processing
- **psycopg2-binary**: PostgreSQL adapter for Python
- **requests**: HTTP library for API calls
- **python-dotenv**: Environment variable management

## System Dependencies

- **ffmpeg**: Required for advanced video processing

## Installation

The dependencies can be installed using the following command:

```bash
pip install flask flask-sqlalchemy gunicorn opencv-python psycopg2-binary requests python-dotenv
```

For system dependencies:

```bash
# On Debian/Ubuntu
apt-get install ffmpeg

# On macOS with Homebrew
brew install ffmpeg
```

## Cloud Database Integration

The application is configured to work with cloud PostgreSQL providers like Supabase. The configuration includes:

- Connection pooling
- Connection recycling
- Pre-ping mechanism to verify connections

Make sure to set the `DATABASE_URL` environment variable to your cloud database connection string.