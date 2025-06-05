import logging
import datetime
from flask import Blueprint, request, jsonify, current_app
from api.models import AIModel, SOP
from api import db
from sqlalchemy.exc import SQLAlchemyError

model_bp = Blueprint('model', __name__)
logger = logging.getLogger(__name__)

@model_bp.route('/api/models', methods=['GET'])
def get_models():
    """API endpoint to list all AI models"""
    try:
        models = AIModel.query.order_by(AIModel.name).all()
        models_data = [{
            'id': model.id,
            'name': model.name,
            'description': model.description,
            'link': model.link,
            'model_type': model.model_type,
            'sop_count': len(model.sops)
        } for model in models]
        
        return jsonify({'success': True, 'models': models_data})
    except SQLAlchemyError as e:
        logger.error(f"Database error while fetching models: {str(e)}")
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while fetching models: {str(e)}")
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@model_bp.route('/api/models', methods=['POST'])
def create_model():
    """API endpoint to create a new AI model"""
    try:
        data = request.json
        
        # Validate required fields
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        if not data.get('name'):
            return jsonify({'success': False, 'error': 'Required fields missing: name is required'}), 400
        
        # Check if model with this name already exists
        existing_model = AIModel.query.filter_by(name=data['name']).first()
        if existing_model:
            return jsonify({'success': False, 'error': 'AI model with this name already exists'}), 409
        
        # Create new AI model record
        model = AIModel(
            name=data['name'],
            description=data.get('description', ''),
            link=data.get('link', ''),
            model_type=data.get('model_type', '')
        )
        db.session.add(model)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'model_id': model.id,
            'message': 'AI model created successfully'
        })
    
    except SQLAlchemyError as e:
        logger.error(f"Database error while creating model: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while creating model: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@model_bp.route('/api/models/<int:model_id>', methods=['GET'])
def get_model(model_id):
    """API endpoint to get details of a specific AI model"""
    try:
        model = AIModel.query.get(model_id)
        if not model:
            return jsonify({
                'success': False,
                'error': f'Model with ID {model_id} not found'
            }), 404

        # Get all SOPs that use this model
        sops = SOP.query.filter_by(model_id=model_id).all()

        return jsonify({
            'success': True,
            'model': {
                'id': model.id,
                'name': model.name,
                'description': model.description,
                'link': model.link,
                'model_type': model.model_type,
                'sops': [{
                    'id': sop.id,
                    'name': sop.name,
                    'description': sop.description
                } for sop in sops],
                'type': model.type
            }
        })
    except SQLAlchemyError as e:
        logger.error(f"Database error while fetching model {model_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while fetching model {model_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@model_bp.route('/api/models/<int:model_id>', methods=['PUT'])
def update_model(model_id):
    """API endpoint to update an existing AI model"""
    try:
        model = AIModel.query.get_or_404(model_id)
        data = request.json
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided for update'}), 400
        
        if 'name' in data:
            # Check if new name conflicts with existing model
            existing_model = AIModel.query.filter_by(name=data['name']).first()
            if existing_model and existing_model.id != model_id:
                return jsonify({'success': False, 'error': 'AI model with this name already exists'}), 409
            model.name = data['name']
        if 'description' in data:
            model.description = data['description']
        if 'link' in data:
            model.link = data['link']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'AI model updated successfully'
        })
    
    except SQLAlchemyError as e:
        logger.error(f"Database error while updating model {model_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while updating model {model_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@model_bp.route('/api/models/<int:model_id>', methods=['DELETE'])
def delete_model(model_id):
    """API endpoint to delete an AI model"""
    try:
        model = AIModel.query.get_or_404(model_id)
        
        # Check if model is being used by any SOPs
        sops_using_model = SOP.query.filter_by(model_id=model_id).first()
        if sops_using_model:
            return jsonify({
                'success': False,
                'error': 'Cannot delete model that is being used by SOPs. Please update or delete the associated SOPs first.'
            }), 409
        
        db.session.delete(model)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'AI model deleted successfully'
        })
    
    except SQLAlchemyError as e:
        logger.error(f"Database error while deleting model {model_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while deleting model {model_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500