#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 6: Daily Market Intelligence Report Generator (run_p6.py)

Function:
1. [Scan] Load data from `topics.db` (Clusters) - Metadata Only.
2. [Select] "Chief Editor" LLM selects high-impact topics for Exec Summary & Sections.
3. [Retrieve] Fetch full article content (Snippets) ONLY for selected topics.
4. [Write] "Senior Analyst" LLM generates the professional report.
5. Export report to Markdown.
"""

import sys
import os
import json
import logging
import argparse
import sqlite3
import time
import re
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from storage.db_adapter import DatabaseAdapter
from src.utils.logger import setup_logger
from src.utils.timezone_utils import get_kst_now, format_kst_date, format_kst_datetime
from config.settings import (
    DB_TYPE, DB_NAME, LOG_LEVEL, GOOGLE_API_KEY, GEMINI_MODEL, BASE_DIR
)
from config.prompts.daily_market_intelligence import (
    get_system_prompt,
    get_topic_selection_prompt,
    get_key_takeaways_prompt,
    get_section_body_prompt
)

# Initialize Logger
logger = setup_logger(log_level=LOG_LEVEL)

# Constants
TOPICS_DB_PATH = BASE_DIR / "data" / "topics.db"
OUTPUT_DIR = BASE_DIR / "outputs" / "daily_reports"

# Map raw categories to report sections
# Map raw categories to report sections
CATEGORY_MAP = {
    # New Short Codes
    'G_mac': 'Global > Macro',
    'G_mak': 'Global > Market',
    'G_tech': 'Global > Tech',
    'G_re': 'Global > Region',
    'K_mac': 'Korea > Macro',
    'K_mak': 'Korea > Market',
    'K_in': 'Korea > Industry',
    'Real_G': 'Real Estate > Global',
    'Real_K': 'Real Estate > Korea',
    
    # Legacy Support (Optional, can keep for safety)
    'G_macro': 'Global > Macro',
    'G_market': 'Global > Market',
    'G_region': 'Global > Region',
    'K_macro': 'Korea > Macro',
    'K_market': 'Korea > Market',
    'K_industry': 'Korea > Industry',
    'RealEstate_G': 'Real Estate > Global',
    'RealEstate_K': 'Real Estate > Korea'
}

# Trusted Publishers List for Curation Priority (Ordered by Rank)
TRUSTED_PUBLISHERS_ORDER = [
    # Global Tier 1 (Foreign Major)
    "Bloomberg", "Reuters", "Wall Street Journal", "Financial Times",
    # Korea Tier 1 (Domestic Major)
    "Chosun Ilbo", "Dong-A Ilbo", "Maeil Business", "Korea Economic Daily", "Yonhap Infomax"
]

# Check Google Generative AI availability
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


class TopicsDB:
    """Read-only adapter for topics.db"""
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.connection = None
        self.cursor = None

    def connect(self):
        if not self.db_path.exists():
            raise FileNotFoundError(f"Topics DB not found at {self.db_path}")
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.cursor = self.connection.cursor()

    def get_all_topics_metadata(self):
        """Fetch all topics with minimal metadata for Selection Step"""
        self.cursor.execute("SELECT id, category, topic_title, news_ids FROM topics")
        return self.cursor.fetchall()

    def close(self):
        if self.connection:
            self.connection.close()


def fetch_article_details(news_db: DatabaseAdapter, news_ids: List[int]) -> List[Dict[str, Any]]:
    """Fetch detailed article info (Title, Publisher, Snippet) from news.db"""
    if not news_ids:
        return []
    
    placeholders = ",".join(["?"] * len(news_ids)) if DB_TYPE == "sqlite" else ",".join(["%s"] * len(news_ids))
    
    # Assumes 'processed_news' links to 'raw_news'
    query = f"""
        SELECT p.id, r.title, COALESCE(r.publisher, r.source) as publisher, r.snippet, r.url
        FROM processed_news p
        JOIN raw_news r ON p.ref_raw_id = r.id
        WHERE p.id IN ({placeholders})
    """
    
    try:
        cursor = news_db.connection.cursor()
        cursor.execute(query, tuple(news_ids))
        rows = cursor.fetchall()
        
        articles = []
        for row in rows:
            articles.append({
                "id": row[0],
                "title": row[1],
                "publisher": row[2],
                "snippet": row[3],
                "url": row[4]
            })
        return articles
    except Exception as e:
        logger.error(f"Error fetching articles {news_ids}: {e}")
        return []


def generate_content(model: Any, system_prompt: str, user_prompt: str, context_data: str, retries: int = 3) -> str:
    """Generate content using Gemini with retry logic"""
    for attempt in range(retries):
        try:
            full_prompt = f"{system_prompt}\n\n{user_prompt}\n\n[Data]\n{context_data}"
            response = model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            logger.warning(f"Gemini generation failed (Attempt {attempt+1}/{retries}): {e}")
            time.sleep(2 ** attempt)  # Exponential backoff
    
    logger.error("❌ Gemini generation failed after all retries.")
    return "생성 실패 (API Error)"

def curate_articles(articles: List[Dict[str, Any]], trusted_publishers: List[str], max_candidates: int = 12) -> List[Dict[str, Any]]:
    """
    Selects a subset of articles.
    Priority 1: Title contains 'Exclusive' or '단독'
    Priority 2: Trusted Publishers
    Priority 3: Others
    """
    if len(articles) <= max_candidates:
        return articles

    exclusive = []
    trusted = []
    others = []
    
    for art in articles:
        title = str(art.get('title', '')).lower()
        pub = str(art.get('publisher', '')).lower()
        
        # Priority 1
        if 'exclusive' in title or '단독' in title:
            exclusive.append(art)
            continue
            
        # Priority 2
        is_trusted = any(tp.lower() in pub for tp in trusted_publishers)
        if is_trusted:
            trusted.append(art)
        else:
            others.append(art)
            
    # Selection
    selected = []
    
    # 1. Fill all Exclusive (up to max)
    selected.extend(exclusive[:max_candidates])
    
    # 2. Fill with Trusted (if space left)
    if len(selected) < max_candidates:
        remaining = max_candidates - len(selected)
        # Take up to 70% of remaining slots from Trusted to leave room for diversity
        # But if 'others' is small, take more trusted.
        trusted_quota = int(remaining * 0.7) if len(others) > 2 else remaining
        selected.extend(trusted[:trusted_quota])
        
    # 3. Fill with Others (Diversity)
    if len(selected) < max_candidates:
        remaining = max_candidates - len(selected)
        selected.extend(others[:remaining])
        
    # 4. Final fill if unbalanced
    if len(selected) < max_candidates:
        # Try finding more from trusted first that were skipped
        used_trusted_count = sum(1 for a in selected if a in trusted)
        more_trusted = trusted[used_trusted_count:]
        needed = max_candidates - len(selected)
        selected.extend(more_trusted[:needed])
        
    # Double check 'others' fallback
    if len(selected) < max_candidates:
         used_others_count = sum(1 for a in selected if a in others)
         more_others = others[used_others_count:]
         needed = max_candidates - len(selected)
         selected.extend(more_others[:needed])

    return selected

def sanitize_article_data(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Clean article titles and URLs to prevent Markdown/JSON issues and reduce data size"""
    import re
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    
    def clean_url(url: str) -> str:
        """Remove unnecessary query parameters to reduce data size"""
        if not url:
            return ""
        
        try:
            parsed = urlparse(url)
            
            # Keep only essential parameters (article identifiers)
            # Remove: utm_*, ref*, tracking*, fbclid, gclid, mode, type, page, date, etc.
            essential_params = ['article_id', 'office_id', 'idxno', 'id', 'no', 'seq']
            
            if parsed.query:
                params = parse_qs(parsed.query, keep_blank_values=False)
                # Filter to keep only essential params
                cleaned_params = {k: v for k, v in params.items() 
                                if any(essential in k.lower() for essential in essential_params)}
                
                # Rebuild query string (take first value of each param)
                new_query = urlencode({k: v[0] for k, v in cleaned_params.items()})
                
                # Rebuild URL without fragment
                return urlunparse((parsed.scheme, parsed.netloc, parsed.path, 
                                 parsed.params, new_query, ''))
            else:
                # No query params, just remove fragment
                return urlunparse((parsed.scheme, parsed.netloc, parsed.path, 
                                 parsed.params, '', ''))
        except Exception:
            # If parsing fails, return original URL
            return url
    
    cleaned = []
    for art in articles:
        c_art = art.copy()
        
        # Clean title: Remove brackets and unescape HTML
        raw_title = str(c_art.get('title', ''))
        clean_title = html.unescape(raw_title)
        clean_title = clean_title.replace('[', '(').replace(']', ')')
        
        # 1. Clean URL
        raw_url = c_art.get('url', '')
        clean_u = clean_url(raw_url) if raw_url and raw_url.strip() else ""

        c_art_clean = {
            "id": c_art.get('id'), # Keep ID
            "title": clean_title,
            "publisher": c_art.get('publisher', 'Unknown'),
            "snippet": c_art.get('snippet', ''),
            "url": clean_u
        }
            
        cleaned.append(c_art_clean)
    return cleaned

