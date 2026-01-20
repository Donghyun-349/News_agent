import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.stats_collector import StatsCollector
from src.exporters.gsheet import GSheetAdapter
from src.utils.timezone_utils import format_kst_date
from config.settings import GOOGLE_SHEET_ID, LOG_LEVEL
from src.utils.logger import setup_logger

logger = setup_logger(log_level=LOG_LEVEL)

def main():
    if not GOOGLE_SHEET_ID:
        logger.warning("GOOGLE_SHEET_ID is missing. Skipping summary export.")
        return

    collector = StatsCollector()
    stats = collector.get_stats()
    
    # Define Layout
    # Date | Total | ... Sources ... | Dedup Removed | Keyword Filtered | LLM Keep | LLM Drop
    
    # Fixed Source List (Order Matters for Columns)
    # Using the same list as run_p1.py for consistency
    KNOWN_SOURCES = [
        "Big Tech", "Bloomberg", "Reuters", "Financial Times", "Wall Street Journal", 
        "Investing.com", "US Real Estate", "Korean Economy", "GEnews", "Infomax", "Naver Finance"
    ]
    
    # Prepare Row Data
    # stats의 날짜 대신 현재 실행 시점의 KST 날짜를 사용 (로그 일관성 유지)
    date_str = format_kst_date("%Y-%m-%d")
    total_collected = stats.get("total_collected", 0)
    
    row = [date_str, total_collected]
    
    # Append Source Counts
    collection_data = stats.get("collection", {})
    for src in KNOWN_SOURCES:
        row.append(collection_data.get(src, 0))
        
    # Append Processing Stats
    row.append(stats.get("dedup_removed", 0))
    # Check if keyword filtered exists (Phase 3 currently not instrumented or might not be running)
    row.append(stats.get("keyword_filtered", 0)) 
    row.append(stats.get("llm_keep", 0))
    row.append(stats.get("llm_drop", 0))
    
    # Headers Construction (for check/init)
    headers = ["Date", "Total Collected"] + KNOWN_SOURCES + [
        "Dedup Removed", "Keyword Filtered", "LLM Keep", "LLM Drop"
    ]
    
    TAB_NAME = "log"
    
    try:
        adapter = GSheetAdapter(sheet_id=GOOGLE_SHEET_ID, worksheet_name=TAB_NAME)
        adapter.connect()
        
        # Check if sheet is empty (or has headers)
        existing_data = adapter.worksheet.get_all_values()
        
        if not existing_data:
            # Init Headers
            adapter.worksheet.append_row(headers)
            logger.info(f"Initialized headers for {TAB_NAME}")
        
        # Check if we should update or append
        # If the last row has the same date, update it? 
        # For simplicity, we just append. If rerunning multiple times a day, duplicates might occur.
        # User requested: "매일 실행 후 업데이트".
        # Let's check last row date
        if existing_data and len(existing_data) > 1:
            last_row = existing_data[-1]
            if last_row[0] == date_str:
                # Update last row
                # gspread indexes are 1-based. Row number is len(existing_data)
                row_idx = len(existing_data)
                
                # Construct range to update entire row
                # But adapter might not have simple update_row, let's just delete and append or overwrite cells
                # Simple: Append new row, user can ignore old. 
                # Better: Overwrite.
                # Actually, GSheetAdapter might natively support append_row.
                # Let's trying deleting the last row if date matches, then append.
                adapter.worksheet.delete_rows(row_idx)
                logger.info(f"Removed existing row for today ({date_str}) to update.")
        
        adapter.worksheet.append_row(row)
        logger.info(f"✅ Summary Stats Exported to '{TAB_NAME}': {row}")
        
    except Exception as e:
        logger.error(f"❌ Summary Export Failed: {e}")

if __name__ == "__main__":
    main()
