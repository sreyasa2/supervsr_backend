import os
import base64
import logging
import requests
import json
from flask import current_app

logger = logging.getLogger(__name__)

def analyze_screenshot(image_path):
    """
    Analyze a screenshot using Google Gemini API
    
    Args:
        image_path (str): Path to the image file
    
    Returns:
        str: Analysis text from Gemini
    """
    api_key = current_app.config.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')
    if not api_key:
        logger.error("Gemini API key not found")
        raise ValueError("Gemini API key not configured")
    
    model_name = current_app.config.get('GEMINI_MODEL_NAME') or "gemini-pro-vision"
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
    try:
        # Read and encode the image
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Prepare the request payload
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": "Analyze this CCTV screenshot. Describe what you see, including any people, activities, objects, or anomalies. Focus on security-relevant details such as suspicious behavior, safety hazards, or unusual events."
                        },
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_base64
                            }
                        }
                    ]
                }
            ],
            "generation_config": {
                "temperature": 0.4,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048
            }
        }
        
        # Make the API request
        headers = {"Content-Type": "application/json"}
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        
        # Handle the response
        if response.status_code == 200:
            response_data = response.json()
            
            # Extract the text from the response
            try:
                analysis_text = response_data["candidates"][0]["content"]["parts"][0]["text"]
                return analysis_text
            except (KeyError, IndexError) as e:
                logger.error(f"Error parsing Gemini API response: {str(e)}")
                logger.debug(f"Response data: {response_data}")
                raise ValueError("Failed to parse Gemini API response")
        else:
            logger.error(f"Gemini API error: {response.status_code} - {response.text}")
            raise ValueError(f"Gemini API returned error: {response.status_code}")
    
    except Exception as e:
        logger.error(f"Error analyzing image with Gemini: {str(e)}")
        raise