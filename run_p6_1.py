
import os
import sys
import json
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.logger import setup_logger
from src.utils.timezone_utils import format_kst_date

# Load env
load_dotenv(override=True)

logger = setup_logger()

# Define paths
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "outputs" / "daily_reports"


def format_topics(json_topics):
    """
    Format topics from JSON structure:
    1. *Title*
    Content
    [Link]
    """
    if not json_topics:
        return "특이사항 없음"
    
    formatted = []
    for i, topic in enumerate(json_topics, 1):
        # 1. Title (Bold)
        text = f"{i}. *{topic.get('title', '')}*\n"
        
        # Content
        text += f"{topic.get('text', '')}\n"
        
        # Links (top 2)
        links = topic.get('links', [])
        for link in links[:2]:  # Show maximum 2 links
            # Handle potential missing keys just in case
            l_title = link.get('title', 'Link')
            l_url = link.get('url', '#')
            l_source = link.get('source', 'Source')
            text += f"📰 [{l_title}]({l_url}) - {l_source}\n"
        
        formatted.append(text)
    
    return "\n".join(formatted)


def build_telegram_messages_from_json(report_data, date_str):
    """
    Build 4 condensed Telegram messages from JSON data
    """
    sections = report_data.get('sections', {})
    messages = []
    
    # Message 1: Executive Summary
    # Executive Summary in JSON is a list of topics too, usually just text in 'text' field
    # Check structure: it seems to be list of objects with title/text
    # Based on previous JSON, Executive Summary has "text" with numbered list.
    exec_summary_list = sections.get('Executive Summary', [])
    exec_text = ""
    if exec_summary_list:
        # Usually it's one item with the full text, or multiple items
        # Let's simple join their texts
        lines = [item.get('text', '') for item in exec_summary_list]
        exec_text = "\n".join(lines)
    else:
        exec_text = "내용 없음"

    msg1 = f"""📊 *Daily Market Intelligence* ({date_str})

*Executive Summary*
{exec_text}
"""
    messages.append(msg1)
    
    # Message 2-1: Global Macro
    # Global Section is too long, splitting into Macro vs Market/Tech
    # Map JSON keys to Telegram Sections
    global_macro = sections.get('Global > Macro', [])
    global_market = sections.get('Global > Market', [])
    global_tech = sections.get('Global > Tech', [])
    
    msg2_1 = f"""🌍 *Global Market (1/2)*

📉 *Macro*
{format_topics(global_macro)}
"""
    messages.append(msg2_1)

    # Message 2-2: Global Market & Tech
    msg2_2 = f"""🌍 *Global Market (2/2)*

🚀 *Market*
{format_topics(global_market)}

🤖 *Tech*
{format_topics(global_tech)}
"""
    messages.append(msg2_2)
    
    # Message 2-3: Global Region (NEW - was missing!)
    global_region = sections.get('Global > Region', [])
    
    if global_region:  # Only send if there's content
        msg2_3 = f"""🌍 *Global Region*

🌐 *Regional Markets*
{format_topics(global_region)}
"""
        messages.append(msg2_3)
    
    # Message 3: Korea
    korea_macro = sections.get('Korea > Macro', [])
    korea_market = sections.get('Korea > Market', [])
    korea_industry = sections.get('Korea > Industry', [])
    
    msg3 = f"""🇰🇷 *Korea Market*

💸 *Macro*
{format_topics(korea_macro)}

🚀 *Market*
{format_topics(korea_market)}

🏭 *Industry*
{format_topics(korea_industry)}
"""
    messages.append(msg3)
    
    # Message 4: Real Estate
    # FIX: Key should be 'Real Estate > Global', not found in current JSON
    # Actual key is 'Real Estate > Korea' only
    re_global = sections.get('Real Estate > Global', [])
    re_korea = sections.get('Real Estate > Korea', [])
    
    msg4 = f"""🏢 *Real Estate*

🌐 *Global*
{format_topics(re_global) if re_global else "특이사항 없음"}

🇰🇷 *Korea*
{format_topics(re_korea)}
"""
    messages.append(msg4)
    
    # Split messages that exceed Telegram's 4096 character limit
    return split_long_messages(messages)


