"""프롬프트 모듈

각 프롬프트를 별도 파일로 관리하여 수정 시 다른 프롬프트에 영향을 주지 않도록 함.

기존 코드와의 호환성을 위해 모든 프롬프트 함수를 여기서 export합니다.
"""

from config.prompts.classification_pt import get_p4_topic_classification_prompt
from config.prompts.topic_clustering import get_topic_clustering_prompt

__all__ = [
    "get_p4_topic_classification_prompt",
    "get_topic_clustering_prompt",
]
