#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 7: Evergreen Content Generator (run_p7.py)

Function:
1.  Read `topics.db` (Phase 5 output).
2.  Select 3 "Evergreen" & "High CPC" topics using a Strategist LLM.
3.  Fetch full article details from `news.db`.
4.  Generate two assets for each topic:
    -   SEO-optimized Blog Post (Markdown)
    -   YouTube Script (Spoken Word)
5.  Save outputs to `outputs/content/{date}/`.
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

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from storage.db_adapter import DatabaseAdapter
from src.utils.logger import setup_logger
from src.utils.timezone_utils import format_kst_date, format_kst_datetime
from config.settings import (
    DB_TYPE, DB_NAME, LOG_LEVEL, GOOGLE_API_KEY, GEMINI_MODEL, BASE_DIR
)
from config.prompts.content_creator import (
    get_content_strategist_prompt,
    get_seo_blog_prompt,
    get_youtube_script_prompt
)

# Initialize Logger
logger = setup_logger(log_level=LOG_LEVEL)

# Constants
TOPICS_DB_PATH = BASE_DIR / "data" / "topics.db"
OUTPUT_DIR = BASE_DIR / "outputs" / "content"

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
        """Fetch all topics with minimal metadata"""
        self.cursor.execute("SELECT id, category, topic_title, news_ids FROM topics")
        return self.cursor.fetchall()

    def close(self):
        if self.connection:
            self.connection.close()


def generate_content(model: Any, system_prompt: str, user_prompt: str, retries: int = 3) -> str:
    """Generate content using Gemini with retry logic"""
    for attempt in range(retries):
        try:
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            logger.warning(f"Gemini generation failed (Attempt {attempt+1}/{retries}): {e}")
            time.sleep(2 ** attempt)  # Exponential backoff
    
    logger.error("❌ Gemini generation failed after all retries.")
    return "생성 실패 (API Error)"


