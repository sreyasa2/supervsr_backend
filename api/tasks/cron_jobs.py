import logging
import time
from io import BytesIO
import os
import shutil
from flask import current_app
from datetime import datetime
from collections import defaultdict
import tempfile

from api.tasks.stream_manager import StreamManager
from api.tasks.stitcher import process_images
from api.utils.gcs_utils import GCSUtils
from api.tasks.screenshot_processor import ScreenshotProcessor

logger = logging.getLogger(__name__)

# Initialize utilities
gcs_utils = GCSUtils()
stream_manager = StreamManager()

# Get grid dimensions from environment variables with defaults
GRID_ROWS = 2
GRID_COLS = 3
screenshot_processor = ScreenshotProcessor(gcs_utils, screenshots_per_grid=GRID_ROWS * GRID_COLS)

# Track screenshot counts for each stream
screenshot_counts = defaultdict(int)

def initialize_streams(app):
    """Start all RTSP streams in memory"""
    from api.models import RTSPStream
    with app.app_context():
        streams = RTSPStream.query.all()
        for stream in streams:
            success = stream_manager.start_stream(stream.id, stream.rtsp_url)
            if not success:
                logger.error(f"Failed to initialize stream: {stream.name}")
                # Try to restart the stream after a delay
                time.sleep(5)
                success = stream_manager.start_stream(stream.id, stream.rtsp_url)
                if not success:
                    logger.error(f"Failed to initialize stream after retry: {stream.name}")

def verify_streams(app):
    """Verify all streams are running properly"""
    from api.models import RTSPStream
    with app.app_context():
        streams = RTSPStream.query.all()
        for stream in streams:
            status = stream_manager.get_stream_status(stream.id)
            if status["status"] != "running":
                logger.error(f"Stream {stream.name} not running (status: {status['status']}), attempting restart")
                stream_manager.stop_stream(stream.id)
                time.sleep(2)
                stream_manager.start_stream(stream.id, stream.rtsp_url)

def get_recent_screenshot_urls(stream_id: str, count: int) -> list[str]:
    """
    Get the most recent screenshot URLs for a stream from GCS.
    
    Args:
        stream_id: The ID of the stream
        count: Number of screenshots to fetch
        
    Returns:
        List of GCS URLs for the screenshots
    """
    # List all blobs in the screenshots folder
    blobs = list(bucket.list_blobs(prefix=f"screenshots/{stream_id}-"))
    
    # Sort by creation time (newest first) and take the most recent ones
    recent_blobs = sorted(blobs, key=lambda x: x.time_created, reverse=True)[:count]
    
    # Get public URLs for each blob
    return [blob.public_url for blob in recent_blobs]

def screenshots(app):
    """Capture latest frame from memory and upload every 10 seconds"""
    from api.models import RTSPStream
    with app.app_context():
        streams = RTSPStream.query.all()
        for stream in streams:
            status = stream_manager.get_stream_status(stream.id)
            if status["status"] != "running":
                logger.error(f"Skipping screenshot for {stream.name} - stream not running (status: {status['status']})")
                continue

            frame_path = stream_manager.get_latest_frame(stream.id)
            if frame_path is None:
                continue

            # Process the screenshot with grid dimensions
            screenshot_processor.process_screenshot(
                stream_id=stream.id,
                stream_name=stream.name,
                frame_path=frame_path,
                grid_rows=GRID_ROWS,  
                grid_cols=GRID_COLS
            )

def register_cron_jobs(scheduler, app):
    # Check if jobs are already registered
    existing_jobs = scheduler.get_jobs()
    if any(job.id == 'screenshots' for job in existing_jobs):
        return
        
    initialize_streams(app)  # Start streams at scheduler startup
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
