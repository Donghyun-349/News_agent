
import json

def estimate_tokens(text):
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except ImportError:
        return len(text) // 4

# 1. Clustering System Prompt
from config.prompts.topic_clustering import get_topic_clustering_prompt
cluster_prompt = get_topic_clustering_prompt()

print(f"=== [Clustering] System Prompt ===")
print(f"Chars: {len(cluster_prompt)}")
print(f"Est Tokens: {estimate_tokens(cluster_prompt)}")

# 2. Clustering Input Payload (Batch of 25)
# Input format: {"id": a["id"], "reason": a["reason"]}
articles = []
for i in range(25):
    articles.append({
        "id": i,
        "reason": "Samsung Electronics reports Q4 profit jump due to memory chip recovery. [Samsung Electronics] + [Profit Surge]"
    })

payload_default = json.dumps(articles, ensure_ascii=False, indent=2)
# Proposed Optimization: id -> i, reason -> r
articles_opt = [{"i": a["id"], "r": a["reason"]} for a in articles]
payload_opt = json.dumps(articles_opt, ensure_ascii=False, separators=(',', ':'))

print(f"\n=== [Clustering] User Payload (Batch 25) ===")
print(f"Default (Indent=2) Chars: {len(payload_default)}")
print(f"Default Est Tokens: {estimate_tokens(payload_default)}")
print(f"Optimized Chars: {len(payload_opt)}")
print(f"Optimized Est Tokens: {estimate_tokens(payload_opt)}")


# 3. Translation Prompt (Inside transform code)
# Updated optimized prompt
print(f"\n=== [Translation] System Prompt ===")
trans_prompt = """You are a professional translator. Translate the following article titles to Korean.

Rules:
1. If a title is already in Korean, return an empty string "" for that title
2. If a title is in a foreign language (English, etc.), translate it to natural Korean
3. Keep proper nouns (company names, people names, places) in their original form
4. Return ONLY a valid JSON array in this exact format:
[
  {"i": 0, "t": "번역된 제목 또는 빈 문자열"},
  {"i": 1, "t": "번역된 제목 또는 빈 문자열"}
]

Titles to translate (i=id, t=title):
..."""
print(f"Chars: {len(trans_prompt)}")
print(f"Est Tokens: {estimate_tokens(trans_prompt)}")

# 4. Translation Payload
titles = [{"id": i, "title": "Samsung Electronics profit jumps"} for i in range(25)]
trans_payload = json.dumps(titles, ensure_ascii=False)
titles_opt = [{"i": t["id"], "t": t["title"]} for t in titles]
trans_payload_opt = json.dumps(titles_opt, ensure_ascii=False, separators=(',', ':'))

print(f"\n=== [Translation] User Payload (Batch 25) ===")
print(f"Default Chars: {len(trans_payload)}")
print(f"Default Est Tokens: {estimate_tokens(trans_payload)}")
print(f"Optimized Chars: {len(trans_payload_opt)}")
print(f"Optimized Est Tokens: {estimate_tokens(trans_payload_opt)}")
