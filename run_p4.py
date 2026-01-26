#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 4: LLM Classification (run_p4.py)

기능:
1. processed_news 테이블에서 기사 조회
2. LLM(GPT-4o)을 사용하여 배치 단위로 9가지 카테고리로 분류
3. 분류 결과 (Decision, Category, Reason)를 DB에 저장
4. 결과 통계를 Google Sheet에 출력 (4.llm_classification)

Usage:
    python run_p4.py
"""

import sys
import json
import re
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# 프로젝트 루트 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from storage.db_adapter import DatabaseAdapter
from src.exporters.gsheet import GSheetAdapter
from src.utils.logger import setup_logger
from config.settings import (
    DB_TYPE, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    GOOGLE_SHEET_ID, LOG_LEVEL, OPENAI_API_KEY
)
from config.prompts.classification_pt import get_p4_topic_classification_prompt

# OpenAI 클라이언트 (Phase 2와 동일하게 체크)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# 로거 설정
logger = setup_logger(log_level=LOG_LEVEL)

def get_articles_to_process(db: DatabaseAdapter, limit: int = None, force_all: bool = False) -> List[Dict[str, Any]]:
    """처리할 기사 조회"""
    try:
        cursor = db.connection.cursor()
        
        # 1. processed_news에서 ref_raw_id를 통해 title, snippet 조인
        # 만약 force_all=False이면, llm_decision이 NULL 또는 ERROR인 것만 조회 (Two-Pass)
        where_clause = "" if force_all else "WHERE (p.llm_decision IS NULL OR p.llm_decision = 'ERROR')"
        limit_clause = f"LIMIT {limit}" if limit else ""
        
        # SQLite vs Others
        query = f"""
            SELECT p.id, r.title
            FROM processed_news p
            JOIN raw_news r ON p.ref_raw_id = r.id
            {where_clause}
            ORDER BY p.id DESC
            {limit_clause}
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        articles = []
        for row in rows:
            articles.append({
                "id": row[0],
                "title": row[1]
            })
            
        return articles
    except Exception as e:
        logger.error(f"❌ Failed to fetch articles: {e}")
        return []

def call_llm_batch(client: OpenAI, articles: List[Dict[str, Any]], model: str = "gpt-4o-mini") -> List[Dict[str, Any]]:
    """LLM 배치 호출"""
    if not articles:
        return []
    
    # Prompt 구성
    system_prompt = get_p4_topic_classification_prompt()
    
    # User Content: JSON Array of articles (Title-only for efficiency)
    user_content_data = [
        {"id": str(a["id"]), "title": a["title"]} 
        for a in articles
    ]
    user_content = json.dumps(user_content_data, ensure_ascii=False, indent=2)
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Here are the articles to classify:\n{user_content}"}
            ],
            temperature=0.0,
            response_format={"type": "json_object"} # JSON 모드
        )
        
        # Parse Response
        response_text = response.choices[0].message.content
        parsed_data = json.loads(response_text)
        
        # GPT가 가끔 {"articles": [...]} 형태로 줄 때도 있고 바로 [...] 줄 때도 있음.
        # 프롬프트는 Array를 요구했으나, json_object 모드는 root object를 강제하기도 함.
        # 따라서 보통 {"results": [...]} 같은 래퍼를 쓰거나 응답을 유연하게 처리.
        
        # 여기서는 프롬프트가 Array를 리턴하라고 강력히 지시했지만, 
        # API response_format={"type": "json_object"}를 쓰면 반드시 {}로 감싸야 오류가 안남.
        # 따라서 프롬프트 수정 혹은 후처리 필요.
        # -> 프롬프트에서 "Return ONLY a JSON Array"라고 했지만 json_object 모드는 { key: value }를 요구함.
        # 안전하게는 response_format을 빼거나, 프롬프트를 { "results": [ ... ] }로 바꾸는게 정석.
        # 일단 P4 프롬프트는 Array를 요구하므로 response_format을 뺍니다. (gpt-4o는 잘 알아들음)
        # 혹은 Text 모드로 받고 파싱.
        
        # 만약 response_format={"type": "json_object"}를 썼다면 에러 났을 수 있음.
        # 위 코드에서 response_format을 제거하고 진행하거나,
        # 프롬프트와 맞춤. 여기서는 response_format 없이 진행하겠습니다.
        
        if isinstance(parsed_data, list):
            return parsed_data
        elif isinstance(parsed_data, dict):
            # 혹시 키값 안에 리스트가 있다면
            for key in parsed_data:
                if isinstance(parsed_data[key], list):
                    return parsed_data[key]
            # 없다면 단일 객체일수도?
            return [parsed_data]
            
        return []
        
    except json.JSONDecodeError:
        logger.error("❌ LLM output is not valid JSON")
        logger.debug(f"Output: {response_text}")
        return []
    except Exception as e:
        logger.error(f"❌ LLM Call Failed: {e}")
        return []

