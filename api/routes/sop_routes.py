import logging
import datetime
from flask import Blueprint, request, jsonify, current_app
from api.models import SOP
from api import db

sop_bp = Blueprint('sop', __name__)
logger = logging.getLogger(__name__)

@sop_bp.route('/api/sops', methods=['GET'])
def get_sops():
    """API endpoint to list all SOPs"""
    sops = SOP.query.order_by(SOP.created_at.desc()).all()
    sops_data = [{
        'id': sop.id,
        'title': sop.title,
        'description': sop.description,
        'category': sop.category,
        'status': sop.status,
        'created_at': sop.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'updated_at': sop.updated_at.strftime('%Y-%m-%d %H:%M:%S')
    } for sop in sops]
    
    return jsonify({'success': True, 'sops': sops_data})

@sop_bp.route('/api/sops', methods=['POST'])
def create_sop():
    """API endpoint to create a new SOP"""
    data = request.json
    
    # Validate required fields
    if not data or not data.get('title'):
        return jsonify({'success': False, 'error': 'Required fields missing: title is required'}), 400
    
    try:
        # Create new SOP record
        sop = SOP(
            title=data.get('title'),
            description=data.get('description', ''),
            category=data.get('category', 'general'),
            status='active',
            content=data.get('content', '')
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
    sop = SOP.query.get_or_404(sop_id)
    
    return jsonify({
        'success': True,
        'sop': {
            'id': sop.id,
            'title': sop.title,
            'description': sop.description,
            'category': sop.category,
            'status': sop.status,
            'content': sop.content,
            'created_at': sop.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': sop.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }
    })

@sop_bp.route('/api/sops/<int:sop_id>', methods=['PUT'])
def update_sop(sop_id):
    """API endpoint to update an existing SOP"""
    sop = SOP.query.get_or_404(sop_id)
    data = request.json
    
    try:
        if 'title' in data:
            sop.title = data['title']
        if 'description' in data:
            sop.description = data['description']
        if 'category' in data:
            sop.category = data['category']
        if 'status' in data:
            sop.status = data['status']
        if 'content' in data:
            sop.content = data['content']
        
        sop.updated_at = datetime.datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'SOP updated successfully'
        })
    
    except Exception as e:
        logger.error(f"Error updating SOP: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@sop_bp.route('/api/sops/<int:sop_id>', methods=['DELETE'])
def delete_sop(sop_id):
    """API endpoint to delete a SOP"""
    sop = SOP.query.get_or_404(sop_id)
    
    try:
        db.session.delete(sop)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'SOP deleted successfully'
        })
    
    except Exception as e:
        logger.error(f"Error deleting SOP: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500 