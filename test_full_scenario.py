import unittest
import sys
import os
import re
import html
from typing import List, Dict

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.processors.similarity_deduplicator import SimilarityDeduplicator

# --- Logic Simulation ---

# 1. Cleaning Logic (from TitleDeduplicator)
def clean_title(title: str) -> str:
    return html.unescape(title).strip()

# 2. Filtering Logic (from run_p3.py)
# Copied Patterns for safety
TITLE_DROP_PATTERNS = [
    r"^\[(포토|속보|개장|마감|1보|2보|3보|상보|부고|인사|동정|행사|알림|모집)\]"
]

def check_drop(title: str) -> bool:
    for pattern in TITLE_DROP_PATTERNS:
        if re.search(pattern, title):
            return True
    return False

# --- Test Case ---

class TestFullScenario(unittest.TestCase):
    def setUp(self):
        self.deduplicator = SimilarityDeduplicator(similarity_threshold=0.5)
        
        # Raw Data from User Images
        self.raw_articles = [
            # Case 1: Exchange Rate (Image 1)
            {"id": 101, "source": "Infomax", "title": "골드만 &quot;국민연금 환헤지 500억불까지 늘 수도&quot;", "reason": "[FX] Pension Fund Hedge"},
            {"id": 102, "source": "조선일보", "title": "[단독] GDP 대비 외환보유액 비율, 대만 73%인데 한국 20%대", "reason": "[FX] Forex Reserves"},
            {"id": 103, "source": "Infomax", "title": "달러-원, 1,470원대 유지...美휴장에 달러인덱스 하락", "reason": "[FX] Dollar-Won Rate"},
            {"id": 104, "source": "Infomax", "title": "달러-원, 런던장서 소폭 반등...美휴장에 상승폭은 제한", "reason": "[FX] Dollar-Won Rate"},
            {"id": 105, "source": "Infomax", "title": "달러-원 환율, 장중 1470원 등락... 외인 매수", "reason": "[FX] Dollar-Won Fluctuation"},

            # Case 2: KOSPI (Image 2)
            {"id": 201, "source": "한국경제", "title": "[포토] 코스피 사상 첫 4,900선...장중 4,917.37", "reason": "[Market] KOSPI Record"},
            {"id": 202, "source": "한국경제", "title": "[포토] '오천피' 눈앞...코스피 사상 첫 4900 돌파", "reason": "[Market] KOSPI Surge"},
            {"id": 203, "source": "동아일보", "title": "코스피 '하이킥' 4900도 뚫었다", "reason": "[Market] KOSPI High"},
            {"id": 204, "source": "머니S", "title": "새해 질주 코스피, 2주 만에 690포인트↑... '오천피' 1% 남았다", "reason": "[Market] KOSPI Rally"},
            {"id": 205, "source": "Infomax", "title": "[증시-마감] 4,900도 넘긴 코스피...랠리 주역 로봇·최고가 버티는 반도체", "reason": "[Market] KOSPI Close"},
            {"id": 206, "source": "Infomax", "title": "코스피, 하루 만에 4,900도 뚫었다...1.24% 오른 4,900.77", "reason": "[Market] KOSPI Break"},
            {"id": 207, "source": "조선일보", "title": "코스피 5000 눈앞인데 네이버·카카오는 뒷걸음...‘국가 대표 IT’의 긴 부진", "reason": "[Market] KOSPI Analysis"}
        ]

    def test_pipeline(self):
        print("\n" + "="*60)
        print("[Step 1] HTML Entity Cleaning")
        cleaned_articles = []
        for a in self.raw_articles:
            old = a['title']
            new = clean_title(old)
            a['title'] = new  # Update
            cleaned_articles.append(a)
            if old != new:
                print(f"  Fixed: {old}  ->  {new}")
        
        print("\n[Step 2] Filtering (Deleting Noise)")
        filtered_articles = []
        dropped_count = 0
        for a in cleaned_articles:
            if check_drop(a['title']):
                print(f"  DROP: {a['title']}")
                dropped_count += 1
            else:
                filtered_articles.append(a)
        print(f"  -> Deleted {dropped_count} articles. Remaining: {len(filtered_articles)}")

        print("\n[Step 3] Similarity Deduplication")
        dedup_result = self.deduplicator.run(filtered_articles)
        final_articles = dedup_result["articles"]
        
        print("\n" + "="*60)
        print("Final Result (After Pipeline):")
        for a in final_articles:
            print(f"  * [{a['source']}] {a['title']}")
            
        # Assertions
        
        # 1. Clean Check
        self.assertTrue(any('"' in a['title'] for a in final_articles if '골드만' in a['title']))
        
        # 2. Filter Check
        self.assertFalse(any('[포토]' in a['title'] for a in final_articles))
        self.assertTrue(any('[단독]' in a['title'] for a in final_articles)) # 단독은 유지
        self.assertFalse(any('[증시-마감]' in a['title'] for a in final_articles)) # 마감은 TITLE_DROP_PATTERNS에 추가했으므로 삭제되어야 함
        
        # 3. Dedup Check
        # KOSPI 관련 기사는 내용이 거의 같으므로 (4900 돌파) 1~2개로 압축되어야 함
        # 현재: 동아, 머니S, Infomax(코스피 하루만에..), 조선일보(네이버 카카오..)
        
        # Check KOSPI count
        kospi_arts = [a for a in final_articles if "코스피" in a['title']]
        # 예상: 4900 돌파 팩트 기사 1~2개 + IT 분석 기사 1개
        print(f"\n  KOSPI Articles kept: {len(kospi_arts)}")
        
if __name__ == "__main__":
    unittest.main()
