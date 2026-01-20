#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 1.5: Title-Based Deduplication Processor (Refactored)

제목이 동일한 기사들을 병합하여 중복을 제거합니다.
Lane 할당 로직은 제거되었습니다.
"""

import logging
import re
import html
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from datetime import datetime

from config.source_hierarchy import get_source_tier

logger = logging.getLogger(__name__)


class TitleDeduplicator:
    """제목 기반 중복 제거 프로세서"""
    
    def __init__(self, db_adapter):
        """
        초기화
        
        Args:
            db_adapter: DatabaseAdapter instance
        """
        self.db_adapter = db_adapter
    
    @staticmethod
    def normalize_title(title: str) -> str:
        """
        제목 정규화: 공백, 특수문자 제거
        
        Args:
            title: 원본 제목
            
        Returns:
            정규화된 제목
        """
        if not title:
            return ""
        
        # 공백 정규화
        normalized = re.sub(r'\s+', ' ', title)
        # 특수문자 제거 (따옴표, 대괄호 등)
        normalized = normalized.strip()
        # 소문자 변환 (대소문자 무시)
        normalized = normalized.lower()
        
        return normalized
    
    def select_representative(self, articles: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], int, List[int], List[str]]:
        """
        그룹에서 대표 기사 선택
        
        Args:
            articles: 동일 제목의 기사 리스트
            
        Returns:
            (representative_article, weight, merged_ids, source_list)
        """
        if not articles:
            return None, 0, [], []
        
        # Source tier 기준으로 정렬 (낮은 tier = 높은 우선순위)
        sorted_articles = sorted(
            articles,
            key=lambda a: (
                get_source_tier(a.get("source", "")),
                -len(a.get("title", ""))  # 같은 tier면 제목이 긴 것 우선
            )
        )
        
        representative = sorted_articles[0]
        weight = len(articles)
        merged_ids = [a.get("id") for a in articles if a.get("id") is not None]
        source_list = list(set([a.get("source", "") for a in articles]))
        
        return representative, weight, merged_ids, source_list
    
    def deduplicate_by_title(self) -> Dict[str, Any]:
        """
        raw_news 테이블에서 제목이 동일한 기사들을 병합하여
        processed_news 테이블에 저장 (Incremental Update)
        
        기존 processed_news 데이터를 삭제하지 않고,
        이미 처리된 기사 그룹은 건너뛰고 새로운 그룹만 추가합니다.
        
        Returns:
            처리 결과 통계
        """
        logger.info("\n" + "="*80)
        logger.info("🔄 Phase 1.5: Title-Based Deduplication (Incremental) 시작")
        logger.info("="*80)

        # 0. Clean HTML Entities in DB first
        self.clean_and_update_db_titles()
        
        cursor = self.db_adapter.connection.cursor()
        
        # 0. 이미 처리된 raw_id 목록 로드 (Set for O(1) lookup)
        cursor.execute("SELECT ref_raw_id FROM processed_news WHERE ref_raw_id IS NOT NULL")
        existing_raw_ids = set(row[0] for row in cursor.fetchall())
        logger.info(f"💾 Found {len(existing_raw_ids)} already processed articles in DB.")
        
        # 1. raw_news에서 모든 기사 가져오기
        cursor.execute("""
            SELECT id, source, title, snippet, url, published, collected_at, publisher
            FROM raw_news
            WHERE title IS NOT NULL AND title != ''
        """)
        
        raw_articles = []
        for row in cursor.fetchall():
            raw_articles.append({
                "id": row[0],
                "source": row[7] or row[1], # publisher가 있으면 사용, 없으면 source (category) 사용
                "title": row[2],
                "snippet": row[3],
                "link": row[4],  # url을 link로 매핑
                "published_date": row[5],  # published를 published_date로 매핑
                "collected_date": row[6]  # collected_at를 collected_date로 매핑
            })
        
        logger.info(f"📥 Loaded {len(raw_articles)} articles from raw_news")
        
        # 2. 제목으로 그룹화
        title_groups = defaultdict(list)
        for article in raw_articles:
            normalized_title = self.normalize_title(article["title"])
            if normalized_title:
                title_groups[normalized_title].append(article)
        
        logger.info(f"📊 Grouped into {len(title_groups)} unique titles")
        
        # 3. 각 그룹 처리 (Incremental Logic)
        total_new_saved = 0
        total_skipped_existing = 0
        total_duplicates_removed = 0
        duplicate_examples = []
        removed_articles = []
        
        for normalized_title, articles in title_groups.items():
            # Check if ANY article in this group has already been processed
            # (If one is processed, we assume the group is handled or represents the same story)
            
            # 그룹 내의 id 집합
            group_ids = set(a["id"] for a in articles)
            
            # 교집합이 있으면 (하나라도 처리된 적이 있으면) -> Skip
            if not group_ids.isdisjoint(existing_raw_ids):
                total_skipped_existing += 1
                continue
            
            # 없으면 -> New Group -> Process & Insert
            representative, weight, merged_ids, source_list = self.select_representative(articles)
            
            if not representative:
                continue
            
            # DB에 저장
            cursor.execute("""
                INSERT INTO processed_news (
                    ref_raw_id, published_at, source_normalized
                ) VALUES (?, ?, ?)
            """, (
                representative["id"],
                representative.get("published_date") or datetime.now(),
                representative["source"]
            ))
            
            total_new_saved += 1
            
            # 중복 제거 통계 (신규 처리된 것 내에서만)
            if weight > 1:
                total_duplicates_removed += (weight - 1)
                
                # 삭제된 기사 추적 (대표 기사 제외)
                for article in articles:
                    if article["id"] != representative["id"]:
                        removed_articles.append({
                            "removed_id": article["id"],
                            "removed_source": article["source"],
                            "title": article["title"],
                            "kept_id": representative["id"],
                            "kept_source": representative["source"]
                        })
                
                # 예시용
                if len(duplicate_examples) < 10:
                    duplicate_examples.append({
                        "title": representative["title"],
                        "weight": weight,
                        "sources": source_list,
                        "selected_source": representative.get("source")
                    })
        
        self.db_adapter.connection.commit()
        
        # 5. 결과 통계
        stats = {
            "total_raw_articles": len(raw_articles),
            "total_processed_articles": len(existing_raw_ids) + total_new_saved, # Total valid in DB
            "total_new_saved": total_new_saved,
            "total_skipped_existing": total_skipped_existing,
            "total_duplicates_removed": total_duplicates_removed,
            "duplicate_examples": duplicate_examples,
            "removed_articles": removed_articles
        }
        
        logger.info("\n" + "="*80)
        logger.info("📊 Deduplication (Incremental) 완료")
        logger.info("="*80)
        logger.info(f"  원본 기사 Total: {stats['total_raw_articles']}")
        logger.info(f"  기존 처리됨 (Skip): {stats['total_skipped_existing']} groups")
        logger.info(f"  신규 추가됨 (New): {stats['total_new_saved']}")
        logger.info(f"  신규 중 중복 제거: {stats['total_duplicates_removed']}")
        
        return stats
    
    def clean_and_update_db_titles(self):
        """raw_news의 타이틀에서 HTML Entity 문제 해결 및 DB 업데이트"""
        try:
            cursor = self.db_adapter.connection.cursor()
            
            # Fetch candidates (titles with '&')
            if hasattr(self.db_adapter, 'db_type') and self.db_adapter.db_type == 'sqlite':
                cursor.execute("SELECT id, title FROM raw_news WHERE title LIKE '%&%'")
            else:
                cursor.execute("SELECT id, title FROM raw_news WHERE title LIKE '%&%'")
                
            rows = cursor.fetchall()
            
            updates = []
            for row in rows:
                original_title = row[1]
                if not original_title: continue
                
                # HTML unescape only (No prefix removal here)
                cleaned_title = html.unescape(original_title).strip()
                
                if original_title != cleaned_title:
                    updates.append((cleaned_title, row[0]))
                    
            if updates:
                logger.info(f"🧹 Cleaning HTML entities for {len(updates)} articles in raw_news...")
                
                if hasattr(self.db_adapter, 'db_type') and self.db_adapter.db_type == 'sqlite':
                    query = "UPDATE raw_news SET title = ? WHERE id = ?"
                else:
                    query = "UPDATE raw_news SET title = %s WHERE id = %s"
                    
                cursor.executemany(query, updates)
                self.db_adapter.connection.commit()
                logger.info("✅ Title HTML entity cleaning complete.")
            else:
                logger.info("✨ No HTML entities found in titles to clean.")
        except Exception as e:
            logger.error(f"⚠️ Title cleaning failed: {e}")
    
    def process(self) -> Dict[str, Any]:
        """Phase 1.5 전체 처리"""
        return self.deduplicate_by_title()
