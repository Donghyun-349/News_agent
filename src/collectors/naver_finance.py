"""네이버 금융 주요뉴스 수집기"""

from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin
import time
import requests
from bs4 import BeautifulSoup
from newspaper import Article
import re

from src.collectors.base import BaseScraper
from src.utils.retry import retry_with_backoff
from config.settings import (
    REQUEST_TIMEOUT,
    MIN_ARTICLES_PER_SOURCE,
    NAVER_FINANCE_BASE_URL,
    NAVER_FINANCE_MAX_PAGES,
    NAVER_FINANCE_DELAY
)

logger = logging.getLogger(__name__)


class NaverFinanceScraper(BaseScraper):
    """네이버 금융 주요뉴스 수집기"""
    
    def __init__(self, base_url: str = None):
        """
        초기화
        
        Args:
            base_url: 기본 URL (None이면 설정에서 가져옴)
        """
        super().__init__(
            source_name="Naver Finance",
            rss_url=None  # RSS 없음
        )
        self.base_url = base_url or NAVER_FINANCE_BASE_URL
        self.target_endpoint = "https://finance.naver.com/news/mainnews.naver"
        self.max_pages = NAVER_FINANCE_MAX_PAGES
        self.delay = NAVER_FINANCE_DELAY
    
    @retry_with_backoff(
        max_attempts=3,
        initial_delay=1.0,
        exceptions=(Exception,)
    )
    def _fetch_list_page(self, page: int) -> List[Dict[str, str]]:
        """
        리스트 페이지에서 기사 링크, 제목, 요약, 언론사 정보를 추출합니다.
        
        Args:
            page: 페이지 번호 (1부터 시작)
        
        Returns:
            기사 정보 딕셔너리 리스트 (url, title_from_list, summary_from_list, press_from_list 포함)
        """
        target_url = f"{self.target_endpoint}?&page={page}"
        self.logger.info(f"Fetching Naver Finance list page {page}: {target_url}")
        
        try:
            # User-Agent 헤더 추가 (봇 차단 방지)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(target_url, timeout=REQUEST_TIMEOUT, headers=headers)
            response.raise_for_status()
            
            # 인코딩 처리 (네이버는 cp949/euc-kr을 사용할 수 있음)
            if response.encoding and ('cp949' in response.encoding.lower() or 'euc-kr' in response.encoding.lower()):
                response.encoding = 'cp949'
            else:
                response.encoding = response.apparent_encoding or 'utf-8'
            
            # BeautifulSoup에 명시적으로 인코딩 지정
            try:
                soup = BeautifulSoup(response.content, 'html.parser', from_encoding=response.encoding)
            except:
                # 인코딩 실패 시 UTF-8로 재시도
                soup = BeautifulSoup(response.text, 'html.parser')
            
            # 네이버 금융 뉴스 리스트 Selector - 여러 방법으로 찾기
            articles = []
            
            # 방법 1: ul.newsList li.block1 구조 찾기
            articles = soup.select('ul.newsList li.block1')
            if articles:
                self.logger.debug(f"Found {len(articles)} articles using ul.newsList li.block1")
            
            # 방법 2: ul.newsList 아래의 모든 li 찾기
            if not articles:
                news_list = soup.find('ul', class_='newsList')
                if news_list:
                    articles = news_list.find_all('li', recursive=False)
                    if articles:
                        self.logger.debug(f"Found {len(articles)} articles using ul.newsList > li")
            
            # 방법 3: class에 'newsList'가 포함된 ul 안의 li 찾기
            if not articles:
                list_uls = soup.find_all('ul', class_=lambda x: x and 'newsList' in str(x).lower())
                for ul in list_uls:
                    found = ul.find_all('li', recursive=False)
                    if found:
                        articles.extend(found)
                        self.logger.debug(f"Found {len(found)} articles using ul with newsList class")
            
            # 방법 4: class에 'block1'이 포함된 li 찾기
            if not articles:
                block1_items = soup.find_all('li', class_=lambda x: x and 'block1' in str(x).lower())
                if block1_items:
                    articles = block1_items
                    self.logger.debug(f"Found {len(articles)} articles using li.block1")
            
            # 방법 5: dd.articleSubject 또는 dt.articleSubject가 있는 li 찾기
            if not articles:
                article_subjects = soup.find_all(['dd', 'dt'], class_=lambda x: x and 'articleSubject' in str(x).lower())
                if article_subjects:
                    articles = [elem.find_parent('li') for elem in article_subjects if elem.find_parent('li')]
                    articles = [a for a in articles if a is not None]
                    if articles:
                        self.logger.debug(f"Found {len(articles)} articles using articleSubject")
            
            # 방법 6: 모든 li 태그 중 링크가 있는 것 찾기 (최후의 수단)
            if not articles:
                all_lis = soup.find_all('li')
                articles = [li for li in all_lis if li.find('a', href=True) and li.find('dd') or li.find('dt')]
                if articles:
                    self.logger.debug(f"Found {len(articles)} articles using fallback method")
            
            if not articles:
                self.logger.warning(f"No articles found on page {page}.")
                return []
            
            article_info_list = []
            seen_urls = set()
            
            for item in articles:
                try:
                    # 1. 제목과 링크 추출 - 여러 방법으로 시도
                    subject_tag = None
                    link = ""
                    title_from_list = ""
                    
                    # 방법 1: dd.articleSubject a
                    subject_tag = item.select_one('dd.articleSubject a')
                    if not subject_tag:
                        # 방법 2: dt.articleSubject a
                        subject_tag = item.select_one('dt.articleSubject a')
                    if not subject_tag:
                        # 방법 3: .articleSubject a (클래스만)
                        subject_tag = item.select_one('.articleSubject a')
                    if not subject_tag:
                        # 방법 4: li 안의 첫 번째 a 태그
                        subject_tag = item.find('a', href=True)
                    if not subject_tag:
                        # 방법 5: dd 또는 dt 안의 a 태그
                        dd_or_dt = item.find(['dd', 'dt'])
                        if dd_or_dt:
                            subject_tag = dd_or_dt.find('a', href=True)
                    
                    if subject_tag:
                        title_from_list = subject_tag.get_text(strip=True)
                        link = subject_tag.get('href', '')
                    
                    # 제목이 없으면 다른 방법으로 찾기
                    if not title_from_list:
                        title_elem = item.find(['h3', 'h4', 'strong', 'span'], class_=lambda x: x and ('title' in str(x).lower() or 'subject' in str(x).lower()))
                        if title_elem:
                            title_from_list = title_elem.get_text(strip=True)
                        else:
                            # li의 직접 텍스트 사용
                            title_from_list = item.get_text(strip=True)
                            # 너무 긴 경우 앞부분만 사용
                            if len(title_from_list) > 200:
                                title_from_list = title_from_list[:200]
                    
                    if not link:
                        # 링크가 없으면 li 안의 모든 a 태그 찾기
                        all_links = item.find_all('a', href=True)
                        if all_links:
                            link = all_links[0].get('href', '')
                    
                    if not link or not title_from_list:
                        continue
                    
                    # 상대 경로인 경우 절대 경로로 변환
                    if not link.startswith('http'):
                        full_url = urljoin(self.base_url, link)
                    else:
                        full_url = link
                    
                    # 중복 제거
                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)
                    
                    # 2. 요약 추출
                    summary_from_list = ""
                    summary_tag = item.select_one('dd.articleSummary')
                    if summary_tag:
                        summary_from_list = summary_tag.get_text(strip=True)
                    
                    # 3. 언론사 정보 추출
                    press_from_list = "Naver Finance"
                    press_tag = item.select_one('span.press')
                    if press_tag:
                        press_text = press_tag.get_text(strip=True)
                        if press_text:
                            press_from_list = press_text
                    
                    # 4. 발행일 추출 (리스트 페이지에서)
                    date_from_list = ""
                    # 방법 1: span.date 태그 찾기
                    date_tag = item.select_one('span.date')
                    if date_tag:
                        date_text = date_tag.get_text(strip=True)
                        if date_text:
                            date_from_list = date_text
                    # 방법 2: dd.date 또는 dt.date 찾기
                    if not date_from_list:
                        date_tag = item.select_one('dd.date, dt.date')
                        if date_tag:
                            date_text = date_tag.get_text(strip=True)
                            if date_text:
                                date_from_list = date_text
                    # 방법 3: class에 'date'가 포함된 태그 찾기
                    if not date_from_list:
                        date_tags = item.find_all(['span', 'dd', 'dt'], class_=lambda x: x and 'date' in str(x).lower())
                        if date_tags:
                            date_text = date_tags[0].get_text(strip=True)
                            if date_text:
                                date_from_list = date_text
                    # 방법 4: summary에서 날짜 추출 시도 (summary 형식: "...MBN|2025-12-20 20:14:07")
                    if not date_from_list and summary_from_list:
                        # "YYYY-MM-DD HH:MM:SS" 패턴 찾기
                        date_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', summary_from_list)
                        if date_match:
                            date_from_list = date_match.group(1)
                    
                    article_info_list.append({
                        'url': full_url,
                        'title_from_list': title_from_list,
                        'summary_from_list': summary_from_list,
                        'press_from_list': press_from_list,
                        'date_from_list': date_from_list
                    })
                    
                except Exception as e:
                    self.logger.warning(f"Failed to parse item on page {page}: {e}")
                    continue
            
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
        Newspaper3k를 사용하여 기사 본문을 추출합니다.
        제목과 요약은 리스트 페이지에서 추출한 정보를 우선 사용합니다.
        
        Args:
            article_info: 리스트 페이지에서 추출한 기사 정보 (url, title_from_list, summary_from_list, press_from_list)
        
        Returns:
            기사 딕셔너리 또는 None (실패 시)
        """
        url = article_info.get('url', '')
        title_from_list = article_info.get('title_from_list', '')
        summary_from_list = article_info.get('summary_from_list', '')
        press_from_list = article_info.get('press_from_list', 'Naver Finance')
        date_from_list = article_info.get('date_from_list', '')
        
        try:
            self.logger.debug(f"Extracting article: {url}")
            
            article = Article(url, language='ko')
            article.config.request_timeout = REQUEST_TIMEOUT
            article.download()
            article.parse()
            
            # 제목: 리스트 페이지에서 추출한 제목 우선 사용, 없으면 newspaper3k 결과 사용
            title = title_from_list if title_from_list else (article.title or "")
            
            # 요약: 리스트 페이지에서 추출한 요약 우선 사용, 없으면 본문 앞부분 사용
            summary = summary_from_list
            if not summary and article.text:
                summary = article.text[:200].strip()
            
            # 발행일: 리스트 페이지에서 추출한 날짜 우선 사용
            published = None
            if date_from_list:
                try:
                    from dateutil import parser as date_parser
                    # 네이버 날짜 형식 파싱
                    date_text = date_from_list.strip()
                    
                    # 이미 "YYYY-MM-DD HH:MM:SS" 형식인 경우
                    if re.match(r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', date_text):
                        published = date_text
                    else:
                        # 다른 형식 파싱 시도
                        # 연도가 없으면 현재 연도 추가
                        if len(date_text.split('.')) == 3 and len(date_text.split('.')[0]) == 2:
                            # "25.12.20" 형식
                            current_year = datetime.now().year
                            date_text = f"{current_year}.{date_text}"
                        elif len(date_text.split('-')) == 2 and ':' in date_text:
                            # "12-20 14:30" 형식
                            current_year = datetime.now().year
                            date_text = f"{current_year}-{date_text}"
                        
                        pub_date = date_parser.parse(date_text, fuzzy=True)
                        if pub_date.tzinfo:
                            pub_date = pub_date.astimezone(timezone.utc).replace(tzinfo=None)
                        published = pub_date.strftime("%Y-%m-%d %H:%M:%S")
                except Exception as e:
                    self.logger.debug(f"Failed to parse date from list: {date_from_list}, {e}")
            
            # 리스트 페이지 날짜가 없으면 newspaper3k 결과 사용
            if not published and article.publish_date:
                pub_date = article.publish_date
                if pub_date.tzinfo:
                    pub_date = pub_date.astimezone(timezone.utc).replace(tzinfo=None)
                published = pub_date.strftime("%Y-%m-%d %H:%M:%S")
            
            # 발행일이 없으면 현재 시간 사용 (시간 필터링을 통과시키기 위해)
            if not published:
                published = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            
            article_data = {
                "title": title,
                "summary": summary,
                "url": url,
                "published": published,
                # source는 fetch_news에서 _add_source 호출 후 언론사 정보 포함하여 설정
            }
            
            # 날짜 필터링: 시간 제한 이내의 기사만 수집
            if not self._is_within_time_limit(published):
                return None
            
            # 속도 조절
            time.sleep(self.delay)
            
            return article_data
            
        except Exception as e:
            self.logger.warning(f"Failed to extract article {url}: {e}")
            return None
    
    def fetch_news(self) -> List[Dict[str, Any]]:
        """
        네이버 금융 주요뉴스를 수집합니다.
        
        Returns:
            기사 딕셔너리 리스트
        """
        try:
            all_article_info = []
            
            # 1. 리스트 페이지에서 기사 정보 수집 (1~max_pages 페이지)
            for page in range(1, self.max_pages + 1):
                try:
                    article_info_list = self._fetch_list_page(page)
                    self.logger.info(f"Page {page}: Found {len(article_info_list)} article URLs")
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
                    
                    # 소스는 언론사명만 사용
                    press_from_list = article_info.get('press_from_list', '')
                    if press_from_list:
                        article_data["source"] = press_from_list
                    else:
                        article_data["source"] = "Naver Finance"
                    
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
                    f"Naver Finance: Only collected {len(articles)} articles "
                    f"(target: {MIN_ARTICLES_PER_SOURCE}+)."
                )
            
            self.logger.info(f"✅ Collected {len(articles)} Naver Finance articles")
            return articles
            
        except Exception as e:
            self.logger.error(f"Failed to fetch Naver Finance: {e}")
            return []

