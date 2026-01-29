#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 6-2: WordPress Auto-Posting (run_p6_2.py)

Function:
1. Load latest Daily Brief (JSON & MD).
2. Generate Title using LLM (Executive Summary -> Keywords).
3. Select Thumbnail based on Day of Week.
4. Convert Content to HTML with STRICT Inline CSS (Developer Style Guide).
5. Post to WordPress via REST API.
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
from config.prompts.wordpress_posting import get_title_generation_prompt

# Check Google Generative AI availability
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

logger = setup_logger(log_level=LOG_LEVEL)

# --- Configuration ---
OUTPUT_DIR = BASE_DIR / "outputs" / "daily_reports"

# WordPress Configuration (Env Vars)
WP_URL = os.getenv("WP_URL")
WP_USERNAME = os.getenv("WP_USERNAME")
WP_PASSWORD = os.getenv("WP_PASSWORD") # Application Password

# Media ID Mapping (Mon=0 .. Sat=5) based on user request
# Sun(6) is not specified, defaulting to Mon or avoiding run.
# Map: 0->74, 1->75, 2->76, 3->77, 4->78, 5->73
THUMBNAIL_MAP = {
    0: 74, # Mon
    1: 75, # Tue
    2: 76, # Wed
    3: 77, # Thu
    4: 78, # Fri
    5: 73, # Sat
    6: 74  # Sun (Fallback to Mon image if run)
}

# --- Style Definitions (Inline CSS) ---
STYLES = {
    # Colors
    "primary": "#2E7D32",       # Dark Green
    "primary_light": "#4CAF50", # Light Green
    "primary_bg_grad": "linear-gradient(135deg, #E8F5E9 0%, #D5F4E6 100%)",
    "text_primary": "#333333",
    "text_secondary": "#666666",
    
    # Typography
    "h2": "font-size: 20px; font-weight: 700; color: #2E7D32; border-bottom: 2px solid #4CAF50; margin-top: 30px; margin-bottom: 15px; padding-bottom: 8px;",
    "h3": "font-size: 20px; font-weight: 600; color: #2E7D32; margin-top: 20px; margin-bottom: 12px;",
    "h4": "font-size: 20px; font-weight: 600; color: #2E7D32; border-bottom: 2px solid #4CAF50; margin-top: 25px; margin-bottom: 12px; padding-bottom: 8px;",
    "p": "font-size: 16px; line-height: 1.8; color: #333333; margin-bottom: 16px;",
    "strong": "color: #666666; font-weight: 700;",
    
    # Components
    "briefing_box": "background: linear-gradient(135deg, #E8F5E9 0%, #D5F4E6 100%); border-left: 5px solid #4CAF50; box-shadow: 0 2px 8px rgba(0,0,0,0.1); padding: 24px 28px; margin-bottom: 30px; border-radius: 4px;",
    "briefing_item": "position: relative; padding-left: 24px; margin: 8px 0; line-height: 1.5; color: #333333;",
    "briefing_bullet": "position: absolute; left: 0; top: 0; color: #4CAF50; font-weight: bold; font-size: 18px;",
    
    "body_list_bullet": "position: absolute; left: 0; color: #333333; font-weight: bold; font-size: 18px;",
    "body_list_item": "position: relative; padding-left: 20px; margin-bottom: 8px; line-height: 1.8;",
    
    "disclaimer_box": "background: linear-gradient(to right, #FFF8E1, #FFFFFF); border-left: 4px solid #FF9800; padding: 20px; margin-top: 50px; color: #666666; font-size: 14px; line-height: 1.6;",
    
    "link": "color: #1976D2; text-decoration: none; border-bottom: 1px dotted #1976D2;"
}


def get_latest_report(target_date: str = None):
    """
    Find report files.
    If target_date is provided (YYYY_MM_DD), look for that specific file.
    Otherwise, find the latest by filename.
    """
    if target_date:
        json_path = OUTPUT_DIR / f"Daily_Brief_{target_date}.json"
        md_path = OUTPUT_DIR / f"Daily_Brief_{target_date}.md"
        
        if json_path.exists() and md_path.exists():
            return json_path, md_path
        else:
            logger.error(f"❌ Targeted report not found: {target_date}")
            return None, None

    json_files = sorted(OUTPUT_DIR.glob("Daily_Brief_*.json"), reverse=True)
    if not json_files:
        return None, None
    
    latest_json = json_files[0]
    # Assuming MD has same suffix
    latest_md = OUTPUT_DIR / latest_json.name.replace(".json", ".md")
    
    if not latest_md.exists():
        return latest_json, None
        
    return latest_json, latest_md

