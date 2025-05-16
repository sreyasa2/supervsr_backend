import logging
import time
from io import BytesIO
from google.cloud import storage
import os
import shutil
from flask import current_app

from api.tasks.stream_manager import StreamManager

logger = logging.getLogger(__name__)

# Set up GCS
storage_client = storage.Client.from_service_account_json("databae-9a66ad3b2692.json")
bucket = storage_client.get_bucket("supervsr-dev")

# Shared stream manager instance
stream_manager = StreamManager()

def initialize_streams(app):
    """Start all RTSP streams in memory"""
    from api.models import RTSPStream
    with app.app_context():
        streams = RTSPStream.query.all()
        for stream in streams:
            logger.info(f"Initializing stream: {stream.name}")
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
                logger.warning(f"Stream {stream.name} not running (status: {status['status']}), attempting restart")
                stream_manager.stop_stream(stream.id)
                time.sleep(2)
                stream_manager.start_stream(stream.id, stream.rtsp_url)

def screenshots(app):
    """Capture latest frame from memory and upload every 10 seconds"""
    from api.models import RTSPStream
    with app.app_context():
        logger.info("Scheduled screenshot job triggered")

        streams = RTSPStream.query.all()
        for stream in streams:
            status = stream_manager.get_stream_status(stream.id)
            if status["status"] != "running":
                logger.warning(f"Skipping screenshot for {stream.name} - stream not running (status: {status['status']})")
                continue

            frame_path = stream_manager.get_latest_frame(stream.id)
            if frame_path is None:
                logger.warning(f"No frame available yet for {stream.name}")
                continue

            file_name = f"screenshots/{stream.name.replace(' ', '_')}-{int(time.time())}.jpg"

            # Upload to GCS
            ''' try:
                blob = bucket.blob(file_name)
                blob.upload_from_filename(frame_path)
                logger.info(f"Uploaded screenshot to GCS: {file_name}")
            except Exception as e:
                logger.exception(f"Upload failed for {stream.name}: {e}") '''

            # Save locally
            try:
                local_dir = os.path.join('uploads', 'screenshots')
                os.makedirs(local_dir, exist_ok=True)
                local_path = os.path.join(local_dir, os.path.basename(file_name))
                shutil.copy2(frame_path, local_path)
                logger.info(f"Saved screenshot locally: {local_path}")
            except Exception as e:
                logger.exception(f"Local save failed for {stream.name}: {e}")

def register_cron_jobs(scheduler, app):
    # Check if jobs are already registered
    existing_jobs = scheduler.get_jobs()
    if any(job.id == 'screenshots' for job in existing_jobs):
        logger.info("Screenshot job already registered")
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
