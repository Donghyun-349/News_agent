"""뉴스 수집기 기본 추상 클래스"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging
from newspaper import Article
import time

from src.utils.logger import get_default_logger
from config.settings import ENABLE_NEWSPAPER3K, NEWSPAPER3K_TIMEOUT, RATE_LIMIT_DELAY, COLLECTION_TIME_LIMIT_HOURS
from datetime import datetime, timedelta

logger = get_default_logger()


class BaseScraper(ABC):
    """모든 뉴스 수집기가 상속받아야 하는 추상 클래스"""
    
    def __init__(self, source_name: str, rss_url: Optional[str] = None):
        """
        초기화
        
        Args:
            source_name: 뉴스 소스 이름 (예: "WSJ", "FT")
            rss_url: RSS Feed URL (선택적, RSS가 없는 수집기의 경우 None)
        """
        self.source_name = source_name
        self.rss_url = rss_url
        self.logger = logging.getLogger(f"{__name__}.{source_name}")
    
    @abstractmethod
    def fetch_news(self) -> List[Dict[str, Any]]:
        """
        뉴스 목록을 수집하여 반환합니다.
        
        Returns:
            기사 딕셔너리 리스트. 각 딕셔너리는 다음 키를 포함:
            - title: 제목
            - summary: 요약
            - url: 기사 링크
            - published: 발행일 (문자열)
            - source: 소스 이름
            - image_url: 썸네일 이미지 URL (선택적)
            - authors: 작성자 리스트 (선택적)
        """
        pass
    
    def _enrich_metadata(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Newspaper3k를 사용하여 메타데이터를 보강합니다.
        
        Args:
            article_data: RSS에서 얻은 기본 기사 데이터
        
        Returns:
            메타데이터가 보강된 기사 데이터
        """
        if not ENABLE_NEWSPAPER3K:
            return article_data
        
        url = article_data.get("url")
        if not url:
            return article_data
        
        try:
            self.logger.debug(f"Enriching metadata for: {url}")
            
            from config.settings import NEWSPAPER3K_TIMEOUT
            
            article = Article(url)
            article.config.request_timeout = NEWSPAPER3K_TIMEOUT
            article.download()
            article.parse()
            
            # 발행일 보강 (RSS에 없을 수 있음)
            if not article_data.get("published") and article.publish_date:
                from datetime import timezone
                # UTC로 변환
                pub_date = article.publish_date
                if pub_date.tzinfo:
                    pub_date = pub_date.astimezone(timezone.utc).replace(tzinfo=None)
                article_data["published"] = pub_date.strftime("%Y-%m-%d %H:%M:%S")
            
            # 썸네일 이미지 보강
            if not article_data.get("image_url") and article.top_image:
                article_data["image_url"] = article.top_image
            
            # 작성자 보강
            if not article_data.get("authors") and article.authors:
                article_data["authors"] = article.authors
            
            # Summary 보강: summary가 없거나 제목과 같으면 article.text에서 추출
            existing_summary = article_data.get("summary", "").strip()
            existing_title = article_data.get("title", "").strip()
            
            if (not existing_summary or existing_summary == existing_title) and article.text:
                # article.text의 처음 200자를 summary로 사용
                summary_text = article.text[:200].strip()
                if summary_text:
                    article_data["summary"] = summary_text
            
            # Rate limiting
            time.sleep(RATE_LIMIT_DELAY)
            
        except Exception as e:
            # Newspaper3k 파싱 실패 시 RSS 데이터만 사용 (폴백)
            self.logger.warning(
                f"Failed to enrich metadata for {url}: {e}. Using RSS data only."
            )
        
        return article_data
    
    def _add_source(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        기사 데이터에 소스 정보를 추가하고, image_url과 authors를 공란으로 처리합니다.
        
        Args:
            article: 기사 딕셔너리
        
        Returns:
            소스 정보가 추가된 기사 딕셔너리
        """
        article["source"] = self.source_name
        # 모든 수집기에서 image_url과 authors는 수집하지 않음
        article["image_url"] = ""
        article["authors"] = ""
        return article
    
    def _add_content_category(self, article: Dict[str, Any], 
                             category: str,
                             source_type: str = "foreign") -> Dict[str, Any]:
        """
        기사에 content_category를 추가합니다.
        
        Args:
            article: 기사 딕셔너리
            category: 카테고리 (finance, bigtech, real_estate, tech_general, companies)
            source_type: "foreign" 또는 "domestic"
        
        Returns:
            카테고리가 추가된 기사 딕셔너리
        """
        article["content_category"] = category
        article["source_type"] = source_type
        return article
    
    def _is_within_time_limit(self, published: str) -> bool:
        """
        기사 발행일이 수집 시간 제한 이내인지 확인합니다.
        한국 시간 기준으로 30시간 이내 기사만 수집합니다.
        
        Args:
            published: 발행일 문자열 (YYYY-MM-DD HH:MM:SS 형식)
        
        Returns:
            시간 제한 이내이면 True, 아니면 False
        """
        if not published:
            return True  # 날짜가 없으면 통과 (나중에 처리)
        
        try:
            from dateutil import parser as date_parser
            import pytz
            
            # 발행일 파싱
            pub_date = date_parser.parse(published)
            
            # 한국 시간대 설정
            korea_tz = pytz.timezone('Asia/Seoul')
            
            # 발행일을 한국 시간으로 변환
            if pub_date.tzinfo is None:
                # 타임존 정보가 없으면 UTC로 가정하고 한국 시간으로 변환
                from datetime import timezone
                pub_date = pub_date.replace(tzinfo=timezone.utc)
            
            pub_date_korea = pub_date.astimezone(korea_tz)
            
            # 현재 한국 시간
            now_korea = datetime.now(korea_tz)
            
            # 한국 시간 기준으로 30시간 전 계산
            time_limit_korea = now_korea - timedelta(hours=COLLECTION_TIME_LIMIT_HOURS)
            
            # 발행일이 시간 제한 이내인지 확인
            return pub_date_korea >= time_limit_korea
            
        except Exception as e:
            # 날짜 파싱 실패 시 통과 (나중에 처리)
            self.logger.debug(f"Failed to parse date for filtering: {published}, {e}")
            return True

