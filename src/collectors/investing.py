"""인베스팅닷컴(Investing.com) 뉴스 수집기"""

from typing import List, Dict, Any
import logging
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.collectors.base_rss import BaseRSSScraper
from config.settings import (
    REQUEST_TIMEOUT,
    MIN_ARTICLES_PER_SOURCE,
    ENABLE_NEWSPAPER3K,
    NEWSPAPER3K_TIMEOUT,
    RATE_LIMIT_DELAY
)

logger = logging.getLogger(__name__)


class InvestingScraper(BaseRSSScraper):
    """
    인베스팅닷컴(Investing.com) 수집기
    전략: 공식 RSS Feed 활용 (Cloudflare 우회 및 속도 확보)
    """
    
    def __init__(self):
        """
        초기화
        여러 RSS 피드를 관리합니다.
        """
        super().__init__(
            source_name="Investing",
            rss_url=None  # 다중 RSS 피드 사용
        )
        
        # 영문판 (Global) RSS 목록
        self.rss_feeds = {
            "Investing (Economy)": "https://www.investing.com/rss/news_14.rss",      # 거시 경제 (필수)
            "Investing (Commodities)": "https://www.investing.com/rss/news_11.rss",  # 원자재 (유가, 금)
            "Investing (Forex)": "https://www.investing.com/rss/news_1.rss",         # 외환 시장
            "Investing (Stocks)": "https://www.investing.com/rss/news_25.rss",       # 주식 시장
            
            # 한국어판 (Korea) 필요시 주석 해제하여 사용
            # "Investing KR (Economy)": "https://kr.investing.com/rss/news_14.rss",
            # "Investing KR (Crypto)": "https://kr.investing.com/rss/news_301.rss"
        }
    
    def _parse_rss_feed(self, category: str, rss_url: str) -> List[Dict[str, Any]]:
        """
        개별 RSS 피드를 파싱합니다.
        
        Args:
            category: RSS 피드 카테고리 이름
            rss_url: RSS 피드 URL
        
        Returns:
            파싱된 기사 리스트
        """
        self.logger.info(f"Fetching Investing.com RSS feed: {category}")
        
        # BaseRSSScraper의 _parse_rss를 사용
        articles = super()._parse_rss(rss_url)
        
        # Investing.com 특별 처리: Newspaper3k를 이용한 본문 앞부분 추출
        if ENABLE_NEWSPAPER3K:
            for article in articles:
                try:
                    from newspaper import Article
                    import time
                    
                    link = article.get("url", "")
                    if not link:
                        continue
                    
                    # 타임아웃을 짧게 주어 Cloudflare에 걸리면 바로 포기하고 RSS 요약 사용
                    article_obj = Article(link, language='en')
                    article_obj.config.request_timeout = NEWSPAPER3K_TIMEOUT
                    article_obj.download()
                    article_obj.parse()
                    
                    # article.nlp()는 호출하지 않음 (속도 향상)
                    if article_obj.text:
                        # 본문 앞 300자만 추출
                        final_summary = article_obj.text.strip().replace('\n', ' ')[:300]
                        article["summary"] = final_summary
                    
                    # Rate limiting
                    time.sleep(RATE_LIMIT_DELAY)
                    
                except Exception as e:
                    # 본문 수집 실패 시 RSS 기본 요약 사용
                    self.logger.debug(f"Failed to fetch article content for {link}: {e}. Using RSS summary.")
                    pass
        
        return articles
    
    def _process_rss_entry(self, entry: Dict[str, Any], article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Investing.com RSS 엔트리를 후처리합니다.
        HTML 태그 제거.
        """
        # HTML 태그 제거 (RSS 요약에 포함된 경우)
        summary = article.get("summary", "")
        if summary:
            article["summary"] = self._remove_html_tags(summary)
        
        return article
    
    def _remove_html_tags(self, text: str) -> str:
        """
        HTML 태그를 제거하고 텍스트만 추출합니다.
        
        Args:
            text: HTML이 포함된 텍스트
        
        Returns:
            HTML 태그가 제거된 순수 텍스트
        """
        if not text:
            return ""
        
        try:
            soup = BeautifulSoup(text, 'html.parser')
            return soup.get_text(separator=' ', strip=True)
        except Exception as e:
            self.logger.warning(f"Failed to remove HTML tags: {e}. Using original text.")
            # 폴백: 간단한 문자열 치환
            return text.replace('<p>', '').replace('</p>', '').replace('<br>', ' ').replace('<br/>', ' ')
    
    def fetch_news(self) -> List[Dict[str, Any]]:
        """
        Investing.com 뉴스를 수집합니다.
        여러 RSS 피드를 병렬로 처리하여 속도를 향상시킵니다.
        
        Returns:
            기사 딕셔너리 리스트
        """
        self.logger.info("Fetching Investing.com RSS Feeds (Parallel)...")
        
        all_articles = []
        seen_urls = set()  # 중복 제거용
        
        # ThreadPoolExecutor를 사용하여 여러 RSS 피드를 병렬로 처리
        with ThreadPoolExecutor(max_workers=len(self.rss_feeds)) as executor:
            # 모든 RSS 피드 처리 작업 제출
            future_to_category = {
                executor.submit(self._parse_rss_feed, category, rss_url): category
                for category, rss_url in self.rss_feeds.items()
            }
            
            # 완료된 작업 처리
            for future in as_completed(future_to_category):
                category = future_to_category[future]
                try:
                    articles = future.result()
                    
                    for article in articles:
                        url = article.get("url", "")
                        if url and url not in seen_urls:
                            all_articles.append(article)
                            seen_urls.add(url)
                    
                    self.logger.info(f"✅ {category}: Collected {len(articles)} articles")
                    
                except Exception as e:
                    self.logger.error(f"Failed to process RSS feed {category}: {e}")
                    continue
        
        if not all_articles:
            self.logger.warning("No articles collected from Investing.com RSS feeds.")
            return []
        
        # 최소 수집 개수 확인
        if len(all_articles) < MIN_ARTICLES_PER_SOURCE:
            self.logger.warning(
                f"Investing.com: Only collected {len(all_articles)} articles "
                f"(target: {MIN_ARTICLES_PER_SOURCE}+). "
                f"Consider adding additional RSS feeds."
            )
        
        # 소스 정보 추가
        enriched_articles = []
        total = len(all_articles)
        
        self.logger.info(f"Processing {total} Investing.com articles...")
        
        for idx, article in enumerate(all_articles, 1):
            # 진행 상황 로깅 (20개마다)
            if idx % 20 == 0 or idx == total:
                self.logger.info(f"Processing Investing.com article {idx}/{total}...")
            
            # _add_source() 메서드 활용 (image_url, authors는 자동으로 공란 처리)
            article = self._add_source(article)
            
            # 카테고리 추가
            article = self._add_content_category(
                article,
                category="finance",
                source_type="foreign"
            )
            
            enriched_articles.append(article)
        
        self.logger.info(f"✅ Collected total {len(enriched_articles)} articles from Investing.com.")
        return enriched_articles

