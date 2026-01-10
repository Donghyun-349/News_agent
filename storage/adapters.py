"""ArticleRecord와 딕셔너리 간 변환 어댑터"""

from typing import List, Dict, Any
from storage.models import ArticleRecord


def dicts_to_article_records(data: List[Dict[str, Any]]) -> List[ArticleRecord]:
    """딕셔너리 리스트를 ArticleRecord 리스트로 변환"""
    return [ArticleRecord.from_dict(item) for item in data]


def article_records_to_dicts(articles: List[ArticleRecord]) -> List[Dict[str, Any]]:
    """ArticleRecord 리스트를 딕셔너리 리스트로 변환"""
    return [article.to_dict() for article in articles]


