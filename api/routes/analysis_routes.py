import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from api.models import Analysis, RTSPStream, SOP
from api import db
from sqlalchemy.exc import SQLAlchemyError

analysis_bp = Blueprint('analysis', __name__)
logger = logging.getLogger(__name__)

@analysis_bp.route('/api/analysis', methods=['GET'])
def get_analysis_list():
    """API endpoint to list all analysis with optional filtering"""
    try:
        query = Analysis.query
        
        # Filter by start date if provided
        start_date = request.args.get('start_date')
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
                query = query.filter(Analysis.timestamp >= start_date)
            except ValueError:
                return jsonify({'success': False, 'error': 'Invalid start date format. Use YYYY-MM-DD'}), 400
        
        # Filter by end date if provided
        end_date = request.args.get('end_date')
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d')
                query = query.filter(Analysis.timestamp <= end_date)
            except ValueError:
                return jsonify({'success': False, 'error': 'Invalid end date format. Use YYYY-MM-DD'}), 400
        
        # Get all analysis ordered by timestamp
        analysis_list = query.order_by(Analysis.timestamp.desc()).all()
        
        analysis_data = [{
            'id': analysis.id,
            'rtsp_id': analysis.rtsp_id,
            'sop_id': analysis.sop_id,
            'timestamp': analysis.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'output': analysis.output
        } for analysis in analysis_list]
        
        return jsonify({'success': True, 'analysis': analysis_data})
    except SQLAlchemyError as e:
        logger.error(f"Database error while fetching analysis: {str(e)}")
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while fetching analysis: {str(e)}")
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@analysis_bp.route('/api/analysis/<int:analysis_id>', methods=['GET'])
def get_analysis(analysis_id):
    """API endpoint to get details of a specific analysis"""
    try:
        analysis = Analysis.query.get_or_404(analysis_id)
        
        return jsonify({
            'success': True,
            'analysis': {
                'id': analysis.id,
                'rtsp_id': analysis.rtsp_id,
                'sop_id': analysis.sop_id,
                'timestamp': analysis.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'output': analysis.output
            }
        })
    except SQLAlchemyError as e:
        logger.error(f"Database error while fetching analysis {analysis_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while fetching analysis {analysis_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@analysis_bp.route('/api/analysis', methods=['POST'])
def create_analysis():
    """API endpoint to create a new analysis"""
    try:
        data = request.json
        
        # Validate required fields
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        if not data.get('rtsp_id'):
            return jsonify({'success': False, 'error': 'Required fields missing: rtsp_id is required'}), 400
        if not data.get('output'):
            return jsonify({'success': False, 'error': 'Required fields missing: output is required'}), 400
        
        # Create new analysis record
        analysis = Analysis(
            rtsp_id=data['rtsp_id'],
            sop_id=data.get('sop_id'),
            timestamp=datetime.now(),
            output=data['output']
        )
        db.session.add(analysis)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'analysis_id': analysis.id,
            'message': 'Analysis created successfully'
        })
    
    except SQLAlchemyError as e:
        logger.error(f"Database error while creating analysis: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while creating analysis: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@analysis_bp.route('/api/analysis/<int:analysis_id>', methods=['PUT'])
def update_analysis(analysis_id):
    """API endpoint to update an existing analysis"""
    try:
        analysis = Analysis.query.get_or_404(analysis_id)
        data = request.json
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided for update'}), 400
        
        if 'output' in data:
            analysis.output = data['output']
        if 'sop_id' in data:
            analysis.sop_id = data['sop_id']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Analysis updated successfully'
        })
    
    except SQLAlchemyError as e:
        logger.error(f"Database error while updating analysis {analysis_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while updating analysis {analysis_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@analysis_bp.route('/api/analysis/<int:analysis_id>', methods=['DELETE'])
def delete_analysis(analysis_id):
    """API endpoint to delete an analysis"""
    try:
        analysis = Analysis.query.get_or_404(analysis_id)
        
        db.session.delete(analysis)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Analysis deleted successfully'
        })
    
    except SQLAlchemyError as e:
        logger.error(f"Database error while deleting analysis {analysis_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error while deleting analysis {analysis_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500 