# Defined 9 Categories + Validation
VALID_CATEGORIES = {
    "G_mac", "G_mak", "G_tech", "G_re", 
    "Real_G", "Real_K", 
    "K_mac", "K_mak", "K_in"
}

def call_llm_batch_no_json_mode(client: OpenAI, articles: List[Dict[str, Any]], model: str = "gpt-4o-mini") -> List[Dict[str, Any]]:
    """LLM 배치 호출 (개선된 에러 처리 및 Regex Fallback 포함)"""
    system_prompt = get_p4_topic_classification_prompt()
    
    # Payload Optimization:
    # 1. Rename keys: id -> i, title -> t
    # 2. Remove snippet (title only sufficient per user request)
    user_content_data = [
        {"i": str(a["id"]), "t": a["title"]} 
        for a in articles
    ]
    # 3. Minified JSON: separators=(',', ':') removes whitespace
    user_content = json.dumps(user_content_data, ensure_ascii=False, separators=(',', ':'))
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.0
        )
        content = response.choices[0].message.content
        
        # Markdown backticks 제거 (```json ... ```)
        if "```" in content:
            content = content.replace("```json", "").replace("```", "").strip()
        
        # Parse Response (Array of Arrays)
        # Expected: [[id, decision_bool, category, reason], ...]
        # Robust JSON Extraction: Find first '[' and last ']'
        # Robust JSON Extraction: Find first '['
        raw_list = None
        try:
            start_idx = content.find('[')
            if start_idx == -1:
                # No list found
                logger.warning(f"⚠️ No JSON list found in response. Trying regex fallback...")
            else:
                # Use raw_decode to parse starting from the first bracket
                # This handles cases where there is extra text/data after the valid JSON
                json_str = content[start_idx:]
                raw_list, _ = json.JSONDecoder().raw_decode(json_str)
            
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ JSON Decode Error: {e}. Trying regex fallback...")
        
        # Regex Fallback: Extract list items if JSON parsing failed
        if raw_list is None or not raw_list:
            # Pattern: ["id", decision_bool, "category", "reason"]
            # Handles: ["123", 1, "K_mac", "reason text"], ["124", 0, "G_tech", "reason"]
            pattern = r'\[\s*["\']?(\d+)["\']?\s*,\s*([01]|true|false)\s*,\s*["\']([^"\',]+)["\']\s*,\s*["\']([^"\']*)["\']]'
            matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
            
            if matches:
                logger.info(f"✅ Regex fallback recovered {len(matches)} items")
                raw_list = [[m[0], m[1], m[2], m[3]] for m in matches]
            else:
                logger.error(f"❌ Both JSON and Regex parsing failed. Content: {content[:200]}...")
                # Return ERROR state for all articles in this batch
                return [{"id": str(a["id"]), "decision": "ERROR", "category": None, "reason": "Parsing failed"} for a in articles]
        
        parsed_results = []
        for item in raw_list:
            # Robust parsing: handle both old dict style (just in case) and new list style
            if isinstance(item, list) and len(item) >= 4:
                # [ID, DECISION_BOOL, CATEGORY, REASON]
                p_id = item[0]
                dec_bool = item[1]
                cat = item[2]
                reason = item[3]
                
                # Validation Logic: Hallucination Check (개선됨)
                if cat not in VALID_CATEGORIES:
                    # 잘못된 카테고리 → ERROR 상태로 마킹 (재처리 기회 부여)
                    logger.warning(f"⚠️ Hallucination detected: Category '{cat}' is invalid. Marking as ERROR for retry (ID: {p_id}).")
                    decision = "ERROR"
                else:
                    decision = "KEEP" if str(dec_bool) == "1" or str(dec_bool).lower() == "true" else "DROP"
                
                parsed_results.append({
                    "id": p_id,
                    "decision": decision,
                    "category": cat,
                    "reason": reason
                })
            elif isinstance(item, dict):
                # Fallback for dict (should mostly not happen with new prompt)
                parsed_results.append(item)
                
        return parsed_results
        
    except Exception as e:
        logger.error(f"❌ LLM Call Failed: {e}")
        return []

