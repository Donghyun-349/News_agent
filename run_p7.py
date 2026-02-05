#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 7: Global Daily Market Intelligence Report Generator (run_p7.py)

Function:
1. [Scan] Load data from `topics.db` (Clusters) - Metadata Only.
2. [Filter] Filter for ENGLISH articles only (language = 'en').
3. [Select] "Chief Editor" LLM selects high-impact global topics.
4. [Retrieve] Fetch full article content (Snippets) ONLY for selected topics.
5. [Write] "Global Market Analyst" LLM generates the professional English report.
6. Export report to JSON and Markdown.

Sections:
- Executive Summary
- Global Outlook (Economy/Policy - was Global > Macro)
- Global Market (Stocks/Indices)
- Global Tech (AI/Semiconductors)

**Korea sections and Real Estate sections are excluded.**
"""

import sys
import os
import json
import logging
import argparse
import sqlite3
import time
import re
from difflib import SequenceMatcher
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
from src.utils.timezone_utils import get_et_now, format_et_date, format_et_datetime
from config.settings import (
    DB_TYPE, DB_NAME, LOG_LEVEL, GOOGLE_API_KEY, GEMINI_MODEL, BASE_DIR
)
from config.prompts.global_market_intelligence import (
    get_system_prompt_en,
    get_topic_selection_prompt_en,
    get_executive_summary_prompt_en,
    get_section_body_prompt_en
)

# Initialize Logger
logger = setup_logger(log_level=LOG_LEVEL)

# Constants
TOPICS_DB_PATH = BASE_DIR / "data" / "topics.db"
OUTPUT_DIR = BASE_DIR / "outputs" / "daily_reports"

# Map raw categories to report sections (ENGLISH VERSION - GLOBAL ONLY)
# Map raw categories to report sections (ENGLISH VERSION - GLOBAL ONLY)
CATEGORY_MAP_EN = {
    'G_mac': 'Global Outlook',      # Economy/Policy
    'G_mak': 'Global Market',        # Stocks/Indices
    'G_tec': 'Global Tech',          # AI/Semiconductors
    'G_tech': 'Global Tech',         # Alternative spelling
    'G_re': 'Global Region',         # Regional developments
    'G_reg': 'Global Region',        # Alternative code
    # Korea and Real Estate sections excluded
}

# Trusted Publishers List (Global focus)
TRUSTED_PUBLISHERS_ORDER = [
    # Global Tier 1
    "Bloomberg", "Reuters", "Wall Street Journal", "Financial Times",
    "CNBC", "MarketWatch", "The Economist", "Forbes"
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


def fetch_article_details_en(news_db: DatabaseAdapter, news_ids: List[int]) -> List[Dict[str, Any]]:
    """Fetch detailed article info - FOREIGN PRESS ONLY (based on publisher)"""
    if not news_ids:
        return []
    
    # Foreign Press Publishers (English articles)
    FOREIGN_PUBLISHERS = [
        "Bloomberg", "Reuters", "Financial Times", "Wall Street Journal", 
        "CNBC", "MarketWatch", "The Economist", "Forbes", "Investing",
        "FT", "WSJ", "Barron's", "Business Insider", "TechCrunch",
        "The Verge", "Ars Technica", "digitimes", "fibre-systems.com",
        "Network World", "Asia Business Outlook", "Technetbook",
        "Edge Industry Review", "Astute Group", "Microsoft Source",
        "MSN", "findarticles.com", "Chrome Unboxed", "Retail TouchPoints",
        "Food Industry Executive", "University of Arkansas News",
        "WebProNews", "CX Today", "TechPowerUp", "PC Gamer",
        "The Jerusalem Post", 'Google News'
    ]
    
    placeholders = ",".join(["?"] * len(news_ids)) if DB_TYPE == "sqlite" else ",".join(["%s"] * len(news_ids))
    
    # Fetch articles WITHOUT language filter
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
            publisher = row[2] or ""
            
            # Filter: Only include foreign publishers
            is_foreign = any(fp.lower() in publisher.lower() for fp in FOREIGN_PUBLISHERS)
            
            if is_foreign:
                articles.append({
                    "id": row[0],
                    "title": row[1],
                    "publisher": publisher,
                    "snippet": row[3],
                    "url": row[4]
                })
        
        logger.debug(f"Fetched {len(articles)} foreign press articles from {len(news_ids)} IDs")
        return articles
    except Exception as e:
        logger.error(f"Error fetching foreign press articles {news_ids}: {e}")
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
    return "Generation failed (API Error)"


def sanitize_article_data(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Clean article titles and URLs to prevent Markdown/JSON issues"""
    import re
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    
    def clean_url(url: str) -> str:
        """Remove unnecessary query parameters"""
        if not url:
            return ""
        
        try:
            parsed = urlparse(url)
            essential_params = ['article_id', 'office_id', 'idxno', 'id', 'no', 'seq']
            
            if parsed.query:
                params = parse_qs(parsed.query, keep_blank_values=False)
                cleaned_params = {k: v for k, v in params.items() 
                                if any(essential in k.lower() for essential in essential_params)}
                new_query = urlencode({k: v[0] for k, v in cleaned_params.items()})
                return urlunparse((parsed.scheme, parsed.netloc, parsed.path, 
                                 parsed.params, new_query, ''))
            else:
                return urlunparse((parsed.scheme, parsed.netloc, parsed.path, 
                                 parsed.params, '', ''))
        except Exception:
            return url
    
    cleaned = []
    for art in articles:
        c_art = art.copy()
        
        # Clean title
        raw_title = str(c_art.get('title', ''))
        clean_title = html.unescape(raw_title)
        clean_title = clean_title.replace('[', '(').replace(']', ')')
        
        # Clean URL
        raw_url = c_art.get('url', '')
        clean_u = clean_url(raw_url) if raw_url and raw_url.strip() else ""

        c_art_clean = {
            "id": c_art.get('id'),
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
        return 999  # Not in trusted list

    # Sort: Rank (Asc) -> ID (Desc/Newest)
    sorted_articles = sorted(articles, key=lambda x: (get_rank(x['publisher']), -x['id']))

    selected = []
    publisher_counts = {}  # Track count per publisher

    for art in sorted_articles:
        if len(selected) >= max_candidates:
            break
            
        pub = art['publisher']
        
        # Max 2 articles per publisher
        if publisher_counts.get(pub, 0) >= 2:
            continue
            
        # Title Similarity Check (Dedup)
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
            return section_name, "No significant developments."

        # Create independent DB connection for this thread
        local_db = DatabaseAdapter(db_type=DB_TYPE, database=DB_NAME)
        local_db.connect()

        try:
            # Gather full data
            section_context_data = []
            article_map = {}  # Map ID -> {url, title, pub}
            for tid in topic_ids:
                if tid in topic_map:
                    t_obj = topic_map[tid]
                    news_ids = json.loads(t_obj['news_ids_json'])
                    articles = fetch_article_details_en(local_db, news_ids)  # ENGLISH ONLY
                    
                    # Sanitize Data
                    articles = sanitize_article_data(articles)

                    # Curation
                    curated_articles = curate_articles(articles, trusted_publishers, max_candidates=8)
                    
                    logger.debug(f"[{section_name}] Topic {tid}: {len(curated_articles)} English articles curated")

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
                            {"i": ca['id'], "t": ca['title'], "p": ca['publisher'], "s": ca['snippet']}
                            for ca in curated_articles
                        ]
                    })
        finally:
            local_db.close()
        
        sec_prompt = get_section_body_prompt_en(section_name)
        # Minified JSON
        sec_json = json.dumps(section_context_data, ensure_ascii=False, separators=(',', ':'))
        
        total_articles = sum(len(topic.get("a", [])) for topic in section_context_data)
        logger.info(f"[{section_name}] Sending {total_articles} English articles to LLM")
        
        raw_content = generate_content(model, system_prompt, sec_prompt, sec_json)
        
        # Post-Processing: Convert [Ref:ID] to Citation Links
        def replace_ref(match):
            ref_ids_str = match.group(1)
            ref_ids = [rid.strip() for rid in ref_ids_str.split(',') if rid.strip()]
            
            links = []
            for ref_id in ref_ids:
                if ref_id in article_map:
                    meta = article_map[ref_id]
                    links.append(f"> * [{meta['t']}]({meta['u']}) - ({meta['p']})")
            
            return "\n".join(links) if links else ""

        final_content = re.sub(r'\[Ref:\s*([\d,\s]+)\]', replace_ref, raw_content)

        return section_name, final_content
    except Exception as e:
        logger.error(f"Error processing section '{section_name}': {e}")
        return section_name, "Error during generation"


