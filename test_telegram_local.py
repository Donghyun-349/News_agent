#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Telegram Export Locally
Usage: python test_telegram_local.py
"""

import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# Project root setup
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# Load .env explicitly
load_dotenv()

from src.exporters.telegram_exporter import TelegramExporter
from src.utils.logger import setup_logger

logger = setup_logger()

def main():
    # 1. Verification of Env Vars
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    print(f"Token: {'[OK]' if token else '[MISSING]'}")
    print(f"Chat ID: {'[OK]' if chat_id else '[MISSING]'}")
    
    if not token or not chat_id:
        print("Please check your .env file.")
        return

    # 2. Load Sample Data
    # specific file specified by user context
    json_path = BASE_DIR / "outputs" / "daily_reports" / "Daily_Market_Intelligence_2026-01-12.json"
    
    if not json_path.exists():
        # Fallback to finding latest json
        files = sorted((BASE_DIR / "outputs" / "daily_reports").glob("*.json"), key=os.path.getmtime, reverse=True)
        if files:
            json_path = files[0]
        else:
            print("❌ No JSON report found to test with.")
            return

    print(f"Loading report: {json_path.name}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    raw_sections = data.get("sections", {})
    date_str = data.get("meta", {}).get("date", "Unknown Date")

    # Adapt legacy/raw JSON to new block-based format for testing
    from run_p6 import parse_section_content
    
    sections = {}
    for k, v in raw_sections.items():
        if isinstance(v, str):
            sections[k] = parse_section_content(v)
        else:
            sections[k] = v
    
    # 3. Initialize Exporter
    exporter = TelegramExporter(token, chat_id)
    
    # 4. Send
    print("Sending messages to Telegram... (Check your phone!)")
    
    header = f"🧪 *TEST RUN* 📊 *Daily Market Intelligence* ({date_str})\n\n테스트 메시지입니다."
    
    # Only send a subset for testing if needed, but user asked to test it all likely.
    # But to avoid spamming too much, maybe just send executive summary + one section?
    # User said "send it", implying the full flow. Let's send it all.
    exporter.send_report_sections(sections, header_text=header)
    
    print("✅ Done.")

if __name__ == "__main__":
    main()
