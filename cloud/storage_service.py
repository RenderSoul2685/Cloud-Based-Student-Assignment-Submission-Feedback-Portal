"""
Firebase Cloud Storage Service Adapter.
Handles file uploads, time-limited signed URL generation, and file deletions on Firebase Storage.
"""
import time
from datetime import timedelta
from typing import BinaryIO, Optional, Union
from firebase_admin import storage
from backend.app.firebase_config import get_firebase_app, STORAGE_BUCKET


def build_storage_path(
    course_id: str,
    assignment_id: str,
    student_id: str,
    filename: str,
    timestamp: Optional[int] = None,
) -> str:
    """
    Constructs canonical storage path for assignment submissions:
    assignments/{courseId}/{assignmentId}/{studentId}/{timestamp}_{filename}
    """
    ts = timestamp or int(time.time())
    # Clean filename of path traversals
    safe_filename = filename.replace("\\", "_").replace("/", "_").strip()
    return f"assignments/{course_id}/{assignment_id}/{student_id}/{ts}_{safe_filename}"


class StorageService:
    """
    Firebase Storage wrapper for assignment document storage.
    Spark Plan Free-Tier compatible (Direct GCS Object Bucket Operations).
    """

    def __init__(self, bucket_name: Optional[str] = None):
        self.app = get_firebase_app()
        self.bucket_name = bucket_name or STORAGE_BUCKET

    @property
    def bucket(self):
        return storage.bucket(name=self.bucket_name, app=self.app)

    def upload_file(
        self,
        file_data: Union[bytes, BinaryIO],
        storage_path: str,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Uploads file bytes or file stream to Firebase Storage bucket and returns storage path.
        """
        blob = self.bucket.blob(storage_path)
        if isinstance(file_data, bytes):
            blob.upload_from_string(file_data, content_type=content_type)
        else:
            blob.upload_from_file(file_data, content_type=content_type)
        return storage_path

    def get_download_url(self, storage_path: str, expiration_minutes: int = 60) -> str:
        """
        Generates a secure time-limited signed download URL (default: 60 minutes).
        Avoids permanently public URLs to maintain academic submission privacy.
        """
        blob = self.bucket.blob(storage_path)
        return blob.generate_signed_url(expiration=timedelta(minutes=expiration_minutes))

    def delete_file(self, storage_path: str) -> bool:
        """
        Deletes a file from Firebase Storage.
        Returns True if deleted, False if blob does not exist.
        """
        blob = self.bucket.blob(storage_path)
        if blob.exists():
            blob.delete()
            return True
        return False
