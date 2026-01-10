#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2: Pre-processing & Deduplication (run_p2.py)

기능:
1. raw_news 테이블의 기사를 제목 기반으로 중복 제거 (Dedup)
2. 대표 기사를 선정하여 processed_news 테이블에 저장
3. 결과 통계를 Google Sheet에 출력

Usage:
    python run_p2.py
"""

import sys
import logging
import argparse
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from storage.db_adapter import DatabaseAdapter
from src.processors.title_deduplicator import TitleDeduplicator
from src.exporters.gsheet import GSheetAdapter
from src.utils.logger import setup_logger
from config.settings import (
    DB_TYPE, DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    GOOGLE_SHEET_ID, LOG_LEVEL
)

# 로거 설정
logger = setup_logger(log_level=LOG_LEVEL)

def export_to_gsheet(stats, sheet_id):
    """결과를 Google Sheets에 출력"""
    if not sheet_id:
        logger.warning("⚠️  GOOGLE_SHEET_ID not configured. Skipping export.")
        return
    
    # 시트 이름 설정
    tab_name = "2.Ded_up"
    
    try:
        adapter = GSheetAdapter(sheet_id=sheet_id, worksheet_name=tab_name)
        adapter.connect()
        adapter.worksheet.clear()
        
        rows = []
        
        # 1. Statistics Header
        rows.append(["=== Phase 2 Deduplication Statistics ===", ""])
        rows.append(["Total Raw Articles", stats["total_raw_articles"]])
        rows.append(["Total Processed (Unique)", stats["total_processed_articles"]])
        rows.append(["Duplicates Removed", stats["total_duplicates_removed"]])
        if stats["total_raw_articles"] > 0:
            dedup_rate = (stats["total_duplicates_removed"] / stats["total_raw_articles"] * 100)
        else:
            dedup_rate = 0
        rows.append(["Deduplication Rate", f"{dedup_rate:.1f}%"])
        rows.append(["", ""])
        
        # 2. Duplicate Examples
        if stats.get("duplicate_examples"):
            rows.append(["=== DUPLICATE MERGE EXAMPLES ===", "", "", ""])
            rows.append(["Representative Title", "Count", "Selected Source", "Merged Sources"])
            
            for example in stats["duplicate_examples"]:
                rows.append([
                    example["title"][:100],
                    example["weight"],
                    example["selected_source"],
                    ", ".join(example["sources"])
                ])
            rows.append(["", "", "", ""])
        
        # 3. Removed Articles Detail
        if stats.get("removed_articles"):
            rows.append(["=== REMOVED ARTICLES DETAILS ===", "", "", "", ""])
            rows.append(["Removed ID", "Removed Source", "Title", "Kept ID", "Kept Source"])
            
            for removed in stats["removed_articles"]:
                rows.append([
                    removed["removed_id"],
                    removed["removed_source"],
                    removed["title"][:100],
                    removed["kept_id"],
                    removed["kept_source"]
                ])
        
        # Export rows
        if rows:
            adapter.worksheet.insert_rows(rows, 1)
        
        logger.info(f"✅ 결과를 Google Sheets '{tab_name}' 탭에 출력했습니다.")
        
    except Exception as e:
        logger.error(f"❌ Google Sheets 출력 실패: {e}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(description="Phase 2: Deduplication")
    parser.add_argument("--no-export", action="store_true", help="Google Sheet 출력 건너뛰기")
    args = parser.parse_args()

    logger.info("\n" + "="*80)
    logger.info("🚀 Phase 2 Start: Title-Based Deduplication (No Lanes)")
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

    # 2. Deduplication 실행
    try:
        deduplicator = TitleDeduplicator(db_adapter)
        stats = deduplicator.process()
    except Exception as e:
        logger.error(f"❌ Deduplication 처리 중 오류 발생: {e}", exc_info=True)
        db_adapter.close()
        return

    # 3. 결과 출력 (생략)
    # if not args.no_export:
    #     export_to_gsheet(stats, GOOGLE_SHEET_ID)
    pass
    
    logger.info("\n" + "="*80)
    logger.info("✅ Phase 2 Deduplication 완료")
    logger.info("="*80)
    
    # 마무리
    db_adapter.close()

if __name__ == "__main__":
    main()
