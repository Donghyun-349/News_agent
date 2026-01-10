"""날짜 파싱 유틸리티"""

from typing import Optional
from datetime import datetime
import dateutil.parser


def parse_rss_date(date_str: Optional[str]) -> Optional[str]:
    """
    RSS 날짜 문자열을 표준 형식으로 변환
    
    Args:
        date_str: RSS 날짜 문자열
    
    Returns:
        표준 형식 날짜 문자열 (YYYY-MM-DD HH:MM:SS) 또는 None
    """
    if not date_str:
        return None
    
    try:
        # dateutil로 파싱 (타임존 정보 포함)
        dt = dateutil.parser.parse(date_str)
        
        # UTC로 변환
        if dt.tzinfo:
            dt = dt.astimezone(dateutil.tz.tzutc())
        
        # 표준 형식으로 반환
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None
