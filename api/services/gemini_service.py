# To run this code you need to install the following dependencies:
# pip install google-genai

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Set
import os
import base64
import logging
import json
import imghdr
import time
from flask import current_app
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class GeminiConfigError(Exception):
    """Raised when there's an issue with Gemini configuration."""
    pass

class GeminiAnalysisError(Exception):
    """Raised when there's an error during image analysis."""
    pass

class GeminiTimeoutError(GeminiAnalysisError):
    """Raised when the Gemini API call times out."""
    pass

@dataclass
class GeminiConfig:
    """Configuration for Gemini service."""
    api_key: str
    model_name: str = "gemini-2.0-flash"
    temperature: float = 1.0
    timeout_seconds: int = 30  # Default timeout of 30 seconds

    @classmethod
    def from_app_config(cls) -> 'GeminiConfig':
        """Create config from Flask app configuration."""
        api_key = current_app.config.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise GeminiConfigError("Gemini API key not configured")
        
        model_name = current_app.config.get('GEMINI_MODEL_NAME', "gemini-2.0-flash")
        timeout = current_app.config.get('GEMINI_TIMEOUT_SECONDS', 30)
        return cls(api_key=api_key, model_name=model_name, timeout_seconds=timeout)

class DecanterAnalysisResult:
    """Structured result of decanter analysis."""
    def __init__(self, data: Dict[str, bool]):
        self.is_being_opened = data["Decanter being opened"]
        self.is_already_opened = data["Decanter already opened"]
        self.is_being_closed = data["Decanter being closed"]
        self.is_already_closed = data["Decanter already closed"]

    @classmethod
    def from_dict(cls, data: Dict[str, bool]) -> 'DecanterAnalysisResult':
        """Create result from dictionary."""
        return cls(data)

