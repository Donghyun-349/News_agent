"""Phase 5 Processor: Source-Specific Narrative Clustering"""

import os
import json
import logging
import math
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

import numpy as np
try:
    from sklearn.cluster import MiniBatchKMeans
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from config.prompts.phase5_narrative import get_narrative_mapper_prompt, get_source_report_prompt

logger = logging.getLogger(__name__)

@dataclass
class SourceNarrative:
    """Individual Narrative Block within a Source"""
    cluster_id: int
    cluster_name: str
    content: Dict[str, List[str]]  # {exclusive: [], news: [], opinion: []}

@dataclass
class SourceReport:
    """Report for a single Source (e.g., WSJ Report)"""
    source_name: str
    total_articles: int
    content: Dict[str, Any]  # {key_takeaways: [], sections: {}}
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

class Phase5Processor:
    """
    Phase 5: Source-Specific Narrative Clustering
    Isolated clustering per media source to extract top narratives.
    """

    def __init__(self, openai_api_key: Optional[str] = None, gemini_api_key: Optional[str] = None):
        self.openai_client = None
        self.use_gemini = False
        
        # 1. Gemini Configuration (Priority)
        if GEMINI_AVAILABLE:
            api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                self.use_gemini = True
                logger.info("✨ Using Gemini 2.0 Flash for Phase 5.")
            
        # 2. OpenAI Configuration (Fallback)
        if not self.use_gemini and OPENAI_AVAILABLE:
            if openai_api_key:
                self.openai_client = OpenAI(api_key=openai_api_key)
            else:
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    self.openai_client = OpenAI(api_key=api_key)
        
        if not self.use_gemini and not self.openai_client:
            logger.warning("⚠️ No valid LLM Client (Gemini/OpenAI) initialized. Narrative mapping will be skipped.")

        if not SKLEARN_AVAILABLE:
            logger.warning("⚠️ sklearn not available. K-Means clustering will fail.")

    def process_all_sources(self, story_objects: List[Dict[str, Any]]) -> List[SourceReport]:
        """
        Main entry point: Group by Source -> Cluster -> LLM Map
        """
        # 1. Group by Source (Filter for Verified TopSources only)
        TARGET_SOURCES = [
            "Wall Street Journal", 
            "Bloomberg", 
            "Financial Times", 
            "Reuters"
        ]
        
        grouped_articles = defaultdict(list)
        for obj in story_objects:
            source = obj.get("source", "Unknown")
            # Loose matching to catch variations if needed, but assuming exact match for now
            if source in TARGET_SOURCES:
                grouped_articles[source].append(obj)

        reports = []

        # 2. Iterate each source
        for source, articles in grouped_articles.items():
            report = self._process_single_source(source, articles)
            if report:
                reports.append(report)
        
        return reports

    def _process_single_source(self, source: str, articles: List[Dict[str, Any]]) -> Optional[SourceReport]:
        """
        Process a single source: Vector extraction -> K-Means -> LLM
        """
        N = len(articles)
        
        # 3. Dynamic K Formula
        if N < 1:  # Modified: Allow even 1 article for testing (Original: < 5)
            logger.info(f"Skipping {source} (Count {N} < 1)")
            return None
        elif N < 20:
            K = 3
        else:
            K = 5
        
        # Limit K if N is small (safeguard)
        K = min(K, N)

        logger.info(f"Processing {source}: {N} articles -> K={K}")

        # 4. Preparing Vectors
        vectors = []
        valid_indices = []
        for i, obj in enumerate(articles):
            vec = obj.get("embedding_vector")
            
            # Debug Log for first item
            if i == 0:
                logger.info(f"Vector Type: {type(vec)}, Length: {len(vec) if vec else 'None'}")

            # Parse if string/JSON
            if isinstance(vec, str):
                try:
                    vec = json.loads(vec)
                except:
                    vec = None
            elif isinstance(vec, bytes):
                # Unpack binary blob (assuming float 4-bytes)
                try:
                    import struct
                    num_floats = len(vec) // 4
                    vec = struct.unpack(f'{num_floats}f', vec)
                    vec = list(vec)
                except Exception as e:
                    logger.error(f"Vector unpack failed: {e}")
                    vec = None
            
            if vec and len(vec) > 0:
                vectors.append(vec)
                valid_indices.append(i)
        
        logger.info(f"{source}: Found {len(vectors)} valid vectors for K={K}")
        
        if len(vectors) < K:
            logger.warning(f"{source}: Not enough valid vectors for K={K} (Found {len(vectors)})")
            return None

        # 5. K-Means Clustering
        try:
            kmeans = MiniBatchKMeans(
                n_clusters=K,
                random_state=42,
                batch_size=256,
                n_init='auto'
            )
            labels = kmeans.fit_predict(np.array(vectors))
        except Exception as e:
            logger.error(f"{source} K-Means failed: {e}")
            return None

        # Group by Cluster ID
        clusters = defaultdict(list)
        for idx, label in enumerate(labels):
            article_idx = valid_indices[idx]
            article = articles[article_idx]
            clusters[label].append(article)
        
        # 6. LLM Source Reporting (Aggregated)
        # Prepare Batch Input
        cluster_data_list = []
        for cluster_id, cluster_articles in clusters.items():
            # Limit to top 15 articles per cluster for broader context
            articles_snippet = []
            for i, art in enumerate(cluster_articles[:15]):
                title = art.get('title', 'No Title')
                snippet = art.get('snippet', 'No Snippet')
                articles_snippet.append(f"[{i+1}] {title} (Summary: {snippet})")
            
            cluster_data_list.append({
                "cluster_id": int(cluster_id),
                "texts": articles_snippet
            })
        
        # Call Source Report LLM
        report_content = self._generate_source_report(source, cluster_data_list)
        
        if not report_content:
            logger.warning(f"Failed to generate report content for {source}")
            return None

        return SourceReport(
            source_name=source,
            total_articles=N,
            content=report_content
        )

    def _generate_source_report(self, source: str, cluster_data: List[Dict]) -> Dict[str, Any]:
        """Call LLM once to generate the Final Source Report"""
        if not self.use_gemini and not self.openai_client:
            return {}
        
        if not cluster_data:
            return {}

        # Format Batch Input Text
        batch_input_text = ""
        for item in cluster_data:
            c_id = item['cluster_id']
            texts = "\n".join(item['texts'])
            batch_input_text += f"### Cluster ID: {c_id}\n{texts}\n\n"

        prompt = get_source_report_prompt(source, batch_input_text)
        content = ""

        try:
            if self.use_gemini:
                # Gemini Call
                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                # Increase token limit for full report if needed
                response = model.generate_content(
                    f"You are a helpful media analyst.\n{prompt}",
                    generation_config={"response_mime_type": "application/json"}
                )
                content = response.text.strip()
            else:
                # OpenAI Call
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a helpful media analyst."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3
                )
                content = response.choices[0].message.content.strip()
            
            # Clean JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Parse Dictionary
            report_data = json.loads(content)
            
            if isinstance(report_data, dict):
                return report_data
            else:
                logger.error(f"LLM returned list instead of dict for {source}")
                return {}

        except Exception as e:
            logger.error(f"Source Reporting failed for {source}: {e}")
            return {}
