"""데이터 검증 유틸리티"""

import re
from typing import Dict, Any, Optional
from urllib.parse import urlparse


def is_valid_url(url: str) -> bool:
    """
    URL 형식이 유효한지 검증합니다.
    
    Args:
        url: 검증할 URL 문자열
    
    Returns:
        유효하면 True, 아니면 False
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def validate_article(article: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    기사 데이터의 필수 필드를 검증합니다.
    
    Args:
        article: 검증할 기사 딕셔너리
    
    Returns:
        (유효성 여부, 에러 메시지) 튜플
    """
    required_fields = ["title", "url", "source"]
    
    for field in required_fields:
        if field not in article:
            return False, f"Missing required field: {field}"
        
        if not article[field] or not str(article[field]).strip():
            return False, f"Empty required field: {field}"
    
    # URL 형식 검증
    if not is_valid_url(article["url"]):
        return False, f"Invalid URL format: {article['url']}"
    
    return True, None


def sanitize_text(text: str) -> str:
    """
    텍스트를 정제합니다 (앞뒤 공백 제거, 연속 공백 정리).
    
    Args:
        text: 정제할 텍스트
    
    Returns:
        정제된 텍스트
    """
    if not text:
        return ""
    
    # 앞뒤 공백 제거
    text = text.strip()
    
    # 연속된 공백을 단일 공백으로 변환
    text = re.sub(r'\s+', ' ', text)
    
    return text




















