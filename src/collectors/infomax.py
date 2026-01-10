"""연합인포맥스(Infomax) 뉴스 수집기 (RSS 기반)"""

from typing import List, Dict, Any
import logging

from src.collectors.base_rss import BaseRSSScraper
from config.settings import MIN_ARTICLES_PER_SOURCE

logger = logging.getLogger(__name__)


class InfomaxScraper(BaseRSSScraper):
    """연합인포맥스(Infomax) 뉴스 수집기 (RSS 기반)"""
    
    # RSS 피드 URL과 카테고리 매핑
    RSS_FEEDS = {
        "증권": {
            "url": "https://news.einfomax.co.kr/rss/S1N2.xml",
            "category": "finance"
        },
        "기업": {
            "url": "https://news.einfomax.co.kr/rss/S1N7.xml",
            "category": "companies"
        },
        "금융": {
            "url": "https://news.einfomax.co.kr/rss/S1N15.xml",
            "category": "finance"
        },
        "채권, 외환": {
            "url": "https://news.einfomax.co.kr/rss/S1N16.xml",
            "category": "finance"
        },
        "부동산": {
            "url": "https://news.einfomax.co.kr/rss/S1N17.xml",
            "category": "real_estate"
        },
        "해외 주식": {
            "url": "https://news.einfomax.co.kr/rss/S1N21.xml",
            "category": "finance"
        }
    }
    
    def __init__(self, rss_url: str = None):
        """
        초기화
        
        Args:
            rss_url: RSS Feed URL (None이면 첫 번째 RSS 피드 사용)
        """
        # 첫 번째 RSS 피드를 기본값으로 사용
        default_url = list(self.RSS_FEEDS.values())[0]["url"]
        super().__init__(
            source_name="Infomax",
            rss_url=rss_url or default_url
        )
    
    def _process_rss_entry(self, entry: Dict[str, Any], article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Infomax RSS 엔트리를 후처리합니다.
        summary가 title과 동일하면 공란으로 처리.
        저작권 관련 내용이 포함된 스니펫은 수집하지 않습니다.
        """
        title = article.get("title", "").strip()
        summary = article.get("summary", "").strip()
        
        # Infomax: summary가 title과 동일하면 공란으로 처리
        if summary == title:
            article["summary"] = ""
            return article
        
        # 저작권 관련 내용 필터링
        copyright_keywords = [
            "저작권자",
            "연합인포맥스",
            "무단전재",
            "재배포 금지",
            "AI 학습",
            "활용 금지",
            "(c)",
            "©"
        ]
        
        summary_lower = summary.lower()
        # 저작권 관련 키워드가 포함되어 있으면 스니펫 제거
        if any(keyword.lower() in summary_lower for keyword in copyright_keywords):
            article["summary"] = ""
            self.logger.debug(f"Filtered copyright notice from summary: {title[:50]}...")
        
        return article
    
    def _parse_rss(self, rss_url: str = None) -> List[Dict[str, Any]]:
        """
        RSS 피드를 파싱합니다.
        Infomax는 날짜 필터링을 완화하여 더 많은 기사를 수집합니다.
        
        Args:
            rss_url: 파싱할 RSS URL (None이면 self.rss_url 사용)
        
        Returns:
            파싱된 기사 리스트
        """
        from src.utils.rss_parser import parse_rss_feed
        from src.utils.date_parser import parse_rss_date
        from config.settings import REQUEST_TIMEOUT
        import pytz
        from datetime import datetime, timedelta
        
        target_url = rss_url or self.rss_url
        if not target_url:
            self.logger.error("No RSS URL provided")
            return []
        
        self.logger.info(f"Fetching {self.source_name} news from: {target_url}")
        
        # RSS 피드 파싱
        feed = parse_rss_feed(target_url, timeout=REQUEST_TIMEOUT, use_ssl_context=False)
        if not feed:
            return []
        
        articles = []
        total_entries = len(feed.entries)
        
        self.logger.info(f"Parsing {total_entries} entries from {self.source_name} RSS...")
        
        # 날짜 필터링: 설정값(COLLECTION_TIME_LIMIT_HOURS)을 사용하여 기사 수집
        from config.settings import COLLECTION_TIME_LIMIT_HOURS
        korea_tz = pytz.timezone('Asia/Seoul')
        now_korea = datetime.now(korea_tz)
        # Infomax는 기사 수 확보를 위해 48시간으로 확장
        time_limit_korea = now_korea - timedelta(hours=48)
        
        for idx, entry in enumerate(feed.entries, 1):
            try:
                # 진행 상황 로깅 (10개마다)
                if idx % 10 == 0 or idx == total_entries:
                    self.logger.info(f"Processing entry {idx}/{total_entries}...")
                
                # 날짜 파싱
                date_str = entry.get("published") or entry.get("updated") or entry.get("pubDate") or getattr(entry, "published", None)
                published = parse_rss_date(date_str)
                
                # 날짜 필터링: 설정된 시간 제한 이내의 기사만 수집
                if published:
                    try:
                        from dateutil import parser as date_parser
                        pub_date = date_parser.parse(published)
                        
                        # 한국 시간으로 변환
                        if pub_date.tzinfo is None:
                            from datetime import timezone
                            pub_date = pub_date.replace(tzinfo=timezone.utc)
                        
                        pub_date_korea = pub_date.astimezone(korea_tz)
                        
                        # 시간 제한 이전 기사는 건너뛰기
                        if pub_date_korea < time_limit_korea:
                            continue
                    except Exception as e:
                        # 날짜 파싱 실패 시 로깅만 하고 계속 진행
                        self.logger.debug(f"Failed to parse date for filtering: {published}, {e}")
                
                # URL 추출 (여러 필드 시도)
                url = entry.get("link") or entry.get("id") or entry.get("href") or getattr(entry, "link", None)
                if url:
                    url = str(url).strip()
                    # URL 유효성 검사 (http 또는 https로 시작)
                    if not (url.startswith("http://") or url.startswith("https://")):
                        self.logger.warning(f"Entry {idx}: 유효하지 않은 URL 형식 (제목: {entry.get('title', 'N/A')[:50]}, URL: {url[:100]})")
                        url = None
                else:
                    url = ""
                
                # URL이 없거나 유효하지 않으면 건너뛰기
                if not url:
                    self.logger.warning(f"Entry {idx}: URL이 없음 (제목: {entry.get('title', 'N/A')[:50]})")
                    continue
                
                # 기본 기사 데이터
                article = {
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "url": url,  # 검증된 URL만 사용
                    "published": published,
                }
                
                # 후처리 메서드 호출
                article = self._process_rss_entry(entry, article)
                
                # None이 반환된 경우 제외
                if article is not None:
                    articles.append(article)
                
            except Exception as e:
                self.logger.error(f"Error parsing entry {idx}: {e}")
                continue
        
        self.logger.info(f"Found {len(articles)} articles from {self.source_name}")
        return articles
    
    def fetch_news(self) -> List[Dict[str, Any]]:
        """
        Infomax 뉴스를 수집합니다.
        여러 RSS 피드를 모두 수집하여 통합합니다.
        최소 30개 이상 수집을 목표로 합니다.
        
        Returns:
            기사 딕셔너리 리스트
        """
        try:
            all_articles = []
            seen_urls = set()  # 중복 제거용
            
            # 모든 RSS 피드 수집
            for feed_name, feed_info in self.RSS_FEEDS.items():
                rss_url = feed_info["url"]
                category = feed_info["category"]
                
                try:
                    self.logger.info(f"Fetching Infomax RSS feed: {feed_name} ({rss_url})")
                    articles = self._parse_rss(rss_url)
                    
                    # 각 기사에 카테고리 정보 추가
                    for article in articles:
                        url = article.get("url", "")
                        if url and url not in seen_urls:
                            article["_category"] = category  # 임시로 카테고리 저장
                            all_articles.append(article)
                            seen_urls.add(url)
                    
                    self.logger.info(f"  Collected {len(articles)} articles from {feed_name} (total: {len(all_articles)})")
                    
                    # 모든 RSS 피드를 수집 (목표 개수 도달해도 계속 수집)
                    # Infomax는 여러 카테고리의 피드가 있으므로 모두 수집하여 다양성 확보
                    
                except Exception as e:
                    self.logger.warning(f"Failed to parse RSS feed {feed_name} ({rss_url}): {e}")
                    continue
            
            if not all_articles:
                self.logger.warning("No articles collected from Infomax RSS feeds")
                return []
            
            # 메타데이터 보강 및 소스 추가
            enriched_articles = self._process_articles(
                all_articles,
                skip_enrichment=False,
                clear_summary=False
            )
            
            # 카테고리 추가 (임시로 저장한 카테고리 사용)
            for idx, article in enumerate(enriched_articles):
                category = article.pop("_category", "finance")  # 기본값은 finance
                enriched_articles[idx] = self._add_content_category(
                    article,
                    category=category,
                    source_type="domestic"
                )
            
            self.logger.info(f"✅ Collected {len(enriched_articles)} Infomax articles")
            return enriched_articles
            
        except Exception as e:
            self.logger.error(f"Failed to fetch Infomax news: {e}")
            return []
