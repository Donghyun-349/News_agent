"""Wall Street Journal 뉴스 수집기 (Google News RSS 사용)"""

from typing import List, Dict, Any
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from urllib.parse import quote_plus
import os

from src.collectors.base_rss import BaseRSSScraper
from src.utils.text_cleaner import remove_wsj_suffix, is_valid_article_title
from config.settings import MIN_ARTICLES_PER_SOURCE, MAJOR_FOREIGN_NEWS_TARGET_COUNT

logger = logging.getLogger(__name__)


class WSJScraper(BaseRSSScraper):
    """Wall Street Journal 뉴스 수집기 (Google News RSS 우회 전략)"""
    
    def __init__(self, rss_url: str = None):
        """
        초기화
        
        Args:
            rss_url: Google News RSS URL (None이면 설정에서 가져옴)
        """
        from config.settings import WSJ_GOOGLE_NEWS_URL
        super().__init__(
            source_name="WSJ",
            rss_url=rss_url or WSJ_GOOGLE_NEWS_URL
        )
        # 여러 쿼리를 시도하기 위한 URL 리스트
        self.rss_urls = [
            WSJ_GOOGLE_NEWS_URL,
            f"https://news.google.com/rss/search?q={quote_plus('site:wsj.com when:1d')}&hl=en-US&gl=US&ceid=US:en",
            f"https://news.google.com/rss/search?q={quote_plus('site:wsj.com (finance OR business OR economy OR market) when:1d')}&hl=en-US&gl=US&ceid=US:en",
        ]
    
    
    def _is_recent_article(self, published: str) -> bool:
        """
        기사가 최근 기사인지 확인합니다 (1년 이내).
        
        Args:
            published: 발행일 문자열
        
        Returns:
            최근 기사면 True, 아니면 False
        """
        if not published:
            return True  # 날짜가 없으면 통과 (다른 검증에서 걸러짐)
        
        try:
            # 날짜 파싱
            pub_date = datetime.strptime(published, "%Y-%m-%d %H:%M:%S")
            # 1년 이내인지 확인
            one_year_ago = datetime.now() - timedelta(days=365)
            return pub_date >= one_year_ago
        except Exception as e:
            self.logger.debug(f"Failed to parse date '{published}': {e}")
            return True  # 파싱 실패 시 통과 (다른 검증에서 걸러짐)
    
    def _process_rss_entry(self, entry: Dict[str, Any], article: Dict[str, Any]) -> Dict[str, Any]:
        """
        WSJ RSS 엔트리를 후처리합니다.
        제목에서 "- The Wall Street Journal" 제거 및 summary 처리.
        """
        title = article.get("title", "")
        summary = article.get("summary", "")
        
        # 제목에서 "- The Wall Street Journal" 제거 (유틸리티 함수 사용)
        title_cleaned = remove_wsj_suffix(title)
        
        # 유효하지 않은 제목은 None 반환하여 필터링
        if not is_valid_article_title(title_cleaned):
            return None
        
        article["title"] = title_cleaned
        
        # WSJ: summary가 title과 동일하면 공란으로 처리
        if summary and summary.strip() == title_cleaned:
            article["summary"] = ""
        
        return article
    
    def _filter_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        수집된 기사들을 필터링합니다.
        
        Args:
            articles: 수집된 기사 리스트
        
        Returns:
            필터링된 기사 리스트
        """
        filtered = []
        skipped_count = 0
        
        for article in articles:
            title = article.get("title", "").strip()
            published = article.get("published", "")
            
            # 제목 유효성 검사 (이미 _process_rss_entry에서 필터링되었지만, 추가 확인)
            if not is_valid_article_title(title):
                skipped_count += 1
                self.logger.debug(f"Skipping article with invalid title: {title[:50]}...")
                continue
            
            # 최근 기사인지 확인
            if not self._is_recent_article(published):
                skipped_count += 1
                self.logger.debug(f"Skipping old article: {title[:50]}... (published: {published})")
                continue
            
            filtered.append(article)
        
        if skipped_count > 0:
            self.logger.info(f"Filtered out {skipped_count} invalid/old WSJ articles")
        
        return filtered
    
    def fetch_news(self) -> List[Dict[str, Any]]:
        """
        WSJ 뉴스를 수집합니다.
        최소 30개 이상 수집을 목표로 합니다.
        여러 Google News RSS 쿼리를 시도하여 더 많은 기사를 수집합니다.
        
        Returns:
            기사 딕셔너리 리스트
        """
        try:
            all_articles = []
            seen_urls = set()  # 중복 제거용
            
            # 여러 RSS URL 시도
            for rss_url in self.rss_urls:
                if len(all_articles) >= MIN_ARTICLES_PER_SOURCE:
                    break
                
                try:
                    self.logger.info(f"Trying WSJ RSS: {rss_url[:80]}...")
                    articles = self._parse_rss(rss_url)
                    
                    # 기사 필터링 및 중복 제거
                    filtered_articles = self._filter_articles(articles)
                    for article in filtered_articles:
                        url = article.get("url", "")
                        if url and url not in seen_urls:
                            all_articles.append(article)
                            seen_urls.add(url)
                    
                    self.logger.info(f"  Collected {len(filtered_articles)} articles from this query (total: {len(all_articles)})")
                    
                except Exception as e:
                    self.logger.warning(f"Failed to parse RSS URL {rss_url[:80]}...: {e}")
                    continue
            
            if not all_articles:
                self.logger.warning("No valid WSJ articles collected")
                return []
            
            articles = all_articles
            
            # 최소 수집 개수 확인
            if len(articles) < MIN_ARTICLES_PER_SOURCE:
                self.logger.warning(
                    f"WSJ: Only collected {len(articles)} articles "
                    f"(target: {MIN_ARTICLES_PER_SOURCE}+). "
                    f"Consider adjusting Google News RSS query."
                )
            
            # 메타데이터 보강 및 소스 추가
            # WSJ는 Google News RSS를 사용하므로 Newspaper3k 보강은 선택적으로 실행
            # (Paywall로 인해 403 에러가 많이 발생하지만, 일부는 성공할 수 있음)
            # 속도 향상을 위해 메타데이터 보강 건너뛰기 옵션 추가
            skip_enrichment = os.getenv("WSJ_SKIP_ENRICHMENT", "false").lower() == "true"
            
            if skip_enrichment:
                # 메타데이터 보강 건너뛰기 (Bloomberg, Reuters처럼)
                enriched_articles = self._process_articles(
                    articles,
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
            else:
                # 병렬 처리로 메타데이터 보강
                max_workers = int(os.getenv("WSJ_MAX_WORKERS", "5"))
                enriched_articles = []
                total = len(articles)
                
                self.logger.info(f"Enriching metadata for {total} WSJ articles using {max_workers} workers...")
                
                def process_article(article):
                    article = self._enrich_metadata(article)
                    article["summary"] = ""
                    article = self._add_source(article)
                    return article
                
                completed = 0
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_article = {
                        executor.submit(process_article, article): article 
                        for article in articles
                    }
                    
                    for future in as_completed(future_to_article):
                        completed += 1
                        if completed % 10 == 0 or completed == total:
                            self.logger.info(f"Processing WSJ article {completed}/{total}...")
                        
                        try:
                            enriched_article = future.result()
                            # 카테고리 추가
                            enriched_article = self._add_content_category(
                                enriched_article,
                                category="finance",
                                source_type="foreign"
                            )
                            enriched_articles.append(enriched_article)
                        except Exception as e:
                            self.logger.warning(f"Failed to enrich article: {e}")
            
            # 목표 개수로 제한
            limited_articles = enriched_articles[:MAJOR_FOREIGN_NEWS_TARGET_COUNT]
            self.logger.info(f"✅ Completed processing {len(limited_articles)} WSJ articles (limited to {MAJOR_FOREIGN_NEWS_TARGET_COUNT})")
            return limited_articles
            
        except Exception as e:
            self.logger.error(f"Failed to fetch WSJ news: {e}")
            return []