def export_to_gsheet(run_stats: Dict[str, int], sheet_id: str, db: DatabaseAdapter):
    """결과를 Google Sheets에 출력"""
    if not sheet_id:
        return
    
    tab_name = "4.llm_classification"
    
    try:
        adapter = GSheetAdapter(sheet_id=sheet_id, worksheet_name=tab_name)
        adapter.connect()
        adapter.worksheet.clear()
        
        # 최근 처리된 항목들 조회 (limit) - 혹은 전체 조회
        cursor = db.connection.cursor()
        
        # 1. Total Remaining in DB (KEEP only)
        # Note: DROP items are deleted at the end of script, so current DB might still have them if called before cleanup
        # But we want to show "Effective Saved".
        if DB_TYPE == "sqlite":
            cursor.execute("SELECT COUNT(*) FROM processed_news WHERE llm_decision = 'KEEP'")
        else:
            cursor.execute("SELECT COUNT(*) FROM processed_news WHERE llm_decision = 'KEEP'")
        
        total_saved_in_db = cursor.fetchone()[0]
        
        # 2. Get details for sheet
        query = """
            SELECT p.id, p.llm_decision, p.llm_category, p.llm_reason, r.title, COALESCE(r.publisher, r.source) as source
            FROM processed_news p
            JOIN raw_news r ON p.ref_raw_id = r.id
            WHERE p.llm_decision IS NOT NULL
            ORDER BY p.id DESC
            LIMIT 1000
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        sheet_rows = []
        sheet_rows.append(["=== Phase 4 LLM Classification Results (Last 1000) ===", "", "", "", "", ""])
        sheet_rows.append(["ID", "Decision", "Category", "Reason", "Title", "Publisher"])
        
        for row in rows:
            p_id, dec, cat, rea, title, src = row
            # dec might be None if query logic changes, but here it's filtered
            sheet_rows.append([p_id, dec, cat, rea, title[:50] if title else "", src])
                
        # 상단에 통계 추가 (User Request Format)
        # "Total Processed 000, KEEP: 000, DROP: 000 | Total Saved in DB: 000"
        
        stats_str = f"Current Run: {run_stats['processed']} (KEEP: {run_stats['KEEP']}, DROP: {run_stats['DROP']})"
        db_str = f"Total Saved in DB: {total_saved_in_db}"
        
        sheet_rows.insert(1, [stats_str, "", db_str, "", "", ""])
        sheet_rows.insert(2, ["", "", "", "", "", ""])

        if sheet_rows:
            adapter.worksheet.insert_rows(sheet_rows, 1)
        
        logger.info(f"✅ Exported {len(rows)} rows to sheet '{tab_name}'")
        
    except Exception as e:
        logger.error(f"❌ Sheet Export Failed: {e}")

def main():
    parser = argparse.ArgumentParser(description="Phase 4: LLM Classification")
    parser.add_argument("--limit", type=int, help="처리할 기사 수 제한")
    parser.add_argument("--batch-size", type=int, default=50, help="LLM 배치 사이즈 (기본: 50, 안정성 개선)")
    parser.add_argument("--force-all", action="store_true", help="이미 처리된 기사도 다시 처리")
    parser.add_argument("--no-export", action="store_true", help="Sheet 출력 건너뛰기")
    args = parser.parse_args()

    # OpenAI Client
    if not OPENAI_AVAILABLE or not OPENAI_API_KEY:
        logger.error("❌ OpenAI API Key is missing. Cannot proceed.")
        return
    
    client = OpenAI(api_key=OPENAI_API_KEY)

    logger.info("\n" + "="*80)
    logger.info("🚀 Phase 4: LLM Classification Start")
    logger.info("="*80)

    # DB 연결
    try:
        db = DatabaseAdapter(
            db_type=DB_TYPE,
            host=DB_HOST if DB_TYPE != "sqlite" else None,
            port=DB_PORT if DB_TYPE != "sqlite" else None,
            database=DB_NAME,
            user=DB_USER if DB_TYPE != "sqlite" else None,
            password=DB_PASSWORD if DB_TYPE != "sqlite" else None
        )
        db.connect()
        # 컬럼 확인 및 추가
        db.ensure_llm_columns()
        db.ensure_publisher_column()
    except Exception as e:
        logger.error(f"❌ DB Init Failed: {e}")
        return

    # 0. 이전 실행의 DROP 기사 삭제 (Option A: Delayed DELETE)
    logger.info("\n" + "="*80)
    logger.info("🧹 Cleanup: Deleting DROP articles from previous run...")
    logger.info("="*80)
    delete_dropped_articles(db)

    # 1. 대상 기사 가져오기 (NULL + ERROR)
    articles = get_articles_to_process(db, limit=args.limit, force_all=args.force_all)
    total_articles = len(articles)
    logger.info(f"📥 Processing {total_articles} articles (Batch Size: {args.batch_size})")
    
    # 2. Two-Pass 처리
    run_stats = {"processed": 0, "KEEP": 0, "DROP": 0, "ERROR": 0, "RETRY_SUCCESS": 0, "RETRY_FAILED": 0}
    
    # ========== PASS 1: 초기 처리 ==========
    logger.info("\n" + "="*80)
    logger.info("🔄 PASS 1: Initial Processing")
    logger.info("="*80)
    
    for i in range(0, total_articles, args.batch_size):
        batch = articles[i:i + args.batch_size]
        logger.info(f"🤖 Processing Batch {i//args.batch_size + 1} ({len(batch)} articles)...")
        
        llm_results = call_llm_batch_no_json_mode(client, batch)
        
        if llm_results:
            # DB 업데이트
            updated = db.update_llm_results(llm_results)
            
            # Stats Counting
            for res in llm_results:
                run_stats["processed"] += 1
                dec = res.get("decision", "DROP").upper() # Default to DROP if missing (safety)
                if dec == "KEEP":
                    run_stats["KEEP"] += 1
                elif dec == "DROP":
                    run_stats["DROP"] += 1
                elif dec == "ERROR":
                    run_stats["ERROR"] += 1
        else:
            logger.warning("⚠️ Empty results from LLM batch.")
            
    logger.info(f"✅ Pass 1 Completed. Processed: {run_stats['processed']}, KEEP: {run_stats['KEEP']}, DROP: {run_stats['DROP']}, ERROR: {run_stats['ERROR']}")
    
    # ========== PASS 2: ERROR 재처리 ==========
    if run_stats["ERROR"] > 0:
        logger.info("\n" + "="*80)
        logger.info(f"🔄 PASS 2: Retrying {run_stats['ERROR']} ERROR articles")
        logger.info("="*80)
        
        # ERROR 상태 기사만 다시 조회
        error_articles = get_articles_to_process(db, limit=None, force_all=False)
        # 이미 Pass 1에서 처리된 것들이므로, 실제로는 ERROR인 것만 필터링됨 (쿼리 조건 참조)
        error_articles = [a for a in error_articles if a["id"] not in [art["id"] for art in articles]]
        
        # 재조회: 실제로는 DB에서 ERROR 상태인 것만 가져오기
        cursor = db.connection.cursor()
        cursor.execute("""
            SELECT p.id, r.title
            FROM processed_news p
            JOIN raw_news r ON p.ref_raw_id = r.id
            WHERE p.llm_decision = 'ERROR'
            ORDER BY p.id DESC
        """)
        error_rows = cursor.fetchall()
        error_articles = [{"id": row[0], "title": row[1]} for row in error_rows]
        
        logger.info(f"📥 Found {len(error_articles)} ERROR articles to retry")
        
        for i in range(0, len(error_articles), args.batch_size):
            batch = error_articles[i:i + args.batch_size]
            logger.info(f"🔁 Retry Batch {i//args.batch_size + 1} ({len(batch)} articles)...")
            
            llm_results = call_llm_batch_no_json_mode(client, batch)
            
            if llm_results:
                # DB 업데이트
                db.update_llm_results(llm_results)
                
                # Retry Stats
                for res in llm_results:
                    dec = res.get("decision", "DROP").upper()
                    if dec == "KEEP":
                        run_stats["KEEP"] += 1
                        run_stats["RETRY_SUCCESS"] += 1
                        run_stats["ERROR"] -= 1
                    elif dec == "DROP":
                        run_stats["DROP"] += 1
                        run_stats["RETRY_SUCCESS"] += 1
                        run_stats["ERROR"] -= 1
                    elif dec == "ERROR":
                        run_stats["RETRY_FAILED"] += 1
        
        logger.info(f"✅ Pass 2 Completed. Retry Success: {run_stats['RETRY_SUCCESS']}, Still ERROR: {run_stats['ERROR']}")
    
    # 최종 통계
    logger.info("\n" + "="*80)
    logger.info(f"✅ Final Results: Total Processed: {run_stats['processed']}, KEEP: {run_stats['KEEP']}, DROP: {run_stats['DROP']}, ERROR: {run_stats['ERROR']}")
    logger.info("="*80)
    
    # Stats Collection
    try:
        from src.utils.stats_collector import StatsCollector
        sc = StatsCollector()
        sc.set_stat("llm_keep", run_stats['KEEP'])
        sc.set_stat("llm_drop", run_stats['DROP'])
        sc.set_stat("llm_error", run_stats['ERROR'])
    except Exception as e:
        logger.error(f"Stats collection failed: {e}")
    
    # NOTE: 현재 실행의 DROP 기사는 삭제하지 않음 (다음 실행 시 삭제됨)
    # 이를 통해 사후 검증 가능
    
    db.close()

def delete_dropped_articles(db: DatabaseAdapter):
    """LLM이 'DROP'으로 판정한 기사를 DB에서 영구 삭제"""
    logger.info("\n" + "="*60)
    logger.info("🗑️ Cleanup: Deleting 'DROP' articles...")
    logger.info("="*60)
    
    try:
        cursor = db.connection.cursor()
        
        # 1. 삭제할 대상 조회 (processed_news)
        # DROP인 항목의 id와 ref_raw_id를 조회
        if DB_TYPE == "sqlite":
            query_select = "SELECT id, ref_raw_id FROM processed_news WHERE llm_decision = 'DROP'"
        else:
            query_select = "SELECT id, ref_raw_id FROM processed_news WHERE llm_decision = 'DROP'"
            
        cursor.execute(query_select)
        rows = cursor.fetchall()
        
        if not rows:
            logger.info("ℹ️ No 'DROP' articles found to delete.")
            return

        p_ids = [row[0] for row in rows]
        r_ids = [row[1] for row in rows if row[1] is not None]
        
        logger.info(f"Found {len(p_ids)} articles marked as DROP.")
        
        # 2. processed_news에서 삭제
        if DB_TYPE == "sqlite":
             placeholders_p = ",".join("?" * len(p_ids))
             cursor.execute(f"DELETE FROM processed_news WHERE id IN ({placeholders_p})", tuple(p_ids))
        else:
             placeholders_p = ",".join(["%s"] * len(p_ids))
             cursor.execute(f"DELETE FROM processed_news WHERE id IN ({placeholders_p})", tuple(p_ids))
             
        p_deleted = cursor.rowcount
        
        # 3. raw_news에서 삭제
        if r_ids:
            if DB_TYPE == "sqlite":
                placeholders_r = ",".join("?" * len(r_ids))
                cursor.execute(f"DELETE FROM raw_news WHERE id IN ({placeholders_r})", tuple(r_ids))
            else:
                placeholders_r = ",".join(["%s"] * len(r_ids))
                cursor.execute(f"DELETE FROM raw_news WHERE id IN ({placeholders_r})", tuple(r_ids))
            r_deleted = cursor.rowcount
        else:
            r_deleted = 0
            
        db.connection.commit()
        logger.info(f"✅ Cleanup Complete: Deleted {p_deleted} processed_news rows and {r_deleted} raw_news rows.")
        
    except Exception as e:
        logger.error(f"❌ Failed to delete DROP articles: {e}")
        db.connection.rollback()


if __name__ == "__main__":
    main()
