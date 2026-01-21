#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Send report to @lgh_2008 channel
"""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.exporters.telegram_exporter import TelegramExporter

def send_report_to_channel():
    """Send full report to @lgh_2008"""
    
    # 1. Load JSON
    json_path = r"d:\Dev\Developing\News_Agent\outputs\daily_reports\Daily_Brief_2026_01_14.json"
    print(f"[*] Loading: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    sections = data.get('sections', {})
    date_str = data.get('meta', {}).get('date', 'Unknown')
    
    print(f"[OK] Loaded {len(sections)} sections from {date_str}")
    
    # 2. Initialize Telegram Exporter with new channel
    print(f"\n[*] Initializing Telegram Bot for @lgh_2008...")
    
    from config.settings import TELEGRAM_BOT_TOKEN
    exporter = TelegramExporter(bot_token=TELEGRAM_BOT_TOKEN, chat_id='@lgh_2008')
    
    if not exporter.bot:
        print("[ERROR] Telegram Bot initialization failed!")
        return
    
    print("[OK] Bot initialized")
    
    # 3. Send to Telegram
    print(f"\n[*] Sending full report to @lgh_2008...")
    header = f"*Daily Market Intelligence* ({date_str})\n\nReport briefing."
    
    exporter.send_report_sections(sections, header_text=header)
    
    print("\n[OK] Report sent to @lgh_2008!")

if __name__ == "__main__":
    send_report_to_channel()
