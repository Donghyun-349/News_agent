import unittest
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.processors.similarity_deduplicator import SimilarityDeduplicator

class TestSimilarityDeduplicator(unittest.TestCase):
    def setUp(self):
        self.deduplicator = SimilarityDeduplicator(similarity_threshold=0.5)
        
        # Mock Data based on User's IMF Example
        self.imf_articles = [
            {
                "id": 1, "title": "IMF, 올해 한국 경제 1.9% 성장 전망", 
                "source": "한국경제", "reason": "[IMF] Korea Growth Forecast"
            },
            {
                "id": 2, "title": "IMF, 한국 올해 성장률 1.8% -> 1.9% 상향", 
                "source": "매일경제", "reason": "[IMF] GDP Growth Rate Upgrade"
            },
            {
                "id": 3, "title": "IMF \"韓 성장률 올해도 1%대\"... 정부 전망치 못 미쳐", 
                "source": "서울경제", "reason": "[IMF] Korean Growth Rate Forecast"
            },
            {
                "id": 4, "title": "IMF, 한국 성장률 1.9%로 상향... 정부 목표엔 못 미쳐", 
                "source": "파이낸셜뉴스", "reason": "[IMF] Korea Growth Rate Adjustment"
            },
            {
                "id": 5, "title": "IMF, 올해 韓 성장률 1.9% 전망... 4년째 美 밑돌아", 
                "source": "조선일보", "reason": "[IMF] Korea Growth Forecast"
            },
            # Bloomberg Article (Tier 1) - Should be picked primary
            {
                "id": 6, "title": "IMF Slightly Raises Korea Growth Forecast to 1.9%", 
                "source": "Bloomberg", "reason": "[IMF] Korea Growth Update"
            },
            # Irrelevant Article
            {
                "id": 7, "title": "Tesla Stock Jumps 10%", 
                "source": "CNBC", "reason": "[Tesla] Stock Surge"
            }
        ]

    def test_imf_grouping(self):
        """Test if IMF articles are grouped together"""
        # Bloomberg(Tier 1) should be Primary.
        # Among others, longest title might be picked as Secondary.
        
        result = self.deduplicator.run(self.imf_articles)
        cleaned = result["articles"]
        removed = result["removed_count"]
        
        print(f"\n[Test Result] Input: {len(self.imf_articles)} -> Output: {len(cleaned)} (Removed {removed})")
        for art in cleaned:
            print(f" - Kept: {art['source']} | {art['title']}")
            
        # Assertion
        # Group 1: IMF (6 articles) -> Keep 1 or 2
        # Group 2: Tesla (1 article) -> Keep 1
        # Total expected: 2 or 3
        self.assertTrue(len(cleaned) <= 3)
        self.assertTrue(len(cleaned) >= 2)
        
        # Check if Bloomberg is kept (Tier 1)
        sources = [a['source'] for a in cleaned]
        self.assertIn("Bloomberg", sources)
        
        # Check if Tesla is kept
        self.assertIn("CNBC", sources)

    def test_subject_extraction(self):
        reason = "[Samsung] Earnings Shock"
        self.assertEqual(self.deduplicator.extract_reason_subject(reason), "samsung")
        
        reason2 = "Just a string"
        self.assertEqual(self.deduplicator.extract_reason_subject(reason2), "")

if __name__ == "__main__":
    unittest.main()