def process_executive_summary_task(exec_summary_ids: List[int], topic_map: Dict, model: Any, system_prompt: str, trusted_publishers: List[str]) -> tuple:
    """Worker function for Executive Summary - Returns (section_name, (report_title, summary_text))"""
    try:
        if not exec_summary_ids:
            return "Executive Summary", ("Key Market Developments", "N/A (No topics selected)")
            
        # Create independent DB connection
        local_db = DatabaseAdapter(db_type=DB_TYPE, database=DB_NAME)
        local_db.connect()

        try:
            exec_context_data = []
            article_map = {}
            for tid in exec_summary_ids:
                if tid in topic_map:
                    t_obj = topic_map[tid]
                    news_ids = json.loads(t_obj['news_ids_json'])
                    articles = fetch_article_details_en(local_db, news_ids)  # ENGLISH ONLY
                    
                    # Sanitize Data
                    articles = sanitize_article_data(articles)
                    
                    # Curation
                    curated_articles = curate_articles(articles, trusted_publishers, max_candidates=8)

                    exec_context_data.append({
                        "t": t_obj['title'],
                        "c": t_obj['display_category'],
                        "n": t_obj['count'],
                        "a": [
                            {"i": ca['id'], "t": ca['title'], "p": ca['publisher'], "s": ca['snippet']}
                            for ca in curated_articles
                        ]
                    })
        finally:
            local_db.close()
        
        exec_prompt = get_executive_summary_prompt_en()
        exec_json = json.dumps(exec_context_data, ensure_ascii=False, separators=(',', ':'))
        
        total_articles = sum(len(topic.get("a", [])) for topic in exec_context_data)
        logger.info(f"[Executive Summary] Sending {total_articles} English articles to LLM")

        raw_content = generate_content(model, system_prompt, exec_prompt, exec_json)

        # Parse JSON response
        try:
            cleaned = raw_content.strip().replace("```json", "").replace("```", "").strip()
            response_data = json.loads(cleaned)
            
            report_title = response_data.get('report_title', 'Key Market Developments')
            executive_summary_data = response_data.get('executive_summary', [])
            
            # Convert array to numbered list
            if isinstance(executive_summary_data, list):
                executive_summary = "\n".join([f"{i+1}. {item}" for i, item in enumerate(executive_summary_data)])
            else:
                # Fallback for old format (string)
                executive_summary = executive_summary_data
            
            logger.info(f"[Executive Summary] Generated report title: {report_title}")
            
            return "Executive Summary", (report_title, executive_summary)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Executive Summary JSON: {e}")
            logger.error(f"Raw response: {raw_content[:500]}")
            return "Executive Summary", ("Key Market Developments", raw_content)
            
    except Exception as e:
        logger.error(f"Error processing Executive Summary: {e}")
        return "Executive Summary", ("Key Market Developments", "Error during generation")