def is_title_similar(new_title: str, existing_articles: List[Dict], threshold: float = 0.6) -> bool:
    """Check if title is similar to any already selected article"""
    for item in existing_articles:
        similarity = SequenceMatcher(None, new_title, item['title']).ratio()
        if similarity >= threshold:
            return True
    return False

def curate_articles(articles: List[Dict], trusted_publishers: List[str], max_candidates: int = 8) -> List[Dict]:
    """
    Select Priority Articles based on:
    1. Publisher Rank (High Priority First)
    2. Diversity (Max 2 per publisher)
    3. Uniqueness (No similar titles)
    4. Max Total (8)
    """
    if not articles:
        return []

    # Helper to get rank index (Lower is better)
    def get_rank(pub_name):
        for idx, trust_pub in enumerate(trusted_publishers):
            if trust_pub.lower() in pub_name.lower():
                return idx
        return 999 # Not in trusted list

    # Sort: Rank (Asc) -> ID (Desc/Newest)
    # Note: 'id' is used as tie-breaker (Newest IDs are usually larger)
    sorted_articles = sorted(articles, key=lambda x: (get_rank(x['publisher']), -x['id']))

    selected = []
    publisher_counts = {} # Track count per publisher

    for art in sorted_articles:
        if len(selected) >= max_candidates:
            break
            
        pub = art['publisher']
        
        # Condition 1: Max 2 articles per publisher
        if publisher_counts.get(pub, 0) >= 2:
            continue
            
        # Condition 2: Title Similarity Check (Dedup)
        # Threshold 0.6 means 60% similarity -> Skip
        if is_title_similar(art['title'], selected, threshold=0.6):
            continue
            
        # Qualified!
        selected.append(art)
        publisher_counts[pub] = publisher_counts.get(pub, 0) + 1
        
    return selected

