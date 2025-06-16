#!/usr/bin/env python
"""
Example script for testing the CCTV Analysis API
This script demonstrates how to use the API to:
1. Upload a video
2. Extract screenshots
3. Analyze screenshots with Gemini AI
"""
import os
import sys
import json
import requests
import logging
import time
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API configuration
API_BASE_URL = 'http://localhost:8000'

def health_check():
    """Check if the API is running"""
    try:
        response = requests.get(urljoin(API_BASE_URL, '/health'))
        response.raise_for_status()
        return response.json()['status'] == 'ok'
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return False

def list_videos():
    """List all videos in the system"""
    try:
        response = requests.get(urljoin(API_BASE_URL, '/api/videos'))
        response.raise_for_status()
        return response.json()['videos']
    except Exception as e:
        logger.error(f"Error listing videos: {str(e)}")
        return []

def upload_video(video_path):
    """Upload a video file for processing"""
    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        return None
    
    try:
        with open(video_path, 'rb') as f:
            files = {'video': f}
            response = requests.post(urljoin(API_BASE_URL, '/api/videos'), files=files)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Error uploading video: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error uploading video: {str(e)}")
        return None

def get_screenshots(video_id):
    """Get screenshots for a video"""
    try:
        response = requests.get(urljoin(API_BASE_URL, f'/api/video/{video_id}/screenshots'))
        response.raise_for_status()
        return response.json()['screenshots']
    except Exception as e:
        logger.error(f"Error getting screenshots: {str(e)}")
        return []

def analyze_screenshot(screenshot_id):
    """Analyze a screenshot with Gemini AI"""
    try:
        response = requests.post(urljoin(API_BASE_URL, f'/api/screenshot/{screenshot_id}/analyze'))
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error analyzing screenshot: {str(e)}")
        return None

def get_analysis(screenshot_id):
    """Get analysis results for a screenshot"""
    try:
        response = requests.get(urljoin(API_BASE_URL, f'/api/screenshot/{screenshot_id}/analysis'))
        if response.status_code == 200:
            return response.json()['analysis']
        else:
            logger.error(f"Error getting analysis: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error getting analysis: {str(e)}")
        return None

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <video_file>")
        return
    
    video_path = sys.argv[1]
    
    # Check if API is running
    if not health_check():
        logger.error("API is not running. Please start the API server first.")
        return
    
    # Upload video
    logger.info(f"Uploading video: {video_path}")
    result = upload_video(video_path)
    if not result:
        return
    
    video_id = result['video_id']
    logger.info(f"Video uploaded successfully. ID: {video_id}")
    
    # Wait for processing
    logger.info("Waiting for screenshot extraction...")
    time.sleep(2)
    
    # Get screenshots
    screenshots = get_screenshots(video_id)
    logger.info(f"Found {len(screenshots)} screenshots")
    
    if not screenshots:
        return
    
    # Analyze the first screenshot
    screenshot_id = screenshots[0]['id']
    logger.info(f"Analyzing screenshot {screenshot_id}...")
    
    # Check if the screenshot has already been analyzed
    if screenshots[0]['has_analysis']:
        logger.info("Screenshot already has analysis. Getting results...")
        analysis = get_analysis(screenshot_id)
    else:
        # Analyze the screenshot
        result = analyze_screenshot(screenshot_id)
        if result:
            logger.info("Analysis complete.")
            analysis = {'text': result['analysis']}
        else:
            logger.error("Analysis failed.")
            return
    
    # Print analysis results
    if analysis:
        print("\n==== ANALYSIS RESULTS ====")
        print(analysis['text'])
        print("=========================\n")

if __name__ == '__main__':
    main()