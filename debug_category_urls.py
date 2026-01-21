import sqlite3
import json
import sys
from pathlib import Path

# Add project root
sys.path.append(str(Path.cwd()))

from storage.db_adapter import DatabaseAdapter
from config.settings import DB_NAME, DB_TYPE

def debug_korea_market():
    """Korea > Market 카테고리의 URL 조회 과정 추적"""
    
    # 1. topics.db에서 Korea > Market 토픽 조회
    topics_db_path = Path("data/topics.db")
    conn_topics = sqlite3.connect(topics_db_path)
    cursor_topics = conn_topics.cursor()
    
    cursor_topics.execute("SELECT id, topic_title, news_ids FROM topics WHERE category = 'K_market'")
    topics = cursor_topics.fetchall()
    
    print(f"=== Korea > Market 토픽 개수: {len(topics)} ===\n")
    
    # 2. news.db 연결
    news_db = DatabaseAdapter(db_type=DB_TYPE, database=DB_NAME)
    news_db.connect()
    
    for topic in topics[:3]:  # 처음 3개만 확인
        topic_id, title, news_ids_json = topic
        news_ids = json.loads(news_ids_json)
        
        print(f"[Topic {topic_id}] {title}")
        print(f"  - News IDs: {news_ids}")
        
        # 3. fetch_article_details 로직 재현
        placeholders = ",".join(["?"] * len(news_ids))
        query = f"""
            SELECT p.id, r.title, COALESCE(r.publisher, r.source) as publisher, r.snippet, r.url
            FROM processed_news p
            JOIN raw_news r ON p.ref_raw_id = r.id
            WHERE p.id IN ({placeholders})
        """
        
        cursor = news_db.connection.cursor()
        cursor.execute(query, tuple(news_ids))
        rows = cursor.fetchall()
        
        print(f"  - 조회된 기사 수: {len(rows)}")
        
        # URL 상태 통계만 출력
        url_count = sum(1 for row in rows if row[4])  # row[4] is URL
        total_count = len(rows)
        print(f"  - URL Status: {url_count}/{total_count} articles have URLs")
        
        # 샘플 URL 확인 (첫 번째 것만)
        if rows and rows[0][4]:
            print(f"  - Sample URL: {rows[0][4]}")
        else:
            print(f"  - First article has NO URL!")
        
        print()
    
    conn_topics.close()
    news_db.close()

if __name__ == "__main__":
    debug_korea_market()