def process_section_task(section_name: str, topic_ids: List[int], topic_map: Dict, model: Any, system_prompt: str, trusted_publishers: List[str]) -> tuple:
    """Worker function for parallel execution"""
    try:
        if not topic_ids:
            return section_name, "특이사항 없음."

        # Create independent DB connection for this thread
        local_db = DatabaseAdapter(db_type=DB_TYPE, database=DB_NAME)
        local_db.connect()

        try:
            # Gather full data
            section_context_data = []
            article_map = {} # Map ID -> {url, title, pub}
            for tid in topic_ids:
                if tid in topic_map:
                    t_obj = topic_map[tid]
                    news_ids = json.loads(t_obj['news_ids_json'])
                    articles = fetch_article_details(local_db, news_ids)
                    
                    # Sanitize Data
                    articles = sanitize_article_data(articles)

                    # DEBUG: Check URLs after sanitization
                    urls_after_sanitize = [bool(a.get('url')) for a in articles]
                    logger.debug(f"[{section_name}] Topic {tid}: URLs after sanitize: {urls_after_sanitize}")

                    # Curation
                    curated_articles = curate_articles(articles, trusted_publishers, max_candidates=12)
                    
                    # DEBUG: Check URLs after curation
                    urls_after_curate = [bool(a.get('url')) for a in curated_articles]
                    logger.debug(f"[{section_name}] Topic {tid}: URLs after curate: {urls_after_curate}")

                    # Build Article Map for Reference ID Pattern
                    for ca in curated_articles:
                        article_map[str(ca['id'])] = {
                            "t": ca['title'],
                            "u": ca['url'],
                            "p": ca['publisher']
                        }

                    section_context_data.append({
                        "t": t_obj['title'],
                        "n": t_obj['count'],
                        "a": [
                            # ID(i) included, URL(u) REMOVED for token efficiency
                            {"i": ca['id'], "t": ca['title'], "p": ca['publisher'], "s": ca['snippet']}
                            for ca in curated_articles
                        ]
                    })
        finally:
            local_db.close()
        
        sec_prompt = get_section_body_prompt(section_name)
        # Minified JSON
        sec_json = json.dumps(section_context_data, ensure_ascii=False, separators=(',', ':'))
        
        # Log payload size reduction
        total_articles = sum(len(topic.get("a", [])) for topic in section_context_data)
        logger.info(f"[{section_name}] Sending {total_articles} articles to LLM (URLs stripped)")
        
        raw_content = generate_content(model, system_prompt, sec_prompt, sec_json)
        
        # Post-Processing: Restore References
        # Find [Ref:ID] and replace with > • [Title](URL) - (Publisher)
        def replace_ref(match):
            ref_id = match.group(1)
            if ref_id in article_map:
                meta = article_map[ref_id]
                return f"> • [{meta['t']}]({meta['u']}) - ({meta['p']})"
            else:
                return f"(Source ID: {ref_id} not found)"

        # Regex to match [Ref:123] or [Ref: 123]
        final_content = re.sub(r'\[Ref:\s*(\d+)\]', replace_ref, raw_content)

        return section_name, final_content
    except Exception as e:
        logger.error(f"Error processing section '{section_name}': {e}")
        return section_name, "생성 중 오류 발생"

