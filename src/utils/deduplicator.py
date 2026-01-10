"""중복 제거 유틸리티"""

from typing import List, Set
import logging
from urllib.parse import urlparse, parse_qs
import hashlib

from storage.models import ArticleRecord

logger = logging.getLogger(__name__)


class Deduplicator:
    """기사 중복 제거 클래스"""
    
    def __init__(self):
        """초기화"""
        pass
    
    def _normalize_url(self, url: str) -> str:
        """
        URL 정규화 (쿼리 파라미터 제거, 소문자 변환 등)
        
        Args:
            url: 원본 URL
        
        Returns:
            정규화된 URL
        """
        if not url:
            return ""
        
        try:
            parsed = urlparse(url)
            # scheme, netloc, path만 사용 (쿼리 파라미터 제거)
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            # 소문자 변환
            normalized = normalized.lower()
            # 마지막 슬래시 제거 (일관성)
            if normalized.endswith('/'):
                normalized = normalized[:-1]
            return normalized
        except Exception as e:
            logger.warning(f"Failed to normalize URL {url}: {e}")
            return url.lower()
    
    def _normalize_title(self, title: str) -> str:
        """
        제목 정규화 (공백 제거, 소문자 변환)
        
        Args:
            title: 원본 제목
        
        Returns:
            정규화된 제목
        """
        if not title:
            return ""
        
        # 소문자 변환
        normalized = title.lower()
        # 연속된 공백을 단일 공백으로
        normalized = ' '.join(normalized.split())
        # 특수 문자 제거 (선택적, 필요시 추가)
        return normalized
    
    def deduplicate_by_url(self, articles: List[ArticleRecord]) -> List[ArticleRecord]:
        """
        URL 기반 중복 제거
        
        Args:
            articles: ArticleRecord 리스트
        
        Returns:
            중복이 제거된 ArticleRecord 리스트
        """
        if not articles:
            return articles
        
        seen_urls: Set[str] = set()
        unique_articles: List[ArticleRecord] = []
        duplicate_count = 0
        
        for article in articles:
            if not article.url:
                # URL이 없으면 일단 포함 (나중에 필터링 가능)
                unique_articles.append(article)
                continue
            
            normalized_url = self._normalize_url(article.url)
            
            if normalized_url in seen_urls:
                duplicate_count += 1
                logger.debug(f"Duplicate URL found: {article.url}")
                continue
            
            seen_urls.add(normalized_url)
            unique_articles.append(article)
        
        if duplicate_count > 0:
            logger.info(f"Removed {duplicate_count} duplicate articles by URL (kept {len(unique_articles)} unique)")
        
        return unique_articles
    
    def deduplicate_by_title_similarity(
        self, 
        articles: List[ArticleRecord],
        similarity_threshold: float = 0.9
    ) -> List[ArticleRecord]:
        """
        제목 유사도 기반 중복 제거 (선택적 기능)
        
        Args:
            articles: ArticleRecord 리스트
            similarity_threshold: 유사도 임계값 (0.0 ~ 1.0)
        
        Returns:
            중복이 제거된 ArticleRecord 리스트
        """
        # 간단한 구현: 정규화된 제목이 동일하면 중복으로 간주
        # 더 정교한 유사도 계산은 나중에 추가 가능 (예: difflib, fuzzywuzzy)
        
        if not articles:

            return articles
        
        seen_titles: Set[str] = set()
        unique_articles: List[ArticleRecord] = []
        duplicate_count = 0
        
        for article in articles:
            if not article.title:
                unique_articles.append(article)
                continue
            
            normalized_title = self._normalize_title(article.title)
            
            if normalized_title in seen_titles:
                duplicate_count += 1
                logger.debug(f"Duplicate title found: {article.title}")
                continue
            
            seen_titles.add(normalized_title)
            unique_articles.append(article)
        
        if duplicate_count > 0:
            logger.info(f"Removed {duplicate_count} duplicate articles by title (kept {len(unique_articles)} unique)")
        
        return unique_articles
    
    def deduplicate(
        self, 
        articles: List[ArticleRecord],
        use_title: bool = False
    ) -> List[ArticleRecord]:
        """
        종합 중복 제거 (URL 우선, 필요시 제목도 사용)
        
        Args:
            articles: ArticleRecord 리스트
            use_title: 제목 기반 중복 제거도 사용할지 여부
        
        Returns:
            중복이 제거된 ArticleRecord 리스트
        """
        original_count = len(articles)
        
        # 1단계: URL 기반 중복 제거
        articles = self.deduplicate_by_url(articles)
        
        # 2단계: 제목 기반 중복 제거 (선택적)
        if use_title:
            articles = self.deduplicate_by_title_similarity(articles)
        
        removed_count = original_count - len(articles)
        
        if removed_count > 0:
            logger.info(f"✅ Deduplication complete: {removed_count} duplicates removed, {len(articles)} unique articles remaining")
        else:
            logger.info(f"✅ No duplicates found ({len(articles)} articles)")
        
        return articles



