import os
import re
import uuid
import logging
import datetime
import cv2
from flask import Blueprint, request, jsonify, current_app, abort, send_from_directory
from api.models import RTSPStream, Screenshot, AnalysisResult
from api import db

video_bp = Blueprint('video', __name__)
logger = logging.getLogger(__name__)

def validate_rtsp_url(url):
    """
    Validate an RTSP URL
    
    Args:
        url (str): RTSP URL to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Basic pattern for RTSP URLs
    rtsp_pattern = r'^rtsp://(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?(?::\d+)?(?:/[^/\s]+)*/?$'
    
    # Alternative pattern for IP-based RTSP URLs (including auth)
    ip_rtsp_pattern = r'^rtsp://(?:(?:[a-zA-Z0-9._~%-]+(?::[a-zA-Z0-9._~%-]+)?@)?(?:\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|\[[:a-fA-F0-9]+\])(?::\d+)?(?:/[^/\s]+)*/?$)'
    
    return bool(re.match(rtsp_pattern, url) or re.match(ip_rtsp_pattern, url))

def check_rtsp_stream(url):
    """
    Check if an RTSP stream is accessible
    
    Args:
        url (str): RTSP URL to check
        
    Returns:
        bool: True if accessible, False otherwise
    """
    try:
        # Attempt to open the RTSP stream with OpenCV
        cap = cv2.VideoCapture(url)
        
        # Check if opened successfully
        if not cap.isOpened():
            logger.error(f"Could not open RTSP stream: {url}")
            cap.release()
            return False
        
        # Try to read a frame
        ret, frame = cap.read()
        cap.release()
        
        return ret
    except Exception as e:
        logger.error(f"Error checking RTSP stream: {str(e)}")
        return False

@video_bp.route('/api/streams', methods=['GET'])
def get_streams():
    """API endpoint to list all RTSP streams"""
    streams = RTSPStream.query.order_by(RTSPStream.created_at.desc()).all()
    streams_data = [{
        'id': stream.id,
        'name': stream.name,
        'rtsp_url': stream.rtsp_url,
        'location': stream.location,
        'status': stream.status,
        'is_accessible': stream.is_accessible,
        'created_at': stream.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'screenshot_count': len(stream.screenshots)
    } for stream in streams]
    
    return jsonify({'success': True, 'streams': streams_data})

@video_bp.route('/api/streams', methods=['POST'])
def add_rtsp_stream():
    """API endpoint to add a new RTSP stream"""
    data = request.json
    
    # Validate required fields
    if not data or not data.get('rtsp_url') or not data.get('name'):
        return jsonify({'success': False, 'error': 'Required fields missing: rtsp_url and name are required'}), 400
    
    rtsp_url = data.get('rtsp_url')
    name = data.get('name')
    location = data.get('location', '')
    description = data.get('description', '')
    
    # Validate RTSP URL format
    if not validate_rtsp_url(rtsp_url):
        return jsonify({'success': False, 'error': 'Invalid RTSP URL format'}), 400
    
    # Check if stream with this URL already exists
    existing_stream = RTSPStream.query.filter_by(rtsp_url=rtsp_url).first()
    if existing_stream:
        return jsonify({'success': False, 'error': 'RTSP stream with this URL already exists'}), 409
    
    # Check if the stream is accessible
    is_accessible = check_rtsp_stream(rtsp_url)
    if not is_accessible:
        # Still add the stream, but mark it as inaccessible
        logger.warning(f"Added inaccessible RTSP stream: {rtsp_url}")
    
    try:
        # Create new RTSP stream record
        stream = RTSPStream(
            name=name,
            rtsp_url=rtsp_url,
            location=location,
            description=description,
            status='active' if is_accessible else 'error',
            is_accessible=is_accessible,
            last_checked=datetime.datetime.utcnow()
        )
        db.session.add(stream)
        db.session.commit()
        
        # Try to capture an initial screenshot if accessible
        if is_accessible:
            try:
                screenshot = capture_screenshot_from_rtsp(stream.id)
                if screenshot:
                    logger.info(f"Initial screenshot captured for stream {stream.id}")
            except Exception as e:
                logger.error(f"Error capturing initial screenshot: {str(e)}")
        
        return jsonify({
            'success': True,
            'stream_id': stream.id,
            'name': stream.name,
            'is_accessible': stream.is_accessible,
            'message': 'RTSP stream added successfully'
        })
    
    except Exception as e:
        logger.error(f"Error adding RTSP stream: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@video_bp.route('/api/stream/<int:stream_id>', methods=['GET'])
def get_stream(stream_id):
    """API endpoint to get details of a specific RTSP stream"""
    stream = RTSPStream.query.get_or_404(stream_id)
    
    return jsonify({
        'success': True,
        'stream': {
            'id': stream.id,
            'name': stream.name,
            'rtsp_url': stream.rtsp_url,
            'location': stream.location,
            'description': stream.description,
            'status': stream.status,
            'is_accessible': stream.is_accessible,
            'last_checked': stream.last_checked.strftime('%Y-%m-%d %H:%M:%S') if stream.last_checked else None,
            'created_at': stream.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': stream.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }
    })

@video_bp.route('/api/stream/<int:stream_id>/check', methods=['POST'])
def check_stream(stream_id):
    """API endpoint to check if a stream is accessible"""
    stream = RTSPStream.query.get_or_404(stream_id)
    
    # Check if the stream is accessible
    is_accessible = check_rtsp_stream(stream.rtsp_url)
    
    # Update stream status
    stream.is_accessible = is_accessible
    stream.status = 'active' if is_accessible else 'error'
    stream.last_checked = datetime.datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'stream_id': stream.id,
        'is_accessible': stream.is_accessible,
        'status': stream.status
    })

@video_bp.route('/api/stream/<int:stream_id>/screenshots', methods=['GET'])
def get_stream_screenshots(stream_id):
    """API endpoint to list all screenshots for a stream"""
    screenshots = Screenshot.query.filter_by(stream_id=stream_id).order_by(Screenshot.capture_time.desc()).all()
    screenshots_data = [{
        'id': ss.id,
        'filename': ss.filename,
        'capture_time': ss.capture_time.strftime('%Y-%m-%d %H:%M:%S'),
        'created_at': ss.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'analysis_count': len(ss.analysis_results),
        'has_analysis': len(ss.analysis_results) > 0
    } for ss in screenshots]
    
    return jsonify({'success': True, 'screenshots': screenshots_data})

@video_bp.route('/api/screenshot/<int:screenshot_id>/analysis', methods=['GET'])
def get_screenshot_analysis(screenshot_id):
    """API endpoint to get analysis results for a screenshot"""
    analysis = AnalysisResult.query.filter_by(screenshot_id=screenshot_id).order_by(AnalysisResult.created_at.desc()).first()
    
    if not analysis:
        return jsonify({'success': False, 'error': 'No analysis found for this screenshot'}), 404
    
    return jsonify({
        'success': True,
        'analysis': {
            'id': analysis.id,
            'text': analysis.analysis_text,
            'created_at': analysis.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
    })

@video_bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)