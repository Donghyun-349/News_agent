"""Big Tech 기업별 맞춤 검색 수집기 (Google News RSS 사용)"""

from typing import List, Dict, Any, Optional
import logging
import os


from src.collectors.google_news_rss import GoogleNewsRSSScraper
from config.settings import MIN_ARTICLES_PER_SOURCE, BIG_TECH_TARGET_COUNT
from src.utils.config_loader import config_loader

logger = logging.getLogger(__name__)


class BigTechScraper(GoogleNewsRSSScraper):
    """Big Tech 기업별 맞춤 검색 수집기"""
    
    # 쿼리는 config.json에서 로드됩니다.
    
    def __init__(self, company: str = None):
        """
        초기화
        
        Args:
            company: 수집할 기업명 (None이면 모든 기업 수집)
        """
        # Dynamic Config Load
        self.queries = config_loader.get_queries("Big Tech") or {}
        target_count = config_loader.get_setting("big_tech_target_count", BIG_TECH_TARGET_COUNT)
        
        max_workers = int(os.getenv("BIG_TECH_MAX_WORKERS", "5"))
        super().__init__(
            source_name="Big Tech",
            queries=self.queries,
            target_count=target_count,
            max_workers=max_workers
        )
        self.company = company
    
    def _process_topic_articles(self, topic_name: str, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        기업별 기사들을 후처리합니다 (소스 추가, company 필드 추가).
        Big Tech는 스니펫을 수집하지 않도록 설정합니다.
        
        Args:
            topic_name: 기업명
            articles: 기사 리스트
        
        Returns:
            처리된 기사 리스트
        """
        # newspaper3k를 활용하여 메타데이터 보강 (스니펫 제외)
        processed_articles = self._process_articles(
            articles,
            skip_enrichment=False,  # newspaper3k 보강 활성화
            clear_summary=True      # 스니펫 수집하지 않음
        )
        
        # 소스 이름을 발행 언론사로 설정 (없으면 기업명)
        for article in processed_articles:
            # company 필드 추가
            article["company"] = topic_name
            press_name = article.get("press_name", "")
            if press_name:
                article["source"] = press_name
            else:
                article["source"] = topic_name
            
            # 카테고리 추가
            article = self._add_content_category(
                article,
                category="bigtech",
                source_type="foreign"
            )
        
        return processed_articles
    
    def fetch_news(self) -> List[Dict[str, Any]]:
        """
        Big Tech 뉴스를 수집합니다.
        특정 기업이 지정되면 해당 기업만, 아니면 모든 기업 수집.
        
        Returns:
            기사 딕셔너리 리스트
        """
        # 수집할 기업 목록
        companies = [self.company] if self.company else list(self.queries.keys())
        
        # 부모 클래스의 fetch_news 사용
        return super().fetch_news(selected_topics=companies)

