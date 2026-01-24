#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 5: Event Clustering (run_p5.py)

기능:
1. Phase 4에서 'KEEP'으로 분류된 기사를 가져옴 (news.db)
2. 카테고리별로 그룹화
3. Step 1: 1차 클러스터링 (Reason 기반) -> 시트 5.topics_step1 및 DB 저장
   (Step 2 Refinement 과정 삭제됨)

Usage:
    python run_p5.py
"""

import sys
import json
import logging
import argparse
import sqlite3
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict

# 프로젝트 루트 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from storage.db_adapter import DatabaseAdapter
from src.exporters.gsheet import GSheetAdapter
from src.utils.logger import setup_logger
from src.utils.timezone_utils import format_kst_date
from config.settings import (
    DB_TYPE, DB_NAME, LOG_LEVEL, OPENAI_API_KEY, GOOGLE_API_KEY, GEMINI_MODEL, GOOGLE_SHEET_ID, BASE_DIR
)
from config.prompts.topic_clustering import get_topic_clustering_prompt
from src.processors.similarity_deduplicator import SimilarityDeduplicator

# Google Generative AI check
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# 로거 설정
logger = setup_logger(log_level=LOG_LEVEL)

TOPICS_DB_PATH = BASE_DIR / "data" / "topics.db"


class TopicsDB:
    """topics.db 전용 간단한 어댑터"""
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.connection = None
        self.cursor = None

    def connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.cursor = self.connection.cursor()
        self._create_table()

    def _create_table(self):
        query = """
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                topic_title TEXT,
                news_ids TEXT, -- JSON List of IDs
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """
        self.cursor.execute(query)
        self.connection.commit()

    def insert_topic(self, category: str, topic_title: str, news_ids: List[int]):
        query = "INSERT INTO topics (category, topic_title, news_ids) VALUES (?, ?, ?)"
        self.cursor.execute(query, (category, topic_title, json.dumps(news_ids)))
        self.connection.commit()
    
    def clear_topics(self):
        self.cursor.execute("DELETE FROM topics")
        self.connection.commit()

    def get_all_topics(self):
        self.cursor.execute("SELECT * FROM topics ORDER BY id DESC")
        return self.cursor.fetchall()

    def close(self):
        if self.connection:
            self.connection.close()

    def reset_db(self):
        """Drop and recreate table"""
        self.cursor.execute("DROP TABLE IF EXISTS topics")
        self.connection.commit()
        self._create_table()
        logger.warning("⚠️  topics.db has been reset (table dropped and recreated).")



def get_keep_articles(db: DatabaseAdapter, hours: int = 24) -> List[Dict[str, Any]]:
    """KEEP 기사 조회 (최근 N시간 내 수집된 기사만)"""
    try:
        cursor = db.connection.cursor()
        
        # 시간 필터 계산 (UTC 기준)
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Publisher 정보도 함께 가져오기
        if DB_TYPE == "sqlite":
             query = """
                SELECT p.id, r.title, p.llm_category, p.llm_reason, COALESCE(r.publisher, r.source) as pub
                FROM processed_news p
                JOIN raw_news r ON p.ref_raw_id = r.id
                WHERE p.llm_decision = 'KEEP'
                  AND r.collected_at >= ?
                ORDER BY p.id DESC
            """
             cursor.execute(query, (cutoff_time,))
        else:
             query = """
                SELECT p.id, r.title, p.llm_category, p.llm_reason, COALESCE(r.publisher, r.source) as pub
                FROM processed_news p
                JOIN raw_news r ON p.ref_raw_id = r.id
                WHERE p.llm_decision = 'KEEP'
                  AND r.collected_at >= %s
                ORDER BY p.id DESC
            """
             cursor.execute(query, (cutoff_time,))
            
        rows = cursor.fetchall()
        
        articles = []
        for row in rows:
            articles.append({
                "id": row[0],
                "title": row[1],
                "category": row[2],
                "reason": row[3],
                "publisher": row[4],
                "source": row[4] # For deduplicator source tier check
            })
        return articles
    except Exception as e:
        logger.error(f"❌ Failed to fetch KEEP articles: {e}")
        return []



def clean_llm_json_output(conversation: str) -> str:
    """LLM 출력에서 Markdown 코드 블록 및 불필요한 텍스트 제거"""
    import re
    cleaned_content = conversation.strip()
    
    # 1. Markdown code block extraction
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned_content)
    if match:
        return match.group(1).strip()
    
    # 2. If no code block, try to find the first '[' (since we expect a list)
    #    or '{' if we expected a dict (but here we mainly expect list).
    #    Let's just return stripped content if no code block found, 
    #    but remove common prefixes if needed? 
    #    Actually, simple replacement of backticks might be safer as fallback
    if "```" in cleaned_content:
        cleaned_content = cleaned_content.replace("```json", "").replace("```", "").strip()
        
    return cleaned_content


def robust_json_load(content: str) -> Any:
    """JSON 파싱 시도 (리스트/딕셔너리 처리)"""
    try:
        parsed = json.loads(content)
        return parsed
    except json.JSONDecodeError as e:
        logger.error(f"JSON Parsing Error: {e}")
        logger.error(f"Failed Content Preview: {content[:500]}...")  # Log first 500 chars
        return []


def normalize_clusters(parsed: Any) -> List[Dict[str, Any]]:
    """LLM 출력을 표준 포맷(List[Dict])으로 변환"""
    clusters = []
    if isinstance(parsed, dict):
        # {"topics": [...]} 형태 시도
        found_list = False
        for key, value in parsed.items():
            if isinstance(value, list):
                clusters = value
                found_list = True
                break
        
        if not found_list:
            clusters = [parsed]
            
    elif isinstance(parsed, list):
        clusters = parsed
        
    valid_clusters = []
    for c in clusters:
        if isinstance(c, dict):
            # Key normalization: "topic" or "topic_title" -> "topic"
            if "topic_title" in c and "topic" not in c:
                c["topic"] = c["topic_title"]
            valid_clusters.append(c)
            
    return valid_clusters


def cluster_step1(model: Any, category: str, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Step 1: 1차 클러스터링 (Reason 기반) - Gemini Version"""
    if not articles:
        return []
    
    logger.info(f"🤖 [Step 1] Clustering {len(articles)} articles in '{category}'...")

    system_prompt = get_topic_clustering_prompt()
    
    input_data = [
        {"i": a["id"], "r": a["reason"]} # id -> i, reason -> r
        for a in articles
    ]
    # Minified JSON
    user_content = json.dumps(input_data, ensure_ascii=False, separators=(',', ':'))
    
    # Update prompt slightly to inform LLM of key change (implicitly) 
    # Actually, Gemini is smart enough to infer i=id, r=reason from context if we just say "list of articles".
    # But for safety, we can prepend a tiny legend or let it infer. 
    # Given the prompt says "Each item has an id and a reason", mapping i/r is trivial for Gemini 1.5/2.0.
    full_prompt = f"{system_prompt}\n\nCategory: {category}\n\nArticles (i=id, r=reason):\n{user_content}"

    try:
        response = model.generate_content(full_prompt)
        content = clean_llm_json_output(response.text)
        parsed = robust_json_load(content)
        return normalize_clusters(parsed)

    except Exception as e:
        logger.error(f"❌ Step 1 Failed for '{category}': {e}")
        return []


