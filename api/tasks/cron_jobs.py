# tasks/cron_jobs.py

import logging
import time
from io import BytesIO
import cv2
import os
from google.cloud import storage
from flask import current_app

logger = logging.getLogger(__name__)

# Set up the client with the service account key
storage_client = storage.Client.from_service_account_json("databae-9a66ad3b2692.json")
bucket = storage_client.get_bucket("supervsr-dev")

def screenshots(app):
    from api.models import RTSPStream
    with app.app_context():
        logger.info("Running scheduled cron task...")

        streams = RTSPStream.query.order_by(RTSPStream.created_at.desc()).all()
        for stream in streams:
            logger.info(f"Processing stream: {stream.name} ({stream.rtsp_url})")

            try:
                cap = cv2.VideoCapture(stream.rtsp_url)
                if not cap.isOpened():
                    logger.warning(f"Unable to open stream: {stream.rtsp_url}")
                    continue

                ret, frame = cap.read()
                cap.release()

                if not ret:
                    logger.warning(f"Failed to capture frame from stream: {stream.rtsp_url}")
                    continue

                # Encode frame to JPEG
                success, encoded_image = cv2.imencode('.jpg', frame)
                if not success:
                    logger.error("Failed to encode image")
                    continue

                # Prepare in-memory upload
                image_bytes = BytesIO(encoded_image.tobytes())
                file_name = f"screenshots/{stream.name.replace(' ', '_')}-{int(time.time())}.jpg"
                blob = bucket.blob(file_name)
                blob.upload_from_file(image_bytes, content_type='image/jpeg')
                logger.info(f"Uploaded screenshot to GCS: {file_name}")

                # Save locally to uploads/screenshots
                local_dir = os.path.join('uploads', 'screenshots')
                os.makedirs(local_dir, exist_ok=True)
                local_path = os.path.join(local_dir, os.path.basename(file_name))
                cv2.imwrite(local_path, frame)
                logger.info(f"Saved screenshot locally: {local_path}")

            except Exception as e:
                logger.exception(f"Error processing stream {stream.name}: {e}")

def register_cron_jobs(scheduler, app):
    scheduler.add_job(func=screenshots, args=(app,), trigger="interval", seconds=10)
