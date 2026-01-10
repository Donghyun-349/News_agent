"""글로벌이코노믹 뉴스 수집기"""

from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse
import time
import requests
from bs4 import BeautifulSoup
from newspaper import Article

from src.collectors.base import BaseScraper
from src.utils.retry import retry_with_backoff
from config.settings import (
    REQUEST_TIMEOUT,
    MIN_ARTICLES_PER_SOURCE,
    GENEWS_BASE_URL,
    GENEWS_MAX_PAGES,
    GENEWS_DELAY
)

logger = logging.getLogger(__name__)


class GEnewsScraper(BaseScraper):
    """글로벌이코노믹 뉴스 수집기"""
    
    def __init__(self, base_url: str = None):
        """
        초기화
        
        Args:
            base_url: 기본 URL (None이면 설정에서 가져옴)
        """
        super().__init__(
            source_name="GEnews",
            rss_url=None  # RSS 없음
        )
        self.base_url = base_url or GENEWS_BASE_URL
        self.domain = "https://www.g-enews.com"
        self.section_endpoint = self.base_url  # list.php?ct=g080200
        self.max_pages = GENEWS_MAX_PAGES
        self.delay = GENEWS_DELAY
        
        # 현재 날짜로 날짜 파라미터 생성 (로컬 시간 사용 - 한국 시간)
        now = datetime.now()
        self.year = now.year
        self.month = now.month
        self.day = now.day
    
    @retry_with_backoff(
        max_attempts=3,
        initial_delay=1.0,
        exceptions=(Exception,)
    )
    def _fetch_list_page(self, page: int) -> List[Dict[str, str]]:
        """
        리스트 페이지에서 기사 링크, 제목, 날짜를 함께 추출합니다.
        
        Args:
            page: 페이지 번호
        
        Returns:
            기사 정보 딕셔너리 리스트 (url, title, date_from_list 포함)
        """
        # 페이지네이션: G-enews는 &pg= 파라미터 사용, 날짜 파라미터 포함
        # URL 형식: list.php?ct=g080200&ssk=&ny=2025&nm=12&nmd=1&pg=4
        if '?' in self.section_endpoint:
            target_url = f"{self.section_endpoint}&ssk=&ny={self.year}&nm={self.month}&nmd={self.day}&pg={page}"
        else:
            target_url = f"{self.section_endpoint}?ssk=&ny={self.year}&nm={self.month}&nmd={self.day}&pg={page}"
        
        self.logger.info(f"Fetching GEnews list page {page}: {target_url}")
        
        try:
            # User-Agent 헤더 추가 (봇 차단 방지)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(target_url, timeout=REQUEST_TIMEOUT, headers=headers)
            response.raise_for_status()
            
            # 인코딩 처리 (EUC-KR 또는 UTF-8)
            if response.encoding.lower() in ['iso-8859-1', 'windows-1252']:
                # 잘못 감지된 경우 명시적으로 시도
                try:
                    response.encoding = 'utf-8'
                    response.text  # 인코딩 적용
                except:
                    response.encoding = 'euc-kr'
            else:
                response.encoding = response.apparent_encoding or 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 기사 정보 추출 - 상단 2개 + 하단 12개 = 총 14개
            # 링크, 제목, 날짜를 함께 추출하여 매칭 보장
            article_info_list = []
            seen_urls = set()
            
            article_links = []
            
            # 방법 1: 상단 기사 찾기 (div.11d 또는 div.w1 구조)
            try:
                top_containers = soup.find_all('div', class_=lambda x: x and ('11d' in str(x) or 'w1' in str(x)))
                for container in top_containers:
                    links = container.find_all('a', href=True)
                    for link in links:
                        href = link.get('href', '')
                        if href and '/article/' in href:
                            article_links.append(link)
                
                if article_links:
                    self.logger.debug(f"Found {len(article_links)} top articles")
            except Exception as e:
                self.logger.debug(f"Error finding top articles: {e}")
            
            # 방법 2: 하단 기사 찾기 (div.12d.mt50 > ul > li > div.w2 > a.e1)
            try:
                bottom_links = soup.find_all('a', class_='e1', href=True)
                for link in bottom_links:
                    href = link.get('href', '')
                    if href and '/article/' in href:
                        if link not in article_links:
                            article_links.append(link)
                
                if bottom_links:
                    self.logger.debug(f"Found {len(bottom_links)} bottom article links")
            except Exception as e:
                self.logger.debug(f"Error finding bottom articles: {e}")
            
            # 방법 3: 모든 a.e1 클래스로 찾기 (전체 기사)
            if not article_links:
                try:
                    article_links = soup.find_all('a', class_='e1', href=True)
                    article_links = [link for link in article_links if '/article/' in link.get('href', '')]
                    if article_links:
                        self.logger.info(f"Found {len(article_links)} links with a.e1 class and /article/ path")
                except Exception as e:
                    self.logger.debug(f"Error finding a.e1: {e}")
            
            # 방법 4: /article/ 경로가 있는 모든 링크 찾기 (최후의 수단)
            if not article_links:
                self.logger.warning(f"No articles found with selectors on page {page}. Trying /article/ path search...")
                all_links = soup.find_all('a', href=True)
                article_links = [link for link in all_links if '/article/' in link.get('href', '')]
                if article_links:
                    self.logger.info(f"Found {len(article_links)} links with /article/ path")
            
            # 링크, 제목, 날짜를 함께 추출
            for link_tag in article_links:
                href = link_tag.get('href', '').strip()
                if not href or '/article/' not in href:
                    continue
                
                # 전체 URL 만들기
                if href.startswith('http'):
                    full_url = href
                elif href.startswith('/'):
                    full_url = self.domain + href
                else:
                    full_url = self.domain + '/' + href.lstrip('/')
                
                # 중복 제거
                if full_url in seen_urls or 'g-enews.com' not in full_url:
                    continue
                seen_urls.add(full_url)
                
                # 제목 추출 (리스트 페이지에서)
                # a 태그 내부의 span.elip2 또는 직접 텍스트
                title_from_list = ""
                title_span = link_tag.find('span', class_='elip2')
                if title_span:
                    title_from_list = title_span.get_text(strip=True)
                else:
                    title_from_list = link_tag.get_text(strip=True)
                
                # 날짜 추출 (리스트 페이지에서) - 여러 방법 시도
                date_from_list = ""
                
                # 방법 1: 같은 li 내부의 p.e2 찾기
                parent_li = link_tag.find_parent('li')
                if parent_li:
                    date_elem = parent_li.find('p', class_='e2') or parent_li.find('span', class_=lambda x: x and 'date' in str(x).lower())
                    if date_elem:
                        date_text = date_elem.get_text(strip=True)
                        # "2025.12.16 10:38" 형식을 "2025-12-16 10:38:00" 형식으로 변환
                        try:
                            import re
                            # "2025.12.16 10:38" 형식 파싱
                            date_match = re.match(r'(\d{4})\.(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})', date_text)
                            if date_match:
                                year, month, day, hour, minute = date_match.groups()
                                date_from_list = f"{year}-{month}-{day} {hour}:{minute}:00"
                            else:
                                self.logger.debug(f"Date format not matched: {date_text}")
                        except Exception as e:
                            self.logger.debug(f"Failed to parse date from list: {date_text}, error: {e}")
                
                # 방법 2: URL에서 날짜 추출 (리스트 페이지 날짜 추출 실패 시)
                if not date_from_list:
                    try:
                        import re
                        # URL에서 14자리 숫자 패턴 찾기 (YYYYMMDDHHMMSS)
                        date_match = re.search(r'/(\d{14})', href)
                        if date_match:
                            date_time_str = date_match.group(1)  # 20251223172107
                            # YYYY-MM-DD HH:MM:SS 형식으로 변환
                            date_from_list = f"{date_time_str[:4]}-{date_time_str[4:6]}-{date_time_str[6:8]} {date_time_str[8:10]}:{date_time_str[10:12]}:{date_time_str[12:14]}"
                            self.logger.debug(f"Extracted date from URL: {date_from_list}")
                    except Exception as e:
                        self.logger.debug(f"Failed to extract date from URL: {e}")
                
                # 방법 3: 상단 기사의 경우 다른 구조에서 찾기
                if not date_from_list:
                    parent = link_tag.find_parent(['div', 'article'])
                    if parent:
                        date_elem = parent.find('p', class_='e2') or parent.find('span', class_='date')
                        if date_elem:
                            date_text = date_elem.get_text(strip=True)
                            try:
                                import re
                                date_match = re.match(r'(\d{4})\.(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})', date_text)
                                if date_match:
                                    year, month, day, hour, minute = date_match.groups()
                                    date_from_list = f"{year}-{month}-{day} {hour}:{minute}:00"
                            except Exception as e:
                                self.logger.debug(f"Failed to parse date from parent: {date_text}, error: {e}")
                
                article_info_list.append({
                    'url': full_url,
                    'title_from_list': title_from_list,
                    'date_from_list': date_from_list
                })
            
            if not article_info_list:
                self.logger.warning(f"No article links found on page {page}")
            else:
                self.logger.debug(f"Sample articles from page {page}: {article_info_list[:2]}")
            
            self.logger.info(f"Found {len(article_info_list)} article links on page {page}")
            return article_info_list
            
        except Exception as e:
            self.logger.error(f"Failed to fetch list page {page}: {e}")
            return []
    
    @retry_with_backoff(
        max_attempts=2,
        initial_delay=1.0,
        exceptions=(Exception,)
    )
    def _extract_article(self, article_info: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        newspaper3k를 사용하여 기사 본문을 추출합니다.
        제목과 날짜는 리스트 페이지에서 추출한 정보를 우선 사용합니다.
        
        Args:
            article_info: 리스트 페이지에서 추출한 기사 정보 (url, title_from_list, date_from_list)
        
        Returns:
            기사 딕셔너리 또는 None (실패 시)
        """
        url = article_info.get('url', '')
        title_from_list = article_info.get('title_from_list', '')
        date_from_list = article_info.get('date_from_list', '')
        
        try:
            self.logger.debug(f"Extracting article: {url}")
            
            article = Article(url, language='ko')
            article.config.request_timeout = REQUEST_TIMEOUT
            article.download()
            article.parse()
            
            # 제목: 리스트 페이지에서 추출한 제목 우선 사용, 없으면 newspaper3k 결과 사용
            title = title_from_list if title_from_list else (article.title or "")
            
            # 발행일: 리스트 페이지에서 추출한 날짜 우선 사용
            published = date_from_list
            
            # 리스트 페이지 날짜가 없으면 URL에서 추출 시도
            if not published:
                try:
                    import re
                    # URL에서 14자리 숫자 패턴 찾기 (YYYYMMDDHHMMSS)
                    date_match = re.search(r'/(\d{14})', url)
                    if date_match:
                        date_time_str = date_match.group(1)  # 20251216103618
                        # YYYY-MM-DD HH:MM:SS 형식으로 변환
                        published = f"{date_time_str[:4]}-{date_time_str[4:6]}-{date_time_str[6:8]} {date_time_str[8:10]}:{date_time_str[10:12]}:{date_time_str[12:14]}"
                        self.logger.debug(f"Extracted date from URL: {published}")
                except Exception as e:
                    self.logger.debug(f"Failed to extract date from URL: {e}")
            
            # URL에서 추출 실패 시 newspaper3k 결과 사용
            if not published and article.publish_date:
                from datetime import timezone
                pub_date = article.publish_date
                if pub_date.tzinfo:
                    pub_date = pub_date.astimezone(timezone.utc).replace(tzinfo=None)
                published = pub_date.strftime("%Y-%m-%d %H:%M:%S")
            
            # 둘 다 실패하면 현재 시간 사용
            if not published:
                published = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            
            # Summary 처리: 공란으로 설정 (요구사항)
            summary = ""
            
            article_data = {
                "title": title,
                "summary": summary,
                "url": url,
                "published": published,
            }
            
            # 날짜 필터링: 시간 제한 이내의 기사만 수집
            if not self._is_within_time_limit(published):
                return None
            
            # 속도 조절 제거 (불필요한 딜레이 제거로 속도 향상)
            # 페이지 간 딜레이는 fetch_news()에서만 유지
            
            return article_data
            
        except Exception as e:
            self.logger.warning(f"Failed to extract article {url}: {e}")
            return None
    
    def fetch_news(self) -> List[Dict[str, Any]]:
        """
        글로벌이코노믹 뉴스를 수집합니다.
        
        Returns:
            기사 딕셔너리 리스트
        """
        try:
            all_article_info = []
            
            # 1. 리스트 페이지에서 기사 정보 수집 (1~max_pages 페이지)
            # 각 페이지마다 상단 2개 + 하단 12개 = 총 14개씩 수집 예상
            for page in range(1, self.max_pages + 1):
                try:
                    article_info_list = self._fetch_list_page(page)
                    self.logger.info(f"Page {page}: Found {len(article_info_list)} article URLs (expected: ~14 per page)")
                    all_article_info.extend(article_info_list)
                    
                    # 페이지 간 딜레이
                    if page < self.max_pages:
                        time.sleep(self.delay)
                        
                except Exception as e:
                    self.logger.error(f"Failed to fetch page {page}: {e}")
                    continue
            
            if not all_article_info:
                self.logger.warning("No article URLs found")
                return []
            
            # 중복 제거 (URL 기준)
            seen_urls = set()
            unique_article_info = []
            for article_info in all_article_info:
                url = article_info.get('url', '')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_article_info.append(article_info)
            
            self.logger.info(f"Total unique article URLs: {len(unique_article_info)}")
            
            # 2. 각 기사 본문 추출
            articles = []
            total = len(unique_article_info)
            
            self.logger.info(f"Extracting content from {total} articles...")
            
            for idx, article_info in enumerate(unique_article_info, 1):
                # 진행 상황 로깅 (10개마다)
                if idx % 10 == 0 or idx == total:
                    self.logger.info(f"Processing article {idx}/{total}...")
                
                article_data = self._extract_article(article_info)
                if article_data:
                    # 소스 추가 및 image_url, authors 공란 처리
                    article_data = self._add_source(article_data)
                    
                    # 카테고리 추가
                    article_data = self._add_content_category(
                        article_data,
                        category="finance",
                        source_type="domestic"
                    )
                    
                    articles.append(article_data)
            
            # 최소 수집 개수 확인
            if len(articles) < MIN_ARTICLES_PER_SOURCE:
                self.logger.warning(
                    f"GEnews: Only collected {len(articles)} articles "
                    f"(target: {MIN_ARTICLES_PER_SOURCE}+)."
                )
            
            self.logger.info(f"✅ Collected {len(articles)} GEnews articles")
            return articles
            
        except Exception as e:
            self.logger.error(f"Failed to fetch GEnews: {e}")
            return []

