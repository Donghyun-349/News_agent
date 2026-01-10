"""Google News RSS 기반 검색 수집기 기본 클래스"""

from typing import List, Dict, Any, Optional
import logging
from urllib.parse import quote_plus
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

from src.collectors.base_rss import BaseRSSScraper
from src.utils.text_cleaner import normalize_press_name, is_valid_article_title
from config.settings import REQUEST_TIMEOUT, MIN_ARTICLES_PER_SOURCE

logger = logging.getLogger(__name__)


class GoogleNewsRSSScraper(BaseRSSScraper):
    """
    Google News RSS를 사용하는 검색 기반 수집기의 기본 클래스
    Big Tech, US Real Estate 등이 상속받아 사용합니다.
    """
    
    def __init__(self, source_name: str, queries: Dict[str, Dict[str, str]], 
                 target_count: int = 30, max_workers: int = 5):
        """
        초기화
        
        Args:
            source_name: 뉴스 소스 이름
            queries: 검색 쿼리 딕셔너리 {topic_name: {"primary": query, "fallback": query}}
            target_count: 주제당 목표 수집 개수
            max_workers: 병렬 처리 워커 수
        """
        super().__init__(source_name=source_name, rss_url=None)
        self.queries = queries
        self.target_count = target_count
        self.max_workers = max_workers
    
    def _build_rss_url(self, query: str) -> str:
        """
        Google News RSS URL 생성
        
        Args:
            query: 검색 쿼리
            
        Returns:
            Google News RSS URL
        """
        encoded_query = quote_plus(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        return rss_url
    
    def _parse_rss(self, rss_url: Optional[str] = None, topic_name: str = None) -> List[Dict[str, Any]]:
        """
        Google News RSS 피드를 파싱합니다.
        
        Args:
            rss_url: RSS URL (필수)
            topic_name: 주제명 (소스 이름에 사용)
        
        Returns:
            파싱된 기사 리스트
        """
        if not rss_url:
            self.logger.error("RSS URL is required")
            return []
        
        if not topic_name:
            topic_name = self.source_name
        
        self.logger.info(f"Fetching {topic_name} news from Google News RSS")
        
        # BaseRSSScraper의 _parse_rss 사용
        articles = super()._parse_rss(rss_url)
        
        # HTML 태그 제거를 위한 import
        from bs4 import BeautifulSoup
        import re
        
        # Google News RSS 특별 처리: 제목에서 "- Source" 추출 및 언론사명 정규화
        processed_articles = []
        for article in articles:
            title = article.get("title", "")
            summary = article.get("summary", "")
            
            # HTML 태그 제거
            if summary:
                try:
                    # BeautifulSoup을 사용하여 HTML 태그 제거
                    soup = BeautifulSoup(summary, "html.parser")
                    summary = soup.get_text(separator=" ", strip=True)
                except Exception:
                    # HTML 파싱 실패 시 정규식으로 기본 제거 시도
                    summary = re.sub(r'<[^>]+>', '', summary)
                    summary = re.sub(r'&nbsp;', ' ', summary)
                    summary = re.sub(r'&amp;', '&', summary)
                    summary = summary.strip()
            
            # 제목에서 "- Source" 추출 (발행 언론사)
            title_cleaned = title.strip()
            press_name = ""
            if " - " in title_cleaned:
                parts = title_cleaned.rsplit(" - ", 1)
                title_cleaned = parts[0].strip()
                press_name = parts[1].strip() if len(parts) > 1 else ""
            
            # 유효하지 않은 제목은 필터링
            if not is_valid_article_title(title_cleaned):
                continue
            
            # 소스명 정리 (bloomberg.com → Bloomberg 등) - 유틸리티 함수 사용
            press_name = normalize_press_name(press_name)
            
            # summary가 제목과 동일하거나 없으면 빈 문자열로 설정 (나중에 newspaper3k로 보강)
            if summary and summary.strip() == title_cleaned:
                summary = ""
            elif not summary:
                summary = ""
            
            article["title"] = title_cleaned  # "- Source" 제거된 제목
            article["summary"] = summary  # HTML 제거된 summary (newspaper3k 보강 전)
            article["press_name"] = press_name  # 발행 언론사 추가
            
            processed_articles.append(article)
        
        return processed_articles
    
    def _process_rss_entry(self, entry: Dict[str, Any], article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Google News RSS 엔트리를 후처리합니다.
        기본 구현은 BaseRSSScraper의 동작을 따릅니다.
        """
        # 기본 처리 (summary가 title과 동일하면 공란으로 처리)
        return super()._process_rss_entry(entry, article)
    
    def _fetch_topic_news(self, topic_name: str) -> List[Dict[str, Any]]:
        """
        특정 주제의 뉴스를 수집합니다 (Fallback 전략 포함).
        
        Args:
            topic_name: 주제명
        
        Returns:
            기사 딕셔너리 리스트
        """
        if topic_name not in self.queries:
            self.logger.error(f"Unknown topic: {topic_name}")
            return []
        
        query_config = self.queries[topic_name]
        all_articles = []
        seen_urls = set()
        
        # 1차 시도: Primary 쿼리 (site 제한)
        self.logger.info(f"[{topic_name}] Trying primary query (with site restriction)...")
        primary_url = self._build_rss_url(query_config["primary"])
        primary_articles = self._parse_rss(primary_url, topic_name)
        
        for article in primary_articles:
            url = article.get("url", "")
            if url and url not in seen_urls:
                all_articles.append(article)
                seen_urls.add(url)
        
        self.logger.info(f"[{topic_name}] Primary query: {len(all_articles)} articles")
        
        # 2차 시도: Fallback 쿼리 (site 제한 해제, 목표 개수에 못 미칠 때)
        if len(all_articles) < self.target_count:
            self.logger.info(f"[{topic_name}] Trying fallback query (without site restriction)...")
            fallback_url = self._build_rss_url(query_config["fallback"])
            fallback_articles = self._parse_rss(fallback_url, topic_name)
            
            for article in fallback_articles:
                url = article.get("url", "")
                if url and url not in seen_urls:
                    all_articles.append(article)
                    seen_urls.add(url)
                    # 목표 개수에 도달하면 중단
                    if len(all_articles) >= self.target_count:
                        break
            
            self.logger.info(f"[{topic_name}] Fallback query: {len(fallback_articles)} articles (total: {len(all_articles)})")
        
        return all_articles[:self.target_count]  # 최대 목표 개수만큼만
    
    def _process_topic_articles(self, topic_name: str, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        주제별 기사들을 후처리합니다 (newspaper3k 보강, 소스 추가 등).
        
        Args:
            topic_name: 주제명
            articles: 기사 리스트
        
        Returns:
            처리된 기사 리스트
        """
        # newspaper3k를 활용하여 메타데이터 보강 (summary 추출 포함)
        processed_articles = self._process_articles(
            articles,
            skip_enrichment=False,  # newspaper3k 보강 활성화
            clear_summary=False     # summary 보존 (newspaper3k로 추출)
        )
        
        # 소스 이름을 발행 언론사로 설정 (없으면 주제명)
        for article in processed_articles:
            press_name = article.get("press_name", "")
            if press_name:
                article["source"] = press_name
            else:
                article["source"] = topic_name
        
        return processed_articles
    
    def fetch_news(self, selected_topics: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        뉴스를 수집합니다.
        하위 클래스에서 오버라이드하여 구현합니다.
        
        Args:
            selected_topics: 수집할 주제 리스트 (None이면 모든 주제)
        
        Returns:
            기사 딕셔너리 리스트
        """
        try:
            all_articles = []
            
            # 수집할 주제 목록
            topics = selected_topics if selected_topics else list(self.queries.keys())
            
            # 병렬 처리 함수
            def fetch_topic_articles(topic_name):
                self.logger.info(f"\n{'='*60}")
                self.logger.info(f"Collecting {topic_name} news...")
                self.logger.info(f"{'='*60}")
                
                topic_articles = self._fetch_topic_news(topic_name)
                processed_articles = self._process_topic_articles(topic_name, topic_articles)
                
                self.logger.info(f"[{topic_name}] ✅ Collected {len(processed_articles)} articles")
                return processed_articles
            
            # 병렬 처리로 주제별 뉴스 수집
            self.logger.info(f"Collecting {self.source_name} news using {self.max_workers} workers...")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_topic = {
                    executor.submit(fetch_topic_articles, topic_name): topic_name 
                    for topic_name in topics
                }
                
                for future in as_completed(future_to_topic):
                    topic_name = future_to_topic[future]
                    try:
                        topic_articles = future.result()
                        all_articles.extend(topic_articles)
                    except Exception as e:
                        self.logger.error(f"Failed to collect {topic_name} news: {e}", exc_info=True)
            
            # 최소 수집 개수 확인
            if len(all_articles) < MIN_ARTICLES_PER_SOURCE:
                self.logger.warning(
                    f"{self.source_name}: Only collected {len(all_articles)} articles "
                    f"(target: {MIN_ARTICLES_PER_SOURCE}+)."
                )
            
            self.logger.info(f"\n✅ Total collected {len(all_articles)} {self.source_name} articles")
            return all_articles
            
        except Exception as e:
            self.logger.error(f"Failed to fetch {self.source_name} news: {e}")
            return []