def parse_selection_json(json_text: str) -> Dict[str, Any]:
    """Robustly parse JSON output from LLM"""
    try:
        clean_text = re.sub(r"```json\s*|\s*```", "", json_text, flags=re.IGNORECASE).strip()
        data = json.loads(clean_text)
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Selection JSON: {e}") 
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
        stripped = line.strip()
        
        if not stripped:
            continue
            
        # Check for link markers
        is_link = stripped.startswith('>') or stripped.startswith('•') or stripped.startswith('- ') or stripped.startswith('*-')
        
        # Check for Title Header
        is_header = stripped.startswith('###') or (stripped.startswith('**') and stripped.endswith('**') and len(stripped) < 100)
        
        if is_link:
            # Parse Markdown Link
            link_content = re.sub(r'^[>•\-\*]+\s*', '', stripped).replace('**', '').strip()
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


def format_report(sections: Dict[str, Any], date_str: str, report_title: str = "") -> str:
    """Combine sections into final Markdown"""
    
    def get_sec_text(key):
        val = sections.get(key, 'No significant developments.')
        if isinstance(val, list):
             full_text = []
             for block in val:
                 title = block.get('title', '')
                 text = block.get('text', '')
                 links = block.get('links', [])
                 
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
             return val.get('summary', '')
        return val

    # Create header with report title
    header_title = f'# 🌐 Global Daily Market Intelligence: "{report_title}"' if report_title else "# 🌐 Global Daily Market Intelligence"
    
    md = f"""{header_title}
**Date:** {date_str}

---

## 1. Executive Summary
{get_sec_text('Executive Summary')}

---

## 2. 🌍 Global Outlook (Economy & Policy)
{get_sec_text('Global Outlook')}

---

## 3. 📈 Global Market (Stocks & Indices)
{get_sec_text('Global Market')}

---

## 4. 🤖 Global Tech (AI & Semiconductors)
{get_sec_text('Global Tech')}

---

## 5. 🌏 Global Region
{get_sec_text('Global Region')}

---
*By Lan Analyst at {format_et_datetime()}*
"""
    return md


