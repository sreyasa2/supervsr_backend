#!/usr/bin/env python
"""
CLI tool for testing CCTV analysis functionality
"""
import os
import sys
import argparse
import logging
from api import create_app
from api.models import Video, Screenshot, AnalysisResult
from api.services.video_processor import extract_screenshots
from api.services.gemini_service import analyze_screenshot
from api import db

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_video(video_path, app):
    """Process a video file and extract screenshots"""
    with app.app_context():
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            return None
        
        # Create a Video record
        filename = os.path.basename(video_path)
        video = Video(
            filename=filename,
            original_filename=filename,
            file_path=os.path.abspath(video_path),
            filesize=os.path.getsize(video_path)
        )
        db.session.add(video)
        db.session.commit()
        
        logger.info(f"Created video record with ID: {video.id}")
        
        # Extract screenshots
        screenshots = extract_screenshots(video.id)
        logger.info(f"Extracted {len(screenshots)} screenshots")
        
        return video

def analyze_screenshots(video_id, app, limit=3):
    """Analyze screenshots for a given video"""
    with app.app_context():
        screenshots = Screenshot.query.filter_by(video_id=video_id).limit(limit).all()
        
        if not screenshots:
            logger.error(f"No screenshots found for video ID: {video_id}")
            return
        
        for screenshot in screenshots:
            logger.info(f"Analyzing screenshot {screenshot.id} at {screenshot.timestamp}s")
            
            try:
                analysis_text = analyze_screenshot(screenshot.file_path)
                
                # Create analysis record
                analysis = AnalysisResult(
                    screenshot_id=screenshot.id,
                    analysis_text=analysis_text
                )
                db.session.add(analysis)
                db.session.commit()
                
                logger.info(f"Analysis created with ID: {analysis.id}")
                logger.info(f"Analysis result: {analysis_text[:100]}...")
            
            except Exception as e:
                logger.error(f"Error analyzing screenshot: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='CCTV Analysis CLI Tool')
    parser.add_argument('--video', '-v', help='Path to the video file to process')
    parser.add_argument('--analyze', '-a', type=int, help='Analyze screenshots for video ID')
    parser.add_argument('--limit', '-l', type=int, default=3, 
                        help='Maximum number of screenshots to analyze (default: 3)')
    
    args = parser.parse_args()
    
    if not args.video and not args.analyze:
        parser.print_help()
        return
    
    # Create Flask app
    app = create_app()
    
    if args.video:
        video = process_video(args.video, app)
        if video and args.analyze is None:
            # If --analyze wasn't explicitly specified, but we processed a video, analyze it
            analyze_screenshots(video.id, app, args.limit)
    
    elif args.analyze:
        analyze_screenshots(args.analyze, app, args.limit)

if __name__ == '__main__':
    main()