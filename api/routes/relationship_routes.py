import logging
from flask import Blueprint, request, jsonify
from api.models import RTSPStream, SOP
from api import db
from sqlalchemy.exc import SQLAlchemyError

relationship_bp = Blueprint('relationship', __name__)
logger = logging.getLogger(__name__)

@relationship_bp.route('/api/stream/<int:stream_id>/sops', methods=['GET'])
def get_stream_sops(stream_id):
    """Get all SOPs associated with a stream"""
    try:
        stream = RTSPStream.query.get_or_404(stream_id)
        return jsonify({
            'success': True,
            'sops': [{
                'id': sop.id,
                'name': sop.name,
                'description': sop.description
            } for sop in stream.sops]
        })
    except SQLAlchemyError as e:
        logger.error(f"Database error while fetching stream SOPs: {str(e)}")
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500

@relationship_bp.route('/api/sop/<int:sop_id>/streams', methods=['GET'])
def get_sop_streams(sop_id):
    """Get all streams associated with a SOP"""
    try:
        sop = SOP.query.get_or_404(sop_id)
        return jsonify({
            'success': True,
            'streams': [{
                'id': stream.id,
                'name': stream.name,
                'rtsp_url': stream.rtsp_url
            } for stream in sop.rtsp_streams]
        })
    except SQLAlchemyError as e:
        logger.error(f"Database error while fetching SOP streams: {str(e)}")
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500

@relationship_bp.route('/api/stream/<int:stream_id>/sop/<int:sop_id>', methods=['POST'])
def add_stream_sop(stream_id, sop_id):
    """Add a SOP to a stream"""
    try:
        stream = RTSPStream.query.get_or_404(stream_id)
        sop = SOP.query.get_or_404(sop_id)
        
        if sop in stream.sops:
            return jsonify({
                'success': False,
                'error': 'SOP is already associated with this stream'
            }), 409
        
        stream.sops.append(sop)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'SOP added to stream successfully'
        })
    except SQLAlchemyError as e:
        logger.error(f"Database error while adding SOP to stream: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500

@relationship_bp.route('/api/stream/<int:stream_id>/sop/<int:sop_id>', methods=['DELETE'])
def remove_stream_sop(stream_id, sop_id):
    """Remove a SOP from a stream"""
    try:
        stream = RTSPStream.query.get_or_404(stream_id)
        sop = SOP.query.get_or_404(sop_id)
        
        if sop not in stream.sops:
            return jsonify({
                'success': False,
                'error': 'SOP is not associated with this stream'
            }), 404
        
        stream.sops.remove(sop)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'SOP removed from stream successfully'
        })
    except SQLAlchemyError as e:
        logger.error(f"Database error while removing SOP from stream: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500

@relationship_bp.route('/api/stream/<int:stream_id>/sops/batch', methods=['POST'])
def batch_update_stream_sops(stream_id):
    """Batch update SOPs for a stream"""
    try:
        stream = RTSPStream.query.get_or_404(stream_id)
        data = request.json
        
        if not data or 'sop_ids' not in data:
            return jsonify({
                'success': False,
                'error': 'No SOP IDs provided'
            }), 400
        
        # Validate all SOP IDs exist
        sop_ids = data['sop_ids']
        sops = SOP.query.filter(SOP.id.in_(sop_ids)).all()
        
        if len(sops) != len(sop_ids):
            return jsonify({
                'success': False,
                'error': 'One or more SOP IDs are invalid'
            }), 400
        
        # Update relationships
        stream.sops = sops
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Stream SOPs updated successfully',
            'sops': [{
                'id': sop.id,
                'name': sop.name
            } for sop in stream.sops]
        })
    except SQLAlchemyError as e:
        logger.error(f"Database error while batch updating stream SOPs: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500 