def translate_titles(model: Any, titles: List[str]) -> List[str]:
    """
    Translate foreign article titles to Korean using Gemini.
    Returns list of translated titles (or empty string if already Korean).
    """
    if not titles:
        return []
    
    # Filter out empty titles
    non_empty_titles = [(i, title) for i, title in enumerate(titles) if title]
    
    if not non_empty_titles:
        return ["" for _ in titles]
    
    logger.info(f"🌐 Translating {len(non_empty_titles)} article titles to Korean...")
    
    # Create a prompt for batch translation
    # Optimization: id -> i, title -> t, Minified JSON
    titles_data = [{"i": i, "t": title} for i, title in non_empty_titles]
    titles_json = json.dumps(titles_data, ensure_ascii=False, separators=(',', ':'))
    
    prompt = f"""You are a professional translator. Translate the following article titles to Korean.

Rules:
1. If a title is already in Korean, return an empty string "" for that title
2. If a title is in a foreign language (English, etc.), translate it to natural Korean
3. Keep proper nouns (company names, people names, places) in their original form
4. Return ONLY a valid JSON array in this exact format:
[
  {{"i": 0, "t": "번역된 제목 또는 빈 문자열"}},
  {{"i": 1, "t": "번역된 제목 또는 빈 문자열"}}
]

Titles to translate (i=id, t=title):
{titles_json}

Return ONLY the JSON array, no other text."""
    
    try:
        response = model.generate_content(prompt)
        content = clean_llm_json_output(response.text)
        parsed = robust_json_load(content)
        
        # Create result array with same length as input
        translations = ["" for _ in titles]
        
        if isinstance(parsed, list):
            for item in parsed:
                # Optimized keys: i=id, t=translation
                if isinstance(item, dict):
                    idx = item.get("i")
                    trans_text = item.get("t")
                    
                    if idx is not None:
                        # Map back to original indices
                        for orig_idx, orig_title in non_empty_titles:
                            if orig_idx == idx:
                                translations[orig_idx] = trans_text or ""
                                break
        
        return translations
    
    except Exception as e:
        logger.error(f"❌ Translation Failed: {e}")
        return ["" for _ in titles]


