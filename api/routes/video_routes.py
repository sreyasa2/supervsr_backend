import os
import re
import uuid
import logging
from datetime import datetime
import cv2
from flask import Blueprint, request, jsonify, current_app, abort, send_from_directory
from api.models import RTSPStream, SOP
from api import db
from sqlalchemy.exc import SQLAlchemyError

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
    try:
        streams = RTSPStream.query.all()
        streams_data = [{
            'id': stream.id,
            'name': stream.name,
            'rtsp_url': stream.rtsp_url,
            'description': stream.description,
            'coco_link': stream.coco_link,
            'created_at': stream.created_at.strftime('%Y-%m-%d %H:%M:%S') if stream.created_at else None,
            'sops': [{'id': sop.id, 'name': sop.name} for sop in stream.sops],
            'analysis_count': len(stream.analysis)
        } for stream in streams]
        
        return jsonify({'success': True, 'streams': streams_data})
    except SQLAlchemyError as e:
        logger.error(f"Database error while fetching streams: {str(e)}")
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while fetching streams: {str(e)}")
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@video_bp.route('/api/streams', methods=['POST'])
def add_rtsp_stream():
    """API endpoint to add a new RTSP stream"""
    try:
        data = request.json
        
        # Validate required fields
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        if not data.get('rtsp_url'):
            return jsonify({'success': False, 'error': 'Required fields missing: rtsp_url is required'}), 400
        if not data.get('name'):
            return jsonify({'success': False, 'error': 'Required fields missing: name is required'}), 400
        
        rtsp_url = data.get('rtsp_url')
        name = data.get('name')
        description = data.get('description', '')
        coco_link = data.get('coco_link', '')
        
        # Validate RTSP URL format
        if not validate_rtsp_url(rtsp_url):
            return jsonify({'success': False, 'error': 'Invalid RTSP URL format'}), 400
        
        # Check if stream with this URL already exists
        existing_stream = RTSPStream.query.filter_by(rtsp_url=rtsp_url).first()
        if existing_stream:
            return jsonify({'success': False, 'error': 'RTSP stream with this URL already exists'}), 409
        
        # Create new RTSP stream record
        stream = RTSPStream(
            name=name,
            rtsp_url=rtsp_url,
            description=description,
            coco_link=coco_link,
            created_at=datetime.now()  # Set created_at on creation
        )
        db.session.add(stream)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'stream_id': stream.id,
            'name': stream.name,
            'message': 'RTSP stream added successfully'
        })
    
    except SQLAlchemyError as e:
        logger.error(f"Database error while creating stream: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while creating stream: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@video_bp.route('/api/stream/<int:stream_id>', methods=['GET'])
def get_stream(stream_id):
    """API endpoint to get details of a specific RTSP stream"""
    try:
        stream = RTSPStream.query.get_or_404(stream_id)
        
        return jsonify({
            'success': True,
            'stream': {
                'id': stream.id,
                'name': stream.name,
                'rtsp_url': stream.rtsp_url,
                'description': stream.description,
                'coco_link': stream.coco_link,
                'created_at': stream.created_at.strftime('%Y-%m-%d %H:%M:%S') if stream.created_at else None,
                'sops': [{
                    'id': sop.id,
                    'name': sop.name,
                    'description': sop.description
                } for sop in stream.sops],
                'analysis': [{
                    'id': analysis.id,
                    'timestamp': analysis.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'output': analysis.output
                } for analysis in stream.analysis]
            }
        })
    except SQLAlchemyError as e:
        logger.error(f"Database error while fetching stream {stream_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while fetching stream {stream_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@video_bp.route('/api/stream/<int:stream_id>', methods=['PUT'])
def update_stream(stream_id):
    """API endpoint to update a specific RTSP stream"""
    try:
        stream = RTSPStream.query.get_or_404(stream_id)
        logger.info(f"Fetching stream {stream}")
        data = request.json
        
        logger.info(f"Updating stream {stream_id} with data: {data}")
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided for update'}), 400
        
        if 'name' in data:
            stream.name = data['name']
        if 'description' in data:
            stream.description = data['description']
        if 'coco_link' in data:
            stream.coco_link = data['coco_link']
        if 'rtsp_url' in data:
            if not validate_rtsp_url(data['rtsp_url']):
                return jsonify({'success': False, 'error': 'Invalid RTSP URL format'}), 400
            # Check if new URL conflicts with existing stream
            existing_stream = RTSPStream.query.filter_by(rtsp_url=data['rtsp_url']).first()
            if existing_stream and existing_stream.id != stream_id:
                return jsonify({'success': False, 'error': 'RTSP stream with this URL already exists'}), 409
            stream.rtsp_url = data['rtsp_url']
        
        # Handle SOP updates
        if 'sops' in data:
            logger.info(f"Updating SOPs for stream {stream_id}. Current SOPs: {[sop.id for sop in stream.sops]}")
            logger.info(f"New SOP IDs: {data['sops']}")
            
            # Clear existing SOPs if provided
            if data['sops'] is None:
                stream.sops = []
            else:
                # Validate that all SOP IDs exist
                sop_ids = data['sops']
                sops = SOP.query.filter(SOP.id.in_(sop_ids)).all()
                logger.info(f"Found SOPs in database: {[sop.id for sop in sops]}")
                
                if len(sops) != len(sop_ids):
                    logger.error(f"Invalid SOP IDs. Requested: {sop_ids}, Found: {[sop.id for sop in sops]}")
                    return jsonify({'success': False, 'error': 'One or more SOP IDs are invalid'}), 400
                
                stream.sops = sops
                logger.info(f"Updated stream SOPs to: {[sop.id for sop in stream.sops]}")
        
        db.session.commit()
        logger.info(f"Successfully updated stream {stream_id}")
        
        return jsonify({
            'success': True,
            'message': 'Stream updated successfully',
            'stream': {
                'id': stream.id,
                'name': stream.name,
                'rtsp_url': stream.rtsp_url,
                'description': stream.description,
                'coco_link': stream.coco_link,
                'created_at': stream.created_at.strftime('%Y-%m-%d %H:%M:%S') if stream.created_at else None,
                'sops': [{'id': sop.id, 'name': sop.name} for sop in stream.sops]
            }
        })
    
    except SQLAlchemyError as e:
        logger.error(f"Database error while updating stream {stream_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while updating stream {stream_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@video_bp.route('/api/stream/<int:stream_id>', methods=['DELETE'])
def delete_stream(stream_id):
    """API endpoint to delete a specific RTSP stream"""
    try:
        stream = RTSPStream.query.get_or_404(stream_id)
        
        # Delete the stream - cascade will handle associated records
        db.session.delete(stream)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Stream deleted successfully'
        })
    
    except SQLAlchemyError as e:
        logger.error(f"Database error while deleting stream {stream_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while deleting stream {stream_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500
