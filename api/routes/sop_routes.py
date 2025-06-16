import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from api.models import SOP, AIModel, RTSPStream
from api import db
from sqlalchemy.exc import SQLAlchemyError

sop_bp = Blueprint('sop', __name__)
logger = logging.getLogger(__name__)

@sop_bp.route('/api/sops', methods=['GET'])
def get_sops():
    """API endpoint to list all SOPs"""
    try:
        sops = SOP.query.all()
        sops_data = [{
            'id': sop.id,
            'name': sop.name,
            'description': sop.description,
            'model_id': sop.model_id,
            'prompt': sop.prompt,
            'frequency': sop.frequency,
            'structured_output': sop.structured_output,
            'model': sop.model.name if sop.model else None
        } for sop in sops]
        
        return jsonify({'success': True, 'sops': sops_data})
    except SQLAlchemyError as e:
        logger.error(f"Database error while fetching SOPs: {str(e)}")
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while fetching SOPs: {str(e)}")
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@sop_bp.route('/api/sops', methods=['POST'])
def create_sop():
    """API endpoint to create a new SOP"""
    data = request.json
    
    # Validate required fields
    if not data or not data.get('name'):
        return jsonify({'success': False, 'error': 'Required fields missing: name is required'}), 400
    
    try:
        # Create new SOP record
        sop = SOP(
            name=data.get('name'),
            description=data.get('description', ''),
            model_id=data.get('model_id'),
            prompt=data.get('prompt', ''),
            frequency=data.get('frequency', 10),  # Default to 10 if not provided
            structured_output=data.get('structured_output')
        )
        db.session.add(sop)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'sop_id': sop.id,
            'message': 'SOP created successfully'
        })
    
    except Exception as e:
        logger.error(f"Error creating SOP: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@sop_bp.route('/api/sops/<int:sop_id>', methods=['GET'])
def get_sop(sop_id):
    """API endpoint to get details of a specific SOP"""
    try:
        sop = SOP.query.get_or_404(sop_id)
        return jsonify({
            'success': True,
            'sop': {
                'id': sop.id,
                'name': sop.name,
                'description': sop.description,
                'model_id': sop.model_id,
                'prompt': sop.prompt,
                'frequency': sop.frequency,
                'structured_output': sop.structured_output,
                'model': sop.model.name if sop.model else None,
                'rtsp_streams': [{'id': stream.id, 'name': stream.name} for stream in sop.rtsp_streams]
            }
        })
    except SQLAlchemyError as e:
        logger.error(f"Database error while fetching SOP {sop_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while fetching SOP {sop_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@sop_bp.route('/api/sops/<int:sop_id>', methods=['PUT'])
def update_sop(sop_id):
    """API endpoint to update an existing SOP"""
    try:
        sop = SOP.query.get_or_404(sop_id)
        data = request.json
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided for update'}), 400
            
        if 'name' in data:
            sop.name = data['name']
        if 'description' in data:
            sop.description = data['description']
        if 'model_id' in data:
            sop.model_id = data['model_id']
        if 'prompt' in data:
            sop.prompt = data['prompt']
        if 'frequency' in data:
            sop.frequency = data['frequency']
        if 'structured_output' in data:
            sop.structured_output = data['structured_output']
            
        # Handle RTSP stream updates
        if 'rtsp_streams' in data:
            logger.info(f"Updating RTSP streams for SOP {sop_id}. Current streams: {[stream.id for stream in sop.rtsp_streams]}")
            logger.info(f"New stream IDs: {data['rtsp_streams']}")
            
            # Clear existing streams if provided
            if data['rtsp_streams'] is None:
                sop.rtsp_streams = []
            else:
                # Validate that all stream IDs exist
                stream_ids = data['rtsp_streams']
                streams = RTSPStream.query.filter(RTSPStream.id.in_(stream_ids)).all()
                logger.info(f"Found streams in database: {[stream.id for stream in streams]}")
                
                if len(streams) != len(stream_ids):
                    logger.error(f"Invalid stream IDs. Requested: {stream_ids}, Found: {[stream.id for stream in streams]}")
                    return jsonify({'success': False, 'error': 'One or more stream IDs are invalid'}), 400
                
                sop.rtsp_streams = streams
                logger.info(f"Updated SOP streams to: {[stream.id for stream in sop.rtsp_streams]}")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'SOP updated successfully',
            'sop': {
                'id': sop.id,
                'name': sop.name,
                'description': sop.description,
                'model_id': sop.model_id,
                'prompt': sop.prompt,
                'frequency': sop.frequency,
                'structured_output': sop.structured_output,
                'rtsp_streams': [{'id': stream.id, 'name': stream.name} for stream in sop.rtsp_streams]
            }
        })
    
    except SQLAlchemyError as e:
        logger.error(f"Database error while updating SOP {sop_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while updating SOP {sop_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@sop_bp.route('/api/sops/<int:sop_id>', methods=['DELETE'])
def delete_sop(sop_id):
    """API endpoint to delete a SOP"""
    try:
        sop = SOP.query.get_or_404(sop_id)
        db.session.delete(sop)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'SOP deleted successfully'
        })
    
    except SQLAlchemyError as e:
        logger.error(f"Database error while deleting SOP {sop_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while deleting SOP {sop_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500 