# ... (Keep existing imports)

def get_headers():
    if not WP_USERNAME or not WP_PASSWORD:
        return {}
    credentials = f"{WP_USERNAME}:{WP_PASSWORD}"
    token = base64.b64encode(credentials.encode()).decode('utf-8')
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json"
    }

def get_or_create_category(name: str) -> int:
    """Find category ID by name, or create if not exists."""
    if not WP_URL: return 0
    headers = get_headers()
    
    # 1. Search existing
    try:
        search_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/categories?search={name}"
        resp = requests.get(search_url, headers=headers)
        if resp.status_code == 200:
            for cat in resp.json():
                if cat['name'].lower() == name.lower():
                    return cat['id']
    except Exception as e:
        logger.error(f"❌ Failed to search category '{name}': {e}")
        
    # 2. Create if not found
    try:
        create_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/categories"
        payload = {"name": name}
        resp = requests.post(create_url, headers=headers, json=payload)
        if resp.status_code == 201:
            return resp.json()['id']
    except Exception as e:
        logger.error(f"❌ Failed to create category '{name}': {e}")
        
    return 0 # Fail safe

def get_or_create_tag(name: str) -> int:
    """Find tag ID by name, or create if not exists."""
    if not WP_URL: return 0
    headers = get_headers()
    
    # 1. Search existing
    try:
        search_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/tags?search={name}"
        resp = requests.get(search_url, headers=headers)
        if resp.status_code == 200:
            for tag in resp.json():
                if tag['name'].lower() == name.lower():
                    return tag['id']
    except Exception as e:
        logger.error(f"❌ Failed to search tag '{name}': {e}")

    # 2. Create if not found
    try:
        create_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/tags"
        payload = {"name": name}
        resp = requests.post(create_url, headers=headers, json=payload)
        if resp.status_code == 201:
            return resp.json()['id']
    except Exception as e:
        logger.error(f"❌ Failed to create tag '{name}': {e}")
        
    return 0

def generate_title_and_keywords(exec_summary_list: list, date_str: str):
    """
    Generate title using LLM and return (title, keyword_list).
    Template: [M/D Briefing] Main! Sub1 & Sub2
    """
    if not GENAI_AVAILABLE or not GOOGLE_API_KEY:
        logger.warning("⚠️ LLM not available. Using fallback.")
        return f"[{date_str} 브리핑] 오늘의 주요 시장 이슈", ["Finance", "Market", "News"]

    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        
        system_prompt = get_title_generation_prompt()
        user_prompt = f"[Summary Sentences]\n" + "\n".join(exec_summary_list)
        
        response = model.generate_content(f"{system_prompt}\n\n{user_prompt}")
        
        text = response.text.strip().replace("```json", "").replace("```", "")
        data_json = json.loads(text)
        
        # Get generated title
        generated_title = data_json.get('title_text', '주요 시장 이슈 요약')
        keyword_list = data_json.get('keywords', ['Finance', 'Market'])
        
        # Format Date
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        fmt_date = f"{dt.month}/{dt.day}"
        
        # Final Format: [1/29 브리핑] + Generated Title
        title = f"[{fmt_date} 브리핑] {generated_title}"
        
        return title, keyword_list
        
    except Exception as e:
        logger.error(f"❌ Title Generation Failed: {e}")
        return f"[{date_str} 브리핑] 오늘의 글로벌 시장/경제 분석", ["News", "Analysis"]

