#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 6-3: WordPress Auto-Posting (English) - run_p6_3.py

Function:
1. Load latest English Daily Brief (Daily_Brief_YYYY_MM_DD_EN.json).
2. Use the generated English Title from Phase 6.
3. Post to WordPress in "Global Outlook" category.
4. Auto-tagging with English keywords.
"""

import sys
import os
import json
import logging
import argparse
import requests
import markdown
import re
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
import base64

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.logger import setup_logger
from src.utils.timezone_utils import get_kst_now, format_kst_date
from config.settings import (
    LOG_LEVEL, GOOGLE_API_KEY, GEMINI_MODEL, BASE_DIR
)

logger = setup_logger(log_level=LOG_LEVEL)

# --- Configuration ---
OUTPUT_DIR = BASE_DIR / "outputs" / "daily_reports"

# WordPress Configuration (Env Vars)
WP_URL = os.getenv("WP_URL")
WP_USERNAME = os.getenv("WP_USERNAME")
WP_PASSWORD = os.getenv("WP_PASSWORD")

# Media ID Mapping (Same as KR for now, or can be different)
THUMBNAIL_MAP = {
    0: 74, # Mon
    1: 75, # Tue
    2: 76, # Wed
    3: 77, # Thu
    4: 78, # Fri
    5: 73, # Sat
    6: 74  # Sun
}

# --- Style Definitions (Inline CSS) ---
STYLES = {
    "primary": "#2E7D32",       # Dark Green
    "h2": "font-size: 20px; font-weight: 700; color: #2E7D32; border-bottom: 2px solid #4CAF50; margin-top: 30px; margin-bottom: 15px; padding-bottom: 8px;",
    "h3": "font-size: 20px; font-weight: 600; color: #2E7D32; margin-top: 20px; margin-bottom: 12px;",
    "h4": "font-size: 20px; font-weight: 600; color: #2E7D32; border-bottom: 2px solid #4CAF50; margin-top: 25px; margin-bottom: 12px; padding-bottom: 8px;",
    "p": "font-size: 16px; line-height: 1.8; color: #333333; margin-bottom: 16px;",
    "strong": "color: #666666; font-weight: 700;",
    "briefing_box": "background: linear-gradient(135deg, #E8F5E9 0%, #D5F4E6 100%); border-left: 5px solid #4CAF50; box-shadow: 0 2px 8px rgba(0,0,0,0.1); padding: 24px 28px; margin-bottom: 30px; border-radius: 4px;",
    "briefing_item": "position: relative; padding-left: 24px; margin: 8px 0; line-height: 1.5; color: #333333;",
    "briefing_bullet": "position: absolute; left: 0; top: 0; color: #4CAF50; font-weight: bold; font-size: 18px;",
    "body_list_item": "position: relative; padding-left: 20px; margin-bottom: 8px; line-height: 1.8;",
    "body_list_bullet": "position: absolute; left: 0; color: #333333; font-weight: bold; font-size: 18px;",
    "disclaimer_box": "background: linear-gradient(to right, #FFF8E1, #FFFFFF); border-left: 4px solid #FF9800; padding: 20px; margin-top: 50px; color: #666666; font-size: 14px; line-height: 1.6;",
    "link": "color: #1976D2; text-decoration: none; border-bottom: 1px dotted #1976D2;"
}

def get_latest_en_report(target_date: str = None):
    """Find latest ENGLISH report (Daily_Brief_YYYY_MM_DD_EN.json)"""
    if target_date:
        json_path = OUTPUT_DIR / f"Daily_Brief_{target_date}_EN.json"
        md_path = OUTPUT_DIR / f"Daily_Brief_{target_date}_EN.md"
        if json_path.exists() and md_path.exists():
            return json_path, md_path
        else:
            logger.error(f"❌ Targeted EN report not found: {target_date}")
            return None, None

    # Search pattern: *_EN.json
    json_files = sorted(OUTPUT_DIR.glob("Daily_Brief_*_EN.json"), reverse=True)
    if not json_files:
        return None, None
    
    latest_json = json_files[0]
    latest_md = OUTPUT_DIR / latest_json.name.replace(".json", ".md")
    
    if not latest_md.exists():
        return latest_json, None
        
    return latest_json, latest_md

def get_headers():
    if not WP_USERNAME or not WP_PASSWORD: return {}
    credentials = f"{WP_USERNAME}:{WP_PASSWORD}"
    token = base64.b64encode(credentials.encode()).decode('utf-8')
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

def get_or_create_term(term_type: str, name: str) -> int:
    """Generic WP Term (Category/Tag) Resolver"""
    if not WP_URL: return 0
    headers = get_headers()
    base_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/{term_type}"
    
    try:
        # Search
        resp = requests.get(f"{base_url}?search={name}", headers=headers)
        if resp.status_code == 200:
            for item in resp.json():
                if item['name'].lower() == name.lower():
                    return item['id']
        
        # Create
        resp = requests.post(base_url, headers=headers, json={"name": name})
        if resp.status_code == 201:
            return resp.json()['id']
    except Exception as e:
        logger.error(f"❌ Failed to resolve {term_type} '{name}': {e}")
        
    return 0

def convert_and_style_html(md_text: str) -> str:
    """Convert MD to HTML with English Styling"""
    
    # 1. Trimming (Same as KR)
    lines = md_text.split('\n')
    start_idx = 0
    end_idx = len(lines)
    for i, line in enumerate(lines):
        if line.strip().startswith("## ") and "Executive Summary" in line:
            start_idx = i
        if "Generated by Auto-DMI System" in line:
            end_idx = i
    
    lines = lines[start_idx:end_idx] if start_idx > 0 else lines[:end_idx]
    
    # Fix Headers
    processed_lines = []
    for i, line in enumerate(lines):
        if line.strip() in ['---', '***', '___'] and i > 0 and lines[i-1].strip():
             processed_lines.append('')
        processed_lines.append(line)
    md_text = '\n'.join(processed_lines)
    
    # 2. Markdown -> HTML
    raw_html = markdown.markdown(md_text)
    soup = BeautifulSoup(raw_html, 'html.parser')
    
    # 3. Apply Styles
    for tag_name, style in STYLES.items():
        if tag_name in ['primary', 'briefing_box', 'briefing_item', 'briefing_bullet', 'body_list_bullet', 'body_list_item', 'disclaimer_box', 'link']: continue
        for tag in soup.find_all(tag_name):
            tag['style'] = style
            
    # Links
    for a in soup.find_all('a'):
        a['style'] = STYLES['link']
        a['target'] = "_blank"

    # 4. Executive Summary Styling
    exec_h2 = None
    for h2 in soup.find_all('h2'):
        if "Executive Summary" in h2.get_text():
            exec_h2 = h2
            break
            
    if exec_h2:
        next_elem = exec_h2.next_sibling
        target_ul = None
        while next_elem:
            if hasattr(next_elem, 'name') and next_elem.name == 'ul':
                target_ul = next_elem
                break
            if hasattr(next_elem, 'name') and next_elem.name: break
            next_elem = next_elem.next_sibling
            
        if target_ul:
            wrapper = soup.new_tag('div', style=STYLES['briefing_box'])
            target_ul.wrap(wrapper)
            target_ul['style'] = "list-style-type: none; padding: 0; margin: 0;"
            
            for li in target_ul.find_all('li'):
                div = soup.new_tag('div', style=STYLES['briefing_item'])
                bullet = soup.new_tag('span', style=STYLES['briefing_bullet'])
                bullet.string = "•"
                div.extend(li.contents)
                div.insert(0, bullet)
                li.clear()
                li.append(div)
                li['style'] = "margin-bottom: 8px;"

    # 5. Body Lists
    for ul in soup.find_all('ul'):
        if ul.parent.get('style') and 'border-left' in ul.parent['style']: continue
        ul['style'] = "list-style-type: none; padding: 0; margin: 0 0 16px 0;"
        for li in ul.find_all('li'):
            div = soup.new_tag('div', style=STYLES['body_list_item'])
            bullet = soup.new_tag('span', style=STYLES['body_list_bullet'])
            bullet.string = "•"
            div.extend(li.contents)
            div.insert(0, bullet)
            li.clear()
            li.append(div)

    # 6. Dividers
    # Insert HR after specific subsections
    divider_keywords = {
        "global_outlook": ["global outlook", "rates"],
        "market": ["market", "stock"],
        "tech": ["tech", "ai"],
        "real_estate": ["real estate"]
    }
    
    current_h2 = None
    for tag in soup.find_all(['h2', 'h3']):
        if tag.name == 'h2': current_h2 = tag.get_text().lower()
        elif tag.name == 'h3':
            h3_text = tag.get_text().lower()
            if not current_h2: continue
            
            insert = False
            if "global market" in current_h2:
                if any(k in h3_text for k in divider_keywords['global_outlook']) or \
                   any(k in h3_text for k in divider_keywords['market']) or \
                   any(k in h3_text for k in divider_keywords['tech']):
                    insert = True
            elif "real estate" in current_h2:
                if any(k in h3_text for k in divider_keywords['real_estate']):
                    insert = True
            
            if insert:
                 # Find insertion point
                 next_node = tag.next_sibling
                 insert_node = tag
                 while next_node:
                     if hasattr(next_node, 'name') and next_node.name in ['h2', 'h3', 'h4']: break
                     insert_node = next_node
                     next_node = next_node.next_sibling if hasattr(next_node, 'next_sibling') else None
                 
                 hr = soup.new_tag('hr', style="border: none; border-top: 1px solid #E0E0E0; margin: 20px 0;")
                 if insert_node: insert_node.insert_after(hr)

    # 7. Disclaimer (English)
    disclaimer_html = f"""
    <div style="{STYLES['disclaimer_box']}">
        <strong>⚠️ Disclaimer</strong><br>
        This report is for informational purposes only and does not constitute investment advice. 
        While based on reliable sources, accuracy is not guaranteed. 
        All investment decisions are the sole responsibility of the investor.
    </div>
    """
    soup.append(BeautifulSoup(disclaimer_html, 'html.parser'))
    return str(soup)

def post_to_wp(title, content, media_id, cats, tags):
    if not WP_URL: return False
    url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/posts"
    payload = {
        "title": title, "content": content, "status": "publish",
        "featured_media": media_id, "categories": cats, "tags": tags, "comment_status": "closed"
    }
    try:
        r = requests.post(url, headers=get_headers(), json=payload, timeout=20)
        if r.status_code in [200, 201]:
            logger.info(f"✅ Posted: {r.json().get('link')}")
            return True
        logger.error(f"❌ Failed: {r.text}")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str)
    args = parser.parse_args()

    logger.info("🚀 Phase 6-3: English WordPress Auto-Posting")
    
    # 1. Load Data
    json_path, md_path = get_latest_en_report(args.date)
    if not json_path: 
        logger.error("❌ No English report found.")
        return

    logger.info(f"📄 Processing: {json_path.name}")
    with open(json_path, 'r', encoding='utf-8') as f: data = json.load(f)
    with open(md_path, 'r', encoding='utf-8') as f: md_content = f.read()

    # 2. Title & Tags
    posting_title = data.get('meta', {}).get('posting_title', 'Daily Market Intelligence')
    date_str = data.get('meta', {}).get('date', get_kst_now().strftime("%Y-%m-%d"))
    
    # Title: [Feb 9] Title
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    month_name = dt.strftime("%b") # Feb
    final_title = f"[{month_name} {dt.day}] {posting_title}"
    
    # Tags
    keywords = posting_title.split(' ')
    tags = ["Global Market", "Investment", "Daily Brief"] + [k for k in keywords if len(k) > 3][:3]
    
    logger.info(f"📝 Title: {final_title}")
    
    # 3. Resolve IDs
    cat_id = get_or_create_term("categories", "Global Outlook")
    tag_ids = [get_or_create_term("tags", t) for t in tags]
    tag_ids = [t for t in tag_ids if t] # Filter 0s
    
    # 4. Thumbnail
    media_id = THUMBNAIL_MAP.get(get_kst_now().weekday(), 74)
    
    # 5. HTML
    html = convert_and_style_html(md_content)
    
    # 6. Post
    post_to_wp(final_title, html, media_id, [cat_id] if cat_id else [], tag_ids)

if __name__ == "__main__":
    main()
