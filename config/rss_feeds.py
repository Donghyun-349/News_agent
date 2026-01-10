"""RSS 피드 설정 파일
코드 변경 없이 config/config.json에서 RSS 피드를 로드합니다.
"""

from typing import Dict, List, Any, Optional
from src.utils.config_loader import config_loader

def get_rss_feeds(source_name: str) -> Optional[Dict[str, Any]]:
    """
    특정 소스의 RSS 피드 설정을 가져옵니다.
    
    Args:
        source_name: 소스 이름
    
    Returns:
        RSS 피드 설정 딕셔너리 또는 None
    """
    return config_loader.get_rss_feeds(source_name)


def get_all_rss_sources() -> List[str]:
    """
    등록된 모든 RSS 소스 이름을 반환합니다.
    
    Returns:
        소스 이름 리스트
    """
    return config_loader.get_all_rss_sources()


# 아래 함수들은 UI 통합 시 config_loader에 구현하여 JSON을 업데이트하는 방식으로 변경해야 합니다.
# 현재는 Read-Only로 동작합니다.
def add_rss_feed(source_name: str, feed_name: str, rss_url: str, 
                 use_ssl_context: bool = False) -> None:
    raise NotImplementedError("Use config.json to add feeds")


def remove_rss_feed(source_name: str, feed_name: str) -> bool:
    raise NotImplementedError("Use config.json to remove feeds")



