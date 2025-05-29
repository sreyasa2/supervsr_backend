import logging
import os
from typing import List
from dotenv import load_dotenv
from google.cloud import storage

load_dotenv()

logger = logging.getLogger(__name__)

class GCSUtils:
    def __init__(self):
        credentials_path = os.getenv('GCS_CREDENTIALS_PATH')
        bucket_name = os.getenv('GCS_BUCKET_NAME')
        
        if not credentials_path or not bucket_name:
            raise ValueError("GCS credentials path and bucket name must be set in environment variables")
        
        self.storage_client = storage.Client.from_service_account_json(credentials_path)
        self.bucket = self.storage_client.get_bucket(bucket_name)
    
    def upload_file(self, file_path: str, destination_blob_name: str) -> bool:
        """
        Upload a file to GCS bucket.
        
        Args:
            file_path: Local path to the file
            destination_blob_name: Name of the blob in GCS
            
        Returns:
            bool: True if upload was successful
        """
        try:
            blob = self.bucket.blob(destination_blob_name)
            blob.upload_from_filename(file_path)
            logger.info(f"Uploaded file to GCS: {destination_blob_name}")
            return True
        except Exception as e:
            logger.exception(f"Upload failed for {destination_blob_name}: {e}")
            return False
    
    def get_recent_screenshot_urls(self, stream_id: str, count: int) -> List[str]:
        """
        Get the most recent screenshot URLs for a stream from GCS.
        
        Args:
            stream_id: The ID of the stream
            count: Number of screenshots to fetch
            
        Returns:
            List of GCS URLs for the screenshots
        """
        try:
            blobs = list(self.bucket.list_blobs(prefix=f"screenshots/{stream_id}-"))
            recent_blobs = sorted(blobs, key=lambda x: x.time_created, reverse=True)[:count]
            return [blob.public_url for blob in recent_blobs]
        except Exception as e:
            logger.exception(f"Failed to get screenshot URLs for stream {stream_id}: {e}")
            return []
