# To run this code you need to install the following dependencies:
# pip install google-genai

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Set
import os
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

    def __init__(self, config: GeminiConfig):
        """Initialize the Gemini service."""
        self.config = config
        self.client = genai.Client(api_key=config.api_key)

    def _validate_image(self, image_path: Path) -> tuple[str, str]:
        if not image_path.exists():
            raise GeminiAnalysisError(f"Image file not found: {image_path}")
        image_type = imghdr.what(image_path)
        if not image_type:
            raise GeminiAnalysisError(f"File is not a valid image: {image_path}")
        if image_type not in self.SUPPORTED_IMAGE_TYPES:
            raise GeminiAnalysisError(
                f"Unsupported image type: {image_type}. "
                f"Supported types are: {', '.join(self.SUPPORTED_IMAGE_TYPES)}"
            )
        return image_type, self.MIME_TYPE_MAP[image_type]

    def _read_image(self, image_path: Path) -> tuple[bytes, str]:
        try:
            _, mime_type = self._validate_image(image_path)
            with open(image_path, "rb") as image_file:
                return image_file.read(), mime_type
        except Exception as e:
            raise GeminiAnalysisError(f"Failed to read image file: {e}")

    def _create_schema_from_sop(self, structured_output: dict) -> types.Schema:
        """Convert SOP structured_output to Gemini schema."""
        def convert_type_to_gemini_type(type_str: str) -> types.Type:
            type_map = {
                "string": types.Type.STRING,
                "number": types.Type.NUMBER,
                "boolean": types.Type.BOOLEAN,
                "array": types.Type.ARRAY,
                "object": types.Type.OBJECT
            }
            return type_map.get(type_str.lower(), types.Type.STRING)

        def build_schema(schema_dict: dict) -> types.Schema:
            if "type" not in schema_dict:
                return types.Schema(type=types.Type.OBJECT)
            schema_type = convert_type_to_gemini_type(schema_dict["type"])
            if schema_type == types.Type.OBJECT and "properties" in schema_dict:
                properties = {
                    key: build_schema(prop)
                    for key, prop in schema_dict["properties"].items()
                }
                return types.Schema(
                    type=schema_type,
                    properties=properties,
                    required=schema_dict.get("required", [])
                )
            elif schema_type == types.Type.ARRAY and "items" in schema_dict:
                return types.Schema(
                    type=schema_type,
                    items=build_schema(schema_dict["items"])
                )
            else:
                return types.Schema(type=schema_type)
        return build_schema(structured_output)

    def analyze_image_with_sop(self, image_path: str | Path, sop: 'SOP') -> dict:
        """
        Analyze an image using Google Gemini according to SOP's structured output schema.
        Args:
            image_path: Path to the image file
            sop: SOP model instance containing the prompt and structured_output schema
        Returns:
            dict: Structured analysis result matching the SOP's schema
        Raises:
            GeminiConfigError: If there's an issue with the configuration
            GeminiAnalysisError: If there's an error during analysis
            GeminiTimeoutError: If the API call times out
        """
        try:
            logger.info(f"Starting analysis for image: {image_path}")
            image_path = Path(image_path)
            image_bytes, mime_type = self._read_image(image_path)
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            inline_data=types.Blob(
                                mime_type=mime_type,
                                data=image_bytes
                            )
                        ),
                        types.Part(text=sop.prompt)
                    ],
                ),
            ]
            response_schema = self._create_schema_from_sop(sop.structured_output)
            generate_content_config = types.GenerateContentConfig(
                temperature=self.config.temperature,
                response_mime_type="application/json",
                response_schema=response_schema,
            )
            try:
                full_output = ""
                start_time = time.time()
                response_chunks = self.client.models.generate_content_stream(
                    model=self.config.model_name,
                    contents=contents,
                    config=generate_content_config,
                )
                for chunk in response_chunks:
                    if time.time() - start_time > self.config.timeout_seconds:
                        raise GeminiTimeoutError(f"API call timed out after {self.config.timeout_seconds} seconds")
                    full_output += chunk.text
                result = json.loads(full_output)
                return result
            except Exception as api_error:
                error_msg = str(api_error)
                logger.error(f"API Error: {error_msg}")
                if "deprecated" in error_msg.lower():
                    raise GeminiConfigError(f"Model {self.config.model_name} is deprecated. Please update to gemini-1.5-flash or newer.")
                raise
        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}")
            raise GeminiAnalysisError(f"Failed to analyze image: {str(e)}")
