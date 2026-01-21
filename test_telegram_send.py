#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Telegram export with existing JSON file
"""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.exporters.telegram_exporter import TelegramExporter
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def test_telegram_with_json(json_path: str):
    """Load JSON and send to Telegram"""
    
    # 1. Load JSON
    print(f"[*] Loading: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    sections = data.get('sections', {})
    date_str = data.get('meta', {}).get('date', 'Unknown')
    
    print(f"[OK] Loaded {len(sections)} sections from {date_str}")
    
    # 2. Initialize Telegram Exporter
    print(f"\n[*] Initializing Telegram Bot...")
    exporter = TelegramExporter(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    
    if not exporter.bot:
        print("[ERROR] Telegram Bot initialization failed!")
        return
    
    print("[OK] Bot initialized")
    
    # 3. Send to Telegram
    print(f"\n[*] Sending report to Telegram...")
    header = f"*Daily Market Intelligence* ({date_str})\n\nReport briefing."
    
    exporter.send_report_sections(sections, header_text=header)
    
    print("\n[OK] Test completed!")

if __name__ == "__main__":
    json_file = r"d:\Dev\Developing\News_Agent\outputs\daily_reports\Daily_Brief_2026_01_14.json"
    test_telegram_with_json(json_file)
