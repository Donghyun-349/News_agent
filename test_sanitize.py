import sys
sys.path.append(".")

from run_p6 import sanitize_article_data

# Test sample
test_articles = [
    {
        "id": 1,
        "title": "[증시-마감] 테스트 기사",
        "publisher": "Infomax",
        "snippet": "test snippet",
        "url": "https://example.com/article1"
    },
    {
        "id": 2,
        "title": "정상 기사 제목",
        "publisher": "Test Publisher",
        "snippet": "another snippet",
        "url": "https://example.com/article2"
    }
]

print("BEFORE sanitization:")
for art in test_articles:
    print(f"  {art['id']}: title='{art['title']}' url='{art['url']}'")

cleaned = sanitize_article_data(test_articles)

print("\nAFTER sanitization:")
for art in cleaned:
    print(f"  {art['id']}: title='{art['title']}' url='{art['url']}'")

print("\nURL preserved:", all(art.get('url') for art in cleaned))
