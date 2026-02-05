#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 7-1: WordPress Auto-Posting (English Global Daily Brief)

Function:
1. Load latest Global Daily Brief (JSON & MD).
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
from src.utils.timezone_utils import get_et_now, format_et_date
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
    Find Global Daily Brief report files.
    If target_date is provided (YYYY_MM_DD), look for that specific file.
    Otherwise, find the latest by filename.
    """
    if not OUTPUT_DIR.exists():
        logger.error(f"Output directory not found: {OUTPUT_DIR}")
        return None, None
        
    # Pattern: Global_Daily_Brief_YYYY_MM_DD
    pattern = "Global_Daily_Brief_*.json"
    
    if target_date:
        # Specific date
        json_file = OUTPUT_DIR / f"Global_Daily_Brief_{target_date}.json"
        md_file = OUTPUT_DIR / f"Global_Daily_Brief_{target_date}.md"
        if json_file.exists() and md_file.exists():
            return json_file, md_file
        else:
            logger.error(f"Report files for {target_date} not found")
            return None, None
    else:
        # Latest file
        json_files = sorted(OUTPUT_DIR.glob(pattern), reverse=True)
        if not json_files:
            logger.error("No Global Daily Brief JSON files found")
            return None, None
            
        json_path = json_files[0]
        md_path = json_path.with_suffix('.md')
        
        if not md_path.exists():
            logger.error(f"Markdown file not found for {json_path.name}")
            return None, None
            
        return json_path, md_path


# ... (Keep existing imports)

def get_headers():
    """Build WordPress API headers with authentication."""
    credentials = f"{WP_USERNAME}:{WP_PASSWORD}"
    token = base64.b64encode(credentials.encode())
    return {
        'Authorization': f'Basic {token.decode("utf-8")}',
        'Content-Type': 'application/json'
    }

def get_or_create_category(name: str):
    """Find category ID by name, or create if not exists."""
    if not WP_URL:
        logger.warning("WP_URL not configured, skipping category resolution")
        return None
        
    url = f"{WP_URL}/wp-json/wp/v2/categories"
    headers = get_headers()
    
    # Search for existing category
    response = requests.get(url, headers=headers, params={"search": name})
    if response.status_code == 200:
        categories = response.json()
        for cat in categories:
            if cat['name'].lower() == name.lower():
                return cat['id']
    
    # Create new category
    payload = {"name": name}
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 201:
        return response.json()['id']
    else:
        logger.error(f"Failed to create category '{name}': {response.text}")
        return None

def get_or_create_tag(name: str):
    """Find tag ID by name, or create if not exists."""
    if not WP_URL:
        return None
        
    url = f"{WP_URL}/wp-json/wp/v2/tags"
    headers = get_headers()
    
    # Search for existing tag
    response = requests.get(url, headers=headers, params={"search": name})
    if response.status_code == 200:
        tags = response.json()
        for tag in tags:
            if tag['name'].lower() == name.lower():
                return tag['id']
    
    # Create new tag
    payload = {"name": name}
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 201:
        return response.json()['id']
    else:
        logger.error(f"Failed to create tag '{name}': {response.text}")
        return None

def extract_keywords_from_title(title: str, max_keywords: int = 3) -> list:
    """
    Extract keywords from title by simple tokenization.
    Filters out common English stopwords and short words.
    """
    # English stopwords
    stopwords = [
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
        'before', 'after', 'above', 'below', 'between', 'under', 'over', 'again',
        'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how',
        'all', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such',
        'vs', 'amid', 'as', 'amid', '&'
    ]
    
    # Split by spaces and common delimiters
    import re
    tokens = re.split(r'[\s,!·&]+', title)
    
    keywords = []
    for token in tokens:
        # Remove particles
        cleaned = token.strip()
        # Filter out stopwords, short tokens (< 3 chars), and pure punctuation
        if cleaned and len(cleaned) >= 3 and cleaned.lower() not in stopwords and not all(c in '!?,.' for c in cleaned):
            keywords.append(cleaned)
    
    # Return first N keywords
    return keywords[:max_keywords] if keywords else ['Finance', 'Market', 'Economy']


def format_title_with_date(posting_title: str, date_str: str) -> str:
    """
    Format posting title with date prefix.
    Template: [M/D Global Briefing] Posting Title
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    fmt_date = f"{dt.month}/{dt.day}"
    return f"[{fmt_date} Global Briefing] {posting_title}"

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
        if line.strip().startswith("## ") and "Executive Summary" in line:
            start_idx = i
        
        # Footer Removal (By Lan Analyst at...)
        if "By Lan Analyst at" in line:
            end_idx = i
            break
    
    # Keep only body content
    body_lines = lines[start_idx:end_idx]
    body_md = '\n'.join(body_lines)
    
    # 2. Convert Markdown to HTML
    html = markdown.markdown(body_md, extensions=['extra', 'nl2br'])
    
    # 3. Parse HTML with BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    
    # 4. Apply Inline Styles
    
    # --- H2 (Main Section Headers) ---
    for h2 in soup.find_all('h2'):
        h2['style'] = STYLES['h2']
    
    # --- H3 (Subsection Headers) ---
    for h3 in soup.find_all('h3'):
        h3['style'] = STYLES['h3']
    
    # --- H4 (Minor Headers) ---
    for h4 in soup.find_all('h4'):
        h4['style'] = STYLES['h4']
    
    # --- Paragraphs ---
    for p in soup.find_all('p'):
        p['style'] = STYLES['p']
    
    # --- Strong ---
    for strong in soup.find_all('strong'):
        strong['style'] = STYLES['strong']
    
    # --- Links ---
    for a in soup.find_all('a'):
        a['style'] = STYLES['link']
    
    # --- Special: Executive Summary Briefing Box ---
    # Find "## 1. Executive Summary" section
    # Convert its OL (ordered list) into styled briefing box
    exec_summary_h2 = None
    for h2 in soup.find_all('h2'):
        if 'Executive Summary' in h2.get_text():
            exec_summary_h2 = h2
            break
    
    if exec_summary_h2:
        # Find the OL that follows this H2
        ol = exec_summary_h2.find_next_sibling('ol')
        if ol:
            # Wrap OL in a styled div
            wrapper = soup.new_tag('div', style=STYLES['briefing_box'])
            ol.wrap(wrapper)
            
            # Style each <li> item
            for idx, li in enumerate(ol.find_all('li'), start=1):
                li['style'] = STYLES['briefing_item']
                # Add bullet span
                bullet_span = soup.new_tag('span', style=STYLES['briefing_bullet'])
                bullet_span.string = f"{idx}."
                li.insert(0, bullet_span)
    
    # --- Body Lists (Non-Executive Summary OLs) ---
    for ol in soup.find_all('ol'):
        # Skip if already wrapped (Executive Summary)
        if ol.parent.name == 'div' and 'briefing_box' in ol.parent.get('style', ''):
            continue
            
        for idx, li in enumerate(ol.find_all('li'), start=1):
            li['style'] = STYLES['body_list_item']
            bullet_span = soup.new_tag('span', style=STYLES['body_list_bullet'])
            bullet_span.string = f"{idx}."
            li.insert(0, bullet_span)
    
    # --- Transform Citations (Blockquote -> Custom Style) ---
    # Pattern: > • [Title](URL) - (Publisher)
    # Convert to styled citation blocks
    
    def wrap_citation(match):
        text = match.group(1)
        # Parse [Title](URL) - (Publisher)
        link_match = re.search(r'\[([^\]]+)\]\(([^\)]+)\)\s*-\s*\(([^\)]+)\)', text)
        if link_match:
            title = link_match.group(1)
            url = link_match.group(2)
            publisher = link_match.group(3)
            return f'<div style="margin-left: 20px; padding: 8px 12px; background: #F5F5F5; border-left: 3px solid #4CAF50; margin-bottom: 8px; font-size: 14px; color: #666666;"><a href="{url}" style="{STYLES["link"]}">{title}</a> <span style="color: #999999;">({publisher})</span></div>'
        else:
            # Fallback: Plain text citation
            return f'<div style="margin-left: 20px; padding: 8px 12px; background: #F5F5F5; border-left: 3px solid #4CAF50; margin-bottom: 8px; font-size: 14px; color: #666666;">{text}</div>'
    
    # Find blockquotes and replace
    for blockquote in soup.find_all('blockquote'):
        content = str(blockquote)
        # Extract bullet items
        items = re.findall(r'<p>•\s*(.+?)</p>', content, re.DOTALL)
        if items:
            citation_html = ''.join([wrap_citation(re.match(r'(.+)', item)) for item in items])
            blockquote.replace_with(BeautifulSoup(citation_html, 'html.parser'))
    
    # --- Add Disclaimer at the end ---
    disclaimer_text = """
    <div style="{disclaimer_style}">
    <strong>⚠️ Disclaimer</strong><br>
    This content is for informational purposes only and should not be considered as financial advice. 
    Market conditions are subject to rapid change, and readers should conduct their own research and consult with a financial advisor before making any investment decisions. 
    The author is not responsible for any investment losses incurred based on the information provided.
    </div>
    """.format(disclaimer_style=STYLES['disclaimer_box'])
    
    disclaimer_soup = BeautifulSoup(disclaimer_text, 'html.parser')
    soup.append(disclaimer_soup)
    
    # 5. Return final HTML
    return str(soup)


