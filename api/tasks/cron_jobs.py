import logging
import time
import requests
from collections import defaultdict
from flask import current_app

from api.tasks.stream_manager import StreamManager
from api.tasks.screenshot_processor import ScreenshotProcessor
from api.utils.gcs_utils import GCSUtils
from api.utils.api_utils import get_api_url

logger = logging.getLogger(__name__)
# Grid dimensions
GRID_ROWS = 2
GRID_COLS = 3

# Initialize utilities
gcs_utils = GCSUtils()
stream_manager = StreamManager()
screenshot_processor = ScreenshotProcessor(gcs_utils, screenshots_per_grid=GRID_ROWS * GRID_COLS)


# Track screenshot counts for each stream
screenshot_counts = defaultdict(int)

# Cache for streams
streams_cache = {
    'streams': [],
    'last_updated': 0,
    'ttl': None  # Will be set from config when first used
}

def get_streams():
    """Get streams from cache or API"""
    current_time = time.time()
    
    # Initialize TTL from config if not set
    if streams_cache['ttl'] is None:
        streams_cache['ttl'] = current_app.config.get('STREAMS_CACHE_TTL', 300)
    
    # Return cached streams if they're still valid
    if (current_time - streams_cache['last_updated']) < streams_cache['ttl']:
        return streams_cache['streams']
    
    try:
        # Get streams from API
        api_url = get_api_url('/api/streams')
        logger.info(f"Fetching streams from API: {api_url}")
        
        response = requests.get(api_url)
        
        if not response.ok:
            error_msg = f"API request failed with status {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f": {error_detail}"
            except:
                error_msg += f": {response.text}"
            logger.error(error_msg)
            return streams_cache['streams']  # Return cached streams on error
        
        data = response.json()
        if 'streams' not in data:
            logger.error(f"Invalid API response format. Expected 'streams' key. Got: {data}")
            return streams_cache['streams']
            
        streams = data['streams']
        if not streams:
            logger.warning("No streams found in the database. Please add streams through the API.")
        else:
            logger.info(f"Successfully fetched {len(streams)} streams from API")
        
        # Update cache
        streams_cache['streams'] = streams
        streams_cache['last_updated'] = current_time
        return streams_cache['streams']
        
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Failed to connect to API server: {str(e)}")
        return streams_cache['streams']
    except requests.exceptions.Timeout as e:
        logger.error(f"API request timed out: {str(e)}")
        return streams_cache['streams']
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        return streams_cache['streams']
    except Exception as e:
        logger.error(f"Unexpected error while fetching streams: {str(e)}")
        return streams_cache['streams']  # Return cached streams on error

def initialize_streams(app):
    """Start all RTSP streams in memory"""
    with app.app_context():
        streams = get_streams()
        for stream in streams:
            try:
                success = stream_manager.start_stream(stream['id'], stream['rtsp_url'])
                if not success:
                    logger.error(f"Failed to initialize stream: {stream['name']}")
                    # Try to restart the stream after a delay
                    time.sleep(2)
                    success = stream_manager.start_stream(stream['id'], stream['rtsp_url'])
                    if not success:
                        logger.error(f"Failed to initialize stream after retry: {stream['name']}")
            except Exception as e:
                logger.error(f"Error initializing stream {stream['name']}: {e}")

def verify_streams(app):
    """Verify all streams are running properly"""
    with app.app_context():
        streams = get_streams()
        for stream in streams:
            try:
                status = stream_manager.get_stream_status(stream['id'])
                if status["status"] != "running":
                    logger.error(f"Stream {stream['name']} not running (status: {status['status']}), attempting restart")
                    stream_manager.stop_stream(stream['id'])
                    time.sleep(2)
                    stream_manager.start_stream(stream['id'], stream['rtsp_url'])
            except Exception as e:
                logger.error(f"Error verifying stream {stream['name']}: {e}")

def screenshots(app):
    """Capture latest frame from memory and upload every 10 seconds"""
    with app.app_context():
        streams = get_streams()
        
        for stream in streams:
            try:
                status = stream_manager.get_stream_status(stream['id'])
                if status["status"] != "running":
                    logger.error(f"Skipping screenshot for {stream['name']} - stream not running (status: {status['status']})")
                    continue

                frame_path = stream_manager.get_latest_frame(stream['id'])
                if frame_path is None:
                    logger.warning(f"No frame available for stream {stream['name']}")
                    continue

                # Process the screenshot with grid dimensions
                success = screenshot_processor.process_screenshot(
                    stream_id=stream['id'],
                    stream_name=stream['name'],
                    frame_path=frame_path,
                    grid_rows=GRID_ROWS,  
                    grid_cols=GRID_COLS,
                )
                
                if not success:
                    logger.error(f"Failed to process screenshot for stream {stream['name']}")
            except Exception as e:
                logger.error(f"Error processing screenshot for stream {stream['name']}: {e}")

def register_cron_jobs(scheduler, app):
    """Register cron jobs with proper error handling"""
    try:
        existing_jobs = scheduler.get_jobs()
        if any(job.id == 'screenshots' for job in existing_jobs):
            return

        initialize_streams(app)

        # Verify streams every minute
        scheduler.add_job(
            func=verify_streams,
            args=(app,),
            trigger="interval",
            seconds=60,
            id='verify_streams',
            replace_existing=True
        )

        # Take screenshots every 10 seconds
        scheduler.add_job(
            func=screenshots,
            args=(app,),
            trigger="interval",
            seconds=10,
            id='screenshots',
            replace_existing=True
        )
    except Exception as e:
        logger.error(f"Failed to register cron jobs: {e}")
        raise
