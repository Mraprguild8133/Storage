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
        
        self.bucket_name = os.getenv('WASABI_BUCKET')
        
        # Initialize S3 client
        self.s3_client = boto3.client('s3', **self.config)
        
        # Ensure bucket exists
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket {self.bucket_name} exists")
        except ClientError:
            try:
                self.s3_client.create_bucket(Bucket=self.bucket_name)
                logger.info(f"Created bucket {self.bucket_name}")
            except ClientError as e:
                logger.error(f"Error creating bucket: {e}")
                raise
    
    async def upload_file(self, file_path: str, file_name: str) -> Optional[str]:
        """Upload file to Wasabi and return URL"""
        try:
            # Upload file
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                file_name
            )
            
            # Generate public URL
            url = f"https://{self.bucket_name}.s3.{self.config['region_name']}.wasabisys.com/{file_name}"
            
            logger.info(f"File uploaded successfully: {file_name}")
            return url
            
        except Exception as e:
            logger.error(f"Error uploading file to Wasabi: {e}")
            return None
    
    async def delete_file(self, file_name: str) -> bool:
        """Delete file from Wasabi"""
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
                'total_size': total_size
            }
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {
                'bucket_name': self.bucket_name,
                'region': self.config['region_name'],
                'object_count': 0,
                'total_size': 0
            }
    
    def generate_presigned_url(self, file_name: str, expiration: int = 3600) -> Optional[str]:
        """Generate presigned URL for temporary access"""
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
