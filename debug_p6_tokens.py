import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.prompts.daily_market_intelligence import (
    get_system_prompt,
    get_topic_selection_prompt,
    get_section_body_prompt
)

def estimate_tokens(text: str, model: str = "gpt-4o") -> int:
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except ImportError:
        return len(text) // 4  # Rough estimate

def run_debug():
    print("Phase 6 Token Usage Estimate (Debug)\n")
    
    # --- 1. System Prompt ---
    sys_prompt = get_system_prompt()
    print(f"=== System Prompt ===")
    print(f"Chars: {len(sys_prompt)}")
    print(f"Est Tokens: {estimate_tokens(sys_prompt)}")
    
    # --- 2. Selection Step Payload (Metadata) ---
    # Mock Data: 30 topics
    topics = []
    for i in range(30):
        topics.append({
            "id": i,
            "category": "Global > Macro",
            "topic_title": f"Global Stock Markets Surge as inflation cools down {i}",
            "count": 5
        })
    
    sel_payload = json.dumps(topics, ensure_ascii=False, indent=2)
    sel_payload_opt = json.dumps(topics, ensure_ascii=False, separators=(',', ':'))
    
    # Optimization: keys (id->i, category->c, topic_title->t, count->n)
    topics_opt = []
    for t in topics:
        topics_opt.append({
            "i": t['id'],
            "c": t['category'],
            "t": t['topic_title'],
            "n": t['count']
        })
    sel_payload_super_opt = json.dumps(topics_opt, ensure_ascii=False, separators=(',', ':'))

    print(f"\n=== [Step 2] Selection Payload (30 Topics) ===")
    print(f"Default (Indent=2) Chars: {len(sel_payload)}")
    print(f"Default Est Tokens: {estimate_tokens(sel_payload)}")
    print(f"Optimized (Minified) Est Tokens: {estimate_tokens(sel_payload_opt)}")
    print(f"Super Opt (Keys) Est Tokens: {estimate_tokens(sel_payload_super_opt)}")

    # --- 3. Generation Step Payload (Snippets) ---
    # Mock Data: 1 Section with 3 Topics, each having 4 articles
    # Each article has ~200 chars snippet
    
    section_context = []
    for i in range(3): # 3 Topics
        articles = []
        for j in range(4): # 4 Articles per topic
            articles.append({
                "title": f"Article Title {i}-{j} about market updates",
                "publisher": "Bloomberg",
                "snippet": "Ideally, this snippet contains around 200 characters of text describing the event. " * 3,
                "url": "https://example.com/article/12345"
            })
        
        section_context.append({
            "title": f"Selected Topic {i}",
            "count": 4,
            "articles": articles
        })
        
    gen_payload = json.dumps(section_context, ensure_ascii=False, indent=2)
    gen_payload_opt = json.dumps(section_context, ensure_ascii=False, separators=(',', ':'))
    
    # Optimization: keys (title->t, publisher->p, snippet->s, url->u, articles->a, count->n)
    section_context_opt = []
    for topic in section_context:
        arts_opt = []
        for a in topic['articles']:
            arts_opt.append({
                "t": a['title'],
                "p": a['publisher'],
                "s": a['snippet'],
                "u": a['url']
            })
        section_context_opt.append({
            "t": topic['title'],
            "n": topic['count'],
            "a": arts_opt
        })
    gen_payload_super_opt = json.dumps(section_context_opt, ensure_ascii=False, separators=(',', ':'))

    print(f"\n=== [Step 3] Generation Payload (1 Section, 3 Topics, 12 Articles) ===")
    print(f"Default (Indent=2) Chars: {len(gen_payload)}")
    print(f"Default Est Tokens: {estimate_tokens(gen_payload)}")
    print(f"Optimized (Minified) Est Tokens: {estimate_tokens(gen_payload_opt)}")
    print(f"Super Opt (Keys) Est Tokens: {estimate_tokens(gen_payload_super_opt)}")

if __name__ == "__main__":
    run_debug()
