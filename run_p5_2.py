#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 5-2: WordPress Auto-Posting from Clustering (run_p5_2.py) - REVISED (Ref: 6-3)

Function:
1. Load latest topics from Google Sheet (Phase 5-1 export).
   - Expected Columns: Category(A), Topic Title(B), Orig Count(C), Curated Count(D), Reason(E), Publisher(F), Title(G), Title (Korean)(H), URL(I)
   - Columns F, G, H, I contain multiple items separated by newlines.
2. Filter topics with Curated Count >= 2.
3. Map internal categories to display titles and sort them.
4. Generate HTML content with STRICT Inline CSS (Matching Phase 6-3).
5. Post to WordPress and upload Manual TXT to GDrive.
"""

import sys
import os
import json
import logging
import argparse
import requests
import base64
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from collections import defaultdict

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.logger import setup_logger
from src.utils.timezone_utils import get_kst_now, format_kst_date
from config.settings import (
    LOG_LEVEL, GOOGLE_SHEET_ID, BASE_DIR
)
from src.exporters.gsheet import GSheetAdapter
from src.utils.retry import retry_with_backoff

# Load env variables for WP/GDrive
WP_URL = os.getenv("WP_URL")
WP_USERNAME = os.getenv("WP_USERNAME")
WP_PASSWORD = os.getenv("WP_PASSWORD")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

try:
    from src.exporters.gdrive import GDriveAdapter
except ImportError:
    GDriveAdapter = None

# 로거 설정
logger = setup_logger(log_level=LOG_LEVEL)

# --- Configuration ---
CATEGORY_MAPPING = {
    "G_mac": "Global issue",
    "G_mak": "Global Market",
    "G_tech": "Global Tech",
    "G_re": "Global_region",
    "K_mac": "Korea_macro",
    "K_mak": "Korea Market",
    "K_in": "Korea Industry",
    "Real_G": "Real Estate Global",
    "Real_K": "Real Estate Korea"
}

CATEGORY_ORDER = [
    "G_mac", "G_mak", "G_tech", "G_re", "K_mac", "K_mak", "K_in", "Real_G", "Real_K"
]

# Media ID Mapping (from run_p6_3.py)
THUMBNAIL_MAP = {
    0: 74, # Mon
    1: 75, # Tue
    2: 76, # Wed
    3: 77, # Thu
    4: 78, # Fri
    5: 73, # Sat
    6: 74  # Sun
}

# CSS Definitions (Moving to a single <style> block to reduce payload size)
CSS_BLOCK = """
<style>
    .wp-h2 { font-size: 20px; font-weight: 700; color: #2E7D32; border-bottom: 2px solid #4CAF50; margin-top: 30px; margin-bottom: 15px; padding-bottom: 8px; }
    .wp-h3 { font-size: 20px; font-weight: 600; color: #2E7D32; margin-top: 20px; margin-bottom: 12px; }
    .wp-box { background: linear-gradient(135deg, #E8F5E9 0%, #D5F4E6 100%); border-left: 5px solid #4CAF50; box-shadow: 0 2px 8px rgba(0,0,0,0.1); padding: 15px 18px; margin-bottom: 30px; border-radius: 4px; }
    .wp-link { color: #1976D2; text-decoration: none; border-bottom: 1px dotted #1976D2; font-size: 16px; }
    .wp-disc { background: linear-gradient(to right, #FFF8E1, #FFFFFF); border-left: 4px solid #FF9800; padding: 20px; margin-top: 50px; color: #666666; font-size: 14px; line-height: 1.6; }
</style>
"""

def get_headers():
    if not WP_USERNAME or not WP_PASSWORD: return {}
    credentials = f"{WP_USERNAME}:{WP_PASSWORD}"
    token = base64.b64encode(credentials.encode()).decode('utf-8')
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

@retry_with_backoff(max_attempts=3, initial_delay=2.0, exceptions=(requests.exceptions.RequestException,))
def post_to_wordpress(title: str, html_content: str, media_id: int):
    """Post to WordPress REST API."""
    if not WP_URL:
        logger.warning("⚠️ WP_URL not set. Skipping WordPress posting.")
        return False
        
    headers = get_headers()
    url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/posts"
    
    payload = {
        "title": title,
        "content": html_content,
        "status": "publish",
        "featured_media": media_id,
        "categories": [29], # Global Outlook
        "comment_status": "closed"
    }
    
    try:
        logger.info(f"📤 Posting to WordPress (Size: {len(html_content)/1024:.1f} KB)...")
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        
        if resp.status_code in [200, 201]:
            logger.info(f"✅ WordPress Post Successful: {resp.json().get('link')}")
            return True
        else:
            logger.error(f"❌ WordPress Post Failed: {resp.status_code} - {resp.text}")
            return False
    except requests.exceptions.HTTPError as e:
        if e.response.status_code >= 500:
            logger.warning(f"⚠️ WordPress Server Error (5xx): {e}. Retrying...")
            raise # Let retry_with_backoff handle it
        else:
            logger.error(f"❌ WordPress Client Error (4xx): {e}")
            return False
    except Exception as e:
        logger.error(f"❌ WordPress API Error: {e}")
        raise

def save_to_txt(title: str, content: str, date_str: str):
    """Save content to TXT for manual upload."""
    output_dir = BASE_DIR / "outputs" / "daily_reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"Formatting_For_Upload_P5_{date_str}.txt"
    output_path = output_dir / filename
    
    file_content = f"{title}\n\n{content}\n\nTags: 랜선애널리스트, Daily Briefing, 마켓인텔리전스"
    
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(file_content)
        logger.info(f"✅ Manual Output Saved: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"❌ Failed to save manual output: {e}")
        return None

def fetch_data_from_sheet(sheet_name: str):
    """Read data from GSheet tab using GSheetAdapter.
    Adds wait logic for translation formulas.
    """
    import time
    adapter = GSheetAdapter(sheet_id=GOOGLE_SHEET_ID)
    try:
        adapter.connect()
        if not adapter.client:
            logger.error("❌ GSheet client not initialized.")
            return []
            
        spreadsheet = adapter.client.open_by_key(GOOGLE_SHEET_ID)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        # Max wait: 6 attempts * 10 seconds = 60 seconds
        max_wait_attempts = 6
        wait_interval = 10
        
        for attempt in range(1, max_wait_attempts + 1):
            data = worksheet.get_all_values()
            logger.info(f"📊 Attempt {attempt}: Total rows fetched: {len(data)}")
            
            if len(data) <= 1:
                return []
                
            # Check for "로드 중" or "Loading" in "Title (Korean)" column (index 7, H)
            # We only check the first few data rows for efficiency
            is_loading = False
            for r in data[1:min(6, len(data))]: # Check top 5 topics
                if len(r) > 7 and ("로드 중" in r[7] or "Loading" in r[7]):
                    is_loading = True
                    break
            
            if is_loading:
                if attempt < max_wait_attempts:
                    logger.warning(f"⏳ Google Sheets translation is still loading. Waiting {wait_interval}s... (Attempt {attempt}/{max_wait_attempts})")
                    time.sleep(wait_interval)
                    continue
                else:
                    logger.error("❌ Translation timeout: Proceeding with potentially incomplete data.")
                    return data[1:]
            else:
                if attempt > 1:
                    logger.info("✅ Translation completed.")
                return data[1:]
                
    except Exception as e:
        logger.error(f"❌ Failed to read sheet '{sheet_name}': {e}")
        return []

def generate_html(rows: List[List[str]]):
    """Generate styled HTML from sheet rows. Handles newlined multi-article columns."""
    
    # Structure for grouping: Category -> [TopicData]
    category_groups = defaultdict(list)
    
    for r in rows:
        if len(r) < 9: continue
        cat = r[0]
        topic_title = r[1]
        try:
            curated_count = int(r[3])
        except ValueError:
            curated_count = 0
            
        # Filter: Skip topics with only 1 article
        if curated_count < 2:
            continue
            
        # Extract Multi-item columns (Separated by newlines in Phase 5-1 export)
        # Reason(E), Publisher(F), Title(G), Title (Korean)(H), URL(I)
        pubs = r[5].split('\n')
        titles = r[6].split('\n')
        titles_kr = r[7].split('\n')
        urls = r[8].split('\n')
        
        # Zip them together
        articles = []
        for i in range(len(pubs)):
            pub = pubs[i].strip() if i < len(pubs) else ""
            orig_tit = titles[i].strip() if i < len(titles) else ""
            kr_tit = titles_kr[i].strip() if i < len(titles_kr) else ""
            url = urls[i].strip() if i < len(urls) else ""
            
            # Use KR title preferentially
            final_tit = kr_tit if kr_tit and kr_tit != "" else orig_tit
            if not final_tit: continue
            
            articles.append({
                "pub": pub,
                "title": final_tit,
                "url": url
            })
            
        if articles:
            # Selection Criteria: Select top 6 based on pre-sorting in P5_1
            # Sorting in P5_1 already accounts for Source Tier and Recency.
            selected_articles = articles[:6]
            
            category_groups[cat].append({
                "title": topic_title,
                "articles": selected_articles
            })
            
    if not category_groups:
        return ""
        
    html = [CSS_BLOCK]
    
    # Body Content by Ordered Categories
    for cat_id in CATEGORY_ORDER:
        display_cat = CATEGORY_MAPPING.get(cat_id, cat_id)
        if cat_id not in category_groups: continue
        
        topics = category_groups[cat_id]
        
        # Section Header
        html.append(f'<h2 class="wp-h2">{display_cat}</h2>')
        
        for i, tdata in enumerate(topics, 1):
            html.append(f'<h3 class="wp-h3">{i}. {tdata["title"]}</h3>')
            
            # Briefing Box for articles
            html.append(f'<div class="wp-box">')
            html.append(f'<ul style="list-style-type: none; padding: 0; margin: 0;">')
            for art in tdata["articles"]:
                html.append(f'<li style="margin-bottom: 10px;">')
                html.append(f'[{art["pub"]}] <a href="{art["url"]}" target="_blank" class="wp-link">{art["title"]}</a>')
                html.append(f'</li>')
            html.append('</ul></div>')
            
    # Disclaimer
    disclaimer = f"""
    <div class="wp-disc">
        <strong>⚠️ 면책 조항 (Disclaimer)</strong><br>
        본 보고서는 단순한 정보 제공을 목적으로 작성되었으며, 투자 권유나 조언을 의도하지 않습니다. 
        제공되는 정보는 신뢰할 수 있는 출처를 바탕으로 하나, 그 정확성이나 완전성을 보장하지 않습니다. 
        모든 투자의 책임은 투자자 본인에게 있습니다.
    </div>
    """
    html.append(disclaimer)
    return "".join(html)

def main():
    parser = argparse.ArgumentParser(description="Phase 5-2: WordPress Auto-Posting (Revised - 6-3 Ref)")
    parser.add_argument("--sheet", type=str, help="Sheet tab name (YYMMDD format)")
    args = parser.parse_args()

    logger.info("🚀 Phase 5-2: WordPress Auto-Posting (6-3 Ref) Start")

    kst_now = get_kst_now()
    sheet_name = args.sheet if args.sheet else kst_now.strftime("%y%m%d")
    logger.info(f"📅 Target Sheet: {sheet_name}")

    rows = fetch_data_from_sheet(sheet_name)
    if not rows:
        logger.error(f"❌ No data found or failed to read sheet '{sheet_name}'.")
        return

    html_content = generate_html(rows)
    title = f"[{kst_now.strftime('%m/%d')}] daily news briefing"
    
    if html_content:
        # Save to TXT & Upload to GDrive
        fmt_date = kst_now.strftime("%Y_%m_%d")
        txt_path = save_to_txt(title, html_content, fmt_date)
        
        # GDrive Upload
        if txt_path and GOOGLE_DRIVE_FOLDER_ID and GDriveAdapter:
            logger.info(f"📤 Uploading to Google Drive...")
            try:
                drive_adapter = GDriveAdapter()
                drive_adapter.upload_file(txt_path, GOOGLE_DRIVE_FOLDER_ID)
            except Exception as e:
                logger.error(f"❌ Google Drive Upload Failed: {e}")
        
        # WordPress Posting with Featured Media
        media_id = THUMBNAIL_MAP.get(kst_now.weekday(), 74)
        post_to_wordpress(title, html_content, media_id)
    else:
        logger.warning("⚠️ No topics with 2+ articles to publish.")

if __name__ == "__main__":
    main()
