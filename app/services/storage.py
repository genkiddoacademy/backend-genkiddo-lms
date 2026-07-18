import os
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from typing import Optional
from app.core.config import settings

class R2StorageClient:
    def __init__(self):
        self.account_id = settings.R2_ACCOUNT_ID
        self.access_key_id = settings.R2_ACCESS_KEY_ID
        self.secret_access_key = settings.R2_SECRET_ACCESS_KEY
        self.bucket_name = settings.R2_BUCKET_NAME
        self.endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"
        
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name='auto',
        )
        
    def upload_file(self, file_path_in_bucket: str, file_content: bytes, content_type: str) -> Optional[str]:
        """
        Uploads file content to R2.
        file_path_in_bucket: The full path including bucket-specific directory (e.g., 'materials/attachments/filename.png')
        """
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_path_in_bucket,
                Body=file_content,
                ContentType=content_type
            )
            return file_path_in_bucket
        except (NoCredentialsError, ClientError) as e:
            print(f"R2 Upload Error: {e}")
            return None

    def download_file(self, file_path_in_bucket: str) -> Optional[bytes]:
        """
        Downloads file content from R2.
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_path_in_bucket)
            return response['Body'].read()
        except (NoCredentialsError, ClientError) as e:
            print(f"R2 Download Error: {e}")
            return None

    def delete_file(self, file_path_in_bucket: str) -> bool:
        """
        Deletes a file from R2.
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_path_in_bucket)
            return True
        except (NoCredentialsError, ClientError) as e:
            print(f"R2 Delete Error: {e}")
            return False

    def generate_public_url(self, file_path_in_bucket: str) -> str:
        """
        Generates a public URL for the file. 
        Requires R2 bucket to be publicly accessible (e.g., via a custom domain or R2.dev public access).
        This will be `settings.BACKEND_URL/uploads/{path}` to be compatible with frontend.
        """
        return f"{settings.BACKEND_URL}/uploads/{file_path_in_bucket}"

storage_client = R2StorageClient() # Instantiate the client

# Legacy functions (for compatibility/refactoring later) - these will NOT be used directly anymore
def upload_file_to_bucket(bucket: str, path: str, file_bytes: bytes, content_type: str) -> str:
    """
    Deprecated: Use storage_client.upload_file instead.
    """
    full_path = os.path.join(bucket, path).replace("\\", "/") # Normalize path for R2
    return storage_client.upload_file(full_path, file_bytes, content_type)

def generate_signed_url(bucket: str, path: str, expires_in: int = 900) -> str:
    """
    Deprecated: Use storage_client.generate_public_url instead.
    """
    full_path = os.path.join(bucket, path).replace("\\", "/")
    return storage_client.generate_public_url(full_path)

def delete_file_from_bucket(bucket: str, path: str) -> bool:
    """
    Deprecated: Use storage_client.delete_file instead.
    """
    full_path = os.path.join(bucket, path).replace("\\", "/")
    return storage_client.delete_file(full_path)