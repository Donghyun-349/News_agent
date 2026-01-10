"""미국 부동산 시장 뉴스 수집기 (Google News RSS 사용)"""

from typing import List, Dict, Any, Optional
import logging
import os

from src.collectors.google_news_rss import GoogleNewsRSSScraper
from config.settings import MIN_ARTICLES_PER_SOURCE, US_REAL_ESTATE_TARGET_COUNT
from src.utils.config_loader import config_loader

logger = logging.getLogger(__name__)


class USRealEstateScraper(GoogleNewsRSSScraper):
    """미국 부동산 시장 뉴스 수집기 (Google News RSS 사용)"""
    
    # 쿼리는 config.json에서 로드됩니다.
    
    def __init__(self, topic: str = None):
        """
        초기화
        
        Args:
            topic: 수집할 주제명 (None이면 모든 주제 수집)
        """
        # Dynamic Config Load
        self.queries = config_loader.get_queries("US Real Estate") or {}
        target_count = config_loader.get_setting("us_real_estate_target_count", US_REAL_ESTATE_TARGET_COUNT)
        
        max_workers = int(os.getenv("US_REAL_ESTATE_MAX_WORKERS", "5"))
        
        super().__init__(
            source_name="US Real Estate",
            queries=self.queries,
            target_count=target_count,
            max_workers=max_workers
        )
        self.topic = topic
    
    def _process_topic_articles(self, topic_name: str, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        주제별 기사들을 후처리합니다 (소스 추가, topic 필드 추가).
        US Real Estate는 스니펫을 수집하지 않도록 설정합니다.
        
        Args:
            topic_name: 주제명
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
        
        # 소스 이름을 발행 언론사로 설정 (없으면 주제명)
        for article in processed_articles:
            # topic 필드 추가
            article["topic"] = topic_name
            press_name = article.get("press_name", "")
            if press_name:
                article["source"] = press_name
            else:
                article["source"] = topic_name
            
            # 카테고리 추가
            article = self._add_content_category(
                article,
                category="real_estate",
                source_type="foreign"
            )
        
        return processed_articles
    

    def fetch_news(self) -> List[Dict[str, Any]]:
        """
        미국 부동산 뉴스를 수집합니다.
        특정 주제가 지정되면 해당 주제만, 아니면 모든 주제 수집.
        
        **Sampling Logic**:
        수집된 전체 기사 중 약 1/3 (33%)만 무작위로 샘플링하여 반환합니다.
        단, 주제별 불균형을 막기 위해 Stratified Sampling(주제별 샘플링)을 수행합니다.
        
        Returns:
            기사 딕셔너리 리스트
        """
        import random
        from collections import defaultdict

        # 수집할 주제 목록
        topics = [self.topic] if self.topic else list(self.queries.keys())
        
        # 1. 부모 클래스의 fetch_news 사용하여 전체 수집 (기존 로직 유지)
        full_articles = super().fetch_news(selected_topics=topics)
        
        logger.info(f"📊 Before Sampling: {len(full_articles)} articles collected.")
        
        # 2. 주제별로 그룹화 (Stratified Sampling 준비)
        grouped_articles = defaultdict(list)
        for article in full_articles:
            # article["topic"]은 _process_topic_articles에서 이미 설정됨
            t = article.get("topic", "Unknown")
            grouped_articles[t].append(article)
            
        # 3. 주제별 1/3 샘플링
        sampled_results = []
        for t, items in grouped_articles.items():
            count = len(items)
            # Sampling Logic Removed (100% Selection)
            # 최소 1개는 유지하되, 비율대로 계산 -> 전체 선택
            target_n = count
            
            # 전체 선택
            selected = items
            sampled_results.extend(selected)
            logger.info(f"  - Topic '{t}': {count} -> {len(selected)} (target: {target_n})")
            
        logger.info(f"✅ After Stratified Sampling: {len(sampled_results)} articles final result.")
        
        return sampled_results

