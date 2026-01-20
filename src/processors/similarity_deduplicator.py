import logging
import re
from difflib import SequenceMatcher
from typing import List, Dict, Any, Set
from collections import defaultdict
from config.source_hierarchy import get_source_tier

logger = logging.getLogger(__name__)

class SimilarityDeduplicator:
    """
    Phase 5용 유사 기사 제거 프로세서 (In-Memory)
    
    기준:
    1. Reason의 Key Subject가 동일한 경우
    2. Title 유사도가 50% 이상인 경우
    
    선택 로직:
    - Source Tier가 가장 높은(숫자가 낮은) 기사 1개
    - (옵션) 제목이 가장 긴 기사 1개 추가 (정보 보존용)
    """

    def __init__(self, similarity_threshold: float = 0.5):
        self.similarity_threshold = similarity_threshold

    def extract_reason_subject(self, reason: str) -> str:
        """Reason에서 [Subject] 추출 (예: '[Samsung] Earnigns...' -> 'Samsung')"""
        if not reason:
            return ""
        match = re.match(r"^\[(.*?)\]", reason)
        if match:
            return match.group(1).strip().lower()
        return ""

    def calculate_similarity(self, title1: str, title2: str) -> float:
        """두 제목의 유사도 계산 (0.0 ~ 1.0)"""
        if not title1 or not title2:
            return 0.0
        return SequenceMatcher(None, title1, title2).ratio()

    def find_groups(self, articles: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """기사들을 유사 그룹으로 묶음"""
        # Union-Find 초기화
        parent = {i: i for i in range(len(articles))}
        
        def find(i):
            if parent[i] != i:
                parent[i] = find(parent[i])
            return parent[i]
        
        def union(i, j):
            root_i = find(i)
            root_j = find(j)
            if root_i != root_j:
                parent[root_j] = root_i

        n = len(articles)
        
        # 1. Reason Subject 기반 1차 그룹핑 (속도 최적화용)
        # 같은 Subject를 가진 것들끼리만 정밀 비교하면 됨.
        # 하지만 Subject가 달라도 Title이 비슷할 수 있으므로(오타 등), 
        # N^2 비교는 너무 느리니 Subject Bucketing을 활용하되, Subject가 없으면 전체 비교?
        # 기사 수가 많지 않으므로(수백개) N^2도 가능.
        
        # 전체 N^2 비교 수행 (안전하게)
        for i in range(n):
            for j in range(i + 1, n):
                art_a = articles[i]
                art_b = articles[j]
                
                # Check 1: Reason Subject Identity
                subj_a = self.extract_reason_subject(art_a.get('reason', ''))
                subj_b = self.extract_reason_subject(art_b.get('reason', ''))
                
                is_same_subject = (subj_a and subj_b and subj_a == subj_b)
                
                # Check 2: Title Similarity
                sim_score = self.calculate_similarity(art_a.get('title', ''), art_b.get('title', ''))
                is_similar_title = sim_score >= self.similarity_threshold
                
                if is_same_subject or is_similar_title:
                    union(i, j)
        
        # 그룹 형성
        groups = defaultdict(list)
        for i in range(n):
            root = find(i)
            groups[root].append(articles[i])
            
        return list(groups.values())

    def select_representatives(self, group: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """그룹 내에서 대표 기사 1~2개 선정"""
        if not group:
            return []
        
        if len(group) == 1:
            return group

        # 정렬: Source Tier (오름차순: 1이 좋음) -> Title Length (내림차순: 긴게 좋음)
        # get_source_tier는 외부 함수 사용
        
        # 1. Primary Pick: Best Source
        sorted_by_tier = sorted(
            group, 
            key=lambda x: (get_source_tier(x.get('source')), -len(x.get('title', '')))
        )
        primary = sorted_by_tier[0]
        
        # 2. Secondary Pick: Longest Title (that is not primary)
        # 정보 보강을 위해 제목이 가장 긴 것을 추가 (단, Primary보다 훨씬 길거나 다른 내용일 수 있으므로)
        sorted_by_len = sorted(
            group,
            key=lambda x: -len(x.get('title', ''))
        )
        
        secondary = None
        for cand in sorted_by_len:
            if cand['id'] != primary['id']:
                secondary = cand
                break
        
        result = [primary]
        if secondary:
            # 옵션: 제목 길이 차이가 별로 없으면 굳이 추가 안해도 됨?
            # 사용자 요청: "가장 제목이 긴 가사 1개 정도 남기고"
            # 무조건 추가.
            result.append(secondary)
            
        return result

    def run(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """실행 진입점"""
        logger.info(f"dedup: Input {len(articles)} articles for similarity check.")
        
        groups = self.find_groups(articles)
        
        final_list = []
        dropped_count = 0
        
        for grp in groups:
            selected = self.select_representatives(grp)
            final_list.extend(selected)
            dropped_count += (len(grp) - len(selected))
            
            if len(grp) > 2:
                # 로깅용 (많이 묶인 경우만)
                titles = [a.get('title') for a in grp]
                logger.debug(f"ℹ️ Grouped {len(grp)} articles -> Kept {len(selected)}. Titles: {titles[:3]}...")
        
        logger.info(f"dedup: Removed {dropped_count} redundant articles. Remaining: {len(final_list)}")
        
        return {
            "articles": final_list,
            "removed_count": dropped_count
        }