def process_executive_summary_task(exec_summary_ids: List[int], topic_map: Dict, model: Any, system_prompt: str, trusted_publishers: List[str]) -> tuple:
    """Worker function for Executive Summary"""
    try:
        if not exec_summary_ids:
            return "Executive Summary", "N/A (No topics selected)"
            
        # Create independent DB connection for this thread
        local_db = DatabaseAdapter(db_type=DB_TYPE, database=DB_NAME)
        local_db.connect()

        try:
            exec_context_data = []
            article_map = {} # Map ID -> Meta
            for tid in exec_summary_ids:
                if tid in topic_map:
                    t_obj = topic_map[tid]
                    news_ids = json.loads(t_obj['news_ids_json'])
                    articles = fetch_article_details(local_db, news_ids)
                    
                    # Sanitize Data
                    articles = sanitize_article_data(articles)
                    
                    # Curation
                    curated_articles = curate_articles(articles, trusted_publishers, max_candidates=12)

                    # Build Article Map
                    for ca in curated_articles:
                        article_map[str(ca['id'])] = {
                            "t": ca['title'],
                            "u": ca['url'],
                            "p": ca['publisher']
                        }

                    exec_context_data.append({
                        "t": t_obj['title'],
                        "c": t_obj['display_category'],
                        "n": t_obj['count'],
                        "a": [
                            # ID(i) included, URL(u) REMOVED
                            {"i": ca['id'], "t": ca['title'], "p": ca['publisher'], "s": ca['snippet']}
                            for ca in curated_articles
                        ]
                    })
        finally:
            local_db.close()
        
        exec_prompt = get_key_takeaways_prompt()
        # Minified JSON
        exec_json = json.dumps(exec_context_data, ensure_ascii=False, separators=(',', ':'))
        
        # Log payload size reduction
        total_articles = sum(len(topic.get("a", [])) for topic in exec_context_data)
        logger.info(f"[Executive Summary] Sending {total_articles} articles to LLM (URLs stripped)")

        raw_content = generate_content(model, system_prompt, exec_prompt, exec_json)

        # Post-Processing: Restore References
        def replace_ref(match):
            ref_id = match.group(1)
            if ref_id in article_map:
                meta = article_map[ref_id]
                return f"> • [{meta['t']}]({meta['u']}) - ({meta['p']})"
            else:
                return f"(Source ID: {ref_id} not found)"

        final_content = re.sub(r'\[Ref:\s*(\d+)\]', replace_ref, raw_content)

        return "Executive Summary", final_content
    except Exception as e:
        logger.error(f"Error processing Executive Summary: {e}")
        return "Executive Summary", "생성 중 오류 발생"

def parse_selection_json(json_text: str) -> Dict[str, Any]:
    """Robustly parse JSON output from LLM"""
    try:
        # Clean markdown code blocks
        clean_text = re.sub(r"```json\s*|\s*```", "", json_text, flags=re.IGNORECASE).strip()
        data = json.loads(clean_text)
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Selection JSON: {e}") 
        # Fallback: empty selection
        return {"executive_summary_ids": [], "section_picks": {}}


import html

