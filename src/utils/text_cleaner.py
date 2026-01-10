"""텍스트 정제 유틸리티"""

from typing import Optional, Tuple
import re
import logging

logger = logging.getLogger(__name__)


def normalize_press_name(press_name: str) -> str:
    """
    언론사명을 정규화합니다.
    
    Args:
        press_name: 원본 언론사명
    
    Returns:
        정규화된 언론사명
    """
    if not press_name:
        return ""
    
    # 소문자로 변환하여 비교
    press_lower = press_name.lower()
    
    # Bloomberg.com → Bloomberg
    if "bloomberg" in press_lower:
        return "Bloomberg"
    
    # Reuters → Reuters
    if "reuters" in press_lower:
        return "Reuters"
    
    # The Wall Street Journal → WSJ
    if "wall street journal" in press_lower or press_lower == "wsj":
        return "WSJ"
    
    # Financial Times → FT
    if "financial times" in press_lower or press_lower == "ft":
        return "FT"
    
    # AP News → AP
    if "ap news" in press_lower or press_lower == "ap":
        return "AP"
    
    # TechCrunch → TechCrunch
    if "techcrunch" in press_lower:
        return "TechCrunch"
    
    # 기본값: 원본 반환 (첫 글자만 대문자로 정리)
    return press_name.strip()


def clean_title_suffix(title: str, suffix_patterns: Optional[list] = None) -> Tuple[str, str]:
    """
    제목에서 소스 접미사(- Source)를 제거하고 분리합니다.
    
    Args:
        title: 원본 제목
        suffix_patterns: 특정 패턴 목록 (예: ["- Bloomberg", "- Reuters"])
    
    Returns:
        (cleaned_title, source_name) 튜플
    """
    if not title:
        return "", ""
    
    title_cleaned = title.strip()
    source_name = ""
    
    # 특정 패턴이 지정된 경우
    if suffix_patterns:
        for pattern in suffix_patterns:
            if pattern in title_cleaned:
                # 패턴으로 분리
                parts = title_cleaned.rsplit(pattern, 1)
                if len(parts) > 1:
                    title_cleaned = parts[0].strip()
                    source_name = parts[1].strip()
                    break
    
    # 일반적인 "- " 패턴으로 분리 (특정 패턴이 없는 경우)
    if not source_name and " - " in title_cleaned:
        parts = title_cleaned.rsplit(" - ", 1)
        title_cleaned = parts[0].strip()
        source_name = parts[1].strip() if len(parts) > 1 else ""
    
    return title_cleaned, source_name


def remove_bloomberg_suffix(text: str) -> str:
    """
    Bloomberg 제목 끝의 "- Bloomberg.com" 패턴을 제거합니다.
    
    Args:
        text: 정제할 텍스트
    
    Returns:
        정제된 텍스트
    """
    if not text:
        return ""
    
    text = re.sub(r'\s*-\s*Bloomberg\.?com\s*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*-\s*Bloomberg\s*$', '', text, flags=re.IGNORECASE)
    
    return text.strip()


def remove_reuters_suffix(text: str) -> str:
    """
    Reuters 제목 끝의 "- Reuters" 패턴을 제거합니다.
    
    Args:
        text: 정제할 텍스트
    
    Returns:
        정제된 텍스트
    """
    if not text:
        return ""
    
    text = re.sub(r'\s*-\s*Reuters\s*$', '', text, flags=re.IGNORECASE)
    
    return text.strip()


def remove_wsj_suffix(text: str) -> str:
    """
    WSJ 제목 끝의 "- The Wall Street Journal" 패턴을 제거합니다.
    
    Args:
        text: 정제할 텍스트
    
    Returns:
        정제된 텍스트
    """
    if not text:
        return ""
    
    text = re.sub(r'\s*-\s*The\s+Wall\s+Street\s+Journal\s*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*-\s*WSJ\s*$', '', text, flags=re.IGNORECASE)
    
    return text.strip()


def is_valid_article_title(title: str) -> bool:
    """
    기사 제목이 유효한지 확인합니다.
    
    Args:
        title: 확인할 제목
    
    Returns:
        유효하면 True, 아니면 False
    """
    if not title:
        return False
    
    title_cleaned = title.strip()
    
    # 제목이 너무 짧으면 유효하지 않음 (10자 미만)
    if len(title_cleaned) < 10:
        return False
    
    # 언론사명만 있는 경우 필터링
    invalid_patterns = [
        r'^-\s*(Bloomberg|bloomberg\.com|Reuters|reuters|The\s+Wall\s+Street\s+Journal|WSJ|Financial\s+Times|FT)\.?$',
        r'^(Bloomberg|bloomberg\.com|Reuters|reuters|The\s+Wall\s+Street\s+Journal|WSJ|Financial\s+Times|FT)\.?$',
    ]
    
    for pattern in invalid_patterns:
        if re.match(pattern, title_cleaned, re.IGNORECASE):
            return False
    
    # 카테고리명만 있는 경우 필터링
    category_keywords = [
        "Housing", "Sports", "Real Estate", "Economy", 
        "Print Edition", "Wall Street Journal", "WSJ",
        "Markets", "Business", "Politics", "Opinion",
        "Technology", "Finance", "World", "US", "UK"
    ]
    
    title_lower = title_cleaned.lower()
    for keyword in category_keywords:
        if title_lower == keyword.lower():
            return False
    
    # "Print Edition |", "WSJ |" 같은 메타 정보로 시작하는 경우 필터링
    if re.match(r'^(Print\s+Edition|WSJ|Bloomberg|Reuters|FT)\s*[|:]', title_cleaned, re.IGNORECASE):
        return False
    
    return True

