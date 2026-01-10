"""한국 경제 뉴스 RSS 수집기"""

from typing import List, Dict, Any
import logging
import re

from src.collectors.multi_rss import MultiRSSScraper
from config.rss_feeds import get_rss_feeds

logger = logging.getLogger(__name__)


class KoreanEconomyScraper(MultiRSSScraper):
    """한국 경제 뉴스 RSS 수집기 (RSS Feed Registry 사용)"""
    
    def __init__(self):
        """초기화"""
        # RSS Feed Registry에서 설정 가져오기
        registry_config = get_rss_feeds("Korean Economy")
        if not registry_config:
            raise ValueError("Korean Economy RSS feeds not found in registry")
        
        feeds = registry_config["feeds"]
        options = registry_config.get("options", {})
        use_ssl_context = options.get("use_ssl_context", False)
        
        super().__init__(
            source_name="Korean Economy",
            feeds=feeds,
            use_ssl_context=use_ssl_context
        )
    
    def _process_rss_entry(self, entry: Dict[str, Any], article: Dict[str, Any]) -> Dict[str, Any]:
        """
        한국 경제 뉴스 RSS 엔트리를 후처리합니다.
        제목에서 "- Source" 제거 및 summary 처리.
        """
        title = article.get("title", "").strip()
        summary = article.get("summary", "").strip()
        feed_name = getattr(self, '_current_feed_name', '')
        
        # 제목에서 "- Source" 제거 후 비교
        title_cleaned = title
        if " - " in title_cleaned:
            title_cleaned = title_cleaned.rsplit(" - ", 1)[0].strip()
        
        if summary == title_cleaned:
            article["summary"] = ""
        
        # 파이낸셜뉴스 스니펫에서 [파이낸셜뉴스] 제거
        if feed_name == "파이낸셜뉴스" and summary:
            summary = re.sub(r'\[파이낸셜뉴스\]', '', summary).strip()
            article["summary"] = summary
        
        return article
    
    def _set_source_name(self, article: Dict[str, Any], feed_name: str) -> Dict[str, Any]:
        """
        기사의 소스 이름을 언론사명으로 설정합니다.
        """
        article["source"] = feed_name
        article["press_name"] = feed_name
        
        # 카테고리 추가
        article = self._add_content_category(
            article,
            category="finance",
            source_type="domestic"
        )
        
        return article

