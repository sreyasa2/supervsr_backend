# CCTV Analysis Backend

A Flask-based backend application for analyzing CCTV footage using Google's Gemini AI.

## Features

- Video upload API endpoints
- Automatic screenshot extraction from videos at defined intervals
- Integration with Google Gemini AI for image analysis
- PostgreSQL database for storage
- Optimized for cloud database providers

## Setup

1. Create a PostgreSQL database
2. Set up environment variables (copy `.env.example` to `.env` and fill in values)
3. Install dependencies (see `DEPENDENCIES.md`)

## Running the Application

### Option 1: Using Replit

If you're using Replit, simply click the "Run" button at the top of the interface. This will start the application using the configured workflow.

### Option 2: Using the Command Line

#### Development Mode

For local development with automatic reloading:

```bash
# Start with Flask's built-in development server
python main.py
```

#### Production Mode

For production deployment:

```bash
# Start with Gunicorn (recommended for production)
gunicorn --bind 0.0.0.0:5000 --reload main:app
```

### Option 3: CLI Tools

The project includes two command-line tools:

1. **Direct Database Processing**:

   ```bash
   # Process a video file and extract screenshots
   python cli.py --video path/to/your/video.mp4

   # Analyze screenshots for a specific video ID (limit to 5 screenshots)
   python cli.py --analyze 1 --limit 5

   # Process video and analyze screenshots in one command
   python cli.py --video path/to/your/video.mp4 --limit 3
   ```

2. **API Client Testing**:

   ```bash
   # Process a video through the API (server must be running)
   python example.py path/to/your/video.mp4
   ```

### Environment Configuration

For local development, create a `.env` file in the root directory with:

```
# Flask Environment
FLASK_ENV=development

# Database Configuration
# For PostgreSQL:
DATABASE_URL=postgresql://username:password@localhost:5432/cctv_analysis
# OR for SQLite (easier for local development):
# DATABASE_URL=sqlite:///instance/cctv_analysis.db

# Gemini API Config (required for AI analysis features)
GEMINI_API_KEY=your_gemini_api_key
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check endpoint |
| `/api/videos` | GET | List all uploaded videos |
| `/api/videos` | POST | Upload a new video |
| `/api/video/<id>/screenshots` | GET | Get screenshots for a video |
| `/api/screenshot/<id>/analyze` | POST | Analyze a screenshot with Gemini AI |
| `/api/screenshot/<id>/analysis` | GET | Get analysis results for a screenshot |

## Usage Examples

See `example.py` for a complete demonstration of the API usage.

### Basic Example

```python
import requests

# Upload a video
with open('my_video.mp4', 'rb') as f:
    files = {'video': f}
    response = requests.post('http://localhost:5000/api/videos', files=files)
    
video_id = response.json()['video_id']

# Get screenshots
screenshots = requests.get(f'http://localhost:5000/api/video/{video_id}/screenshots').json()['screenshots']

# Analyze a screenshot
screenshot_id = screenshots[0]['id']
analysis = requests.post(f'http://localhost:5000/api/screenshot/{screenshot_id}/analyze').json()
```

## CLI Tools

The project includes CLI tools for different testing scenarios. See the [Running the Application](#option-3-cli-tools) section for detailed usage examples.

## Configuration

The application supports different environments (development, testing, production) which can be set using the `FLASK_ENV` environment variable.

Key configuration options:

- `SCREENSHOT_INTERVAL`: Time between screenshots (seconds)
- `MAX_SCREENSHOTS_PER_VIDEO`: Maximum number of screenshots to extract
- `GEMINI_API_KEY`: Google Gemini API key
- `DATABASE_URL`: PostgreSQL connection string
- `API_BASE_URL`: Base URL for API endpoints (default: http://localhost:5000)
- `STREAMS_CACHE_TTL`: Time-to-live for streams cache in seconds (default: 300)

## License

[MIT](LICENSE)