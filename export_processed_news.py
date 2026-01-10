import csv
import os
from datetime import datetime
from config.settings import DB_TYPE
from storage.db_adapter import DatabaseAdapter

def export_processed_news():
    db = DatabaseAdapter(db_type=DB_TYPE)
    db.connect()
    
    try:
        # Check if LLM columns exist (just to be safe, though db_adapter should handle it)
        # We will select all likely columns.
        query = """
            SELECT 
                p.id as processed_id,
                p.published_at,
                p.source_normalized,
                p.language,
                p.process_status,
                p.llm_decision,
                p.llm_category,
                p.llm_reason,
                r.title,
                r.snippet,
                r.url,
                r.source as original_source,
                r.publisher
            FROM processed_news p
            LEFT JOIN raw_news r ON p.ref_raw_id = r.id
            ORDER BY p.published_at DESC;
        """
        
        results = db.fetchall(query)
        
        if not results:
            print("No processed news found.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"processed_news_export_{timestamp}.csv"
        filepath = os.path.join(os.getcwd(), filename)
        
        # Define headers
        headers = [
            "processed_id", "published_at", "source_normalized", "language", 
            "process_status", "llm_decision", "llm_category", "llm_reason",
            "title", "snippet", "url", "original_source", "publisher"
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(results)
            
        print(f"Successfully exported {len(results)} rows to {filepath}")
        
    finally:
        db.close()

if __name__ == "__main__":
    export_processed_news()