def parse_section_content(raw_text: str) -> List[Dict[str, Any]]:
    """
    Parse raw LLM output into structured blocks (Text + Links).
    Returns a List of Dicts: [{'text': '...', 'links': [...]}, ...]
    """
    lines = raw_text.split('\n')
    blocks = []
    
    current_title = ""
    current_text = []
    current_links = []
    
    def flush_block():
        nonlocal current_title, current_text, current_links
        # A block must have at least some content
        if current_title or current_text or current_links:
            blocks.append({
                "title": current_title.strip(),
                "text": "\n".join(current_text).strip(),
                "links": list(current_links)
            })
            current_title = ""
            current_text = []
            current_links = []

    for line in lines:
        # Decode HTML entities (e.g., &quot; -> ") immediately
        stripped = line.strip()
        
        if not stripped:
            continue
            
        # Check for link markers
        is_link = stripped.startswith('>') or stripped.startswith('•') or stripped.startswith('- ') or stripped.startswith('*-')
        
        # Check for Title Header (### or **Title**)
        # Usually LLM output format: ### **[Title]** or ### Title
        is_header = stripped.startswith('###') or (stripped.startswith('**') and stripped.endswith('**') and len(stripped) < 100)
        
        if is_link:
            # Parse Markdown Link: >• [Title](URL) - (Source)
            link_content = re.sub(r'^[>•\-\*]+\s*', '', stripped).replace('**', '').strip()
            # IMPROVED REGEX: Greedy match for Title to handle potential nested brackets
            match = re.search(r'\[(.*)\]\((.*?)\)\s*-\s*\((.*?)\)', link_content)
            
            if match:
                link_obj = {
                    "title": match.group(1).strip(),
                    "url": match.group(2).strip(),
                    "source": match.group(3).strip()
                }
                current_links.append(link_obj)
            else:
                match_weak = re.search(r'\[(.*)\]\((.*?)\)\s*-\s*(.*)', link_content)
                if match_weak:
                    link_obj = {
                        "title": match_weak.group(1).strip(),
                        "url": match_weak.group(2).strip(),
                        "source": match_weak.group(3).strip()
                    }
                    current_links.append(link_obj)
                else:
                    current_links.append(link_content)

        elif is_header:
            if current_title or current_text or current_links:
                flush_block()
            
            clean_title = stripped.replace('###', '').replace('**', '').replace('__', '').strip()
            if clean_title.startswith('[') and clean_title.endswith(']'):
                clean_title = clean_title[1:-1]
            
            current_title = clean_title
            
        else:
            if current_links:
                flush_block()

            clean_line = stripped.replace('**', '').replace('__', '')
            clean_line = re.sub(r'^#+\s*', '', clean_line)
            current_text.append(clean_line)
            
    # Final flush
    flush_block()
    return blocks


def format_report(sections: Dict[str, Any], date_str: str) -> str:
    """Combine sections into final Markdown"""
    
    def get_sec_text(key):
        val = sections.get(key, '특이사항 없음.')
        if isinstance(val, list):
             # Reconstruct markdown from structured blocks
             full_text = []
             for block in val:
                 title = block.get('title', '')
                 text = block.get('text', '')
                 links = block.get('links', [])
                 
                 # Construct Block: ### Title \n Text \n Links
                 parts = []
                 if title:
                     parts.append(f"### {title}")
                 
                 if text:
                     parts.append(text)
                     
                 if links:
                     link_strs = []
                     for link in links:
                         if isinstance(link, dict):
                             link_strs.append(f"> • [{link['title']}]({link['url']}) - ({link['source']})")
                         else:
                             link_strs.append(f"> • {link}")
                     parts.append("\n".join(link_strs))
                 
                 full_text.append("\n".join(parts))
             
             return "\n\n".join(full_text)
        elif isinstance(val, dict):
             # Specific fallback if legacy dict format somehow remains
             return val.get('summary', '')
        return val

    md = f"""# 📊 Daily Market Intelligence
**Date:** {date_str}

---

## 1. Executive Summary
{get_sec_text('Executive Summary')}

---

## 2. 🌍 Global Market
### 📉 Macro (Economy/Rates)
{get_sec_text('Global > Macro')}

### 🚀 Market (Stock/Indices)
{get_sec_text('Global > Market')}

### 🤖 Tech (AI/Semiconductors)
{get_sec_text('Global > Tech')}

### 🌏 Region (China/Eurozone)
{get_sec_text('Global > Region')}

---

## 3. 🇰🇷 Korea Market
### 🚀 Market (Stock/Indices)
{get_sec_text('Korea > Market')}

### 💸 Macro (FX/Rates)
{get_sec_text('Korea > Macro')}

### 🏭 Industry (Company/Sector)
{get_sec_text('Korea > Industry')}

---

## 4. 🏢 Real Estate
### 🌐 Global Real Estate
{get_sec_text('Real Estate > Global')}

### 🇰🇷 Korea Real Estate
{get_sec_text('Real Estate > Korea')}

---
*Generated by Auto-DMI System at {format_kst_datetime()}*
"""
    return md


