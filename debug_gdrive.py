
import os
import sys
import logging
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from src.utils.logger import setup_logger

# Configure logging to console
logger = setup_logger()

def test_drive_upload():
    logger.info("="*60)
    logger.info("🧪 Google Drive Upload Debug Script")
    logger.info("="*60)
    
    # 1. Check Env Vars
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    logger.info(f"📂 Target Folder ID: {folder_id if folder_id else 'NOT SET'}")
    
    if not folder_id:
        logger.error("❌ GOOGLE_DRIVE_FOLDER_ID is missing in .env")
        return

    # 2. Create Dummy File
    dummy_file = Path("debug_upload_test.txt")
    with open(dummy_file, "w", encoding="utf-8") as f:
        f.write("This is a test file to debug Google Drive upload.")
    logger.info(f"📄 Created dummy file: {dummy_file}")

    # 3. Initialize Adapter & Upload
    try:
        from src.exporters.gdrive import GDriveAdapter
        logger.info("🔧 Initializing GDriveAdapter...")
        adapter = GDriveAdapter()
        
        logger.info("📤 Attempting Upload...")
        file_id = adapter.upload_file(str(dummy_file), folder_id)
        
        if file_id:
            logger.info(f"✅ Upload Successful! File ID: {file_id}")
            logger.info("🎉 Google Drive integration is working.")
        else:
            logger.error("❌ Upload returned None (Failed).")
            
    except Exception as e:
        logger.error(f"❌ Exception during upload test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    finally:
        # Cleanup
        if dummy_file.exists():
            os.remove(dummy_file)
            logger.info("🧹 Cleaned up dummy file")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(override=True)
    test_drive_upload()
