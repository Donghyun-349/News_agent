"""Bloomberg 뉴스 수집기 (Google News RSS 사용)"""

from typing import List, Dict, Any
import logging

from src.collectors.base_rss import BaseRSSScraper
from src.utils.text_cleaner import remove_bloomberg_suffix, is_valid_article_title
from config.settings import MIN_ARTICLES_PER_SOURCE, MAJOR_FOREIGN_NEWS_TARGET_COUNT

logger = logging.getLogger(__name__)


class BloombergScraper(BaseRSSScraper):
    """Bloomberg 뉴스 수집기 (Google News RSS 우회 전략)"""
    
    def __init__(self, rss_url: str = None):
        """
        초기화
        
        Args:
            rss_url: Google News RSS URL (None이면 설정에서 가져옴)
        """
        from config.settings import BLOOMBERG_GOOGLE_NEWS_URL
        super().__init__(
            source_name="Bloomberg",
            rss_url=rss_url or BLOOMBERG_GOOGLE_NEWS_URL
        )
    
    def _process_rss_entry(self, entry: Dict[str, Any], article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Bloomberg RSS 엔트리를 후처리합니다.
        제목에서 "- Bloomberg.com" 또는 "- Bloomberg" 제거 및 summary 처리.
        """
        title = article.get("title", "")
        summary = article.get("summary", "")
        
        # 제목에서 "- Bloomberg.com" 또는 "- Bloomberg" 제거 (유틸리티 함수 사용)
        title_cleaned = remove_bloomberg_suffix(title)
        
        # 유효하지 않은 제목은 None 반환하여 필터링
        if not is_valid_article_title(title_cleaned):
            return None
        
        article["title"] = title_cleaned
        
        # Bloomberg: summary가 title과 동일하면 공란으로 처리
        if summary and summary.strip() == title_cleaned:
            article["summary"] = ""
        
        return article
    
    def fetch_news(self) -> List[Dict[str, Any]]:
        """
        Bloomberg 뉴스를 수집합니다.
        최소 30개 이상 수집을 목표로 합니다.
        
        Returns:
            기사 딕셔너리 리스트
        """
        try:
            articles = self._parse_rss()
            
            if not articles:
                return []
            
            # 최소 수집 개수 확인
            if len(articles) < MIN_ARTICLES_PER_SOURCE:
                self.logger.warning(
                    f"Bloomberg: Only collected {len(articles)} articles "
                    f"(target: {MIN_ARTICLES_PER_SOURCE}+). "
                    f"Consider adjusting Google News RSS query."
                )
            
            # 유효하지 않은 제목 필터링
            valid_articles = []
            for article in articles:
                if article is not None:  # _process_rss_entry에서 None 반환된 경우 제외
                    valid_articles.append(article)
            
            if not valid_articles:
                self.logger.warning("No valid Bloomberg articles after filtering")
                return []
            
            # 메타데이터 보강 및 소스 추가
            # Bloomberg는 Google News RSS를 사용하므로 Newspaper3k 보강은 건너뛰고 RSS 데이터만 사용
            # (Google News URL은 리다이렉트되므로 보강이 비효율적)
            enriched_articles = self._process_articles(
                valid_articles,
                skip_enrichment=True,
                clear_summary=True
            )
            
            # 카테고리 추가
            for article in enriched_articles:
                article = self._add_content_category(
                    article,
                    category="finance",
                    source_type="foreign"
                )
            
            # 목표 개수로 제한
            limited_articles = enriched_articles[:MAJOR_FOREIGN_NEWS_TARGET_COUNT]
            self.logger.info(f"Completed processing {len(limited_articles)} Bloomberg articles (limited to {MAJOR_FOREIGN_NEWS_TARGET_COUNT})")
            return limited_articles
            
        except Exception as e:
            self.logger.error(f"Failed to fetch Bloomberg news: {e}")
            return []

