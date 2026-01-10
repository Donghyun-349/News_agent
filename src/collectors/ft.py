"""Financial Times 뉴스 수집기"""

from typing import List, Dict, Any
import logging

from src.collectors.base_rss import BaseRSSScraper
from src.utils.text_cleaner import is_valid_article_title
from config.settings import MIN_ARTICLES_PER_SOURCE, MAJOR_FOREIGN_NEWS_TARGET_COUNT

logger = logging.getLogger(__name__)


class FTScraper(BaseRSSScraper):
    """Financial Times 뉴스 수집기"""
    
    def __init__(self, rss_url: str = None):
        """
        초기화
        
        Args:
            rss_url: RSS Feed URL (None이면 설정에서 가져옴)
        """
        from config.settings import FT_RSS_URL, FT_MARKETS_RSS_URL, FT_COMPANIES_RSS_URL
        super().__init__(
            source_name="FT",
            rss_url=rss_url or FT_RSS_URL
        )
        # 추가 RSS 피드 URL
        self.additional_rss_urls = [
            FT_MARKETS_RSS_URL,
            FT_COMPANIES_RSS_URL
        ]
    
    def _parse_rss(self, rss_url: str = None) -> List[Dict[str, Any]]:
        """
        RSS 피드를 파싱합니다.
        FT는 SSL 컨텍스트가 필요합니다.
        
        Args:
            rss_url: 파싱할 RSS URL (None이면 self.rss_url 사용)
        
        Returns:
            파싱된 기사 리스트
        """
        target_url = rss_url or self.rss_url
        # BaseRSSScraper의 _parse_rss를 사용하되, SSL 컨텍스트 사용
        return super()._parse_rss(target_url, use_ssl_context=True)
    
    def fetch_news(self) -> List[Dict[str, Any]]:
        """
        FT 뉴스를 수집합니다.
        최소 30개 이상 수집을 목표로 합니다.
        메인, Markets, Companies RSS 피드를 모두 수집합니다.
        
        Returns:
            기사 딕셔너리 리스트
        """
        try:
            all_articles = []
            seen_urls = set()  # 중복 제거용
            
            # 메인 RSS 피드 수집
            articles = self._parse_rss(self.rss_url)
            for article in articles:
                url = article.get("url", "")
                if url and url not in seen_urls:
                    all_articles.append(article)
                    seen_urls.add(url)
            
            self.logger.info(f"Collected {len(all_articles)} articles from main RSS feed")
            
            # 추가 RSS 피드 수집 (Markets, Companies)
            for additional_url in self.additional_rss_urls:
                if not additional_url:  # 빈 URL은 건너뛰기
                    continue
                if len(all_articles) >= MIN_ARTICLES_PER_SOURCE:
                    break
                
                try:
                    self.logger.info(f"Fetching additional FT RSS feed: {additional_url}")
                    additional_articles = self._parse_rss(additional_url)
                    added_count = 0
                    for article in additional_articles:
                        url = article.get("url", "")
                        if url and url not in seen_urls:
                            all_articles.append(article)
                            seen_urls.add(url)
                            added_count += 1
                            # 목표 개수 이상이면 중단
                            if len(all_articles) >= MIN_ARTICLES_PER_SOURCE:
                                break
                    self.logger.info(f"  Added {added_count} articles from additional feed (total: {len(all_articles)})")
                except Exception as e:
                    self.logger.warning(f"Failed to parse additional RSS feed {additional_url}: {e}")
                    continue
            
            if not all_articles:
                return []
            
            # 최소 수집 개수 확인
            if len(all_articles) < MIN_ARTICLES_PER_SOURCE:
                self.logger.warning(
                    f"FT: Only collected {len(all_articles)} articles "
                    f"(target: {MIN_ARTICLES_PER_SOURCE}+). "
                    f"Consider adding additional RSS feeds."
                )
            
            # 메타데이터 보강 및 소스 추가
            enriched_articles = self._process_articles(
                all_articles,
                skip_enrichment=False,
                clear_summary=False
            )
            
            # 카테고리 추가
            for idx, article in enumerate(enriched_articles):
                enriched_articles[idx] = self._add_content_category(
                    article,
                    category="finance",
                    source_type="foreign"
                )
            
            # 목표 개수로 제한
            limited_articles = enriched_articles[:MAJOR_FOREIGN_NEWS_TARGET_COUNT]
            self.logger.info(f"✅ Completed processing {len(limited_articles)} FT articles (limited to {MAJOR_FOREIGN_NEWS_TARGET_COUNT})")
            return limited_articles
            
        except Exception as e:
            self.logger.error(f"Failed to fetch FT news: {e}")
            return []

