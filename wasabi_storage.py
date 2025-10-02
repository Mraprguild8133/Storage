import boto3
import os
import logging
from typing import Optional, Dict
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class WasabiStorage:
    def __init__(self):
        self.config = {
            'endpoint_url': os.getenv('WASABI_ENDPOINT', 'https://s3.wasabisys.com'),
            'aws_access_key_id': os.getenv('WASABI_ACCESS_KEY'),
            'aws_secret_access_key': os.getenv('WASABI_SECRET_KEY'),
            'region_name': os.getenv('WASABI_REGION', 'us-east-1')
        }
        
        self.bucket_name = os.getenv('WASABI_BUCKET', 'telegram-file-bot')
        
        # Check if Wasabi credentials are provided
        if not self.config['aws_access_key_id'] or not self.config['aws_secret_access_key']:
            logger.warning("Wasabi credentials not provided. Files will be stored locally only.")
            self.s3_client = None
            return
        
        # Initialize S3 client
        try:
            self.s3_client = boto3.client('s3', **self.config)
            
            # Ensure bucket exists
            self._ensure_bucket_exists()
            
        except Exception as e:
            logger.error(f"Failed to initialize Wasabi client: {e}")
            self.s3_client = None
    
    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket {self.bucket_name} exists and is accessible")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                # Bucket doesn't exist, create it
                try:
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"Created bucket {self.bucket_name}")
                except ClientError as create_error:
                    logger.error(f"Error creating bucket: {create_error}")
                    raise
            elif error_code == '403':
                # Bucket exists but we don't have permission
                logger.error(f"Access denied to bucket {self.bucket_name}")
                raise
            elif error_code == 'BucketAlreadyOwnedByYou':
                # Wasabi-specific error - bucket already exists
                logger.info(f"Bucket {self.bucket_name} already exists (Wasabi specific error)")
                # This is actually fine, we can continue
            else:
                logger.error(f"Error checking bucket: {error_code} - {e}")
                raise
    
    async def upload_file(self, file_path: str, file_name: str) -> Optional[str]:
        """Upload file to Wasabi and return URL"""
        if not self.s3_client:
            logger.warning("Wasabi client not available, storing locally only")
            return f"file://{file_path}"  # Return local file path as fallback
        
        try:
            # Upload file
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                file_name
            )
            
            # Generate public URL
            url = f"https://{self.bucket_name}.s3.{self.config['region_name']}.wasabisys.com/{file_name}"
            
            logger.info(f"File uploaded successfully to Wasabi: {file_name}")
            return url
            
        except Exception as e:
            logger.error(f"Error uploading file to Wasabi: {e}")
            # Fallback to local storage
            return f"file://{file_path}"
    
    async def delete_file(self, file_name: str) -> bool:
        """Delete file from Wasabi"""
        if not self.s3_client:
            logger.warning("Wasabi client not available, skip deletion")
            return True  # Return True since there's nothing to delete
        
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_name
            )
            logger.info(f"File deleted from Wasabi: {file_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file from Wasabi: {e}")
            return False
    
    async def get_storage_stats(self) -> Dict:
        """Get storage statistics"""
        if not self.s3_client:
            return {
                'bucket_name': 'Local Storage Only',
                'region': 'N/A',
                'object_count': 0,
                'total_size': 0,
                'status': 'Wasabi not configured'
            }
        
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name)
            
            total_size = 0
            object_count = 0
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    total_size += obj['Size']
                    object_count += 1
            
            return {
                'bucket_name': self.bucket_name,
                'region': self.config['region_name'],
                'object_count': object_count,
                'total_size': total_size,
                'status': 'Active'
            }
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {
                'bucket_name': self.bucket_name,
                'region': self.config['region_name'],
                'object_count': 0,
                'total_size': 0,
                'status': f'Error: {str(e)}'
            }
    
    def generate_presigned_url(self, file_name: str, expiration: int = 3600) -> Optional[str]:
        """Generate presigned URL for temporary access"""
        if not self.s3_client:
            return None
        
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': file_name
                },
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Error generating presigned URL: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if Wasabi storage is available"""
        return self.s3_client is not None
