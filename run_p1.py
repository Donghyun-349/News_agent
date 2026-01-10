# -*- coding: utf-8 -*-
"""
News Collection & Raw Data Sheet Export (run_p1.py)
- 모든 소스 수집
- 하나의 시트(raw_news)에 출력
- 컬럼: 발행일자(KST), Title, 스니펫, Publisher, Source, URL
"""

import sys
import os
import argparse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytz

sys.path.insert(0, str(Path(__file__).parent))

from src.utils.logger import setup_logger
from src.collectors.big_tech import BigTechScraper
from src.collectors.bloomberg import BloombergScraper
from src.collectors.reuters import ReutersScraper
from src.collectors.ft import FTScraper
from src.collectors.wsj import WSJScraper
from src.collectors.investing import InvestingScraper
from src.collectors.us_real_estate import USRealEstateScraper
from src.collectors.korean_economy import KoreanEconomyScraper
from src.collectors.genews import GEnewsScraper
from src.collectors.infomax import InfomaxScraper
from src.collectors.naver_finance import NaverFinanceScraper

from src.exporters.gsheet import GSheetAdapter
from storage.db_adapter import DatabaseAdapter
from config.settings import LOG_LEVEL, GOOGLE_SHEET_ID, DB_TYPE

# 로거 초기화
logger = setup_logger(log_level=LOG_LEVEL)

# 스프레드시트 설정
SHEET_ID = GOOGLE_SHEET_ID or "1XA0G4Po7hCR81IyibTRgzguD4hyB36rHJSVgDRCW-pg"


def to_kst(date_str: str) -> str:
    """
    날짜 문자열을 KST로 변환하여 문자열로 반환
    입력이 없거나 변환 실패 시 원본 반환 (또는 현재 시간)
    
    Args:
        date_str: "YYYY-MM-DD HH:MM:SS" 형식 (UTC 가정) 또는 유사 형식
    """
    if not date_str:
        return ""
    
    try:
        # 다양한 포맷 처리 시도 가능하지만 기본적으로 UTC string 가정
        # settings.py 등의 포맷 참조: "%Y-%m-%d %H:%M:%S"
        
        # 날짜 파싱 (기본적으로 naive datetime은 UTC로 간주하거나, scraper가 이미 formatting함)
        # 대부분의 scraper는 datetime.utcnow() 스타일로 저장함
        
        # 1. 시도: YYYY-MM-DD HH:MM:SS
        try:
            dt_utc = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # 포맷 다르면 그냥 dateutil parser 사용 시도
            from dateutil import parser
            dt_utc = parser.parse(date_str)
            
        # timezone 정보가 없다면 UTC로 가정
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
            
        # KST 변환
        kst_zone = pytz.timezone('Asia/Seoul')
        dt_kst = dt_utc.astimezone(kst_zone)
        
        return dt_kst.strftime("%Y-%m-%d %H:%M:%S")
        
    except Exception as e:
        # logger.warning(f"Date conversion failed for {date_str}: {e}")
        return date_str


def test_and_collect_scraper(scraper_class, scraper_name: str) -> tuple:
    """개별 수집기 실행"""
    logger.info(f"수집 시작: {scraper_name}")
    try:
        scraper = scraper_class()
        articles = scraper.fetch_news()
        logger.info(f"✅ {scraper_name}: {len(articles)}개 수집 완료")
        return True, articles
    except Exception as e:
        logger.error(f"❌ {scraper_name} 수집 실패: {e}", exc_info=True)
        return False, []


def collect_all_sources() -> Dict[str, Dict[str, Any]]:
    """모든 소스 수집"""
    logger.info("=" * 60)
    logger.info("Step 1: 모든 소스 수집 (병렬 처리)")
    logger.info("=" * 60)
    
    all_scrapers = [
        (BigTechScraper, "Big Tech"),
        (BloombergScraper, "Bloomberg"),
        (ReutersScraper, "Reuters"),
        (FTScraper, "Financial Times"),
        (WSJScraper, "Wall Street Journal"),
        (InvestingScraper, "Investing.com"),
        (USRealEstateScraper, "US Real Estate"),
        (KoreanEconomyScraper, "Korean Economy"),
        (GEnewsScraper, "GEnews"),
        (InfomaxScraper, "Infomax"),
        (NaverFinanceScraper, "Naver Finance"),
    ]
    
    collection_results = {}
    
    # 병렬 처리 설정
    import multiprocessing
    calculated_workers = min(len(all_scrapers), max(8, multiprocessing.cpu_count() * 2))
    env_workers = int(os.getenv("COLLECTION_MAX_WORKERS", "0"))
    max_workers = env_workers if env_workers > 0 else calculated_workers
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_info = {
            executor.submit(test_and_collect_scraper, cls, name): name
            for cls, name in all_scrapers
        }
        
        for future in as_completed(future_to_info):
            name = future_to_info[future]
            try:
                success, articles = future.result()
                collection_results[name] = {
                    "success": success,
                    "articles": articles,
                    "count": len(articles)
                }
            except Exception as e:
                logger.error(f"Error collecting {name}: {e}")
                collection_results[name] = {"success": False, "articles": [], "count": 0}
                
    return collection_results


