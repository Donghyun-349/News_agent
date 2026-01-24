"""구글 시트 연동 모듈"""

from typing import List, Dict, Any, Set, Optional
import gspread
from google.oauth2.service_account import Credentials
import logging
from pathlib import Path

from src.utils.retry import retry_with_backoff
from config.settings import (
    GOOGLE_SERVICE_ACCOUNT_PATH,
    GOOGLE_SHEET_ID,
    GOOGLE_WORKSHEET_NAME
)

logger = logging.getLogger(__name__)


class GSheetAdapter:
    """구글 시트 연동 어댑터 클래스"""
    
    def __init__(
        self,
        service_account_path: Optional[str] = None,
        sheet_id: Optional[str] = None,
        worksheet_name: Optional[str] = None
    ):
        """
        초기화
        
        Args:
            service_account_path: 서비스 계정 JSON 파일 경로
            sheet_id: 구글 시트 ID
            worksheet_name: 워크시트 이름
        """
        self.service_account_path = service_account_path or GOOGLE_SERVICE_ACCOUNT_PATH
        self.sheet_id = sheet_id or GOOGLE_SHEET_ID
        self.worksheet_name = worksheet_name or GOOGLE_WORKSHEET_NAME
        
        self.client: Optional[gspread.Client] = None
        self.worksheet: Optional[gspread.Worksheet] = None
        self.existing_urls: Set[str] = set()
        
        self.logger = logging.getLogger(f"{__name__}.GSheetAdapter")
    
    def connect(self) -> None:
        """
        구글 시트에 연결하고 인증합니다.
        """
        try:
            # 서비스 계정 파일 확인
            if not Path(self.service_account_path).exists():
                raise FileNotFoundError(
                    f"Service account file not found: {self.service_account_path}"
                )
            
            # 인증
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            creds = Credentials.from_service_account_file(
                self.service_account_path,
                scopes=scope
            )
            
            self.client = gspread.authorize(creds)
            
            # 시트 열기
            if not self.sheet_id:
                raise ValueError("GOOGLE_SHEET_ID is not set")
            
            spreadsheet = self.client.open_by_key(self.sheet_id)
            
            # 워크시트가 없으면 생성
            try:
                self.worksheet = spreadsheet.worksheet(self.worksheet_name)
            except gspread.exceptions.WorksheetNotFound:
                self.logger.info(f"Worksheet '{self.worksheet_name}' not found, creating new worksheet...")
                self.worksheet = spreadsheet.add_worksheet(
                    title=self.worksheet_name,
                    rows=1000,
                    cols=20
                )
                self.logger.info(f"Created new worksheet: {self.worksheet_name}")
            
            self.logger.info(
                f"Connected to Google Sheet: {self.sheet_id}, "
                f"Worksheet: {self.worksheet_name}"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Google Sheet: {e}")
            raise
    
    @retry_with_backoff(
        max_attempts=3,
        initial_delay=1.0,
        exceptions=(gspread.exceptions.APIError,)
    )
    def load_existing_urls(self) -> Set[str]:
        """
        기존 URL 목록을 로드합니다 (중복 방지용).
        
        Returns:
            기존 URL Set
        """
        if not self.worksheet:
            raise RuntimeError("Not connected to Google Sheet. Call connect() first.")
        
        try:
            # 모든 행 읽기
            all_values = self.worksheet.get_all_values()
            
            if not all_values:
                self.existing_urls = set()
                return self.existing_urls
            
            # URL 컬럼 찾기 (헤더 행 확인)
            headers = all_values[0] if all_values else []
            url_col_idx = None
            
            for idx, header in enumerate(headers):
                if header.lower() in ['url', 'link']:
                    url_col_idx = idx
                    break
            
            if url_col_idx is None:
                # URL 컬럼이 없으면 빈 Set 반환
                self.existing_urls = set()
                return self.existing_urls
            
            # URL 추출 (헤더 제외)
            urls = set()
            for row in all_values[1:]:
                if len(row) > url_col_idx and row[url_col_idx]:
                    urls.add(row[url_col_idx].strip())
            
            self.existing_urls = urls
            self.logger.info(f"Loaded {len(urls)} existing URLs")
            
            return self.existing_urls
            
        except Exception as e:
            self.logger.warning(f"Failed to load existing URLs: {e}")
            self.existing_urls = set()
            return self.existing_urls
    
    @retry_with_backoff(
        max_attempts=3,
        initial_delay=1.0,
        backoff_factor=2.0,
        exceptions=(gspread.exceptions.APIError,)
    )
    def clear_all_data(self, keep_headers: bool = True) -> None:
        """
        시트의 모든 데이터를 삭제합니다 (헤더는 유지할 수 있음).
        
        Args:
            keep_headers: 헤더 행 유지 여부
        """
        if not self.worksheet:
            raise RuntimeError("Not connected to Google Sheet. Call connect() first.")
        
        try:
            # 모든 데이터 읽기
            all_values = self.worksheet.get_all_values()
            
            if not all_values:
                return
            
            # 헤더 행 확인
            if keep_headers and len(all_values) > 1:
                # 헤더 제외하고 삭제
                self.worksheet.delete_rows(2, len(all_values))
                self.logger.info("Cleared all data (headers kept)")
            else:
                # 모두 삭제
                self.worksheet.clear()
                self.logger.info("Cleared all data")
            
            # 기존 URL 목록 초기화
            self.existing_urls = set()
            
        except Exception as e:
            self.logger.error(f"Failed to clear sheet data: {e}")
            raise
    
    @retry_with_backoff(
        max_attempts=5,
        initial_delay=1.0,
        backoff_factor=2.0,
        exceptions=(gspread.exceptions.APIError,)
    )
    def append_articles(self, articles: List[Dict[str, Any]]) -> int:
        """
        새로운 기사를 시트에 추가합니다.
        
        Args:
            articles: 추가할 기사 리스트
        
        Returns:
            추가된 기사 수
        """
        if not self.worksheet:
            raise RuntimeError("Not connected to Google Sheet. Call connect() first.")
        
        if not articles:
            return 0
        
        # 중복 제거
        new_articles = [
            article for article in articles
            if article.get("url") and article.get("url") not in self.existing_urls
        ]
        
        if not new_articles:
            self.logger.info("No new articles to add (all duplicates)")
            return 0
        
        try:
            # 배치로 행 추가
            rows = [self._format_row(article) for article in new_articles]
            
            # 시트에 추가 (최하단 행에)
            self.worksheet.append_rows(rows)
            
            # 기존 URL 목록 업데이트
            for article in new_articles:
                if article.get("url"):
                    self.existing_urls.add(article["url"])
            
            self.logger.info(f"Added {len(new_articles)} articles to sheet")
            return len(new_articles)
            
        except Exception as e:
            self.logger.error(f"Failed to append articles: {e}")
            raise
    
    def _format_row(self, article: Dict[str, Any]) -> List[str]:
        """
        기사 데이터를 시트 행 형식으로 변환합니다.
        
        Args:
            article: 기사 딕셔너리
        
        Returns:
            시트 행 데이터 리스트
        """
        return [
            article.get("published_date", ""),
            article.get("collected_at", ""),
            article.get("source", ""),
            article.get("content_category", ""),
            article.get("title", ""),
            article.get("snippet", ""),
            article.get("url", ""),
            "Ready",
        ]
    
    @retry_with_backoff(
        max_attempts=5,
        initial_delay=1.0,
        backoff_factor=2.0,
        exceptions=(gspread.exceptions.APIError,)
    )
    def append_raw_rows(self, rows: List[List[Any]]) -> None:
        """
        Raw 데이터를 시트에 추가합니다 (Retry 적용).
        Args:
            rows: 행 데이터 리스트
        """
        if not self.worksheet:
            raise RuntimeError("Not connected to Google Sheet. Call connect() first.")
        
        try:
            self.worksheet.append_rows(rows)
            self.logger.info(f"Appended {len(rows)} rows to sheet")
        except Exception as e:
            self.logger.error(f"Failed to append raw rows: {e}")
            raise

    @retry_with_backoff(
        max_attempts=5,
        initial_delay=1.0,
        backoff_factor=2.0,
        exceptions=(gspread.exceptions.APIError,)
    )
    def insert_raw_rows(self, rows: List[List[Any]], index: int = 1) -> None:
        """
        Raw 데이터를 시트에 삽입합니다 (Retry 적용).
        Args:
            rows: 행 데이터 리스트
            index: 삽입할 행 인덱스 (1-based)
        """
        if not self.worksheet:
            raise RuntimeError("Not connected to Google Sheet. Call connect() first.")
        
        try:
            self.worksheet.insert_rows(rows, index)
            self.logger.info(f"Inserted {len(rows)} rows at index {index}")
        except Exception as e:
            self.logger.error(f"Failed to insert raw rows: {e}")
            raise

    def _ensure_headers(self) -> None:
        """
        시트에 헤더 행이 없으면 추가합니다.
        """
        if not self.worksheet:
            return
        
        try:
            # 첫 번째 행 확인 (Retry logic applied internally by API client usually, but safe to wrap if needed. 
            # for now, read operations are less critical for data integrity than writes)
            first_row = self.worksheet.row_values(1)
            
            if not first_row or first_row[0] != "Published Date":
                # 헤더 추가
                headers = [[
                    "Published Date",
                    "Collected Date",
                    "Source",
                    "Content Category",
                    "Title",
                    "Summary",
                    "URL",
                    "Status"
                ]]
                # Use robust method
                self.insert_raw_rows(headers, 1)
                self.logger.info("Added header row to sheet")
        except Exception as e:
            self.logger.warning(f"Failed to ensure headers: {e}")
