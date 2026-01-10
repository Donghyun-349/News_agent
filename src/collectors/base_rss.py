"""RSS 기반 뉴스 수집기 기본 클래스"""

from typing import List, Dict, Any, Optional, Callable
import logging
import pytz

from src.collectors.base import BaseScraper
from src.utils.retry import retry_with_backoff
from src.utils.date_parser import parse_rss_date
from src.utils.rss_parser import parse_rss_feed
from config.settings import REQUEST_TIMEOUT, MIN_ARTICLES_PER_SOURCE, COLLECTION_TIME_LIMIT_HOURS
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BaseRSSScraper(BaseScraper):
    """
    RSS 기반 뉴스 수집기의 기본 클래스
    공통 RSS 파싱 로직을 제공합니다.
    """
    
    def __init__(self, source_name: str, rss_url: Optional[str] = None):
        """
        초기화
        
        Args:
            source_name: 뉴스 소스 이름
            rss_url: RSS Feed URL (선택적)
        """
        super().__init__(source_name=source_name, rss_url=rss_url)
    
    @retry_with_backoff(
        max_attempts=3,
        initial_delay=1.0,
        exceptions=(Exception,)
    )
    def _parse_rss(self, rss_url: Optional[str] = None, use_ssl_context: bool = False) -> List[Dict[str, Any]]:
        """
        RSS 피드를 파싱합니다.
        
        Args:
            rss_url: 파싱할 RSS URL (None이면 self.rss_url 사용)
            use_ssl_context: SSL 컨텍스트 사용 여부 (FT 등 일부 사이트용)
        
        Returns:
            파싱된 기사 리스트
        """
        target_url = rss_url or self.rss_url
        if not target_url:
            self.logger.error("No RSS URL provided")
            return []
        
        self.logger.info(f"Fetching {self.source_name} news from: {target_url}")
        
        # RSS 피드 파싱 (유틸리티 함수 사용)
        feed = parse_rss_feed(target_url, timeout=REQUEST_TIMEOUT, use_ssl_context=use_ssl_context)
        if not feed:
            return []
        
        articles = []
        total_entries = len(feed.entries)
        
        self.logger.info(f"Parsing {total_entries} entries from {self.source_name} RSS...")
        
        # 날짜 필터링: 한국 시간 기준으로 COLLECTION_TIME_LIMIT_HOURS 이내의 기사만 수집
        korea_tz = pytz.timezone('Asia/Seoul')
        now_korea = datetime.now(korea_tz)
        time_limit_korea = now_korea - timedelta(hours=COLLECTION_TIME_LIMIT_HOURS)
        
        for idx, entry in enumerate(feed.entries, 1):
            try:
                # 진행 상황 로깅 (10개마다)
                if idx % 10 == 0 or idx == total_entries:
                    self.logger.info(f"Processing entry {idx}/{total_entries}...")
                
                # 날짜 파싱 (유틸리티 함수 사용 - 타임존 정보 보존)
                # entry에서 날짜 문자열 추출 (published, updated, pubDate 등 시도)
                date_str = entry.get("published") or entry.get("updated") or entry.get("pubDate") or getattr(entry, "published", None)
                published = parse_rss_date(date_str)
                
                # 날짜 필터링: 한국 시간 기준으로 시간 제한 이내의 기사만 수집
                if published:
                    try:
                        from dateutil import parser as date_parser
                        pub_date = date_parser.parse(published)
                        
                        # 한국 시간으로 변환
                        if pub_date.tzinfo is None:
                            from datetime import timezone
                            pub_date = pub_date.replace(tzinfo=timezone.utc)
                        
                        pub_date_korea = pub_date.astimezone(korea_tz)
                        
                        # 한국 시간 기준으로 시간 제한 이전 기사는 건너뛰기
                        if pub_date_korea < time_limit_korea:
                            continue
                    except Exception as e:
                        # 날짜 파싱 실패 시 로깅만 하고 계속 진행
                        self.logger.debug(f"Failed to parse date for filtering: {published}, {e}")
                
                # URL 추출 (여러 필드 시도)
                url = entry.get("link") or entry.get("id") or entry.get("href") or getattr(entry, "link", None)
                if url:
                    url = str(url).strip()
                    # URL 유효성 검사 (http 또는 https로 시작)
                    if not (url.startswith("http://") or url.startswith("https://")):
                        self.logger.warning(f"Entry {idx}: 유효하지 않은 URL 형식 (제목: {entry.get('title', 'N/A')[:50]}, URL: {url[:100]})")
                        url = None
                else:
                    url = ""
                
                # URL이 없거나 유효하지 않으면 건너뛰기
                if not url:
                    self.logger.warning(f"Entry {idx}: URL이 없음 (제목: {entry.get('title', 'N/A')[:50]})")
                    continue
                
                # 기본 기사 데이터
                article = {
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "url": url,  # 검증된 URL만 사용
                    "published": published,
                }
                
                # 하위 클래스에서 커스터마이징할 수 있도록 후처리 메서드 호출
                article = self._process_rss_entry(entry, article)
                
                # None이 반환된 경우 (유효하지 않은 제목 등) 제외
                if article is not None:
                    articles.append(article)
                
            except Exception as e:
                self.logger.error(f"Error parsing entry {idx}: {e}")
                continue
        
        self.logger.info(f"Found {len(articles)} articles from {self.source_name}")
        return articles
    
    def _process_rss_entry(self, entry: Dict[str, Any], article: Dict[str, Any]) -> Dict[str, Any]:
        """
        RSS 엔트리를 후처리합니다.
        하위 클래스에서 오버라이드하여 커스터마이징할 수 있습니다.
        
        Args:
            entry: 원본 RSS 엔트리
            article: 기본 기사 딕셔너리
        
        Returns:
            후처리된 기사 딕셔너리
        """
        # 기본 구현: summary가 title과 동일하면 공란으로 처리
        title = article.get("title", "").strip()
        summary = article.get("summary", "").strip()
        
        if summary == title:
            article["summary"] = ""
        
        return article
    
    def _process_articles(self, articles: List[Dict[str, Any]], 
                         skip_enrichment: bool = False,
                         clear_summary: bool = False) -> List[Dict[str, Any]]:
        """
        수집된 기사들을 처리합니다 (메타데이터 보강, 소스 추가 등).
        
        Args:
            articles: 수집된 기사 리스트
            skip_enrichment: 메타데이터 보강 건너뛰기 여부
            clear_summary: summary를 공란으로 처리할지 여부
        
        Returns:
            처리된 기사 리스트
        """
        if not articles:
            return []
        
        enriched_articles = []
        total = len(articles)
        
        if skip_enrichment:
            self.logger.info(f"Processing {total} {self.source_name} articles (skipping metadata enrichment for speed)...")
        else:
            self.logger.info(f"Processing {total} {self.source_name} articles...")
        
        for idx, article in enumerate(articles, 1):
            # 진행 상황 로깅 (20개마다)
            if idx % 20 == 0 or idx == total:
                self.logger.info(f"Processing article {idx}/{total}...")
            
            # 메타데이터 보강 (선택적)
            if not skip_enrichment:
                article = self._enrich_metadata(article)
            
            # summary 처리
            if clear_summary:
                article["summary"] = ""
            
            # 소스 추가
            article = self._add_source(article)
            enriched_articles.append(article)
        
        return enriched_articles
    
    def fetch_news(self) -> List[Dict[str, Any]]:
        """
        뉴스를 수집합니다.
        하위 클래스에서 오버라이드하여 구현합니다.
        
        Returns:
            기사 딕셔너리 리스트
        """
        raise NotImplementedError("Subclasses must implement fetch_news()")

