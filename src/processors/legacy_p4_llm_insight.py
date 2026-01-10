"""Phase 4 처리 모듈: Taxonomy Classification & Insight Report Generation"""

import os
import json
import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

# LLM
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI not available. Taxonomy classification will be disabled.")

logger = logging.getLogger(__name__)

@dataclass
class InsightReport:
    """Insight Report 객체"""
    cluster_id: str
    taxonomy_code: str
    lane: str
    representative_article_id: int
    representative_article_title: str
    selected_article_ids: List[int]
    status: str = "ACTIVE" # ACTIVE or DELETE
    linked_article_titles: List[str] = field(default_factory=list) # Linked Articles Titles
    merged_cluster_ids: List[str] = field(default_factory=list)
    generated_insight: str = "" # LLM이 생성한 짧은 요약 (선택적)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

class Phase4Processor:
    """Phase 4 처리 클래스: LLM Taxonomy Classification"""

    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Phase 4 프로세서 초기화
        
        Args:
            openai_api_key: OpenAI API 키
        """
        self.openai_client = None
        if OPENAI_AVAILABLE:
            if openai_api_key:
                self.openai_client = OpenAI(api_key=openai_api_key)
            else:
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    self.openai_client = OpenAI(api_key=api_key)
                
        if not self.openai_client:
            logger.warning("⚠️ OpenAI Client not initialized. Features will be limited.")

    def get_taxonomy_prompt(self, lane: str, articles_text: str) -> str:
        """
        Lane별 Taxonomy 분류 프롬프트 생성
        """
        base_prompt = """
You are a financial news analyst. Your task is to classify a group of news articles into a specific Taxonomy Code based on the provided articles.

## Taxonomy Rules

IMPORTANT: If the articles do NOT clearly fit into any of the specific categories below, return `DELETE` as the taxonomy code.

"""
        if lane == "Lane A": # 한국 경제
            base_prompt += """
**Lane A (Korea Economy)**
- `Korea_Economy`: KRW/USD, BOK (Bank of Korea), Export/Import, Inflation (Korea), GDP
- `Korea_Market`: KOSPI, KOSDAQ, Regulations, Short Selling, IPO (Korea)
- `Korea_Ind`: Samsung Electronics, SK Hynix, Hyundai Motors, Korean Chaebols, Specific Industry News
- `Global_Tech`: (Exception) If the articles are purely about US Big Tech (Nvidia, Tesla, Apple) with NO significant Korean context, use this.
"""
        elif lane == "Lane B": # 부동산
            base_prompt += """
**Lane B (Real Estate)**
- `Real_Global`: US Housing Market, Mortgage Rates (US), REITs, Commercial Real Estate (Global)
- `Real_Korea`: Korean Apartment Prices, Jeonse, Project Financing (PF) Crisis, Construction Policy
"""
        elif lane == "Lane C": # 글로벌/기술
            base_prompt += """
**Lane C (Global/Tech)**
- `Global_Macro`: Fed (FOMC), Interest Rates (US), Inflation (US), Unemployment, Oil, Gold, War
- `Global_Market`: S&P 500, Nasdaq, Dow Jones, VIX, Wall Street Trends
- `Global_Tech`: AI, Semiconductors, Cloud, Robotics, Big Tech News (Earnings, Products, Innovation - e.g., Tesla FSD, Nvidia Chips, Apple)
- `Global_Crypto`: Bitcoin, Ethereum, Blockchain Regulation
(Note: If the news is heavily focused on Korea, change prefix to `Korea_` but prefer keeping it `Global_` for Lane C)
"""
        else:
            base_prompt += """
**General Classification**
- Classify into the most appropriate category: `Economy`, `Market`, `Tech`, `Politics`, `Society`
"""

        base_prompt += """
## Input Articles
"""
        base_prompt += articles_text
        
        base_prompt += """
