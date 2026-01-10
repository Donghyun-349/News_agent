import os
import json
import traceback
from pathlib import Path
from src.exporters.gsheet import GSheetAdapter

# Define path (same as in your workflow)
CREDENTIALS_PATH = "credentials/service_account.json"

def main():
    print("="*60)
    print("🔍 Google Sheet Connection & Credential Test")
    print("="*60)

    # 1. Check if file exists
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"❌ Error: {CREDENTIALS_PATH} NOT found.")
        return

    # 2. Inspect File Content (Safely)
    print(f"📂 Checking file: {CREDENTIALS_PATH}")
    try:
        with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        
        print(f"   - File size: {len(content)} bytes")
        print(f"   - First 20 chars: {repr(content[:20])}")
        print(f"   - Last 50 chars:  {repr(content[-50:])}")
        
        # Try pure JSON parse first
        try:
            json.loads(content)
            print("   ✅ JSON validity check passed (json.loads successful).")
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON Validity Check FAILED: {e}")
            print(f"   ❌ Error at position: {e.pos}")
            # Show the neighborhood of the error
            start = max(0, e.pos - 20)
            end = min(len(content), e.pos + 20)
            print(f"   ❌ Context around error: {repr(content[start:end])}")
            return

    except Exception as e:
        print(f"❌ unexpected error reading file: {e}")
        return

    # 3. Test GSheet Adapter Connection
    print("\n🔌 Testing GSheetAdapter Connection...")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not sheet_id:
        print("❌ Warning: GOOGLE_SHEET_ID env var is missing.")
    
    try:
        adapter = GSheetAdapter(
            service_account_path=CREDENTIALS_PATH,
            sheet_id=sheet_id,
            worksheet_name="Test_Connection"
        )
        adapter.connect()
        print("   ✅ GSheetAdapter connected successfully!")
        
        # Optional: Try to access the sheet title to prove it works
        title = adapter.client.open_by_key(sheet_id).title
        print(f"   ✅ Successfully accessed Spreadsheet: '{title}'")
        
    except Exception as e:
        print(f"   ❌ Connection Failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
