"""Phase 3 처리 모듈: 대표 기사 선택 (Anchor)"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)

# NumPy 및 sklearn (선택적)
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("numpy not available. Some features may be limited.")

try:
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("sklearn not available. Distance calculations may be limited.")


@dataclass
class SelectedArticle:
    """선택된 대표 기사"""
    story_object_id: int  # Story Object ID
    pick_number: int  # 선택 순서 (1, 2, 3, ...) - 현재는 항상 1
    pick_role: str  # 역할 ("Anchor") - 현재는 항상 "Anchor"
    sentiment_score: float  # 감정 점수 (-1.0 ~ 1.0)
    distance_to_centroid: float  # Centroid까지의 거리
    article_data: Dict[str, Any]  # 원본 기사 데이터


class Phase3Processor:
    """Phase 3 처리 클래스: 클러스터별 대표 기사 선택"""
    
    def __init__(self):
        """Phase 3 프로세서 초기화"""
        pass
    
    def calculate_weighted_centroid(self, vectors: List[List[float]], weights: List[float]) -> np.ndarray:
        """
        Weighted Centroid 계산
        
        Args:
            vectors: 임베딩 벡터 리스트
            weights: 각 벡터의 가중치 리스트
            
        Returns:
            Weighted Centroid 벡터
        """
        if not NUMPY_AVAILABLE:
            raise ImportError("numpy가 필요합니다.")
        
        vectors_array = np.array(vectors)
        weights_array = np.array(weights)
        
        # 정규화
        weights_array = weights_array / weights_array.sum() if weights_array.sum() > 0 else weights_array
        
        # Weighted sum
        centroid = np.average(vectors_array, axis=0, weights=weights_array)
        return centroid
    
    def calculate_distances_to_centroid(self, vectors: List[List[float]], centroid: np.ndarray) -> List[float]:
        """
        Centroid까지의 거리 계산 (Cosine Distance)
        
        Args:
            vectors: 임베딩 벡터 리스트
            centroid: Centroid 벡터
            
        Returns:
            거리 리스트
        """
        if not NUMPY_AVAILABLE or not SKLEARN_AVAILABLE:
            # 간단한 유클리드 거리 계산 (fallback)
            distances = []
            for vec in vectors:
                vec_array = np.array(vec)
                dist = np.linalg.norm(vec_array - centroid)
                distances.append(float(dist))
            return distances
        
        vectors_array = np.array(vectors)
        centroid_reshaped = centroid.reshape(1, -1)
        
        # Cosine similarity 계산 (1 - similarity = distance)
        similarities = cosine_similarity(vectors_array, centroid_reshaped).flatten()
        distances = 1.0 - similarities
        
        return [float(d) for d in distances]
    

    
    def select_representative_article(self, story_objects: List[Dict[str, Any]], cluster_id: str) -> List[SelectedArticle]:
        """
        클러스터에서 대표 기사 선택 (Anchor만 선택)
        
        Args:
            story_objects: 클러스터에 속한 Story Objects (딕셔너리 리스트)
            cluster_id: 클러스터 ID
            
        Returns:
            선택된 기사 리스트 (현재는 항상 1개의 Anchor만 반환)
        """
        if not story_objects:
            logger.warning(f"⚠️  클러스터 {cluster_id}: Story Objects가 비어있습니다.")
            return []
        
        if len(story_objects) == 1:
            # 기사가 1개만 있는 경우
            obj = story_objects[0]
            article = obj.get("representative_article", {})
            title = article.get("title", "")
            snippet = article.get("snippet", "")
            text = f"{title} {snippet}".strip()
            
            return [
                SelectedArticle(
                    story_object_id=obj.get("id", 0),
                    pick_number=1,
                    pick_role="Anchor",
                    sentiment_score=0.0,  # Sentiment analysis moved to Phase 4
                    distance_to_centroid=0.0,
                    article_data=obj
                )
            ]
        
        # Embedding 벡터 추출
        vectors = [obj.get("embedding_vector", []) for obj in story_objects]
        weights = [obj.get("weight", 1) for obj in story_objects]
        
        # Embedding이 없는 경우 처리
        if not vectors[0] or len(vectors[0]) == 0:
            logger.warning(f"⚠️  클러스터 {cluster_id}: Embedding 벡터가 없습니다. 첫 번째 기사를 대표 기사로 선택.")
            obj = story_objects[0]
            return [
                SelectedArticle(
                    story_object_id=obj.get("id", 0),
                    pick_number=1,
                    pick_role="Anchor",
                    sentiment_score=0.0,
                    distance_to_centroid=0.0,
                    article_data=obj
                )
            ]
        
        # Step 1: Weighted Centroid 계산
        centroid = self.calculate_weighted_centroid(vectors, weights)
        
        # Step 2: Centroid까지의 거리 계산
        distances = self.calculate_distances_to_centroid(vectors, centroid)
        
        # Step 2.5: "Exclusive/Breaking" Boost applied to Distances
        # Representative는 distance가 가장 작은(0에 가까운) 기사가 선택됨
        # 따라서 중요 기사의 distance를 강제로 줄여서 선택 확률을 높임
        for i, obj in enumerate(story_objects):
            title = obj.get("representative_article", {}).get("title", "").lower()
            # User Request: Remove "특종" from boost, keep "단독"
            if any(keyword in title for keyword in ["exclusive", "scoop", "breaking", "단독"]):
                distances[i] *= 0.1  # 거리를 1/10로 줄여서 강력한 우선순위 부여
                logger.info(f"🚀 Boosted Representative Score for: {obj.get('representative_article', {}).get('title')}")
        
        # Representative 선택
        representative_idx = min(range(len(distances)), key=lambda i: distances[i])
        
        selected = [
            SelectedArticle(
                story_object_id=story_objects[representative_idx].get("id", 0),
                pick_number=1,
                pick_role="Anchor",
                sentiment_score=0.0, # Moved to Phase 4
                distance_to_centroid=distances[representative_idx],
                article_data=story_objects[representative_idx]
            )
        ]
        
        logger.info(f"✅ 클러스터 {cluster_id}: 대표 기사 1개 선택 완료 (Anchor)")
        return selected
    
    def process_lane(self, story_objects: List[Dict[str, Any]], lane: str) -> Dict[str, List[SelectedArticle]]:
        """
        Lane별 Phase 3 처리
        
        Args:
            story_objects: Story Objects 리스트 (딕셔너리 형태)
            lane: Lane 이름
            
        Returns:
            클러스터별 선택된 기사 딕셔너리 {cluster_id: [SelectedArticle, ...]}
        """
        if not story_objects:
            logger.warning(f"⚠️  {lane}: 처리할 Story Objects가 없습니다.")
            return {}
        
        # 클러스터별로 그룹화
        clusters = {}
        for obj in story_objects:
            cluster_id = obj.get("cluster_id")
            if not cluster_id:
                continue  # cluster_id가 없는 것은 건너뛰기
            
            if cluster_id not in clusters:
                clusters[cluster_id] = []
            clusters[cluster_id].append(obj)
        
        logger.info(f"📦 {lane}: {len(clusters)}개 클러스터 처리 시작")
        
        # 각 클러스터에서 대표 기사 선택
        selected_articles_by_cluster = {}
        for cluster_id, cluster_objects in clusters.items():
            try:
                selected_articles = self.select_representative_article(cluster_objects, cluster_id)
                if selected_articles:
                    selected_articles_by_cluster[cluster_id] = selected_articles
            except Exception as e:
                logger.error(f"❌ 클러스터 {cluster_id} 대표 기사 선택 실패: {e}", exc_info=True)
                continue
        
        total_selected = sum(len(articles) for articles in selected_articles_by_cluster.values())
        logger.info(f"✅ {lane}: {len(selected_articles_by_cluster)}개 클러스터에서 {total_selected}개 대표 기사 선택 완료")
        
        return selected_articles_by_cluster
