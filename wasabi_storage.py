import boto3
import os
import json
import logging
from typing import Optional, Dict
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class WasabiStorage:
    def __init__(self):
        # Get configuration from environment variables
        self.access_key = os.getenv('WASABI_ACCESS_KEY')
        self.secret_key = os.getenv('WASABI_SECRET_KEY')
        self.bucket_name = os.getenv('WASABI_BUCKET', 'telegram-file-bot')
        self.region = os.getenv('WASABI_REGION', 'us-east-1')
        
        # Check if Wasabi credentials are provided
        if not self.access_key or not self.secret_key:
            logger.warning("Wasabi credentials not provided. Files will be stored locally only.")
            self.s3_client = None
            return
        
        # Initialize S3 client with proper configuration
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                endpoint_url=f'https://s3.{self.region}.wasabisys.com'
            )
            
            # Test connection and ensure bucket exists
            self._ensure_bucket_exists()
            
        except Exception as e:
            logger.error(f"Failed to initialize Wasabi client: {e}")
            self.s3_client = None
    
    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist"""
        try:
            # Try to list buckets first to test credentials
            self.s3_client.list_buckets()
            logger.info("Wasabi credentials are valid")
            
            # Check if bucket exists
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"Bucket {self.bucket_name} exists and is accessible")
                return
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404':
                    # Bucket doesn't exist, create it
                    logger.info(f"Bucket {self.bucket_name} doesn't exist, creating...")
                    self._create_bucket()
                elif error_code == '403':
                    logger.error(f"Access denied to bucket {self.bucket_name}")
                    raise
                else:
                    logger.warning(f"Unexpected error checking bucket: {error_code}")
                    # Try to create bucket anyway
                    self._create_bucket()
                    
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'InvalidAccessKeyId':
                logger.error("Invalid Wasabi access key ID")
                raise
            elif error_code == 'SignatureDoesNotMatch':
                logger.error("Invalid Wasabi secret key")
                raise
            else:
                logger.error(f"Error connecting to Wasabi: {error_code} - {e}")
                raise
    
    def _create_bucket(self):
        """Create the bucket with proper configuration"""
        try:
            if self.region == 'us-east-1':
                # For us-east-1, don't specify LocationConstraint
                self.s3_client.create_bucket(Bucket=self.bucket_name)
            else:
                # For other regions, specify LocationConstraint
                self.s3_client.create_bucket(
                    Bucket=self.bucket_name,
                    CreateBucketConfiguration={
                        'LocationConstraint': self.region
                    }
                )
            logger.info(f"Successfully created bucket {self.bucket_name} in region {self.region}")
            
            # Set public read access for objects (so URLs work)
            try:
                self.s3_client.put_public_access_block(
                    Bucket=self.bucket_name,
                    PublicAccessBlockConfiguration={
                        'BlockPublicAcls': False,
                        'IgnorePublicAcls': False,
                        'BlockPublicPolicy': False,
                        'RestrictPublicBuckets': False
                    }
                )
                
                # Set bucket policy for public read access
                bucket_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": "s3:GetObject",
                            "Resource": f"arn:aws:s3:::{self.bucket_name}/*"
                        }
                    ]
                }
                
                self.s3_client.put_bucket_policy(
                    Bucket=self.bucket_name,
                    Policy=json.dumps(bucket_policy)
                )
                logger.info(f"Set public read access for bucket {self.bucket_name}")
                
            except Exception as policy_error:
                logger.warning(f"Could not set public access policy: {policy_error}")
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'BucketAlreadyExists':
                logger.info(f"Bucket {self.bucket_name} already exists")
            elif error_code == 'BucketAlreadyOwnedByYou':
                logger.info(f"Bucket {self.bucket_name} already owned by you")
            else:
                logger.error(f"Error creating bucket: {error_code} - {e}")
                raise
    
    async def upload_file(self, file_path: str, file_name: str) -> Optional[str]:
        """Upload file to Wasabi and return URL"""
        if not self.s3_client:
            logger.warning("Wasabi client not available, storing locally only")
            return f"file://{file_path}"  # Return local file path as fallback
        
        try:
            # Upload file with public read access
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                file_name,
                ExtraArgs={
                    'ACL': 'public-read',
                    'ContentType': self._get_content_type(file_name)
                }
            )
            
            # Generate public URL
            url = f"https://{self.bucket_name}.s3.{self.region}.wasabisys.com/{file_name}"
            
            logger.info(f"File uploaded successfully to Wasabi: {file_name}")
            return url
            
        except Exception as e:
            logger.error(f"Error uploading file to Wasabi: {e}")
            # Fallback to local storage
            return f"file://{file_path}"
    
    def _get_content_type(self, filename: str) -> str:
        """Get content type based on file extension"""
        extension = filename.lower().split('.')[-1] if '.' in filename else ''
        content_types = {
            'pdf': 'application/pdf',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'mp4': 'video/mp4',
            'mp3': 'audio/mpeg',
            'zip': 'application/zip',
            'txt': 'text/plain',
            'json': 'application/json',
        }
        return content_types.get(extension, 'application/octet-stream')
    
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
                'region': self.region,
                'object_count': object_count,
                'total_size': total_size,
                'status': 'Active'
            }
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {
                'bucket_name': self.bucket_name,
                'region': self.region,
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
