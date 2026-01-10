"""LLM 프롬프트 템플릿 모듈 (레거시 호환성)

⚠️ 이 파일은 레거시 호환성을 위해 유지됩니다.
새로운 프롬프트는 config/prompts/ 디렉토리의 별도 파일에서 관리됩니다.

프롬프트 파일 구조:
- config/prompts/phase4_insight.py - Phase 4 Taxonomy 분류 및 필터링 프롬프트 (통합)
"""

# 기존 코드와의 호환성을 위해 prompts 서브모듈에서 import
from config.prompts import (
    get_p4_topic_classification_prompt,
    get_topic_consolidator_prompt,
    get_topic_clustering_prompt,
)

__all__ = [
    "get_p4_topic_classification_prompt",
    "get_topic_consolidator_prompt",
    "get_topic_clustering_prompt",
]