## Output Format
Return ONLY a JSON object in the following format:
```json
{
    "taxonomy_code": "CODE_HERE",
    "reason": "Brief reason for classification in Korean (한국어로 작성)"
}
```
"""
        return base_prompt

    def generate_insight_reports(self, selected_articles_by_cluster: Dict[str, List[Dict[str, Any]]], lane: str) -> List[InsightReport]:
        """
        클러스터별 Insight Report 생성 (LLM 이용)
        
        Args:
            selected_articles_by_cluster: {cluster_id: [selected_article_dict, ...]}
            lane: Lane 이름
            
        Returns:
            InsightReport 객체 리스트
        """
        reports = []
        
        if not self.openai_client:
            logger.error("OpenAI Client unavailable. Cannot generate taxonomy.")
            return []

        logger.info(f"🚀 [{lane}] Generating Insight Reports for {len(selected_articles_by_cluster)} clusters...")

        for cluster_id, articles in selected_articles_by_cluster.items():
            if not articles:
                continue
            
            # Anchor 기사 찾기 (pick_number=1 or pick_role="Anchor")
            anchor = next((a for a in articles if a.get('pick_number') == 1), articles[0])
            
            # LLM 입력 텍스트 구성 (Top 3 기사만 사용)
            articles_text = ""
            selected_ids = []
            selected_titles = [] # Linked Article Titles
            
            # 정렬: pick_number 순
            sorted_articles = sorted(articles, key=lambda x: x.get('pick_number', 999))
            
            for i, article in enumerate(sorted_articles):
                # LLM에는 상위 3개만, Title 리스트에는 전부 포함
                title = article.get('title', '')
                snippet = article.get('snippet', '')
                
                if i < 3:
                     articles_text += f"[Article {i+1}]\nTitle: {title}\nSummary: {snippet}\n\n"
                
                if article.get('id'):
                    selected_ids.append(article['id'])
                
                # Title 수집 (ID와 순서 맞춤) - Representative Article 중복 방지
                # Anchor 기사와 ID나 Title이 같으면 Linked List에 추가하지 않음
                is_anchor = (article.get('id') == anchor.get('id')) or (title == anchor.get('title', ''))
                if title and not is_anchor:
                    selected_titles.append(f"[{article.get('id')}] {title}")
            
            # LLM 호출
            prompt = self.get_taxonomy_prompt(lane, articles_text)
            
            taxonomy_code = "Unclassified"
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant for financial news classification."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=150
                )
                content = response.choices[0].message.content.strip()
                
                # JSON 파싱
                json_match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\]|\{[\s\S]*?\})\s*```', content)
                if json_match:
                    json_str = json_match.group(1)
                    data = json.loads(json_str)
                    taxonomy_code = data.get("taxonomy_code", "Unclassified")
                else:
                    # JSON 블록이 없는 경우 시도
                    try:
                        data = json.loads(content)
                        taxonomy_code = data.get("taxonomy_code", "Unclassified")
                    except:
                        logger.warning(f"Failed to parse JSON for cluster {cluster_id}. Raw: {content}")
                        taxonomy_code = "Unclassified"

            except Exception as e:
                logger.error(f"LLM Call failed for cluster {cluster_id}: {e}")
            
            # Filtering Logic: Soft Delete
            # 사용자가 정의한 'DELETE' 코드이거나, 기존의 비관련 카테고리인 경우 Status를 DELETE로 설정
            status = "ACTIVE"
            
            # [VIP Protection]
            # Important Keywords that MUST NEVER be deleted
            # User Request: Keep "Exclusive", "Scoop", "Breaking", "단독". Remove "특종", "속보".
            vip_keywords = ["exclusive", "scoop", "breaking", "단독"]
            rep_title_lower = anchor.get('title', '').lower()
            is_vip = any(k in rep_title_lower for k in vip_keywords)
            
            if taxonomy_code == "DELETE" or taxonomy_code in ["Politics", "Society", "Unclassified", "General"]:
                if is_vip:
                    # VIP 기사는 삭제 방지 & 강제 분류
                    status = "ACTIVE"
                    if taxonomy_code == "DELETE" or taxonomy_code == "Unclassified":
                        # 적절한 코드로 강제 변환 (Lane에 따라)
                        if lane == "Lane C" or lane == "Lane B":
                            taxonomy_code = "Global_Issue"  # Global 중요 이슈로 분류
                        else:
                            taxonomy_code = "Korea_Issue"
                    logger.info(f"🛡️ VIP Protection Applied: {anchor.get('title')} (Code: {taxonomy_code})")
                else:
                    status = "DELETE"
                    # 명시적으로 코드를 DELETE로 통일 (사용자 요청: "taxonomy code를 delete로 설정")
                    taxonomy_code = "DELETE" 

            # InsightReport 생성
            report = InsightReport(
                cluster_id=cluster_id,
                taxonomy_code=taxonomy_code,
                status=status,
                lane=lane,
                representative_article_id=anchor.get('story_object_id') or 0, # 주의: story_object_id를 가리킴
                representative_article_title=anchor.get('title', ''),
                selected_article_ids=selected_ids,
                linked_article_titles=selected_titles
            )
            reports.append(report)
            
        return reports