def convert_and_style_html(md_text: str) -> str:
    """
    Convert Markdown to HTML and apply strict inline CSS.
    """
    # 1. Pre-process Markdown
    # Requirement: Remove everything before "1. Executive Summary"
    # Strategy: Find the first line starting with "## " (H2) and keep from there.
    
    lines = md_text.split('\n')
    start_idx = 0
    end_idx = len(lines)
    
    for i, line in enumerate(lines):
        # Header Removal (Start from Executive Summary)
        if line.strip().startswith("## ") and ("Executive Summary" in line or "주요 요약" in line):
            start_idx = i
        
        # Footer Removal (Generated by...)
        if "Generated by Auto-DMI System" in line:
            end_idx = i
            
    # Slicing
    if start_idx > 0:
        lines = lines[start_idx:end_idx]
    else:
        lines = lines[:end_idx]
        
    md_text = '\n'.join(lines)
    
    # Fix Setext headers: Ensure empty line before '---'
    # (Re-process the trimmed lines)
    processed_lines = []
    lines = md_text.split('\n')
    for i, line in enumerate(lines):
        if line.strip() in ['---', '***', '___'] and i > 0 and lines[i-1].strip():
             processed_lines.append('')
        processed_lines.append(line)
    md_text = '\n'.join(processed_lines)
    
    # 2. Convert to HTML
    raw_html = markdown.markdown(md_text)
    soup = BeautifulSoup(raw_html, 'html.parser')
    
    # 3. Apply Base Styles
    # H2
    for tag in soup.find_all('h2'):
        tag['style'] = STYLES['h2']
        
    # H3
    for tag in soup.find_all('h3'):
        tag['style'] = STYLES['h3']
        
    # H4
    for tag in soup.find_all('h4'):
        tag['style'] = STYLES['h4']
        
    # P
    for tag in soup.find_all('p'):
        tag['style'] = STYLES['p']
        
    # Strong
    for tag in soup.find_all('strong'):
        tag['style'] = STYLES['strong']
        
    # 4. Special Handling: Executive Summary (Briefing Box)
    # Find H2 "Executive Summary" (or similar)
    exec_h2 = None
    for h2 in soup.find_all('h2'):
        if "Executive Summary" in h2.get_text() or "주요 요약" in h2.get_text():
            exec_h2 = h2
            break
            
    if exec_h2:
        # Find the next <ul>, skipping headers or NavigableStrings (whitespace)
        # We want the *immediately* following content, but resilient to newlines
        next_sibling = exec_h2.next_sibling
        target_ul = None
        
        while next_sibling:
            if hasattr(next_sibling, 'name') and next_sibling.name == 'ul':
                target_ul = next_sibling
                break
            if hasattr(next_sibling, 'name') and next_sibling.name is not None:
                # Found another tag (e.g. p or div) before ul -> Stop
                break
            # If string/text, check if empty
            if isinstance(next_sibling, str) and not next_sibling.strip():
                next_sibling = next_sibling.next_sibling
                continue
            
            # If non-empty text (unlikely between header and list in valid MD), stop
            if isinstance(next_sibling, str) and next_sibling.strip():
                break
                
            next_sibling = next_sibling.next_sibling
            
        if target_ul:
            # Wrap in Div
            wrapper = soup.new_tag('div', style=STYLES['briefing_box'])
            target_ul.wrap(wrapper)
            
            # Remove default padding of ul
            target_ul['style'] = "list-style-type: none; padding: 0; margin: 0;"
            
            # Style LIs (Green Bullets)
            for li in target_ul.find_all('li'):
                # Content Wrapper
                li_div = soup.new_tag('div', style=STYLES['briefing_item'])
                
                # Bullet
                bullet = soup.new_tag('span', style=STYLES['briefing_bullet'])
                bullet.string = "•"
                
                # Move contents
                li_div.extend(li.contents)
                li_div.insert(0, bullet)
                
                li.clear()
                li.append(li_div)
                li['style'] = "margin-bottom: 8px;" # Reset li style

    # 5. Handle Body Lists (Black Bullets)
    for ul in soup.find_all('ul'):
        # Skip if already styled (e.g., inside briefing box)
        if ul.parent.get('style') and 'border-left' in ul.parent['style']:
            continue
            
        ul['style'] = "list-style-type: none; padding: 0; margin: 0 0 16px 0;"
        
        for li in ul.find_all('li'):
             # Determine context (Plain list)
             li_div = soup.new_tag('div', style=STYLES['body_list_item'])
             
             bullet = soup.new_tag('span', style=STYLES['body_list_bullet'])
             bullet.string = "•"
             
             li_div.extend(li.contents)
             li_div.insert(0, bullet)
             
             li.clear()
             li.append(li_div)
    
    # 6. Links
    for a in soup.find_all('a'):
        a['style'] = STYLES['link']
        a['target'] = "_blank"
        
    # 7. Append Disclaimer
    disclaimer_html = f"""
    <div style="{STYLES['disclaimer_box']}">
        <strong>⚠️ 면책 조항 (Disclaimer)</strong><br>
        본 보고서는 단순한 정보 제공을 목적으로 작성되었으며, 투자 권유나 조언을 의도하지 않습니다. 
        제공되는 정보는 신뢰할 수 있는 출처를 바탕으로 하나, 그 정확성이나 완전성을 보장하지 않습니다. 
        모든 투자의 책임은 투자자 본인에게 있습니다.
    </div>
    """
    disclaimer_soup = BeautifulSoup(disclaimer_html, 'html.parser')
    soup.append(disclaimer_soup)
    
    return str(soup)

