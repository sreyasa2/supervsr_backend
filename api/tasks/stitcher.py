import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
from pathlib import Path
import logging
import requests
from io import BytesIO
from typing import List, Tuple

# Configure logging
logger = logging.getLogger(__name__)

# Constants
LABEL_MARGIN = 60
BORDER_SIZE = 10

def download_image(url: str) -> Image.Image:
    """
    Downloads an image from a URL (GCS bucket link).
    
    Args:
        url: URL of the image to download
        
    Returns:
        PIL Image object
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        logger.error(f"Error downloading image from {url}: {str(e)}")
        raise

def annotate_image(image: Image.Image, name: str) -> Image.Image:
    """
    Annotates a single image with a label bar at the top.
    
    Args:
        image: PIL Image to annotate
        name: Name to display in the label
        
    Returns:
        Annotated PIL Image
    """
    width, height = image.size
    
    # Create new image with label margin
    annotated = Image.new('RGB', (width, height + LABEL_MARGIN), 'white')
    
    # Draw black label bar
    draw = ImageDraw.Draw(annotated)
    draw.rectangle([(0, 0), (width, LABEL_MARGIN)], fill='black')
    
    # Add text
    try:
        font = ImageFont.truetype("Arial", 30)
    except IOError:
        font = ImageFont.load_default()
    
    # Calculate text position for center alignment
    text_bbox = draw.textbbox((0, 0), name, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_x = (width - text_width) // 2
    text_y = (LABEL_MARGIN - 30) // 2
    
    # Draw text
    draw.text((text_x, text_y), name, fill='white', font=font)
    
    # Paste original image below label
    annotated.paste(image, (0, LABEL_MARGIN))
    
    return annotated

def stitch_images(images: List[Tuple[str, Image.Image]], output_path: str, grid_rows: int, grid_cols: int, store_locally: bool = True):
    """
    Stitches a batch of images into a single grid image.
    
    Args:
        images: List of (name, PIL Image) tuples
        output_path: Path to save the stitched image
        grid_rows: Number of rows in the grid
        grid_cols: Number of columns in the grid
        store_locally: Whether to save the image locally
    """
    if not images:
        return None
    
    # Get dimensions of first image
    single_width, single_height = images[0][1].size
    
    # Calculate total dimensions
    total_width = grid_cols * single_width + (grid_cols - 1) * BORDER_SIZE
    total_height = grid_rows * single_height + (grid_rows - 1) * BORDER_SIZE
    
    # Create new image
    stitched = Image.new('RGB', (total_width, total_height), 'white')
    
    # Place each image in the grid
    for i, (_, image) in enumerate(images):
        if i >= grid_rows * grid_cols:
            break
        
        row = i // grid_cols
        col = i % grid_cols
        x = col * (single_width + BORDER_SIZE)
        y = row * (single_height + BORDER_SIZE)
        stitched.paste(image, (x, y))
    
    # Save the stitched image if requested
    if store_locally:
        stitched.save(output_path)
        logger.info(f"✅ Saved stitched image: {output_path}")
    
    return stitched

def process_images(image_urls: List[str], output_path: str, grid_rows: int = 2, grid_cols: int = 3, store_locally=True):
    """
    Downloads images from GCS bucket links and creates a grid image.
    
    Args:
        image_urls: List of GCS bucket URLs for the images
        output_path: Path to save the stitched image
        grid_rows: Number of rows in the grid (default: 2)
        grid_cols: Number of columns in the grid (default: 3)
        store_locally: Whether to save the image locally (default: True)
    """
    if not image_urls:
        raise ValueError("No image URLs provided")
    
    logger.info(f"📥 Processing {len(image_urls)} images into a {grid_rows}x{grid_cols} grid")
    
    # Download and annotate images
    processed_images = []
    for i, url in enumerate(image_urls):
        try:
            # Download image
            image = download_image(url)
            
            # Get filename from URL
            name = Path(url).stem
            
            # Annotate image
            annotated = annotate_image(image, name)
            processed_images.append((name, annotated))
            
            logger.info(f"✅ Processed image {i+1}/{len(image_urls)}: {name}")
            
        except Exception as e:
            logger.error(f"❌ Error processing image {url}: {str(e)}")
            continue
    
    if not processed_images:
        raise ValueError("No images were successfully processed")
    
    # Create grid image
    stitched = stitch_images(processed_images, output_path, grid_rows, grid_cols, store_locally=store_locally)
    
    # Always return the stitched image object for further use (e.g., upload to GCS)
    return stitched

if __name__ == "__main__":
    # Example usage
    image_urls = [
        "https://storage.googleapis.com/your-bucket/image1.jpg",
        "https://storage.googleapis.com/your-bucket/image2.jpg",
        # Add more URLs as needed
    ]
    output_path = "stitched_grid.png"
    
    # Create a 3x2 grid
    process_images(image_urls, output_path, grid_rows=3, grid_cols=2)