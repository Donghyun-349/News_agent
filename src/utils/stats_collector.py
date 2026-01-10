import json
import os
from pathlib import Path
from datetime import datetime

# Define path relative to this file
# src/utils/stats_collector.py -> data/daily_stats.json
BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATS_FILE = BASE_DIR / "data" / "daily_stats.json"

class StatsCollector:
    """
    Collects execution statistics across different phases of the pipeline.
    Persists data to a JSON file to share state between scripts.
    """
    def __init__(self):
        self.stats_file = STATS_FILE
        self.stats = self._load()

    def _load(self):
        """Load stats from file, reset if date has changed"""
        if not self.stats_file.exists():
            return self._init_stats()
        
        try:
            with open(self.stats_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Check if it's from today (KST ideally, but system local time is fine for this context)
            # If running on GitHub Actions (UTC), we might want to be careful.
            # But the pipeline cleans data/ daily usually.
            # Let's rely on date string match.
            saved_date = data.get("date")
            today = datetime.now().strftime("%Y-%m-%d")
            
            if saved_date != today:
                return self._init_stats()
                
            return data
        except Exception:
            return self._init_stats()

    def _init_stats(self):
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "collection": {},    # "Source Name": count
            "total_collected": 0,
            "dedup_removed": 0,
            "keyword_filtered": 0,
            "llm_keep": 0,
            "llm_drop": 0
        }

    def update_collection(self, source: str, count: int):
        """Update collection count for a specific source"""
        self.stats["collection"][source] = count
        self.stats["total_collected"] = sum(self.stats["collection"].values())
        self._save()

    def set_stat(self, key: str, value: int):
        """Set a specific stat value"""
        if key in self.stats:
            self.stats[key] = value
            self._save()
        else:
            # Allow dynamic keys if needed, or ignore
            self.stats[key] = value
            self._save()

    def inc_stat(self, key: str, value: int = 1):
        """Increment a stat value"""
        if key not in self.stats:
            self.stats[key] = 0
        self.stats[key] += value
        self._save()

    def _save(self):
        """Save stats to JSON file"""
        self.stats_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)

    def get_stats(self):
        return self.stats
