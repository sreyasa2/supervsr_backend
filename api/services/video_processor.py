import os
import cv2
import logging
import uuid
from datetime import datetime
from flask import current_app
from api import db
from api.models import RTSPStream, Screenshot

logger = logging.getLogger(__name__)

def capture_screenshot_from_rtsp(stream_id):
    """
    Capture a screenshot from an RTSP stream
    
    Args:
        stream_id (int): The ID of the RTSP stream in the database
    
    Returns:
        Screenshot: Screenshot object created or None if failed
    """
    # Get the stream
    stream = RTSPStream.query.get(stream_id)
    if not stream:
        logger.error(f"RTSP stream with ID {stream_id} not found")
        return None
    
    # Create a directory for screenshots if it doesn't exist
    screenshots_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'screenshots')
    os.makedirs(screenshots_dir, exist_ok=True)
    
    # Open the RTSP stream
    logger.info(f"Attempting to connect to RTSP stream: {stream.rtsp_url}")
    
    try:
        # Open the stream with OpenCV
        cap = cv2.VideoCapture(stream.rtsp_url)
        
        # Check if opened successfully
        if not cap.isOpened():
            logger.error(f"Could not open RTSP stream: {stream.rtsp_url}")
            stream.is_accessible = False
            stream.status = 'error'
            stream.last_checked = datetime.utcnow()
            db.session.commit()
            return None
        
        # Set any required capture properties
        # Sometimes setting the buffer size helps with RTSP streams
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Try to read a frame (might need multiple attempts for RTSP)
        max_attempts = 5
        frame = None
        
        for attempt in range(max_attempts):
            logger.debug(f"Attempt {attempt+1}/{max_attempts} to read frame from RTSP stream")
            ret, frame = cap.read()
            if ret and frame is not None:
                break
                
        # Release the video capture
        cap.release()
        
        # If we couldn't get a frame after all attempts
        if frame is None:
            logger.error(f"Failed to read frame from RTSP stream after {max_attempts} attempts")
            stream.is_accessible = False
            stream.status = 'error'
            stream.last_checked = datetime.utcnow()
            db.session.commit()
            return None
        
        # Create a unique filename for the screenshot
        current_time = datetime.utcnow()
        timestamp_str = current_time.strftime('%Y%m%d_%H%M%S')
        screenshot_filename = f"{stream.id}_{timestamp_str}_{uuid.uuid4().hex}.jpg"
        screenshot_path = os.path.join(screenshots_dir, screenshot_filename)
        
        # Save the screenshot
        cv2.imwrite(screenshot_path, frame)
        
        # Update stream status
        stream.is_accessible = True
        stream.status = 'active'
        stream.last_checked = current_time
        
        # Create a Screenshot record in the database
        screenshot = Screenshot(
            stream_id=stream.id,
            filename=screenshot_filename,
            file_path=screenshot_path,
            capture_time=current_time
        )
        
        db.session.add(screenshot)
        db.session.commit()
        
        logger.info(f"Successfully captured screenshot from RTSP stream {stream_id}")
        return screenshot
    
    except Exception as e:
        logger.error(f"Error capturing screenshot from RTSP stream: {str(e)}")
        db.session.rollback()
        
        # Update stream status on error
        try:
            stream.is_accessible = False
            stream.status = 'error'
            stream.last_checked = datetime.utcnow()
            db.session.commit()
        except Exception as db_error:
            logger.error(f"Error updating stream status: {str(db_error)}")
        
        return None

def get_rtsp_stream_info(rtsp_url):
    """
    Get information about an RTSP stream
    
    Args:
        rtsp_url (str): RTSP stream URL
        
    Returns:
        dict: Dictionary containing stream metadata
    """
    metadata = {
        'is_accessible': False,
        'width': 0,
        'height': 0,
        'fps': 0
    }
    
    try:
        # Open the RTSP stream
        cap = cv2.VideoCapture(rtsp_url)
        
        # Check if opened successfully
        if not cap.isOpened():
            logger.error(f"Could not open RTSP stream: {rtsp_url}")
            return metadata
        
        # Try to read a frame
        ret, frame = cap.read()
        
        if ret:
            metadata['is_accessible'] = True
            
            # Get stream properties
            metadata['width'] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            metadata['height'] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            metadata['fps'] = cap.get(cv2.CAP_PROP_FPS)
        
        # Release the video capture
        cap.release()
        
    except Exception as e:
        logger.error(f"Error getting RTSP stream info: {str(e)}")
    
    return metadata