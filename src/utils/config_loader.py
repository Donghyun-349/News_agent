
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import BASE_DIR

logger = logging.getLogger(__name__)

class ConfigLoader:
    """
    동적 설정 파일(config.json)을 로드하고 관리하는 싱글톤 클래스.
    설정 파일이 없거나 오류가 발생하면 기본값을 사용하거나 비워둡니다.
    """
    _instance = None
    _config = {}
    _loaded = False
    
    CONFIG_PATH = BASE_DIR / "config" / "config.json"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance

    def load(self, force_reload: bool = False):
        """설정 파일을 로드합니다."""
        if self._loaded and not force_reload:
            return

        try:
            if not self.CONFIG_PATH.exists():
                logger.warning(f"⚠️ Config file not found at {self.CONFIG_PATH}. Using empty config.")
                self._config = {}
                return

            with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            
            self._loaded = True
            logger.info(f"✅ Loaded configuration from {self.CONFIG_PATH}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load configuration: {e}")
            self._config = {}

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Global Settings 값을 가져옵니다."""
        if not self._loaded:
            self.load()
        return self._config.get("settings", {}).get(key, default)

    def get_rss_feeds(self, source_name: str) -> Optional[Dict[str, Any]]:
        """특정 소스의 RSS 피드 설정을 가져옵니다."""
        if not self._loaded:
            self.load()
        return self._config.get("rss_feeds", {}).get(source_name)
    
    def get_all_rss_sources(self) -> list:
        """모든 RSS 소스 목록을 가져옵니다."""
        if not self._loaded:
            self.load()
        return list(self._config.get("rss_feeds", {}).keys())

    def get_queries(self, source_name: str) -> Optional[Dict[str, Any]]:
        """특정 소스의 검색 쿼리 설정을 가져옵니다."""
        if not self._loaded:
            self.load()
        return self._config.get("search_queries", {}).get(source_name)

# 전역 인스턴스
config_loader = ConfigLoader()
