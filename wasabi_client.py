import boto3
import logging
from botocore.exceptions import ClientError
from config import config

logger = logging.getLogger(__name__)

class WasabiClient:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=config.WASABI_ACCESS_KEY,
            aws_secret_access_key=config.WASABI_SECRET_KEY,
            endpoint_url=config.WASABI_ENDPOINT,
            region_name=config.WASABI_REGION
        )
        self.bucket = config.WASABI_BUCKET
    
    async def upload_file(self, file_path, object_name=None):
        """Upload a file to Wasabi storage"""
        try:
            if object_name is None:
                object_name = file_path.split('/')[-1]
            
            self.s3_client.upload_file(file_path, self.bucket, object_name)
            
            # Generate presigned URL for download/streaming
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': object_name},
                ExpiresIn=3600 * 24 * 7  # 7 days
            )
            
            return {
                'success': True,
                'object_name': object_name,
                'url': url,
                'size': os.path.getsize(file_path)
            }
        except ClientError as e:
            logger.error(f"Wasabi upload error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def download_file(self, object_name, file_path):
        """Download a file from Wasabi storage"""
        try:
            self.s3_client.download_file(self.bucket, object_name, file_path)
            return {'success': True, 'file_path': file_path}
        except ClientError as e:
            logger.error(f"Wasabi download error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def delete_file(self, object_name):
        """Delete a file from Wasabi storage"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=object_name)
            return {'success': True}
        except ClientError as e:
            logger.error(f"Wasabi delete error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def list_files(self):
        """List all files in Wasabi bucket"""
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket)
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified']
                    })
            return {'success': True, 'files': files}
        except ClientError as e:
            logger.error(f"Wasabi list error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def generate_presigned_url(self, object_name, expires_in=3600):
        """Generate presigned URL for streaming"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': object_name},
                ExpiresIn=expires_in
            )
            return {'success': True, 'url': url}
        except ClientError as e:
            logger.error(f"Wasabi URL generation error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def test_connection(self):
        """Test Wasabi connection"""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket)
            return {'success': True, 'message': 'Wasabi connection successful'}
        except ClientError as e:
            return {'success': False, 'error': str(e)}

# Global instance
wasabi_client = WasabiClient()