def fetch_article_details(news_db: DatabaseAdapter, news_ids: List[int]) -> List[Dict[str, Any]]:
    """Fetch detailed article info (Title, Publisher, Snippet) from news.db"""
    if not news_ids:
        return []
    
    placeholders = ",".join(["?"] * len(news_ids)) if DB_TYPE == "sqlite" else ",".join(["%s"] * len(news_ids))
    
    # Assumes 'processed_news' links to 'raw_news'
    query = f"""
        SELECT p.id, r.title, COALESCE(r.publisher, r.source) as publisher, r.snippet
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
                "snippet": row[3]
            })
        return articles
    except Exception as e:
        logger.error(f"Error fetching articles {news_ids}: {e}")
        return []


def parse_selection_json(json_text: str) -> List[int]:
    """Parse selection JSON output"""
    try:
        clean_text = re.sub(r"```json\s*|\s*```", "", json_text, flags=re.IGNORECASE).strip()
        data = json.loads(clean_text)
        return data.get("selected_ids", [])
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Selection JSON: {e}")
        logger.debug(f"Raw Output: {json_text}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Phase 7: Evergreen Content Generator")
    parser.add_argument("--limit", type=int, default=3, help="Number of topics to generate")
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
    logger.info("🎬 Phase 7: Evergreen Content Generator Start")
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

    # 4. Load Topic Metadata
    raw_topics = topics_db.get_all_topics_metadata()
    logger.info(f"📥 Loaded {len(raw_topics)} topics from DB.")

    topic_Metadata_list = []
    topic_map = {} # ID -> Topic Object

    for t in raw_topics:
        # Filter: Skip if news count is too small (e.g., < 2) to ensure enough content
        news_ids = json.loads(t['news_ids'])
        if len(news_ids) < 2:
            continue

        raw_meta = {
            "id": t['id'],
            "category": t['category'],
            "title": t['topic_title'],
            "news_ids": news_ids
        }
        topic_Metadata_list.append(f"ID: {t['id']} | Category: {t['category']} | Title: {t['topic_title']}")
        topic_map[t['id']] = raw_meta

    if not topic_Metadata_list:
        logger.warning("No eligible topics found (min 2 articles).")
        return

    # 5. [Step 1] Strategist Selection
    logger.info("🧠 [Step 1] Content Strategist is selecting 3 Evergreen Topics...")
    
    strategist_prompt = get_content_strategist_prompt()
    topics_text = "\n".join(topic_Metadata_list)
    system_prompt = "You are a Content Strategist."
    
    selection_response = generate_content(model, system_prompt, f"{strategist_prompt}\n\n[Topic List]\n{topics_text}")
    selected_ids = parse_selection_json(selection_response)
    
    # Safety check: if selection fails, pick top 3 by news count
    if not selected_ids:
        logger.warning("⚠️ Selection failed, fallback to top 3 by size.")
        sorted_topics = sorted(topic_map.values(), key=lambda x: len(x['news_ids']), reverse=True)
        selected_ids = [t['id'] for t in sorted_topics[:3]]

    logger.info(f"✅ Selected Topics: {selected_ids}")

    # 6. [Step 2 & 3] Generate Content (Sequential or Parallel)
    today_str = format_kst_date("%Y-%m-%d")
    output_path = OUTPUT_DIR / today_str
    output_path.mkdir(parents=True, exist_ok=True)

    for i, tid in enumerate(selected_ids):
        if tid not in topic_map:
            continue
            
        topic = topic_map[tid]
        logger.info(f"🚀 Processing Topic {i+1}/{len(selected_ids)}: {topic['title']}")
        
        # A. Fetch Articles
        articles = fetch_article_details(news_db, topic['news_ids'])
        
        # Prepare context text
        articles_text = ""
        for art in articles:
            articles_text += f"- Title: {art['title']}\n  Snippet: {art['snippet']}\n\n"
            
        topic_meta_str = f"Category: {topic['category']}, Title: {topic['title']}"

        # B. Generate Blog Post
        logger.info("  ✍️ Writing SEO Blog Post...")
        blog_prompt = get_seo_blog_prompt(topic_meta_str, articles_text)
        blog_content = generate_content(model, "You are a SEO Writer.", blog_prompt)
        
        # C. Generate YouTube Script
        logger.info("  🎥 Writing YouTube Script...")
        script_prompt = get_youtube_script_prompt(blog_content) # Use the blog content as source
        script_content = generate_content(model, "You are a Scriptwriter.", script_prompt)
        
        # D. Save to File
        # Sanitize filename
        safe_title = re.sub(r'[\\/*?:"<>|]', "", topic['title']).replace(" ", "_")
        filename = f"topic_{tid}_{safe_title}.md"
        file_path = output_path / filename
        
        final_markdown = f"""# 📝 Blog Post & Script
**Topic:** {topic['title']}
**Date:** {format_kst_datetime()}
**Source:** Phase 7 Auto-Generator

---

{blog_content}

---
---

{script_content}
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(final_markdown)
            
        logger.info(f"  ✅ Saved to: {file_path}")

    logger.info(f"✨ Phase 7 Complete. All assets saved in {output_path}")

    # 7. Upload to Google Drive
    google_drive_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
    
    if google_drive_folder_id:
        logger.info(f"📤 Uploading content to Google Drive (Folder ID: {google_drive_folder_id})...")
        try:
            from src.exporters.gdrive import GDriveAdapter
            drive_adapter = GDriveAdapter()
            
            # Helper to upload all generated files
            for md_file in output_path.glob("*.md"):
                logger.info(f"📄 Uploading: {md_file.name}")
                result = drive_adapter.upload_file(str(md_file), google_drive_folder_id, mime_type="text/markdown")
                if result:
                    logger.info(f"✅ Uploaded successfully (File ID: {result})")
                else:
                    logger.warning(f"⚠️ Failed to upload {md_file.name}")
                
        except Exception as e:
            logger.error(f"❌ Google Drive Upload Failed: {e}")
    else:
        logger.info("ℹ️ GOOGLE_DRIVE_FOLDER_ID not set. Skipping Drive upload.")

    topics_db.close()
    news_db.close()


if __name__ == "__main__":
    main()
