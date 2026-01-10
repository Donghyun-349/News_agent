"""Parquet 파일 저장/로드 핸들러"""

from typing import List, Optional
from pathlib import Path
import pandas as pd
import logging

from storage.models import ArticleRecord
from storage.adapters import article_records_to_dicts, dicts_to_article_records

logger = logging.getLogger(__name__)


def save_to_parquet(articles: List[ArticleRecord], filepath: str) -> None:
    """
    ArticleRecord 리스트를 Parquet 파일로 저장
    
    Args:
        articles: 저장할 ArticleRecord 리스트
        filepath: 저장할 파일 경로
    """
    if not articles:
        logger.warning("No articles to save")
        return
    
    # ArticleRecord를 딕셔너리로 변환
    data = article_records_to_dicts(articles)
    
    # DataFrame 생성
    df = pd.DataFrame(data)
    
    # Parquet 저장
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(filepath, index=False, engine='pyarrow')
    
    logger.info(f"✅ Saved {len(articles)} articles to {filepath}")


def load_from_parquet(filepath: str) -> List[ArticleRecord]:
    """
    Parquet 파일에서 ArticleRecord 리스트 로드
    
    Args:
        filepath: 로드할 파일 경로
    
    Returns:
        ArticleRecord 리스트
    """
    if not Path(filepath).exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    # Parquet 파일 읽기
    df = pd.read_parquet(filepath, engine='pyarrow')
    
    # 딕셔너리 리스트로 변환
    data = df.to_dict('records')
    
    # ArticleRecord 리스트로 변환
    articles = dicts_to_article_records(data)
    
    logger.info(f"✅ Loaded {len(articles)} articles from {filepath}")
    
    return articles


def get_parquet_filename(prefix: str, date_str: Optional[str] = None) -> str:
    """
    Parquet 파일명 생성
    
    Args:
        prefix: 파일명 접두사 (예: "labeled", "embedded")
        date_str: 날짜 문자열 (YYYYMMDD), None이면 오늘 날짜 사용
    
    Returns:
        파일명
    """
    from datetime import datetime
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
    return f"{prefix}_{date_str}.parquet"


def list_parquet_files(directory: str, pattern: str = "*.parquet") -> List[str]:
    """
    디렉토리에서 Parquet 파일 목록 반환
    
    Args:
        directory: 디렉토리 경로
        pattern: 파일 패턴
    
    Returns:
        파일 경로 리스트
    """
    path = Path(directory)
    if not path.exists():
        return []
    
    files = list(path.glob(pattern))
    return [str(f) for f in sorted(files)]


