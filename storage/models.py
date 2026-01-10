"""데이터 모델 정의"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class ArticleRecord:
    """기사 데이터 모델"""
    
    # ========== 기본 정보 ==========
    id: Optional[str] = None
    source: Optional[str] = None
    collected_at: Optional[str] = None
    published_date: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None
    
    # ========== 전처리 결과 ==========
    text_clean: Optional[str] = None
    scope: Optional[str] = None  # Global / Korea
    level: Optional[str] = None  # Macro / Market / Sector / Corporate / RealEstate / Other
    bucket: Optional[List[str]] = field(default_factory=list)  # A / B / C
    sector_tag: Optional[str] = None
    company_tag: Optional[str] = None
    article_type: Optional[str] = None
    has_explicit_tag: Optional[bool] = None
    is_scoop: Optional[bool] = None
    base_importance: Optional[float] = None
    is_important: Optional[bool] = None
    
    # ========== 추가 메타데이터 ==========
    content_category: Optional[str] = None
    source_type: Optional[str] = None  # foreign / domestic
    
    # ========== 임베딩 및 클러스터링 ==========
    embedding_vector: Optional[List[float]] = None
    cluster_id_global: Optional[str] = None  # "A1_00", "A4_01" 형식
    cluster_id_source: Optional[str] = None  # "B_WSJ_00", "B_Bloomberg_01" 형식
    
    def to_dict(self) -> Dict[str, Any]:
        """ArticleRecord를 딕셔너리로 변환"""
        result = {}
        
        # 기본 정보
        if self.id:
            result["id"] = self.id
        if self.source:
            result["source"] = self.source
        if self.collected_at:
            result["collected_at"] = self.collected_at
        if self.published_date:
            result["published_date"] = self.published_date
        if self.title:
            result["title"] = self.title
        if self.url:
            result["url"] = self.url
        if self.snippet:
            result["snippet"] = self.snippet
        
        # 전처리 결과
        if self.text_clean:
            result["text_clean"] = self.text_clean
        if self.scope:
            result["scope"] = self.scope
        if self.level:
            result["level"] = self.level
        if self.bucket is not None and len(self.bucket) > 0:
            result["bucket"] = self.bucket
        if self.sector_tag:
            result["sector_tag"] = self.sector_tag
        if self.company_tag:
            result["company_tag"] = self.company_tag
        if self.article_type:
            result["article_type"] = self.article_type
        if self.has_explicit_tag is not None:
            result["has_explicit_tag"] = self.has_explicit_tag
        if self.is_scoop is not None:
            result["is_scoop"] = self.is_scoop
        if self.base_importance is not None:
            result["base_importance"] = self.base_importance
        if self.is_important is not None:
            result["is_important"] = self.is_important
        
        # 추가 메타데이터
        if self.content_category:
            result["content_category"] = self.content_category
        if self.source_type:
            result["source_type"] = self.source_type
        
        # 임베딩 및 클러스터링
        if self.embedding_vector:
            result["embedding_vector"] = self.embedding_vector
        if self.cluster_id_global is not None:
            result["cluster_id_global"] = self.cluster_id_global
        if self.cluster_id_source is not None:
            result["cluster_id_source"] = self.cluster_id_source
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArticleRecord":
        """딕셔너리로부터 ArticleRecord 생성"""
        # "published" 키를 "published_date"로 매핑 (수집기에서 "published"로 저장됨)
        published_date = data.get("published_date") or data.get("published")
        
        return cls(
            id=data.get("id"),
            source=data.get("source"),
            collected_at=data.get("collected_at"),
            published_date=published_date,
            title=data.get("title"),
            url=data.get("url"),
            snippet=data.get("snippet"),
            text_clean=data.get("text_clean"),
            scope=data.get("scope"),
            level=data.get("level"),
            bucket=data.get("bucket", []),
            sector_tag=data.get("sector_tag"),
            company_tag=data.get("company_tag"),
            article_type=data.get("article_type"),
            has_explicit_tag=data.get("has_explicit_tag"),
            is_scoop=data.get("is_scoop"),
            base_importance=data.get("base_importance"),
            is_important=data.get("is_important"),
            content_category=data.get("content_category"),
            source_type=data.get("source_type"),
            embedding_vector=data.get("embedding_vector"),
            cluster_id_global=data.get("cluster_id_global"),
            cluster_id_source=data.get("cluster_id_source"),
        )


