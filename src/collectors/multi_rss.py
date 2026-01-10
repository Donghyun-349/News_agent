"""다중 RSS 피드 수집기 기본 클래스"""

from typing import List, Dict, Any, Optional
import logging
import re

from src.collectors.base_rss import BaseRSSScraper
from config.settings import MIN_ARTICLES_PER_SOURCE

logger = logging.getLogger(__name__)


class MultiRSSScraper(BaseRSSScraper):
    """
    여러 RSS 피드를 수집하는 수집기의 기본 클래스
    RSS Feed Registry를 사용하여 설정 파일 기반으로 관리합니다.
    """
    
    def __init__(self, source_name: str, feeds: Dict[str, str], 
                 use_ssl_context: bool = False):
        """
        초기화
        
        Args:
            source_name: 뉴스 소스 이름
            feeds: RSS 피드 딕셔너리 {feed_name: rss_url}
            use_ssl_context: SSL 컨텍스트 사용 여부
        """
        super().__init__(source_name=source_name, rss_url=None)
        self.feeds = feeds
        self.use_ssl_context = use_ssl_context
        self._current_feed_name = None
    
    def _parse_rss(self, rss_url: Optional[str] = None, feed_name: str = None) -> List[Dict[str, Any]]:
        """
        RSS 피드를 파싱합니다.
        
        Args:
            rss_url: RSS URL (필수)
            feed_name: 피드 이름 (소스 이름에 사용)
        
        Returns:
            파싱된 기사 리스트
        """
        if not rss_url:
            self.logger.error("RSS URL is required")
            return []
        
        if not feed_name:
            feed_name = self.source_name
        
        # 현재 피드 이름 저장 (후처리에서 사용)
        self._current_feed_name = feed_name
        
        # BaseRSSScraper의 _parse_rss 사용
        articles = super()._parse_rss(rss_url, use_ssl_context=self.use_ssl_context)
        
        # 피드 이름 추가
        for article in articles:
            article["feed_name"] = feed_name
        
        return articles
    
    def _process_rss_entry(self, entry: Dict[str, Any], article: Dict[str, Any]) -> Dict[str, Any]:
        """
        RSS 엔트리를 후처리합니다.
        하위 클래스에서 오버라이드하여 커스터마이징할 수 있습니다.
        """
        # 기본 처리 (summary가 title과 동일하면 공란으로 처리)
        title = article.get("title", "").strip()
        summary = article.get("summary", "").strip()
        
        # 제목에서 "- Source" 제거 후 비교
        title_cleaned = title
        if " - " in title_cleaned:
            title_cleaned = title_cleaned.rsplit(" - ", 1)[0].strip()
        
        if summary == title_cleaned:
            article["summary"] = ""
        
        return article
    
    def fetch_news(self) -> List[Dict[str, Any]]:
        """
        여러 RSS 피드에서 뉴스를 수집합니다.
        
        Returns:
            기사 딕셔너리 리스트
        """
        try:
            all_articles = []
            seen_urls = set()
            
            for feed_name, rss_url in self.feeds.items():
                self.logger.info(f"\n{'='*60}")
                self.logger.info(f"Collecting {feed_name} news...")
                self.logger.info(f"{'='*60}")
                
                try:
                    articles = self._parse_rss(rss_url, feed_name)
                    
                    for article in articles:
                        url = article.get("url", "")
                        if url and url not in seen_urls:
                            # 소스 추가
                            article = self._add_source(article)
                            # 소스 이름 설정 (하위 클래스에서 오버라이드 가능)
                            article = self._set_source_name(article, feed_name)
                            all_articles.append(article)
                            seen_urls.add(url)
                    
                    self.logger.info(f"[{feed_name}] ✅ Collected {len(articles)} articles")
                    
                except Exception as e:
                    self.logger.error(f"Failed to fetch {feed_name} news: {e}")
                    continue
            
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
    
    def _set_source_name(self, article: Dict[str, Any], feed_name: str) -> Dict[str, Any]:
        """
        기사의 소스 이름을 설정합니다.
        하위 클래스에서 오버라이드하여 커스터마이징할 수 있습니다.
        
        Args:
            article: 기사 딕셔너리
            feed_name: 피드 이름
        
        Returns:
            소스 이름이 설정된 기사 딕셔너리
        """
        # 기본: 피드 이름을 소스로 사용
        article["source"] = feed_name
        return article


