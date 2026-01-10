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
CATEGORY_MAP = {
    'G_macro': 'Global > Macro',
    'G_market': 'Global > Market',
    'G_tech': 'Global > Tech',
    'G_region': 'Global > Region',
    'K_macro': 'Korea > Macro',
    'K_market': 'Korea > Market',
    'K_industry': 'Korea > Industry',
    'RealEstate_G': 'Real Estate > Global',
    'RealEstate_K': 'Real Estate > Korea'
}

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

def curate_articles(articles: List[Dict[str, Any]], max_candidates: int = 12) -> List[Dict[str, Any]]:
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
        is_trusted = any(tp.lower() in pub for tp in TRUSTED_PUBLISHERS)
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

def process_section_task(section_name: str, topic_ids: List[int], topic_map: Dict, model: Any, system_prompt: str) -> tuple:
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
            for tid in topic_ids:
                if tid in topic_map:
                    t_obj = topic_map[tid]
                    news_ids = json.loads(t_obj['news_ids_json'])
                    articles = fetch_article_details(local_db, news_ids)
                    
                    # Curation
                    curated_articles = curate_articles(articles, max_candidates=12)

                    section_context_data.append({
                        "title": t_obj['title'],
                        "count": t_obj['count'],
                        "articles": curated_articles
                    })
        finally:
            local_db.close()
        
        sec_prompt = get_section_body_prompt(section_name)
        sec_json = json.dumps(section_context_data, ensure_ascii=False, indent=2)
        
        content = generate_content(model, system_prompt, sec_prompt, sec_json)
        return section_name, content
    except Exception as e:
        logger.error(f"Error processing section '{section_name}': {e}")
        return section_name, "생성 중 오류 발생"

def process_executive_summary_task(exec_summary_ids: List[int], topic_map: Dict, model: Any, system_prompt: str) -> tuple:
    """Worker function for Executive Summary"""
    try:
        if not exec_summary_ids:
            return "Executive Summary", "N/A (No topics selected)"
            
        # Create independent DB connection for this thread
        local_db = DatabaseAdapter(db_type=DB_TYPE, database=DB_NAME)
        local_db.connect()

        try:
            exec_context_data = []
            for tid in exec_summary_ids:
                if tid in topic_map:
                    t_obj = topic_map[tid]
                    news_ids = json.loads(t_obj['news_ids_json'])
                    articles = fetch_article_details(local_db, news_ids)
                    # Curation
                    curated_articles = curate_articles(articles, max_candidates=12)

                    exec_context_data.append({
                        "title": t_obj['title'],
                        "category": t_obj['display_category'],
                        "count": t_obj['count'],
                        "articles": curated_articles
                    })
        finally:
            local_db.close()
        
        exec_prompt = get_key_takeaways_prompt()
        exec_json = json.dumps(exec_context_data, ensure_ascii=False, indent=2)
        content = generate_content(model, system_prompt, exec_prompt, exec_json)
        return "Executive Summary", content
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


def format_report(sections: Dict[str, str], date_str: str) -> str:
    """Combine sections into final Markdown"""
    md = f"""# 📊 Daily Market Intelligence
**Date:** {date_str}

---

## 1. Executive Summary
{sections.get('Executive Summary', '정보 없음')}

---

## 2. 🌍 Global Market
### 📉 Macro (Economy/Rates)
{sections.get('Global > Macro', '특이사항 없음.')}

### 🚀 Market (Stock/Indices)
{sections.get('Global > Market', '특이사항 없음.')}

### 🤖 Tech (AI/Semiconductors)
{sections.get('Global > Tech', '특이사항 없음.')}

### 🌏 Region (China/Eurozone)
{sections.get('Global > Region', '특이사항 없음.')}

---

## 3. 🇰🇷 Korea Market
### 🚀 Market (Stock/Indices)
{sections.get('Korea > Market', '특이사항 없음.')}

### 💸 Macro (FX/Rates)
{sections.get('Korea > Macro', '특이사항 없음.')}

### 🏭 Industry (Company/Sector)
{sections.get('Korea > Industry', '특이사항 없음.')}

---

## 4. 🏢 Real Estate
### 🌐 Global Real Estate
{sections.get('Real Estate > Global', '특이사항 없음.')}

### 🇰🇷 Korea Real Estate
{sections.get('Real Estate > Korea', '특이사항 없음.')}

---
*Generated by Auto-DMI System at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
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
    selection_input_data = json.dumps(topic_metadata_list, ensure_ascii=False, indent=2)
    
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
            exec_summary_ids, topic_map, model, system_prompt
        ))
        
        # 6-2. Submit Section Tasks
        for section_name, topic_ids in section_picks.items():
            futures.append(executor.submit(
                process_section_task,
                section_name, topic_ids, topic_map, model, system_prompt
            ))
            
        # 6-3. Collect Results
        for future in as_completed(futures):
            sec_name, content = future.result()
            generated_sections[sec_name] = content
            logger.info(f"  -> ✅ Completed: {sec_name}")

    duration = time.time() - start_time
    logger.info(f"✨ All sections generated in {duration:.2f} seconds.")

    # 7. Format & Save
    today_str = datetime.now().strftime("%Y-%m-%d")

    # 7. Render & Save Outputs based on CLI args
    if "json" in args.formats:
        json_output_file = OUTPUT_DIR / f"Daily_Market_Intelligence_{today_str}.json"
        report_data = {
            "meta": {
                "date": today_str,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "version": "1.0"
            },
            "sections": generated_sections
        }
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(json_output_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ [JSON] Report saved to: {json_output_file}")

    if "markdown" in args.formats:
        final_md = format_report(generated_sections, today_str)
        md_output_file = OUTPUT_DIR / f"Daily_Market_Intelligence_{today_str}.md"
        with open(md_output_file, "w", encoding="utf-8") as f:
            f.write(final_md)
        logger.info(f"✅ [Markdown] Report saved to: {md_output_file}")
    
    topics_db.close()
    news_db.close()

if __name__ == "__main__":
    main()