def post_to_wordpress(title: str, content: str, media_id: int, category_ids: list, tag_ids: list) -> bool:
    """Publish to WordPress with Categories and Tags."""
    if not WP_URL:
        logger.error("❌ WP_URL not configured in environment variables")
        return False
        
    url = f"{WP_URL}/wp-json/wp/v2/posts"
    headers = get_headers()
    
    payload = {
        "title": title,
        "content": content,
        "status": "publish",
        "featured_media": media_id,
        "categories": category_ids,
        "tags": tag_ids
    }
    
    logger.info("📤 Posting to WordPress...")
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 201:
        post_data = response.json()
        post_url = post_data.get('link', 'N/A')
        logger.info(f"✅ Post created successfully: {post_url}")
        return True
    else:
        logger.error(f"❌ Failed to create post: {response.status_code}")
        logger.error(f"Response: {response.text}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Phase 7-1: WordPress Auto-Posting (English)")
    parser.add_argument("--date", type=str, help="Target Date (YYYY_MM_DD) to post specific report")
    args = parser.parse_args()

    logger.info("="*80)
    logger.info("🚀 Phase 7-1: WordPress Auto-Posting (English) Start")
    if args.date:
        logger.info(f"🎯 Target Date: {args.date}")
    logger.info("="*80)
    
    # 1. Load Data
    json_path, md_path = get_latest_report(args.date)
    if not json_path or not md_path:
        logger.error("❌ No Global Daily Brief report files found.")
        return

    logger.info(f"📄 Processing: {md_path.name}")
    
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
        
    date_str = data.get('meta', {}).get('date', format_et_date("%Y-%m-%d"))
    
    # 2. Extract Report Title & Generate Posting Title
    report_title = data.get('meta', {}).get('report_title', 'Global Market Developments')
    
    # Format title with date prefix
    title = format_title_with_date(report_title, date_str)
    
    # Extract keywords from title
    keywords = extract_keywords_from_title(report_title)
    
    logger.info(f"📝 Blog Post Title: {title}")
    logger.info(f"🔑 Keywords: {keywords}")
    
    
    # 3. Resolve Category & Tags
    # Category: "Global Outlook"
    cat_id = get_or_create_category("Global Outlook")
    cat_ids = [cat_id] if cat_id else []
    if cat_id: logger.info(f"📂 Category 'Global Outlook' resolved to ID: {cat_id}")
    
    # Tags: Keywords + "Lan Analyst"
    final_tags = keywords + ["Lan Analyst"]
    tag_ids = []
    for tag_name in final_tags:
        tid = get_or_create_tag(tag_name)
        if tid: tag_ids.append(tid)
    logger.info(f"🏷️ Resolved {len(tag_ids)} Tags")

    # 4. Select Thumbnail
    weekday = get_et_now().weekday()
    media_id = THUMBNAIL_MAP.get(weekday, 74)
    logger.info(f"🖼️ Selected Thumbnail ID: {media_id}")
    
    # 5. Generate HTML with Styles
    html_content = convert_and_style_html(md_content)
    
    # 6. Post
    success = post_to_wordpress(title, html_content, media_id, cat_ids, tag_ids)
    
    if success:
        logger.info("✅ Phase 7-1 Completed Successfully.")
    else:
        logger.error("❌ Phase 7-1 Failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
