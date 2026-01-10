"""프로젝트 설정 파일"""

import os
from pathlib import Path

# .env 파일 로드 (config/__init__.py에서 이미 로드되지만, 직접 import하는 경우를 대비)
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass  # python-dotenv가 없어도 환경 변수는 작동함

# 프로젝트 루트 디렉토리
BASE_DIR = Path(__file__).parent.parent

# 로깅 설정
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# 네트워크 설정
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "20"))  # 30초 → 20초로 최적화
MIN_ARTICLES_PER_SOURCE = int(os.getenv("MIN_ARTICLES_PER_SOURCE", "30"))
RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "0.5"))  # 1.0초 → 0.5초로 최적화
COLLECTION_TIME_LIMIT_HOURS = int(os.getenv("COLLECTION_TIME_LIMIT_HOURS", "24"))
COLLECTION_MAX_WORKERS = int(os.getenv("COLLECTION_MAX_WORKERS", "0"))  # 0이면 자동 계산

# Newspaper3k 설정 (누락된 설정 추가)
ENABLE_NEWSPAPER3K = os.getenv("ENABLE_NEWSPAPER3K", "true").lower() == "true"
NEWSPAPER3K_TIMEOUT = int(os.getenv("NEWSPAPER3K_TIMEOUT", "10"))

# LLM 설정 (누락된 설정 추가)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash")

# 데이터 저장 설정
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = BASE_DIR / "backup"
RESET_MODE = os.getenv("RESET_MODE", "true").lower() == "true"
ENABLE_ACCUMULATION = os.getenv("ENABLE_ACCUMULATION", "false").lower() == "true"
DAYS_TO_KEEP = int(os.getenv("DAYS_TO_KEEP", "30"))


# Google Sheets 설정
GOOGLE_SERVICE_ACCOUNT_PATH = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_PATH",
    str(BASE_DIR / "credentials" / "service_account.json")
)
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1XA0G4Po7hCR81IyibTRgzguD4hyB36rHJSVgDRCW-pg")
GOOGLE_WORKSHEET_NAME = os.getenv("GOOGLE_WORKSHEET_NAME", "Sheet1")
ENABLE_GOOGLE_SHEETS = os.getenv("ENABLE_GOOGLE_SHEETS", "true").lower() == "true"
ENABLE_DEBUG_OUTPUT = os.getenv("ENABLE_DEBUG_OUTPUT", "true").lower() == "true"  # 개발 중 기본값: 활성화

# 주요 해외 뉴스 수집 제한
MAJOR_FOREIGN_NEWS_TARGET_COUNT = int(os.getenv("MAJOR_FOREIGN_NEWS_TARGET_COUNT", "50"))
BIG_TECH_TARGET_COUNT = int(os.getenv("BIG_TECH_TARGET_COUNT", "30"))

# 미국 부동산 뉴스 설정
US_REAL_ESTATE_TARGET_COUNT = int(os.getenv("US_REAL_ESTATE_TARGET_COUNT", "40"))
US_REAL_ESTATE_MAX_WORKERS = int(os.getenv("US_REAL_ESTATE_MAX_WORKERS", "5"))

# 네이버 파이낸스 설정
NAVER_FINANCE_BASE_URL = os.getenv("NAVER_FINANCE_BASE_URL", "https://finance.naver.com")
NAVER_FINANCE_MAX_PAGES = int(os.getenv("NAVER_FINANCE_MAX_PAGES", "3"))
NAVER_FINANCE_DELAY = float(os.getenv("NAVER_FINANCE_DELAY", "1.0"))

# GEnews 설정
GENEWS_BASE_URL = os.getenv("GENEWS_BASE_URL", "https://www.g-enews.com")
GENEWS_MAX_PAGES = int(os.getenv("GENEWS_MAX_PAGES", "3"))
GENEWS_DELAY = float(os.getenv("GENEWS_DELAY", "1.0"))

# Homenews 설정
HOMENEWS_BASE_URL = os.getenv("HOMENEWS_BASE_URL", "https://www.homenews.co.kr")
HOMENEWS_MAX_PAGES = int(os.getenv("HOMENEWS_MAX_PAGES", "3"))
HOMENEWS_DELAY = float(os.getenv("HOMENEWS_DELAY", "1.0"))
HOMENEWS_MAX_WORKERS = int(os.getenv("HOMENEWS_MAX_WORKERS", "5"))

# RSS URL 설정 (선택적)
WSJ_GOOGLE_NEWS_URL = os.getenv("WSJ_GOOGLE_NEWS_URL", "https://news.google.com/rss/search?q=site:wsj.com")
FT_RSS_URL = os.getenv("FT_RSS_URL", "https://www.ft.com/?format=rss")
FT_MARKETS_RSS_URL = os.getenv("FT_MARKETS_RSS_URL", "https://www.ft.com/markets?format=rss")
FT_COMPANIES_RSS_URL = os.getenv("FT_COMPANIES_RSS_URL", "https://www.ft.com/companies?format=rss")
BLOOMBERG_GOOGLE_NEWS_URL = os.getenv("BLOOMBERG_GOOGLE_NEWS_URL", "https://news.google.com/rss/search?q=site:bloomberg.com")

# 데이터베이스 설정
DB_TYPE = os.getenv("DB_TYPE", "sqlite")  # "postgresql", "mysql", or "sqlite" (기본값: sqlite)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432" if DB_TYPE == "postgresql" else "3306"))
DB_NAME = os.getenv("DB_NAME", "news_db" if DB_TYPE != "sqlite" else str(BASE_DIR / "data" / "news.db"))
DB_USER = os.getenv("DB_USER", "postgres" if DB_TYPE == "postgresql" else "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING", "")  # 전체 연결 문자열 (선택적)
