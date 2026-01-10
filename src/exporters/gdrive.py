import os
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

class GDriveAdapter:
    def __init__(self, service_account_path: str = None):
        self.creds = None
        self.service = None
        self.service_account_path = service_account_path or os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "credentials/service_account.json")
        self.scopes = ['https://www.googleapis.com/auth/drive.file']

    def authenticate(self):
        """Authenticate with Google Drive API"""
        if self.service:
            return

        if not os.path.exists(self.service_account_path):
            logger.error(f"Service account file not found: {self.service_account_path}")
            raise FileNotFoundError(f"Service account file not found: {self.service_account_path}")

        try:
            self.creds = service_account.Credentials.from_service_account_file(
                self.service_account_path, scopes=self.scopes
            )
            self.service = build('drive', 'v3', credentials=self.creds)
            logger.info("✅ Google Drive API Authenticated")
        except Exception as e:
            logger.error(f"❌ Google Drive Auth Failed: {e}")
            raise

    def upload_file(self, file_path: str, folder_id: str, mime_type: str = None) -> str:
        """Upload a file to a specific Google Drive folder"""
        if not self.service:
            self.authenticate()

        filename = os.path.basename(file_path)
        
        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        
        media = MediaFileUpload(file_path, mimetype=mime_type)

        try:
            # Check if file exists (Optional: Simple check to overwrite or duplicate)
            # For simplicity, we just create a new file. Drive allows duplicates with same name.
            # To avoid clutter, we could search and update, but daily reports usually have date in filename.
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = file.get('id')
            logger.info(f"📤 Uploaded to Drive: {filename} (ID: {file_id})")
            return file_id
            
        except Exception as e:
            logger.error(f"❌ Failed to upload {filename}: {e}")
            return None
