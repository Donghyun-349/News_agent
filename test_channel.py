#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Telegram message to new channel
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from telegram import Bot
from config.settings import TELEGRAM_BOT_TOKEN
import asyncio

async def send_test_message():
    """Send test message to @lgh_2008"""
    
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    try:
        print("[*] Sending test message to @lgh_2008...")
        result = await bot.send_message(chat_id='@lgh_2008', text='Welcome')
        print(f"[OK] Message sent successfully!")
        print(f"    Message ID: {result.message_id}")
        print(f"    Chat ID: {result.chat.id}")
        print(f"    Chat Title: {result.chat.title}")
    except Exception as e:
        print(f"[ERROR] Failed to send message: {e}")

if __name__ == "__main__":
    asyncio.run(send_test_message())
