
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
run_cleanup.py

Function:
1. Scan 'outputs/daily_reports' directory.
2. Identify files older than 14 days based on filename date.
3. Delete them to maintain repository cleanliness.
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from src.utils.logger import setup_logger
from src.utils.timezone_utils import get_kst_now

logger = setup_logger()

OUTPUT_DIR = BASE_DIR / "outputs" / "daily_reports"
RETENTION_DAYS = 14

def parse_date_from_filename(filename: str):
    """
    Extract date from filename.
    Supported patterns:
    - Daily_Brief_YYYY_MM_DD.json/md
    - Daily_Brief_YYYY_MM_DD_EN.json/md
    - Daily_Market_Intelligence_YYYY-MM-DD.md
    """
    # Pattern 1: YYYY_MM_DD
    match = re.search(r"(\d{4})_(\d{2})_(\d{2})", filename)
    if match:
        return datetime.strptime(f"{match.group(1)}-{match.group(2)}-{match.group(3)}", "%Y-%m-%d").date()
    
    # Pattern 2: YYYY-MM-DD
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", filename)
    if match:
        return datetime.strptime(f"{match.group(1)}-{match.group(2)}-{match.group(3)}", "%Y-%m-%d").date()
        
    return None

def main():
    logger.info("="*60)
    logger.info("🧹 Auto-Cleanup Started")
    logger.info(f"Target Directory: {OUTPUT_DIR}")
    logger.info(f"Retention Period: {RETENTION_DAYS} days")
    logger.info("="*60)

    if not OUTPUT_DIR.exists():
        logger.warning(f"⚠️ Directory not found: {OUTPUT_DIR}")
        return

    today = get_kst_now().date()
    cutoff_date = today - timedelta(days=RETENTION_DAYS)
    logger.info(f"📅 Today (KST): {today}")
    logger.info(f"✂️ Cutoff Date: {cutoff_date} (Files strictly older than this will be deleted)")

    deleted_count = 0
    kept_count = 0
    
    # Verify we are not deleting recent files just in case
    # List all files
    files = [f for f in OUTPUT_DIR.iterdir() if f.is_file()]
    
    for file_path in files:
        file_date = parse_date_from_filename(file_path.name)
        
        if not file_date:
            logger.debug(f"⏭️ Skipping (No date found): {file_path.name}")
            continue

        if file_date < cutoff_date:
            try:
                os.remove(file_path)
                logger.info(f"🗑️ Deleted: {file_path.name} ({file_date})")
                deleted_count += 1
            except Exception as e:
                logger.error(f"❌ Failed to delete {file_path.name}: {e}")
        else:
            kept_count += 1
            # logger.debug(f"✅ Kept: {file_path.name} ({file_date})")

    logger.info("-" * 60)
    logger.info(f"🎉 Cleanup Complete.")
    logger.info(f"   - Deleted: {deleted_count} files")
    logger.info(f"   - Kept:    {kept_count} files")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