def main():
    parser = argparse.ArgumentParser(description="Phase 7: Global Market Intelligence Report Generator (English)")
    parser.add_argument("--formats", nargs="+", default=["json", "markdown"], 
                        choices=["json", "markdown"],
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
    logger.info("🌐 Phase 7: Global Daily Market Intelligence Generator (English) Start")
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

    # 4. [Step 1: SCAN] Load Topic Metadata - FILTER FOR GLOBAL CATEGORIES ONLY
    raw_topics = topics_db.get_all_topics_metadata()
    logger.info(f"📥 Loaded {len(raw_topics)} topics from DB")

    topic_metadata_list = []
    topic_map = {} 

    for t in raw_topics:
        # FILTER: Only include Global categories (G_mac, G_mak, G_tec, G_re)
        if t['category'] not in ['G_mac', 'G_mak', 'G_tec', 'G_tech', 'G_re', 'G_reg']:
            logger.debug(f"Skipping non-global category: {t['category']}")
            continue
        
        mapped_cat = CATEGORY_MAP_EN.get(t['category'], t['category'])
        news_ids = json.loads(t['news_ids'])
        count = len(news_ids)
        
        t_meta = {
            "id": t['id'],
            "original_category": t['category'],
            "display_category": mapped_cat,
            "title": t['topic_title'],
            "count": count,
            "news_ids_json": t['news_ids']
        }
        topic_metadata_list.append({
            "id": t_meta['id'],
            "category": t_meta['original_category'],  # Use shortcode for LLM
            "topic_title": t_meta['title'],
            "count": t_meta['count']
        })
        topic_map[t['id']] = t_meta

    logger.info(f"✅ Filtered to {len(topic_metadata_list)} global topics")

    if not topic_metadata_list:
        logger.warning("⚠️ No global topics found. Exiting.")
        topics_db.close()
        news_db.close()
        return

    # 5. [Step 2: SELECT] Chief Editor selects Top Topics
    logger.info("🧠 [Step 2] Chief Editor is selecting key global topics...")
    selection_prompt = get_topic_selection_prompt_en()
    
    # Payload Optimization
    selection_input_list = []
    for tm in topic_metadata_list:
        selection_input_list.append({
            "i": tm['id'],
            "c": tm['category'],
            "t": tm['topic_title'],
            "n": tm['count']
        })
    
    selection_input_data = json.dumps(selection_input_list, ensure_ascii=False, separators=(',', ':'))
    
    system_prompt = get_system_prompt_en() 
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
        for short_section_name, topic_ids in section_picks.items():
            # Map Short Name to Long Name
            full_section_name = CATEGORY_MAP_EN.get(short_section_name, short_section_name)
            
            # SAFEGUARD: Enforce max 3 topics per section
            if len(topic_ids) > 3:
                logger.warning(f"⚠️ [{full_section_name}] LLM selected {len(topic_ids)} topics, limiting to top 3")
                topic_ids = topic_ids[:3]
            
            futures.append(executor.submit(
                process_section_task,
                full_section_name, topic_ids, topic_map, model, system_prompt, TRUSTED_PUBLISHERS_ORDER
            ))
            
        # 6-3. Collect Results
        report_title = "Key Market Developments"  # Default fallback
        for future in as_completed(futures):
            sec_name, content = future.result()
            
            # Executive Summary returns (report_title, summary_text)
            if sec_name == "Executive Summary":
                if isinstance(content, tuple) and len(content) == 2:
                    report_title, summary_text = content
                    generated_sections[sec_name] = summary_text
                else:
                    generated_sections[sec_name] = content
            else:
                generated_sections[sec_name] = content
                
            logger.info(f"  -> ✅ Completed: {sec_name}")

    duration = time.time() - start_time
    logger.info(f"✨ All sections generated in {duration:.2f} seconds.")
    logger.info(f"📝 Report Title: {report_title}")

    # 7. Format Report (JSON-structured and Markdown)
    today_str = format_et_date("%Y-%m-%d")  # YYYY-MM-DD (New York Time)
    today_str_filename = format_et_date("%Y_%m_%d")  # YYYY_MM_DD (New York Time)

    # STRUCTURING: Parse content into {summary, links}
    structured_sections = {}
    for key, val in generated_sections.items():
        structured_sections[key] = parse_section_content(val)

    # 8. Render & Save Outputs
    if "json" in args.formats:
        json_output_file = OUTPUT_DIR / f"Global_Daily_Brief_{today_str_filename}.json"
        report_data = {
            "meta": {
                "date": today_str,
                "generated_at": format_et_datetime(),  # New York Time
                "version": "1.0",
                "language": "en",
                "report_title": report_title
            },
            "sections": structured_sections
        }
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(json_output_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, separators=(',', ':'))
        logger.info(f"✅ [JSON] Report saved to: {json_output_file}")

    if "markdown" in args.formats:
        final_md = format_report(structured_sections, today_str, report_title)
        md_output_file = OUTPUT_DIR / f"Global_Daily_Brief_{today_str_filename}.md"
        
        with open(md_output_file, "w", encoding="utf-8") as f:
            f.write(final_md)
        logger.info(f"✅ [Markdown] Report saved to: {md_output_file}")
    
    # 9. Upload to Google Drive (Optional)
    google_drive_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    
    if google_drive_folder_id:
        logger.info(f"📤 Uploading reports to Google Drive (Folder ID: {google_drive_folder_id})...")
        try:
            from src.exporters.gdrive import GDriveAdapter
            drive_adapter = GDriveAdapter()
            
            if "json" in args.formats:
                logger.info(f"📄 Uploading JSON: {json_output_file}")
                result = drive_adapter.upload_file(str(json_output_file), google_drive_folder_id, mime_type="application/json")
                if result:
                    logger.info(f"✅ JSON uploaded successfully (File ID: {result})")
                
            if "markdown" in args.formats:
                logger.info(f"📄 Uploading Markdown: {md_output_file}")
                result = drive_adapter.upload_file(str(md_output_file), google_drive_folder_id, mime_type="text/markdown")
                if result:
                    logger.info(f"✅ Markdown uploaded successfully (File ID: {result})")
                
        except Exception as e:
            logger.error(f"❌ Google Drive Upload Failed: {e}")
            logger.warning("⚠️ Continuing pipeline despite upload failure...")
    else:
        logger.info("ℹ️ GOOGLE_DRIVE_FOLDER_ID not set. Skipping Drive upload.")

    # Close DBs
    topics_db.close()
    news_db.close()
    
    logger.info("="*80)
    logger.info("✅ Phase 7 Complete")
    logger.info("="*80)

if __name__ == "__main__":
    main()