def main():
    parser = argparse.ArgumentParser(description="Phase 6: Report Generation (2-Step)")
    parser.add_argument("--formats", nargs="+", default=["json", "markdown"], 
                        choices=["json", "markdown", "html", "blog"],
                        help="Output formats to generate (default: json markdown)")
    args = parser.parse_args()

    # 1. Check API Key
    if not GENAI_AVAILABLE:
        logger.error("❌ google-generativeai package is not installed.")
        return
    
    if not GOOGLE_API_KEY:
        logger.error("❌ GOOGLE_API_KEY is missing in settings.")
        return

    # 2. Configure Gemini
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    
    logger.info("="*80)
    logger.info("🚀 Phase 6: Daily Market Intelligence Generator (2-Step Agentic) Start")
    logger.info("="*80)

    # 3. Connect DBs
    try:
        topics_db = TopicsDB(TOPICS_DB_PATH)
        topics_db.connect()
        
        news_db = DatabaseAdapter(db_type=DB_TYPE, database=DB_NAME)
        news_db.connect()
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return

    # 4. [Step 1: SCAN] Load Topic Metadata
    raw_topics = topics_db.get_all_topics_metadata()
    logger.info(f"📥 Loaded {len(raw_topics)} topics from DB (Metadata only).")

    # Structure for Selection context: List of {ID, Category, Title, Count}
    # Pre-filter: Ignore empty topics or very small ones if critical? No, let LLM decide based on title.
    topic_metadata_list = []
    # Index for fast retrieval later
    topic_map = {} 

    for t in raw_topics:
        mapped_cat = CATEGORY_MAP.get(t['category'], t['category'])
        news_ids = json.loads(t['news_ids'])
        count = len(news_ids)
        
        t_meta = {
            "id": t['id'],
            "original_category": t['category'],
            "display_category": mapped_cat,
            "title": t['topic_title'],
            "count": count,
            "news_ids_json": t['news_ids'] # Keep for later, don't send to LLM
        }
        topic_metadata_list.append({
            "id": t_meta['id'],
            "category": t_meta['display_category'],
            "topic_title": t_meta['title'],
            "count": t_meta['count']
        })
        topic_map[t['id']] = t_meta

    # 5. [Step 2: SELECT] Chief Editor selects Top Topics
    logger.info("🧠 [Step 2] Chief Editor is selecting key topics...")
    selection_prompt = get_topic_selection_prompt()
    
    # Payload Optimization (Step 1):
    # Keys: i=id, c=category, t=topic_title, n=count
    selection_input_list = []
    for tm in topic_metadata_list:
        selection_input_list.append({
            "i": tm['id'],
            "c": tm['category'],
            "t": tm['topic_title'],
            "n": tm['count']
        })
    # Minified JSON
    selection_input_data = json.dumps(selection_input_list, ensure_ascii=False, separators=(',', ':'))
    
    # We use a simple system prompt for selection role
    system_prompt = get_system_prompt() 
    selection_response = generate_content(model, system_prompt, selection_prompt, selection_input_data)
    
    selection_data = parse_selection_json(selection_response)
    
    exec_summary_ids = selection_data.get('executive_summary_ids', [])
    section_picks = selection_data.get('section_picks', {})
    
    logger.info(f"✅ Selected {len(exec_summary_ids)} topics for Executive Summary.")
    logger.info(f"✅ Selected picks for {len(section_picks)} sections.")
    
    # 6. [Step 3 & 4: RETRIEVE & WRITE] Generate Content (Parallel)
    generated_sections = {}
    
    logger.info("⚡ Starting Parallel Generation for all sections...")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        
        # 6-1. Submit Executive Summary Task
        futures.append(executor.submit(
            process_executive_summary_task, 
            exec_summary_ids, topic_map, model, system_prompt, TRUSTED_PUBLISHERS_ORDER
        ))
        
        # 6-2. Submit Section Tasks
        for section_name, topic_ids in section_picks.items():
            futures.append(executor.submit(
                process_section_task,
                section_name, topic_ids, topic_map, model, system_prompt, TRUSTED_PUBLISHERS_ORDER
            ))
            
        # 6-3. Collect Results
        for future in as_completed(futures):
            sec_name, content = future.result()
            generated_sections[sec_name] = content
            logger.info(f"  -> ✅ Completed: {sec_name}")

    duration = time.time() - start_time
    logger.info(f"✨ All sections generated in {duration:.2f} seconds.")

    # 7. Format & Save
    today_str = format_kst_date("%Y-%m-%d")
    today_str_filename = format_kst_date("%Y_%m_%d")

    # STRUCTURING: Parse content into {summary, links}
    structured_sections = {}
    for key, val in generated_sections.items():
        structured_sections[key] = parse_section_content(val)

    # 7. Render & Save Outputs based on CLI args
    if "json" in args.formats:
        json_output_file = OUTPUT_DIR / f"Daily_Brief_{today_str_filename}.json"
        report_data = {
            "meta": {
                "date": today_str,
                "generated_at": format_kst_datetime(),
                "version": "2.0" # Version bump for new structure
            },
            "sections": structured_sections
        }
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(json_output_file, "w", encoding="utf-8") as f:
            # Optimize: Minify JSON for storage efficiency
            json.dump(report_data, f, ensure_ascii=False, separators=(',', ':'))
        logger.info(f"✅ [JSON] Report saved to: {json_output_file}")

    if "markdown" in args.formats:
        # Reconstruct markdown from structured sections to keep it readable
        final_md = format_report(structured_sections, today_str)
        md_output_file = OUTPUT_DIR / f"Daily_Brief_{today_str_filename}.md"
        # md_output_file = OUTPUT_DIR / f"Daily_Brief_{today_str}.md" # Original name style in case user prefers
        
        with open(md_output_file, "w", encoding="utf-8") as f:
            f.write(final_md)
        logger.info(f"✅ [Markdown] Report saved to: {md_output_file}")
    
    # 8. Upload to Google Drive (Optional)
    google_drive_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    google_token_json = os.getenv("GOOGLE_TOKEN_JSON")
    
    if google_drive_folder_id:
        logger.info(f"📤 Uploading reports to Google Drive (Folder ID: {google_drive_folder_id})...")
        try:
            from src.exporters.gdrive import GDriveAdapter
            drive_adapter = GDriveAdapter()
            
            # Upload JSON
            if "json" in args.formats:
                logger.info(f"📄 Uploading JSON: {json_output_file}")
                result = drive_adapter.upload_file(str(json_output_file), google_drive_folder_id, mime_type="application/json")
                if result:
                    logger.info(f"✅ JSON uploaded successfully (File ID: {result})")
                
            # Upload Markdown
            if "markdown" in args.formats:
                logger.info(f"📄 Uploading Markdown: {md_output_file}")
                result = drive_adapter.upload_file(str(md_output_file), google_drive_folder_id, mime_type="text/markdown")
                if result:
                    logger.info(f"✅ Markdown uploaded successfully (File ID: {result})")
                
        except Exception as e:
            logger.error(f"❌ Google Drive Upload Failed: {e}")
    else:
        logger.info("ℹ️ GOOGLE_DRIVE_FOLDER_ID not set. Skipping Drive upload.")

    topics_db.close()
    news_db.close()

    # 9. Telegram Alert (Send Sections)
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            from src.exporters.telegram_exporter import TelegramExporter
            logger.info("🚀 Sending report to Telegram...")
            
            # Support multiple chat IDs separated by comma
            chat_ids = [cid.strip() for cid in TELEGRAM_CHAT_ID.split(',')]
            
            header = f"📊 *Daily Market Intelligence* ({today_str})\n\n주요 시장 동향 브리핑입니다."
            
            for chat_id in chat_ids:
                logger.info(f"  → Sending to: {chat_id}")
                exporter = TelegramExporter(TELEGRAM_BOT_TOKEN, chat_id)
                exporter.send_report_sections(structured_sections, header_text=header)
                logger.info(f"  ✅ Sent to {chat_id}")
            
        except Exception as e:
            logger.error(f"❌ Telegram Export Failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
    else:
        logger.info("ℹ️ Telegram configuration missing. Skipping Telegram export.")

if __name__ == "__main__":
    main()