def post_to_wordpress(title: str, content: str, media_id: int, category_ids: list, tag_ids: list):
    """Publish to WordPress with Categories and Tags."""
    if not WP_URL or not WP_USERNAME or not WP_PASSWORD:
        logger.error("❌ WordPress Credentials missing (WP_URL, WP_USERNAME, WP_PASSWORD).")
        return False
        
    api_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/posts"
    headers = get_headers()
    
    payload = {
        "title": title,
        "content": content,
        "status": "publish",
        "featured_media": media_id,
        "categories": category_ids,
        "tags": tag_ids,
        "comment_status": "closed"
    }
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=20)
        if response.status_code in [200, 201]:
            post_link = response.json().get('link')
            logger.info(f"✅ WordPress Post Successful! Link: {post_link}")
            return True
        else:
            logger.error(f"❌ WP Post Failed ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ WP Connection Error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Phase 6-2: WordPress Auto-Posting")
    parser.add_argument("--date", type=str, help="Target Date (YYYY_MM_DD) to post specific report")
    args = parser.parse_args()

    logger.info("="*80)
    logger.info("🚀 Phase 6-2: WordPress Auto-Posting Start")
    if args.date:
        logger.info(f"🎯 Target Date: {args.date}")
    logger.info("="*80)
    
    # 1. Load Data
    json_path, md_path = get_latest_report(args.date)
    if not json_path or not md_path:
        logger.error("❌ No report files found.")
        return

    logger.info(f"📄 Processing: {md_path.name}")
    
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
        
    date_str = data.get('date', datetime.today().strftime("%Y-%m-%d"))
    
    # 2. Generate Title & Keywords
    exec_summary = data.get('executive_summary', [])
    if isinstance(exec_summary, str):
         exec_summary = [exec_summary]
         
    title, keywords = generate_title_and_keywords(exec_summary, date_str)
    logger.info(f"📝 Generated Title: {title}")
    logger.info(f"🔑 Keywords: {keywords}")
    
    # 3. Resolve Category & Tags
    # Category: "Morning Briefing"
    cat_id = get_or_create_category("Morning Briefing")
    cat_ids = [cat_id] if cat_id else []
    if cat_id: logger.info(f"📂 Category 'Morning Briefing' resolved to ID: {cat_id}")
    
    # Tags: Keywords + "랜선애널리스트"
    final_tags = keywords + ["랜선애널리스트"]
    tag_ids = []
    for tag_name in final_tags:
        tid = get_or_create_tag(tag_name)
        if tid: tag_ids.append(tid)
    logger.info(f"🏷️ Resolved {len(tag_ids)} Tags")

    # 4. Select Thumbnail
    weekday = datetime.today().weekday()
    media_id = THUMBNAIL_MAP.get(weekday, 74)
    logger.info(f"🖼️ Selected Thumbnail ID: {media_id}")
    
    # 5. Generate HTML with Styles
    html_content = convert_and_style_html(md_content)
    
    # 6. Post
    success = post_to_wordpress(title, html_content, media_id, cat_ids, tag_ids)
    
    if success:
        logger.info("✅ Phase 6-2 Completed Successfully.")
    else:
        logger.error("❌ Phase 6-2 Failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
