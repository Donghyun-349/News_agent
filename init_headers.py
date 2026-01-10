import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.exporters.gsheet import GSheetAdapter
from config.settings import GOOGLE_SHEET_ID

# Define the exact headers we want
KNOWN_SOURCES = [
    "Big Tech", "Bloomberg", "Reuters", "Financial Times", "Wall Street Journal", 
    "Investing.com", "US Real Estate", "Korean Economy", "GEnews", "Infomax", "Naver Finance"
]

HEADERS = ["Date", "Total Collected"] + KNOWN_SOURCES + [
    "Dedup Removed", "Keyword Filtered", "LLM Keep", "LLM Drop"
]

def main():
    print("="*60)
    print("🛠 Initializing Log Headers...")
    print("="*60)
    
    if not GOOGLE_SHEET_ID:
        print("❌ Error: GOOGLE_SHEET_ID is missing.")
        return

    try:
        # Connect to 'log' tab
        adapter = GSheetAdapter(sheet_id=GOOGLE_SHEET_ID, worksheet_name="log")
        adapter.connect()
        
        # Check existing data
        existing = adapter.worksheet.get_all_values()
        
        if not existing:
            # Empty -> Add Headers
            adapter.worksheet.append_row(HEADERS)
            print("✅ Headers initialized successfully!")
            print(f"   Headers: {HEADERS}")
        else:
            print("ℹ️ Sheet is not empty.")
            first_row = existing[0]
            if first_row == HEADERS:
                print("✅ Headers are already correct.")
            else:
                print(f"⚠️ Current first row: {first_row}")
                print(f"⚠️ Expected headers:  {HEADERS}")
                print("   (Skipping overwrite to protect data)")

    except Exception as e:
        print(f"❌ Failed to init headers: {e}")
        # If tab doesn't exist, GSheetAdapter might catch it or fail? 
        # Usually GSheetAdapter creates if not exists in __init__ if logic allows, 
        # but let's assume it attempts connection. 
        # If it fails due to missing tab, we might need to create it.
        # But our GSheetAdapter usually just selects.
        
if __name__ == "__main__":
    main()