class GeminiService:
    """Service for interacting with Google's Gemini API."""
    
    SUPPORTED_IMAGE_TYPES: Set[str] = {'jpeg', 'jpg', 'png', 'gif', 'bmp'}
    MIME_TYPE_MAP: Dict[str, str] = {
        'jpeg': 'image/jpeg',
        'jpg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'bmp': 'image/bmp'
    }
    
    RESPONSE_SCHEMA = types.Schema(
        type=types.Type.OBJECT,
        required=[
            "Decanter being opened",
            "Decanter already opened",
            "Decanter being closed",
            "Decanter already closed",
        ],
        properties={
            "Decanter being opened": types.Schema(type=types.Type.BOOLEAN),
            "Decanter already opened": types.Schema(type=types.Type.BOOLEAN),
            "Decanter being closed": types.Schema(type=types.Type.BOOLEAN),
            "Decanter already closed": types.Schema(type=types.Type.BOOLEAN),
        },
    )

    def __init__(self, config: GeminiConfig):
        """Initialize the Gemini service."""
        self.config = config
        self.client = genai.Client(api_key=config.api_key)

    def _validate_image(self, image_path: Path) -> tuple[str, str]:
        """
        Validate image file and return its type and MIME type.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            tuple: (image_type, mime_type)
            
        Raises:
            GeminiAnalysisError: If file is not a valid image or type is not supported
        """
        if not image_path.exists():
            raise GeminiAnalysisError(f"Image file not found: {image_path}")
            
        # Check if file is a valid image
        image_type = imghdr.what(image_path)
        if not image_type:
            raise GeminiAnalysisError(f"File is not a valid image: {image_path}")
            
        # Check if image type is supported
        if image_type not in self.SUPPORTED_IMAGE_TYPES:
            raise GeminiAnalysisError(
                f"Unsupported image type: {image_type}. "
                f"Supported types are: {', '.join(self.SUPPORTED_IMAGE_TYPES)}"
            )
            
        return image_type, self.MIME_TYPE_MAP[image_type]

    def _read_image(self, image_path: Path) -> tuple[bytes, str]:
        """
        Read image file and return its bytes and MIME type.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            tuple: (image_bytes, mime_type)
            
        Raises:
            GeminiAnalysisError: If there's an error reading the file
        """
        try:
            _, mime_type = self._validate_image(image_path)
            with open(image_path, "rb") as image_file:
                return image_file.read(), mime_type
        except Exception as e:
            raise GeminiAnalysisError(f"Failed to read image file: {e}")

    def _create_prompt_content(self, image_bytes: bytes, mime_type: str) -> list[types.Content]:
        """Create the prompt content for Gemini."""
        return [
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        inline_data=types.Blob(
                            mime_type=mime_type,
                            data=image_bytes
                        )
                    ),
                    types.Part(
                        text=(
                            "This is an image of a decanter in an ethanol distillery. "
                            "Focus on the only decanter clearly visible and centered in the image, "
                            "and respond with JSON containing the following boolean fields: "
                            "\"Decanter being opened\", \"Decanter already opened\", "
                            "\"Decanter being closed\", \"Decanter already closed\"."
                        )
                    ),
                ],
            ),
        ]

    def _parse_response(self, response_text: str) -> DecanterAnalysisResult:
        """Parse the Gemini response into a structured result."""
        try:
            logger.info("Attempting to parse JSON response...")
            data = json.loads(response_text)
            logger.info(f"JSON parsed successfully: {data}")
            return DecanterAnalysisResult.from_dict(data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Gemini response: {e}")
            logger.debug(f"Raw output: {response_text}")
            raise GeminiAnalysisError("Gemini response was not valid JSON")

    def analyze_screenshot(self, image_path: str | Path) -> DecanterAnalysisResult:
        """
        Analyze a screenshot using Google Gemini and return structured output.
        
        Args:
            image_path: Path to the image file. Supported formats: JPEG, PNG, GIF, BMP
            
        Returns:
            DecanterAnalysisResult: Structured analysis result
            
        Raises:
            GeminiConfigError: If there's an issue with the configuration
            GeminiAnalysisError: If there's an error during analysis
            GeminiTimeoutError: If the API call times out
        """
        try:
            logger.info(f"Starting analysis for image: {image_path}")
            image_path = Path(image_path)
            logger.info("Reading image file...")
            image_bytes, mime_type = self._read_image(image_path)
            logger.info(f"Image read successfully. Size: {len(image_bytes)} bytes, Type: {mime_type}")
            
            logger.info("Creating prompt content...")
            contents = self._create_prompt_content(image_bytes, mime_type)
            logger.info("Prompt content created successfully")

            generate_content_config = types.GenerateContentConfig(
                temperature=self.config.temperature,
                response_mime_type="application/json",
                response_schema=self.RESPONSE_SCHEMA,
            )
            logger.info(f"Using model: {self.config.model_name} with temperature: {self.config.temperature}")

            try:
                logger.info("Starting Gemini API call...")
                full_output = ""
                start_time = time.time()
                response_chunks = self.client.models.generate_content_stream(
                    model=self.config.model_name,
                    contents=contents,
                    config=generate_content_config,
                )
                
                logger.info("Processing response chunks...")
                chunk_count = 0
                for chunk in response_chunks:
                    # Check for timeout
                    if time.time() - start_time > self.config.timeout_seconds:
                        raise GeminiTimeoutError(f"API call timed out after {self.config.timeout_seconds} seconds")
                    
                    chunk_count += 1
                    full_output += chunk.text
                    if chunk_count % 10 == 0:  # Log every 10 chunks
                        logger.info(f"Processed {chunk_count} chunks...")
                
                logger.info(f"Response processing complete. Total chunks: {chunk_count}")
                logger.info("Parsing response...")
                result = self._parse_response(full_output)
                logger.info("Response parsed successfully")
                return result

            except Exception as api_error:
                error_msg = str(api_error)
                logger.error(f"API Error: {error_msg}")
                if "deprecated" in error_msg.lower():
                    logger.error(f"Model {self.config.model_name} is deprecated. Please update to a newer model.")
                    raise GeminiConfigError(f"Model {self.config.model_name} is deprecated. Please update to gemini-1.5-flash or newer.")
                raise

        except Exception as e:
            if isinstance(e, (GeminiConfigError, GeminiAnalysisError, GeminiTimeoutError)):
                raise
            logger.error(f"Unexpected error during Gemini analysis: {e}")
            raise GeminiAnalysisError(f"Analysis failed: {str(e)}")

def analyze_screenshot_structured(image_path: str | Path) -> Dict[str, bool]:
    """
    Analyze a screenshot using Google Gemini and return structured JSON output.
    
    Args:
        image_path: Path to the image file. Supported formats: JPEG, PNG, GIF, BMP
    
    Returns:
        dict: Parsed JSON object with boolean fields
        
    Raises:
        GeminiConfigError: If there's an issue with the configuration
        GeminiAnalysisError: If there's an error during analysis
    """
    config = GeminiConfig.from_app_config()
    service = GeminiService(config)
    result = service.analyze_screenshot(image_path)
    return {
        "Decanter being opened": result.is_being_opened,
        "Decanter already opened": result.is_already_opened,
        "Decanter being closed": result.is_being_closed,
        "Decanter already closed": result.is_already_closed,
    }
