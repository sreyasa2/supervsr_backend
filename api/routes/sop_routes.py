import logging
import os
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from api.models import SOP, AIModel, RTSPStream
from api import db
from sqlalchemy.exc import SQLAlchemyError

sop_bp = Blueprint('sop', __name__)
logger = logging.getLogger(__name__)

# Create logs directory if it doesn't exist
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

def log_structured_output(sop_id: int, structured_output: dict):
    """Log structured output to a text file."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_file = os.path.join(LOGS_DIR, 'structured_output.log')
    
    # Ensure structured_output is properly serialized
    if isinstance(structured_output, str):
        structured_output = json.loads(structured_output)
    
    log_entry = {
        'timestamp': timestamp,
        'sop_id': sop_id,
        'structured_output': structured_output
    }
    
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_entry, indent=2) + '\n---\n')

def validate_structured_output(schema):
    """Validate the structured_output schema format."""
    if schema is None:
        return True, None
        
    if not isinstance(schema, dict):
        return False, "Schema must be a JSON object"
        
    if "type" not in schema:
        return False, "Schema must have a 'type' field"
        
    valid_types = ["string", "number", "boolean", "array", "object"]
    if schema["type"] not in valid_types:
        return False, f"Invalid type. Must be one of: {', '.join(valid_types)}"
        
    if schema["type"] == "object":
        if "properties" not in schema:
            return False, "Object type must have 'properties' field"
        if not isinstance(schema["properties"], dict):
            return False, "'properties' must be a JSON object"
            
        # Validate each property recursively
        for prop_name, prop_schema in schema["properties"].items():
            is_valid, error = validate_structured_output(prop_schema)
            if not is_valid:
                return False, f"Invalid property '{prop_name}': {error}"
                
        # Validate required fields if present
        if "required" in schema:
            if not isinstance(schema["required"], list):
                return False, "'required' must be a list"
            for req_field in schema["required"]:
                if req_field not in schema["properties"]:
                    return False, f"Required field '{req_field}' not found in properties"
                    
    elif schema["type"] == "array":
        if "items" not in schema:
            return False, "Array type must have 'items' field"
        is_valid, error = validate_structured_output(schema["items"])
        if not is_valid:
            return False, f"Invalid array items: {error}"
            
    return True, None

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
    
    # Validate structured_output if provided
    if 'structured_output' in data:
        try:
            # Ensure structured_output is valid JSON
            if isinstance(data['structured_output'], str):
                data['structured_output'] = json.loads(data['structured_output'])
            is_valid, error = validate_structured_output(data['structured_output'])
            if not is_valid:
                return jsonify({'success': False, 'error': f'Invalid structured_output format: {error}'}), 400
        except json.JSONDecodeError:
            return jsonify({'success': False, 'error': 'structured_output must be valid JSON'}), 400
    
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
        
        # Log structured output if provided
        if sop.structured_output:
            log_structured_output(sop.id, sop.structured_output)
        
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
            try:
                # Ensure structured_output is valid JSON
                if isinstance(data['structured_output'], str):
                    data['structured_output'] = json.loads(data['structured_output'])
                # Validate structured_output
                is_valid, error = validate_structured_output(data['structured_output'])
                if not is_valid:
                    return jsonify({'success': False, 'error': f'Invalid structured_output format: {error}'}), 400
                sop.structured_output = data['structured_output']
                # Log the structured output
                log_structured_output(sop.id, sop.structured_output)
            except json.JSONDecodeError:
                return jsonify({'success': False, 'error': 'structured_output must be valid JSON'}), 400
            
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