def init_sheet(sheet_id: str, tab_name: str):
    """시트 초기화 (Clear & Header)"""
    if not sheet_id:
        return

    try:
        adapter = GSheetAdapter(sheet_id=sheet_id, worksheet_name=tab_name)
        adapter.connect()
        # Retry-safe clear
        adapter.clear_all_data(keep_headers=False)
        
        # 헤더
        headers = [
            ["Category", "Topic Title", "News Count", "Reason", "Publisher", "Title", "Title (Korean)", "URL"]
        ]
        # Retry-safe insert
        adapter.insert_raw_rows(headers, 1)
        logger.info(f"✅ Initialized sheet '{tab_name}'")
    except Exception as e:
        logger.error(f"❌ Sheet Init Failed ({tab_name}): {e}")


def append_topics_to_sheet(sheet_id: str, tab_name: str, topic_list: List[Dict[str, Any]], news_db: DatabaseAdapter, start_row: int, model: Any = None) -> int:
    """결과 리스트를 구글 시트에 추가 (Append)"""
    if not sheet_id or not topic_list:
        return 0

    try:
        adapter = GSheetAdapter(sheet_id=sheet_id, worksheet_name=tab_name)
        adapter.connect()
        
        # Sort topic_list by news count DESC before appending
        # (Within the category, larger topics first)
        topic_list.sort(key=lambda x: -len(x.get("news_ids", [])))

        sheet_rows = []
        
        for i, topic in enumerate(topic_list):
            category = topic.get("category", "")
            title = topic.get("topic", "")
            news_ids = topic.get("news_ids", [])
            
            if not news_ids:
                continue
                
            # 뉴스 정보 조회
            placeholders = ",".join(["?"] * len(news_ids)) if DB_TYPE == "sqlite" else ",".join(["%s"] * len(news_ids))
            
            cursor = news_db.connection.cursor()
            
            if DB_TYPE == "sqlite":
                q = f"""
                    SELECT r.title, p.llm_reason, COALESCE(r.publisher, r.source) as pub, r.url
                    FROM processed_news p
                    JOIN raw_news r ON p.ref_raw_id = r.id
                    WHERE p.id IN ({placeholders})
                """
                cursor.execute(q, tuple(news_ids))
            else:
                q = f"""
                    SELECT r.title, p.llm_reason, COALESCE(r.publisher, r.source) as pub, r.url
                    FROM processed_news p
                    JOIN raw_news r ON p.ref_raw_id = r.id
                    WHERE p.id IN ({placeholders})
                """
                cursor.execute(q, tuple(news_ids))
            
            rows = cursor.fetchall()
            
            titles_list = []
            urls_list = []
            for r in rows:
                title_text = r[0]
                url = r[3]
                titles_list.append(title_text)
                urls_list.append(url if url else "")

            reasons_list = [r[1] or "" for r in rows]
            pubs_list = [r[2] or "" for r in rows]
            
            reasons_str = "\n".join(reasons_list)
            pubs_str = "\n".join(pubs_list)
            titles_str = "\n".join(titles_list)
            urls_str = "\n".join(urls_list)
            
            
            # Use Google Sheets GOOGLETRANSLATE formula instead of LLM
            # Formula will auto-translate foreign titles to Korean
            # Note: We need to track the current row number in the sheet
            # Since we're appending, we need to calculate the row offset
            
            row_idx = start_row + i
            # F col is 'Title' (6th column? A=1, B=2, C=3, D=4, E=5, F=6)
            # Headers: Category, Topic Title, News Count, Reason, Publisher, Title, Title (Korean), URL
            # A, B, C, D, E, F, G, H
            # So Title is F. Correct.
            
            titles_kr_formula = f'=IF(ISBLANK(F{row_idx}), "", GOOGLETRANSLATE(F{row_idx}, "en", "ko"))'
            
            sheet_rows.append([category, title, len(news_ids), reasons_str, pubs_str, titles_str, titles_kr_formula, urls_str])

        if sheet_rows:
            # Retry-safe append with USER_ENTERED to parsing formulas
            adapter.append_raw_rows(sheet_rows, value_input_option='USER_ENTERED')
            logger.info(f"✅ Appended {len(topic_list)} topics to sheet '{tab_name}'")
            return len(sheet_rows)
            
        return 0

    except Exception as e:
        logger.error(f"❌ Sheet Append Failed ({tab_name}): {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Phase 5: Event Clustering")
    parser.add_argument("--no-export", action="store_true", help="Sheet 출력 건너뛰기")
    parser.add_argument("--reset-db", action="store_true", help="DB 초기화 (테이블 삭제 후 재생성)")
    args = parser.parse_args()

    # 2. DB 연결 (Topics DB)
    topics_db = TopicsDB(TOPICS_DB_PATH)
    topics_db.connect()

    if args.reset_db:
        topics_db.reset_db()
        topics_db.close()
        return

    if not GENAI_AVAILABLE:
        logger.error("❌ google-generativeai package is not installed.")
        return
        
    if not GOOGLE_API_KEY:
        logger.error("❌ GOOGLE_API_KEY is missing.")
        return

    logger.info("="*80)
    logger.info(f"🚀 Phase 5: Event Clustering Start (Model: {GEMINI_MODEL})")
    logger.info("="*80)

    # 1. DB 연결 (News DB)
    news_db = DatabaseAdapter(db_type=DB_TYPE, database=DB_NAME)
    news_db.connect()

    # DB 초기화 (이미 위에서 연결됨, 일반 실행시는 clear_topics 호출)
    # topics_db is already connected above
    topics_db.clear_topics()

    # 3. KEEP 기사 가져오기
    articles = get_keep_articles(news_db)
    logger.info(f"📥 Found {len(articles)} KEEP articles.")
    
    # [NEW] Similarity Deduplication
    try:
        deduplicator = SimilarityDeduplicator(similarity_threshold=0.5)
        dedup_result = deduplicator.run(articles)
        articles = dedup_result["articles"]
    except Exception as e:
        logger.error(f"⚠️ Deduplication failed, proceeding with original list: {e}")
    
    # 4. 카테고리별 그룹화
    grouped = defaultdict(list)
    for a in articles:
        cat = a["category"] or "Uncategorized"
        grouped[cat].append(a)

    # Initialize Gemini
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    
    # 결과를 모을 리스트
    all_results = []
    
    # 5. 카테고리별 수행
    # Sort categories to ensure deterministic order (e.g. alphabetical)
    sorted_categories = sorted(grouped.keys())

    # 4. Sheet Init (Clear & Headers) - BEFORE Loop
    tab_name = format_kst_date("%y%m%d")
    # tab_name = "5.Topics"  
    if not args.no_export:
        init_sheet(GOOGLE_SHEET_ID, tab_name)
    
    # Track current row for formula generation
    # Header is row 1, so data starts at row 2
    current_sheet_row = 2

    # 5. 카테고리별 수행
    for category in sorted_categories:
        items = grouped[category]
        if len(items) == 0:
            continue
            
        logger.info(f"Processing Category: {category} ({len(items)} articles)")
        
        # --- Step 1: Clustering ---
        step1_clusters = cluster_step1(model, category, items)
        
        # Add category info to results
        for c in step1_clusters:
            c["category"] = category
            
        all_results.extend(step1_clusters)
        
        # DB 저장 (바로 저장)
        for cluster in step1_clusters:
            topic_title = cluster.get("topic")
            news_ids = cluster.get("news_ids", [])
            if topic_title and news_ids:
                topics_db.insert_topic(category, topic_title, news_ids)
        
        # Sheet Append (Incremental)
        if not args.no_export:
            # Append only this category's clusters
            added_count = append_topics_to_sheet(
                GOOGLE_SHEET_ID, 
                tab_name,
                step1_clusters, 
                news_db,
                start_row=current_sheet_row,
                model=model  # Pass model for title translation
            )
            current_sheet_row += added_count

    logger.info(f"✅ Completed. Generated {len(all_results)} topics.")


    news_db.close()
    topics_db.close()


if __name__ == "__main__":
    main()
