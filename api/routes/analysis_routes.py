import logging
import datetime
from flask import Blueprint, request, jsonify, current_app
from api.models import AnalysisResult, RTSPStream, SOP
from api import db

analysis_bp = Blueprint('analysis', __name__)
logger = logging.getLogger(__name__)

@analysis_bp.route('/api/analysis', methods=['GET'])
def get_analyses():
    """API endpoint to list all analysis results"""
    # Get query parameters for filtering
    rtsp_id = request.args.get('rtsp_id', type=int)
    sop_id = request.args.get('sop_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Start with base query
    query = AnalysisResult.query
    
    # Apply filters if provided
    if rtsp_id:
        query = query.filter_by(rtsp_id=rtsp_id)
    if sop_id:
        query = query.filter_by(sop_id=sop_id)
    if start_date:
        try:
            start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(AnalysisResult.timestamp >= start_date)
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400
    if end_date:
        try:
            end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(AnalysisResult.timestamp <= end_date)
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400
    
    # Order by timestamp descending
    analyses = query.order_by(AnalysisResult.timestamp.desc()).all()
    
    analyses_data = [{
        'id': analysis.id,
        'rtsp_id': analysis.rtsp_id,
        'sop_id': analysis.sop_id,
        'timestamp': analysis.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'output': analysis.output,
        'rtsp_stream': {
            'id': analysis.rtsp_stream.id,
            'name': analysis.rtsp_stream.name
        } if analysis.rtsp_stream else None,
        'sop': {
            'id': analysis.sop.id,
            'name': analysis.sop.name
        } if analysis.sop else None
    } for analysis in analyses]
    
    return jsonify({'success': True, 'analyses': analyses_data})

@analysis_bp.route('/api/analysis/<int:analysis_id>', methods=['GET'])
def get_analysis(analysis_id):
    """API endpoint to get details of a specific analysis result"""
    analysis = AnalysisResult.query.get_or_404(analysis_id)
    
    return jsonify({
        'success': True,
        'analysis': {
            'id': analysis.id,
            'rtsp_id': analysis.rtsp_id,
            'sop_id': analysis.sop_id,
            'timestamp': analysis.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'output': analysis.output,
            'rtsp_stream': {
                'id': analysis.rtsp_stream.id,
                'name': analysis.rtsp_stream.name,
                'rtsp_url': analysis.rtsp_stream.rtsp_url
            } if analysis.rtsp_stream else None,
            'sop': {
                'id': analysis.sop.id,
                'name': analysis.sop.name,
                'description': analysis.sop.description
            } if analysis.sop else None
        }
    })

@analysis_bp.route('/api/analysis', methods=['POST'])
def create_analysis():
    """API endpoint to create a new analysis result"""
    data = request.json
    
    # Validate required fields
    if not data or not data.get('rtsp_id'):
        return jsonify({'success': False, 'error': 'Required fields missing: rtsp_id is required'}), 400
    
    try:
        # Verify RTSP stream exists
        rtsp_stream = RTSPStream.query.get(data['rtsp_id'])
        if not rtsp_stream:
            return jsonify({'success': False, 'error': 'RTSP stream not found'}), 404
        
        # Verify SOP exists if provided
        sop = None
        if data.get('sop_id'):
            sop = SOP.query.get(data['sop_id'])
            if not sop:
                return jsonify({'success': False, 'error': 'SOP not found'}), 404
        
        # Create new analysis record
        analysis = AnalysisResult(
            rtsp_id=data['rtsp_id'],
            sop_id=data.get('sop_id'),
            timestamp=datetime.datetime.utcnow(),
            output=data.get('output', '')
        )
        db.session.add(analysis)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'analysis_id': analysis.id,
            'message': 'Analysis result created successfully'
        })
    
    except Exception as e:
        logger.error(f"Error creating analysis result: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@analysis_bp.route('/api/analysis/<int:analysis_id>', methods=['PUT'])
def update_analysis(analysis_id):
    """API endpoint to update an existing analysis result"""
    analysis = AnalysisResult.query.get_or_404(analysis_id)
    data = request.json
    
    try:
        if 'output' in data:
            analysis.output = data['output']
        if 'sop_id' in data:
            # Verify SOP exists if provided
            if data['sop_id']:
                sop = SOP.query.get(data['sop_id'])
                if not sop:
                    return jsonify({'success': False, 'error': 'SOP not found'}), 404
            analysis.sop_id = data['sop_id']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Analysis result updated successfully'
        })
    
    except Exception as e:
        logger.error(f"Error updating analysis result: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@analysis_bp.route('/api/analysis/<int:analysis_id>', methods=['DELETE'])
def delete_analysis(analysis_id):
    """API endpoint to delete an analysis result"""
    analysis = AnalysisResult.query.get_or_404(analysis_id)
    
    try:
        db.session.delete(analysis)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Analysis result deleted successfully'
        })
    
    except Exception as e:
        logger.error(f"Error deleting analysis result: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500 