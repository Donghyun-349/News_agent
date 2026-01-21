
import sys
import os
from pathlib import Path
import logging

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.collectors.korean_economy import KoreanEconomyScraper
from src.utils.logger import setup_logger

# Setup logger to see output
logger = setup_logger(log_level="INFO")

def test_korean_economy_collection():
    print("Testing Korean Economy Scraper...")
    scraper = KoreanEconomyScraper()
    articles = scraper.fetch_news()
    
    print(f"\nTotal articles collected: {len(articles)}")
    
    # Check for new sources
    sources = {}
    for article in articles:
        # RSS parser puts feed name in 'source' or 'press_name', 
        # but KoreanEconomyScraper._set_source_name sets 'source' to feed_name
        src = article.get('source', 'Unknown')
        sources[src] = sources.get(src, 0) + 1
        
    print("\nArticles per source:")
    for src, count in sources.items():
        print(f"- {src}: {count}")

    # Verify our target sources
    target_sources = ["조선일보", "동아일보"]
    for target in target_sources:
        if target in sources and sources[target] > 0:
            print(f"[SUCCESS] Collected from {target}")
        else:
            print(f"[FAILURE] No articles from {target}")

if __name__ == "__main__":
    test_korean_economy_collection()
