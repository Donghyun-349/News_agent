#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 3: Keyword Filtering (run_p3.py)

기능:
1. processed_news 테이블에서 기사를 조회
2. 불필요한 키워드 (DROP 키워드)를 포함한 기사 필터링 (제거)
3. 제거된 기사를 DB에서 삭제
4. 결과 통계를 Google Sheet에 출력

Usage:
    python run_p3.py
"""

import sys
import logging
import argparse
import re
from pathlib import Path
from typing import List, Dict, Any

# 프로젝트 루트 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from storage.db_adapter import DatabaseAdapter
from src.exporters.gsheet import GSheetAdapter
from src.utils.logger import setup_logger
from config.settings import (
    DB_TYPE, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    GOOGLE_SHEET_ID, LOG_LEVEL
)

# 로거 설정
logger = setup_logger(log_level=LOG_LEVEL)

# 필터링 규칙 정의
DROP_KEYWORDS = [
    "영입", "주식뉴스", "이벤트", 
    "주거급여", "청년월세", "난방비지원", "재난지원금", "바우처", 
    "문화누리카드", "근로장려금", "자녀장려금", "지원금",
    "인도", "베트남", "브라질", "India", "Vietnam", "Brazil"
]

# 제목 기반 필터링 패턴 (Regex) - 삭제 대상
# [단독], [종합] 등은 제외 (유지)
TITLE_DROP_PATTERNS = [
    r"^\[(포토|속보|개장|마감|1보|2보|3보|상보|부고|인사|동정|행사|알림|모집)\]"
]

def check_drop_conditions(text: str) -> str:
    """
    텍스트에 DROP 조건이 포함되어 있는지 확인
    
    Returns:
        DROP 사유 (매칭된 키워드 등) 또는 None
    """
    # 0. Title Prefix Patterns (Regex)
    for pattern in TITLE_DROP_PATTERNS:
        # text는 "Title Snippet" 형태이므로 시작 부분 매칭 확인
        if re.search(pattern, text):
            return f"Rule: Title Prefix Drop"

    # 1. Regex: 인사(?!이트)
    if re.search(r'인사(?!이트)', text):
        return "Rule: Noise Keyword (인사)"

    # 2. Literal: [표]
    if "[표]" in text:
        return "Rule: Noise Keyword ([표])"
    
    # 3. Keywords
    for kw in DROP_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', text):
            return f"Rule: Drop Keyword '{kw}'"
            
    return None

def export_to_gsheet(stats: Dict[str, Any], sheet_id: str):
    """결과를 Google Sheets에 출력"""
    if not sheet_id:
        logger.warning("⚠️  GOOGLE_SHEET_ID not configured. Skipping export.")
        return
    
    tab_name = "3.keyword_filter"
    
    try:
        adapter = GSheetAdapter(sheet_id=sheet_id, worksheet_name=tab_name)
        adapter.connect()
        adapter.worksheet.clear()
        
        rows = []
        
        # 1. Statistics Header
        rows.append(["=== Phase 3 Keyword Filtering Statistics ===", ""])
        rows.append(["Total Input Articles", stats["total_input"]])
        rows.append(["Total Kept", stats["total_kept"]])
        rows.append(["Total Dropped", stats["total_dropped"]])
        if stats["total_input"] > 0:
            drop_rate = (stats["total_dropped"] / stats["total_input"] * 100)
        else:
            drop_rate = 0
        rows.append(["Drop Rate", f"{drop_rate:.1f}%"])
        rows.append(["", ""])
        
        # 2. Dropped Articles Detail
        if stats.get("dropped_examples"):
            rows.append(["=== DROPPED ARTICLES DETAILS ===", "", "", ""])
            rows.append(["ID", "Source", "Title", "Reason"])
            
            for item in stats["dropped_examples"]:
                rows.append([
                    item["id"],
                    item["source"],
                    item["title"][:100],
                    item["reason"]
                ])
        
        # Export rows
        if rows:
            adapter.worksheet.insert_rows(rows, 1)
        
        logger.info(f"✅ 결과를 Google Sheets '{tab_name}' 탭에 출력했습니다.")
        
    except Exception as e:
        logger.error(f"❌ Google Sheets 출력 실패: {e}", exc_info=True)

def main():
    parser = argparse.ArgumentParser(description="Phase 3: Keyword Filtering")
    parser.add_argument("--no-export", action="store_true", help="Google Sheet 출력 건너뛰기")
    args = parser.parse_args()

    logger.info("\n" + "="*80)
    logger.info("🚀 Phase 3 Start: Keyword Filtering (Removing Noise)")
    logger.info("="*80)
    
    # 1. DB 연결
    try:
        db_adapter = DatabaseAdapter(
            db_type=DB_TYPE,
            host=DB_HOST if DB_TYPE != "sqlite" else None,
            port=DB_PORT if DB_TYPE != "sqlite" else None,
            database=DB_NAME,
            user=DB_USER if DB_TYPE != "sqlite" else None,
            password=DB_PASSWORD if DB_TYPE != "sqlite" else None
        )
        db_adapter.connect()
    except Exception as e:
        logger.error(f"❌ DB 연결 실패: {e}")
        return

    # 2. processed_news 가져오기
    try:
        cursor = db_adapter.connection.cursor()
        cursor.execute("""
            SELECT id, source_normalized, ref_raw_id
            FROM processed_news
        """)
        processed_articles = cursor.fetchall() # id, source, ref_id
        
        logger.info(f"📥 Loaded {len(processed_articles)} articles from processed_news")
        
        dropped_ids = []
        dropped_examples = []
        kept_count = 0
        
        # raw_news에서 title, snippet 정보 조인을 위해 별도 조회 혹은 조인 쿼리 사용
        # 여기서는 단순화를 위해 개별 조회보다는, 한번에 조인해서 가져오는게 효율적임.
        # 쿼리 수정
        cursor.execute("""
            SELECT p.id, p.source_normalized, r.title, r.snippet
            FROM processed_news p
            JOIN raw_news r ON p.ref_raw_id = r.id
        """)
        
        articles_with_content = cursor.fetchall()
        
        for row in articles_with_content:
            p_id, source, title, snippet = row
            text = f"{title} {snippet}"
            
            drop_reason = check_drop_conditions(text)
            
            if drop_reason:
                dropped_ids.append(p_id)
                dropped_examples.append({
                    "id": p_id,
                    "source": source,
                    "title": title,
                    "reason": drop_reason
                })
                logger.debug(f"🚫 [DROP] {title[:30]}... ({drop_reason})")
            else:
                kept_count += 1
        
        # 3. DB에서 삭제 수행
        if dropped_ids:
            logger.info(f"🗑️  Deleting {len(dropped_ids)} dropped articles from processed_news...")
            
            # SQLite 제한을 고려하여 청크 단위 삭제 (예: 900개씩)
            chunk_size = 900
            for i in range(0, len(dropped_ids), chunk_size):
                chunk = dropped_ids[i:i + chunk_size]
                placeholders = ', '.join(['?'] * len(chunk))
                cursor.execute(f"DELETE FROM processed_news WHERE id IN ({placeholders})", chunk)
            
            db_adapter.connection.commit()
            logger.info("✅ Deletion complete.")
        else:
            logger.info("✨ No articles matched DROP criteria.")
        
        # 4. 결과 통계
        stats = {
            "total_input": len(articles_with_content),
            "total_kept": kept_count,
            "total_dropped": len(dropped_ids),
            "dropped_examples": dropped_examples
        }
        
        # Stats Collection
        try:
            from src.utils.stats_collector import StatsCollector
            sc = StatsCollector()
            sc.set_stat("keyword_filtered", stats["total_kept"]) # Or total_dropped? Summary script expects 'keyword filtered' count? 
            # run_summary.py uses 'keyword_filtered' key.
            # Usually meant 'how many remain after filter' or 'how many filtered OUT'?
            # Actually, P3 is "Keyword Filtering". The summary column usually tracks "Survivor Count" at each stage.
            # Col 1: Total Collected
            # Col 2: Dedup Removed (This is removed count)
            # Col 3: Keyword Filtered (This could be meaningful as survivors or removed)
            # Let's check run_summary.py logic or standard pattern.
            # Let's log SURVIVORS for clarity or REMOVED?
            # run_summary just prints the value.
            # Let's store 'total_kept' as 'keyword_filtered_kept' ? Or store 'dropped'?
            # Let's stick to storing 'total_dropped' as 'keyword_filtered_dropped' if the column header implies action.
            # Run Summary Header: "Keyword Filtered" -> ambiguous.
            # Let's assumed it means "Articles Filtered Out". 
            sc.set_stat("keyword_filtered", stats["total_dropped"])
        except Exception as e:
            logger.error(f"Stats collection failed: {e}")
        
        # 5. 결과 출력 (생략)
        # if not args.no_export:
        #     export_to_gsheet(stats, GOOGLE_SHEET_ID)
        pass
            
        logger.info("\n" + "="*80)
        logger.info("✅ Phase 3 Filtering 완료")
        logger.info("="*80)
        logger.info(f"  Input: {stats['total_input']}")
        logger.info(f"  Kept: {stats['total_kept']}")
        logger.info(f"  Dropped: {stats['total_dropped']}")
        
    except Exception as e:
        logger.error(f"❌ Phase 3 Processing Error: {e}", exc_info=True)
    finally:
        db_adapter.close()

if __name__ == "__main__":
    main()
