"""
Telegram Exporter Module
Sends generated reports to a specified Telegram chat.
"""

import logging
import asyncio
from typing import Dict, Any, List, Union
from telegram import Bot
from telegram.error import TelegramError, RetryAfter
import time

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

class TelegramExporter:
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.bot = None

        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram Bot Token or Chat ID is missing. Telegram export will be disabled.")
            return

        try:
            self.bot = Bot(token=self.bot_token)
            logger.info("Telegram Bot intialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Telegram Bot: {e}")
            self.bot = None

    async def send_message_async(self, text: str, parse_mode: str = 'Markdown'):
        """Send a single message asynchronously with rate limit handling."""
        if not self.bot:
            return

        try:
            # Fallback to None if Markdown parsing fails usually requires retry,
            # but for now let's stick to simple text if we expect clean input.
            # However, if we want bold titles, we need Markdown.
            # Let's trust the cleaner to have removed complex markdown, 
            # and we manually add bolding in the sender?
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode=parse_mode)
        except RetryAfter as e:
            logger.warning(f"Rate limited. Waiting for {e.retry_after} seconds.")
            await asyncio.sleep(e.retry_after)
            await self.send_message_async(text, parse_mode)
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message: {e}")
            # Optional: Retry without parse_mode if it was a parsing error?
            if "Can't parse entities" in str(e) and parse_mode:
                logger.info("Retrying with plain text...")
                await self.send_message_async(text, parse_mode=None)

    def send_message(self, text: str, parse_mode: str = 'Markdown'):
        """Synchronous wrapper for sending a message."""
        if not self.bot:
            logger.warning("Telegram Bot is not configured. Skipping message send.")
            return

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                 # Should not happen in typical script use, but for safety in async envs
                asyncio.ensure_future(self.send_message_async(text, parse_mode))
            else:
                loop.run_until_complete(self.send_message_async(text, parse_mode))
        except RuntimeError:
             # Fallback context where no loop exists
             asyncio.run(self.send_message_async(text, parse_mode))

    def send_report_sections(self, sections: Dict[str, Any], header_text: str = None):
        """
        Send the report section by section.
        Accepts structured sections: List[Dict] (Blocks) or Dict (Legacy)
        { "Key": [ {"text": "...", "links": [...]}, ... ] }
        
        Args:
            sections: Dictionary of {Section Title: Content}
            header_text: Optional text to send before sections
        """
        if not self.bot:
            return

        # 1. Send Header
        if header_text:
            self.send_message(header_text)
            time.sleep(2) # Increased from 1s
        
        # 2. defined order for sections
        ordered_keys = [
            'Executive Summary',
            'Global > Macro',
            'Global > Market',
            'Global > Tech',
            'Global > Region',
            'Korea > Market',
            'Korea > Macro',
            'Korea > Industry',
            'Real Estate > Global',
            'Real Estate > Korea'
        ]

        # 3. Send Sections
        for key in ordered_keys:
            if key in sections:
                content_obj = sections[key]
                
                # Emoji map
                emoji_map = {
                    'Executive Summary': '📝',
                    'Global > Macro': '🌍 📉',
                    'Global > Market': '🌍 🚀',
                    'Global > Tech': '🌍 🤖',
                    'Global > Region': '🌍 🌏',
                    'Korea > Market': '🇰🇷 🚀',
                    'Korea > Macro': '🇰🇷 💸',
                    'Korea > Industry': '🇰🇷 🏭',
                    'Real Estate > Global': '🏢 🌐',
                    'Real Estate > Korea': '🏢 🇰🇷'
                }
                emoji = emoji_map.get(key, '📄')
                
                # Normalize Content to List of Blocks
                blocks = []
                if isinstance(content_obj, list):
                    blocks = content_obj
                elif isinstance(content_obj, dict):
                    blocks = [content_obj]
                else:
                    clean_content = str(content_obj).replace("### ", "").replace("## ", "").strip()
                    blocks = [{"text": clean_content, "links": []}]
                
                # Iterate Blocks
                for block in blocks:
                    title = block.get("title", "")
                    text = block.get("text", "")
                    links = block.get("links", [])
                    
                    # 1. Send Content Block (Title + Text)
                    full_msg = ""
                    
                    # Section Header Context (Always)
                    full_msg += f"*{emoji} {key}*\n"
                    
                    # Topic Title (if exists)
                    if title:
                        full_msg += f"\n*{title}*"
                        
                    # Body Text
                    if text:
                         full_msg += f"\n{text}"
                    
                    if full_msg.strip():
                        if len(full_msg) > 4000:
                            chunks = [full_msg[i:i+4000] for i in range(0, len(full_msg), 4000)]
                            for chunk in chunks:
                                self.send_message(chunk)
                                time.sleep(1) # Increased from 0.5s
                        else:
                            self.send_message(full_msg)
                            time.sleep(1) # Increased from 0.5s
                    
                    # 2. Send Links (Individual Messages)
                    for link in links:
                        if isinstance(link, dict):
                            # Structured Link: {'title':..., 'url':..., 'source':...}
                            # Format: 🔗 <a href="URL">[Source] Title</a>
                            
                            def escape_html(s):
                                return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                            
                            src_clean = escape_html(link.get('source', 'Source'))
                            title_clean = escape_html(link.get('title', 'Link'))
                            url = link.get('url', '')
                            
                            if url:
                                link_msg = f'🔗 <a href="{url}">[{src_clean}] {title_clean}</a>'
                                self.send_message(link_msg, parse_mode='HTML')
                            else:
                                self.send_message(f"🔗 [{src_clean}] {title_clean}", parse_mode=None)
                            
                        elif isinstance(link, str) and link.strip():
                            # Legacy string
                            link_msg = f"🔗 {link.strip()}"
                            self.send_message(link_msg, parse_mode=None) 
                        
                        time.sleep(0.5) # Increased from 0.3s
                            
                time.sleep(2.0) # Increased from 1.0s - pause between sections
        
        logger.info("✅ Sent all report sections to Telegram.")
