import os
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger("news_ingestor")

class GDriveAdapter:
    def __init__(self, service_account_path: str = None):
        self.creds = None
        self.service = None
        self.service_account_path = service_account_path or os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "credentials/service_account.json")
        self.scopes = ['https://www.googleapis.com/auth/drive']  # Full Drive access (matches token.json)

    def authenticate(self):
        """Authenticate with Google Drive API (Service Account or OAuth Token)"""
        if self.service:
            return

        # 1. Try OAuth Token (User Credentials) - For Personal Drive Uploads
        token_json_env = os.getenv("GOOGLE_TOKEN_JSON")
        local_token_path = "credentials/token.json"
        
        logger.info("🔐 [GDrive Debug] Attempting Authentication...")
        
        # Check Local File
        if os.path.exists(local_token_path):
             logger.info(f"   - Found local token file: {local_token_path}")
             if not token_json_env:
                 logger.info("   - Using local token file as primary source")
                 token_json_env = local_token_path
        else:
             logger.info("   - Local token file NOT found")

        # Check Env Var
        if token_json_env:
            try:
                logger.info(f"   - GOOGLE_TOKEN_JSON provided (Length: {len(token_json_env)} chars)")
                from google.oauth2.credentials import Credentials
                import json
                
                # Check if it's a file path or direct JSON string
                if os.path.isfile(token_json_env):
                    logger.info(f"   - Loading credentials from file: {token_json_env}")
                    self.creds = Credentials.from_authorized_user_file(token_json_env, self.scopes)
                else:
                    logger.info("   - Loading credentials from JSON string")
                    info = json.loads(token_json_env)
                    self.creds = Credentials.from_authorized_user_info(info, self.scopes)
                
                self.service = build('drive', 'v3', credentials=self.creds)
                logger.info("✅ Google Drive Authenticated (User OAuth)")
                
                # Test validity
                if self.creds.expired and self.creds.refresh_token:
                    logger.info("   - Token expired, attempting refresh...")
                    from google.auth.transport.requests import Request
                    self.creds.refresh(Request())
                    logger.info("   - Token refreshed successfully")
                
                return
            except Exception as e:
                logger.warning(f"⚠️ Failed to auth with GOOGLE_TOKEN_JSON: {e}")
                import traceback
                logger.warning(traceback.format_exc())

        # 2. Fallback to Service Account
        if not os.path.exists(self.service_account_path):
             logger.warning(f"   - Service account file not found: {self.service_account_path}")
        else:
            try:
                logger.info(f"   - Attempting Service Account Auth: {self.service_account_path}")
                self.creds = service_account.Credentials.from_service_account_file(
                    self.service_account_path, scopes=self.scopes
                )
                self.service = build('drive', 'v3', credentials=self.creds)
                logger.info("✅ Google Drive Authenticated (Service Account)")
                return
            except Exception as e:
                logger.error(f"❌ Service Account Auth Failed: {e}")
                
        if not self.service:
            logger.error("❌ No valid credentials available.")
            raise Exception("No valid Google Drive credentials found (Token or Service Account).")

    def upload_file(self, file_path: str, folder_id: str, mime_type: str = None) -> str:
        """Upload a file to a specific Google Drive folder"""
        if not self.service:
            self.authenticate()
        
        # Log which authentication method is active
        auth_method = "Unknown"
        if hasattr(self.creds, 'token'):  # OAuth User Token
            auth_method = "OAuth User Token"
            logger.info("ℹ️ Using OAuth User Token for upload (Personal Drive)")
        elif hasattr(self.creds, 'service_account_email'):  # Service Account
            auth_method = "Service Account"
            logger.warning("⚠️ Using Service Account - ensure folder is on Shared Drive or properly shared")

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
                fields='id',
                supportsAllDrives=True
            ).execute()
            
            file_id = file.get('id')
            logger.info(f"📤 Uploaded to Drive: {filename} (ID: {file_id})")
            return file_id
            
        except Exception as e:
            # Check for Storage Quota Error (Common with Service Accounts)
            error_str = str(e)
            if "storageQuotaExceeded" in error_str or "403" in error_str:
                logger.error(f"❌ Storage Quota/Permission Error: {e}")
                logger.error(f"💡 Current Auth Method: {auth_method}")
                logger.error("💡 TIP: Service Accounts have 0 GB quota. Ensure GOOGLE_TOKEN_JSON is set in GitHub Secrets for OAuth authentication.")
            else:
                logger.error(f"❌ Failed to upload {filename}: {e}")
            return None
