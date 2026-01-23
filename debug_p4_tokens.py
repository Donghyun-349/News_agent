
import json

import json

def estimate_tokens(text):
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except ImportError:
        return len(text) // 4  # Rough estimate


# 1. System Prompt Analysis
from config.prompts.classification_pt import get_p4_topic_classification_prompt
system_prompt = get_p4_topic_classification_prompt()

print(f"=== System Prompt ===")
print(f"Chars: {len(system_prompt)}")
print(f"Est Tokens: {estimate_tokens(system_prompt)}")

# 2. User Payload Analysis (Batch of 25)
articles = []
for i in range(25):
    articles.append({
        "id": f"{i}",
        "title": "Samsung Electronics profit jumps 50% on memory chip demand recovery",
        "snippet": "Samsung Electronics reported a robust 50 percent jump in operating profit for the fourth quarter, driven by a strong recovery in memory chip prices and solid demand for premium smartphones. The company..."[:200]
    })

# Current Format (Indent=None or 2 depending on version, let's check both)
payload_default = json.dumps(articles, ensure_ascii=False) # No indent
payload_pretty = json.dumps(articles, ensure_ascii=False, indent=2)

print(f"\n=== User Payload (Batch 25) ===")
print(f"Default (No Indent) Chars: {len(payload_default)}")
print(f"Default Est Tokens: {estimate_tokens(payload_default)}")
print(f"Pretty (Indent=2) Chars: {len(payload_pretty)}")

# 3. Optimized Payload
articles_opt = []
for a in articles:
    articles_opt.append({
        "i": a["id"],        # id -> i
        "t": a["title"]      # title -> t, No snippet
    })
payload_opt = json.dumps(articles_opt, ensure_ascii=False, separators=(',', ':'))

print(f"\n=== Optimized Payload (Batch 25) ===")
print(f"Optimized Chars: {len(payload_opt)}")
print(f"Optimized Est Tokens: {estimate_tokens(payload_opt)}")

savings = estimate_tokens(payload_default) - estimate_tokens(payload_opt)
print(f"\nEstimated Savings per Batch: {savings} tokens")
