import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import the new adapter
from src.exporters.gdrive import GDriveAdapter
import logging

# Configure logging to show everything
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    print("="*60)
    print("Google Drive Upload Test")
    print("="*60)

    # Debug: Check Env Var
    token_val = os.getenv("GOOGLE_TOKEN_JSON")
    if token_val:
        print(f"GOOGLE_TOKEN_JSON found. Length: {len(token_val)}")
        print(f"   First 10 chars: {token_val[:10]}...")
    else:
        print("GOOGLE_TOKEN_JSON is NOT set or empty.")

    # 1. Check Folder ID
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    if not folder_id:
        print("Error: GOOGLE_DRIVE_FOLDER_ID env var is missing.")
        print("   Please set it in GitHub Secrets or .env")
        return

    # 2. Create Dummy File
    test_filename = f"test_upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(test_filename, "w", encoding="utf-8") as f:
        f.write(f"Hello Google Drive!\nUpload Test Timestamp: {datetime.now()}")
    
    print(f"Created dummy file: {test_filename}")

    # 3. Initialize Adapter & Upload
    try:
        adapter = GDriveAdapter() # Will load credentials from default path
        
        print(f"Uploading to Folder ID: {folder_id}...")
        file_id = adapter.upload_file(test_filename, folder_id, mime_type="text/plain")
        
        if file_id:
            print(f"Upload Successful! File ID: {file_id}")
            print("   Please check your Google Drive folder.")
        else:
            print("Upload Failed (returned None). Check logs.")

    except Exception as e:
        print(f"❌ Exception during upload: {e}")
    finally:
        # Cleanup local dummy file
        if os.path.exists(test_filename):
            os.remove(test_filename)
            print("🧹 Cleaned up local test file.")

if __name__ == "__main__":
    main()