def split_long_messages(messages, max_length=4096):
    """
    Split messages that exceed Telegram's character limit.
    Splits at topic boundaries (numbered items) to maintain readability.
    """
    result = []
    
    for msg in messages:
        if len(msg) <= max_length:
            result.append(msg)
            continue
        
        # Message is too long, need to split
        lines = msg.split('\n')
        
        # Extract header (first few lines before numbered topics)
        header_lines = []
        content_start_idx = 0
        
        for i, line in enumerate(lines):
            # Look for first numbered topic (e.g., "1. *Title*")
            if line.strip() and line.strip()[0].isdigit() and '. *' in line:
                content_start_idx = i
                break
            header_lines.append(line)
        
        header = '\n'.join(header_lines)
        
        # Split remaining content by topics
        current_chunk = header
        chunk_count = 1
        
        for i in range(content_start_idx, len(lines)):
            line = lines[i]
            
            # Check if this is a new topic
            is_new_topic = (line.strip() and 
                          len(line.strip()) > 0 and 
                          line.strip()[0].isdigit() and 
                          '. *' in line)
            
            # If adding this line would exceed limit, save current chunk
            test_chunk = current_chunk + '\n' + line
            
            if len(test_chunk) > max_length and is_new_topic and len(current_chunk) > len(header):
                # Save current chunk
                result.append(current_chunk)
                chunk_count += 1
                
                # Start new chunk with header (modified to show part number)
                header_with_part = header.replace('*', f'* ({chunk_count})', 1)
                current_chunk = header_with_part + '\n' + line
            else:
                current_chunk = test_chunk
        
        # Add the last chunk
        if len(current_chunk) > len(header):
            result.append(current_chunk)
    
    return result


def main():
    logger.info("=" * 80)
    logger.info("🚀 Phase 6-1: Telegram Report Sender (JSON Based) Start")
    logger.info("=" * 80)

    # 1. Locate the latest report (JSON file)
    today_str = format_kst_date("%Y-%m-%d")
    today_str_filename = format_kst_date("%Y_%m_%d")
    
    json_output_file = OUTPUT_DIR / f"Daily_Brief_{today_str_filename}.json"
    
    if not json_output_file.exists():
        logger.error(f"❌ Report file not found: {json_output_file}")
        logger.error("Please run Phase 6 (run_p6.py) first.")
        return

    logger.info(f"📥 Loading report from: {json_output_file}")
    
    try:
        with open(json_output_file, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        logger.info("✅ JSON file loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to load JSON file: {e}")
        return
    
    # 2. Build messages
    messages = build_telegram_messages_from_json(report_data, today_str)
    logger.info(f"✅ Built {len(messages)} Telegram messages")
    
    # 3. Configure Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("ℹ️ Telegram configuration missing. Skipping Telegram export.")
        return

    # 4. Send messages
    try:
        from src.exporters.telegram_exporter import TelegramExporter
        logger.info("🚀 Sending report to Telegram...")
        
        # Support multiple chat IDs separated by comma
        chat_ids = [cid.strip() for cid in TELEGRAM_CHAT_ID.split(',')]
        
        for chat_id in chat_ids:
            logger.info(f"  → Sending to: {chat_id}")
            exporter = TelegramExporter(TELEGRAM_BOT_TOKEN, chat_id)
            
            for i, msg in enumerate(messages, 1):
                logger.info(f"    → Message {i}/{len(messages)}")
                exporter.send_message(msg)
                time.sleep(1)  # Rate limiting
            
            logger.info(f"  ✅ Sent all {len(messages)} messages to {chat_id}")
            
    except Exception as e:
        logger.error(f"❌ Telegram Export Failed: {e}")
        import traceback
        logger.error(traceback.format_exc())

    logger.info("=" * 80)
    logger.info("✅ Phase 6-1 Complete")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()
