import os
import cv2
import logging
import uuid
from datetime import datetime
from flask import current_app
from api import db
from api.models import RTSPStream, Screenshot

logger = logging.getLogger(__name__)

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