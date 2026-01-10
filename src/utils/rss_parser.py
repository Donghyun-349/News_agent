"""RSS 피드 파싱 유틸리티"""

from typing import Optional
import feedparser
import socket
import logging
import ssl
import urllib.request

logger = logging.getLogger(__name__)


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"


def parse_rss_feed(rss_url: str, timeout: int = 30, use_ssl_context: bool = False) -> Optional[feedparser.FeedParserDict]:
    """
    RSS 피드를 파싱합니다.
    
    Args:
        rss_url: RSS 피드 URL
        timeout: 타임아웃 (초)
        use_ssl_context: SSL 검증 우회 여부 (FT 등 일부 사이트에서 필요)
    
    Returns:
        feedparser.FeedParserDict 객체 또는 None (실패 시)
    """
    try:
        if use_ssl_context:
            # SSL 검증 우회 (FT의 경우 SSL 인증서 문제가 있을 수 있음)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # urllib를 사용하여 RSS 다운로드 후 feedparser로 파싱
            try:
                headers = {'User-Agent': USER_AGENT}
                req = urllib.request.Request(rss_url, headers=headers)
                with urllib.request.urlopen(req, context=ssl_context, timeout=timeout) as response:
                    rss_content = response.read().decode('utf-8')
                feed = feedparser.parse(rss_content)
            except Exception as e:
                logger.warning(f"SSL context method failed for {rss_url}: {e}. Trying fallback...")
                # 폴백: 일반 feedparser 사용 (request_headers 사용)
                feed = feedparser.parse(rss_url, request_headers={'User-Agent': USER_AGENT})
        else:
            # 일반적인 방식: socket 타임아웃 설정 후 feedparser 사용
            try:
                socket.setdefaulttimeout(timeout)
                # User-Agent 설정
                feed = feedparser.parse(rss_url, request_headers={'User-Agent': USER_AGENT})
                
                # feedparser가 에러를 bozo_exception으로 잡는 경우 (예: 10054)
                if feed.bozo and feed.bozo_exception:
                    exception_str = str(feed.bozo_exception)
                    if "10054" in exception_str or "Connection reset" in exception_str:
                         logger.warning(f"Connection reset detected for {rss_url}. Trying urllib fallback...")
                         # Fallback: urllib 직접 사용
                         headers = {'User-Agent': USER_AGENT}
                         req = urllib.request.Request(rss_url, headers=headers)
                         # 여기서는 기본 SSL context 사용 (검증 함)
                         with urllib.request.urlopen(req, timeout=timeout) as response:
                             rss_content = response.read().decode('utf-8')
                         feed = feedparser.parse(rss_content)
                         
            except Exception as e:
                logger.error(f"Failed to fetch RSS feed {rss_url} (timeout: {timeout}s): {e}")
                return None
            finally:
                socket.setdefaulttimeout(None)  # 타임아웃 초기화
        
        # bozo 체크 (RSS 파싱 경고)
        if feed.bozo and feed.bozo_exception:
            logger.warning(f"RSS parsing warning for {rss_url}: {feed.bozo_exception}")
        
        return feed
        
    except Exception as e:
        logger.error(f"Error parsing RSS feed {rss_url}: {e}")
        return None