def save_to_database(collection_results: Dict[str, Dict[str, Any]], db_adapter: DatabaseAdapter) -> None:
    """
    수집된 기사를 raw_news 테이블에 저장
    
    Args:
        collection_results: 수집 결과
        db_adapter: 데이터베이스 어댑터
    """
    logger.info("\n" + "=" * 60)
    logger.info("Step 1-1: DB 저장 (raw_news)")
    logger.info("=" * 60)
    
    total_saved = 0
    
    for source_name, result in collection_results.items():
        if result["success"] and result["articles"]:
            try:
                inserted_ids = db_adapter.insert_raw_news(result["articles"], source_name)
                total_saved += len(inserted_ids)
            except Exception as e:
                logger.error(f"❌ {source_name} DB 저장 실패: {e}", exc_info=True)
    
    logger.info(f"✅ 총 {total_saved}개 기사 raw_news에 저장 완료")


def export_to_google_sheet(collection_results: Dict[str, Dict[str, Any]], sheet_id: str):
    """결과를 Google Sheet 'raw_news' 시트에 출력"""
    logger.info("\n" + "=" * 60)
    logger.info("Step 2: Google Sheets 출력")
    logger.info("=" * 60)
    
    all_rows = []
    
    # 데이터 가공
    for scraper_source_name, result in collection_results.items():
        if not result["success"]:
            continue
            
        for article in result["articles"]:
            # 컬럼 매핑
            # 1. 발행일자 (KST)
            published_orig = article.get("published", "")
            published_kst = to_kst(published_orig)
            
            # 2. Title
            title = article.get("title", "")
            
            # 3. 스니펫 (summary or snippet)
            snippet = article.get("summary", "") or article.get("snippet", "")
            
            # 4. Publisher (실제 언론사/출처)
            # 수집기별로 article['source']에 실제 언론사가 들어가 있는 경우가 많음
            # 만약 article['source']가 비어있거나 scraper_source_name과 같다면, 
            # press_name 등 다른 필드를 확인하거나 scraper_source_name을 사용
            publisher = article.get("source", "")
            if not publisher:
                publisher = article.get("press_name", "") # 일부 수집기가 사용할 수도 있음
            if not publisher:
                 publisher = scraper_source_name

            # 5. Source (수집기 이름 / 대분류)
            source_category = scraper_source_name
            
            # 6. URL
            url = article.get("url", "")
            
            all_rows.append([
                published_kst,
                title,
                snippet,
                publisher,
                source_category,
                url
            ])
            
    # 최신순 정렬 (발행일자 기준 내림차순)
    # 날짜 포맷이 일정하다면 문자열 정렬도 어느정도 먹히지만, 정확성을 위해 sort key 사용 권장
    # 여기서는 단순 문자열 역순 정렬 (YYYY-MM-DD 포맷이면 작동함)
    all_rows.sort(key=lambda x: x[0], reverse=True)
    
    # 시트 출력
    try:
        adapter = GSheetAdapter(sheet_id=sheet_id, worksheet_name="1.raw_news")
        adapter.connect()
        adapter.worksheet.clear()
        
        # 헤더
        headers = ["발행일자 (KST)", "Title", "스니펫", "Publisher", "Source", "URL"]
        adapter.worksheet.append_row(headers)
        
        # 데이터 배치 출력 (한 번에 출력 시 오류 발생 가능성 줄이기 위해 청크 분할 가능하지만 gspread는 보통 처리함)
        if all_rows:
            adapter.worksheet.append_rows(all_rows)
            
        logger.info(f"✅ 'raw_news' 시트에 {len(all_rows)}개 행 출력 완료")
        
    except Exception as e:
        logger.error(f"❌ Google Sheets 출력 실패: {e}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(description="뉴스 수집 및 Raw Data 시트 별도 출력")
    parser.add_argument("--no-db", action="store_true", help="DB 모드 비활성화 (개발/테스트용)")
    parser.add_argument("--create-tables", action="store_true", help="테이블 생성")
    parser.add_argument("--reset-db", action="store_true", help="DB 초기화 (모든 테이블 삭제 후 재생성) - 테스트용")
    args = parser.parse_args()

    # DB 초기화
    db_adapter = None
    if not args.no_db:
        try:
            from config.settings import RESET_MODE  # Import here to ensure avoiding circular imports if any
            
            db_type = os.getenv("DB_TYPE", DB_TYPE)
            db_adapter = DatabaseAdapter(db_type=db_type)
            db_adapter.connect()
            
            # Check for Reset Mode (Arg > Env > Settings)
            should_reset = args.reset_db or RESET_MODE
            
            if should_reset:
                logger.warning("⚠️  DB 초기화 모드 (RESET_MODE=True): 모든 테이블을 삭제하고 재생성합니다.")
                db_adapter.reset_database()
            else:
                # Always ensure tables exist (Safe 'IF NOT EXISTS' check)
                logger.info("DB 테이블 확인 및 생성 중...")
                db_adapter.create_tables()
                
        except Exception as e:
            logger.error(f"❌ 데이터베이스 연결 실패: {e}")
            if not args.no_db:
                # DB 필수 상황이면 종료하거나 경고
                logger.warning("DB 연결 실패로 인해 DB 저장은 수행하지 않습니다.")
                db_adapter = None

    # 1. 수집
    results = collect_all_sources()
    
    # 2. DB 저장 (옵션)
    if db_adapter:
        save_to_database(results, db_adapter)
        db_adapter.close()
    
    # 3. 출력 (Phase 1, 2, 4는 시트 출력 생략 요청으로 주석 처리)
    #if any(r["success"] and r["count"] > 0 for r in results.values()):
    #    export_to_google_sheet(results, SHEET_ID)
    #else:
    #    logger.warning("수집된 데이터가 없어 시트 출력을 건너뜁니다.")
    pass

if __name__ == "__main__":
    main()
