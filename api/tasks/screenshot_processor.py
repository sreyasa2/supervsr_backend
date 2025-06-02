import logging
import os
import shutil
from datetime import datetime
from collections import defaultdict
from urllib.parse import urlparse

from api.utils.gcs_utils import GCSUtils
from api.tasks.stitcher import process_images
from api.services.gemini_service import analyze_screenshot_structured

logger = logging.getLogger(__name__)

class ScreenshotProcessor:
    def __init__(self, gcs_utils: GCSUtils, screenshots_per_grid: int = 6):
        """
        Initialize the ScreenshotProcessor.
        
        Args:
            gcs_utils: GCSUtils instance for GCS operations
            screenshots_per_grid: Number of screenshots needed for a grid (should be grid_rows * grid_cols)
        """
        self.gcs_utils = gcs_utils
        self.screenshots_per_grid = screenshots_per_grid
        self.screenshot_counts = defaultdict(int)
    
    def analyze_grid_with_gemini(self, grid_path: str) -> dict:
        """
        Analyze a grid image using Gemini service.
        
        Args:
            grid_path: Path to the grid image file
            
        Returns:
            dict: Analysis results from Gemini service
            
        Raises:
            Exception: If analysis fails
        """
        try:
            print(f"\n{'='*50}")  # Visual separator
            print(f"Starting Gemini analysis for grid: {grid_path}")
            print(f"{'='*50}\n")
            
            logger.info(f"Starting Gemini analysis for grid: {grid_path}")
            result = analyze_screenshot_structured(grid_path)
            
            print(f"\n{'='*50}")
            print(f"Gemini analysis result: {result}")
            print(f"{'='*50}\n")
            
            logger.info(f"Gemini analysis result: {result}")
            return result
        except Exception as e:
            print(f"\n{'='*50}")
            print(f"ERROR: Gemini analysis failed for grid {grid_path}: {e}")
            print(f"{'='*50}\n")
            
            logger.error(f"Gemini analysis failed for grid {grid_path}: {e}")
            raise
    
    def process_screenshot(self, stream_id: str, stream_name: str, frame_path: str, grid_rows: int = 2, grid_cols: int = 3) -> bool:
        """
        Process a single screenshot: save locally, upload to GCS, and create grid if needed.
        
        Args:
            stream_id: ID of the stream
            stream_name: Name of the stream
            frame_path: Path to the frame image
            grid_rows: Number of rows in the grid (default 2)
            grid_cols: Number of columns in the grid (default 3)
            
        Returns:
            bool: True if processing was successful
        """
        if not os.path.exists(frame_path):
            logger.error(f"Frame path does not exist: {frame_path}")
            return False
            
        try:
            # Validate grid dimensions
            if grid_rows * grid_cols != self.screenshots_per_grid:
                logger.warning(f"Grid dimensions ({grid_rows}x{grid_cols}) don't match screenshots_per_grid ({self.screenshots_per_grid})")
                self.screenshots_per_grid = grid_rows * grid_cols
            
            # Format current time
            current_time = datetime.now().strftime('%y-%m-%d--%H--%M--%S')
            file_name = f"screenshots/{stream_id}-{stream_name.replace(' ', '_')}-{current_time}.jpg"
            
            # Upload to GCS
            if not self.gcs_utils.upload_file(frame_path, file_name):
                logger.error(f"Failed to upload screenshot to GCS: {file_name}")
                return False
            
            # Save locally
            local_dir = os.path.join('uploads', 'screenshots')
            os.makedirs(local_dir, exist_ok=True)
            local_path = os.path.join(local_dir, os.path.basename(file_name))
            shutil.copy2(frame_path, local_path)
            
            # Increment counter and check if we need to create a grid
            self.screenshot_counts[stream_id] += 1
            
            if self.screenshot_counts[stream_id] >= self.screenshots_per_grid:
                success = self._create_grid(stream_id, stream_name, grid_rows, grid_cols)
                if not success:
                    logger.error(f"Failed to create grid for stream {stream_name}")
                    return False
            
            return True
            
        except Exception as e:
            logger.exception(f"Failed to process screenshot for {stream_name}: {e}")
            return False
    
    def _create_grid(self, stream_id: str, stream_name: str, grid_rows: int, grid_cols: int) -> bool:
        """
        Create a grid image from recent screenshots and analyze it with Gemini.
        
        Args:
            stream_id: ID of the stream
            stream_name: Name of the stream
            grid_rows: Number of rows in the grid
            grid_cols: Number of columns in the grid
            
        Returns:
            bool: True if grid creation and analysis were successful
        """
        try:
            # Get recent screenshot URLs
            recent_screenshot_urls = self.gcs_utils.get_recent_screenshot_urls(
                stream_id, 
                self.screenshots_per_grid
            )
            
            if len(recent_screenshot_urls) != self.screenshots_per_grid:
                logger.warning(f"Not enough screenshots for grid creation: {stream_name}")
                return False
            
            # Use the filename of the first screenshot for the grid filename
            first_url = recent_screenshot_urls[0]
            first_filename = os.path.basename(urlparse(first_url).path)
            grid_filename = f"grids/{first_filename.rsplit('.', 1)[0]}.png"
            grid_path = os.path.join('uploads', grid_filename)
            
            # Ensure grids directory exists
            os.makedirs(os.path.dirname(grid_path), exist_ok=True)
            
            # Process the images into a grid
            process_images(recent_screenshot_urls, grid_path, grid_rows, grid_cols)
            
            # Analyze the grid with Gemini
            try:
                analysis_result = self.analyze_grid_with_gemini(grid_path)
                logger.info(f"Grid analysis completed for {stream_name}: {analysis_result}")
            except Exception as e:
                logger.error(f"Grid analysis failed for {stream_name}: {e}")
                # Don't return False here as the grid was created successfully
                # Just log the error and continue
            
            # Reset counter
            self.screenshot_counts[stream_id] = 0
            return True
            
        except Exception as e:
            logger.exception(f"Grid creation failed for {stream_name}: {e}")
            return False
