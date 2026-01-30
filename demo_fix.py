
import re
import sys

# Force UTF-8 for Windows Console
sys.stdout.reconfigure(encoding='utf-8')

# Mock Article Map
article_map = {
    "101": {"t": "엔비디아 급등", "u": "https://example.com/101", "p": "Bloomberg"},
    "102": {"t": "AI 수요 폭발", "u": "https://example.com/102", "p": "Reuters"},
    "103": {"t": "삼성전자 실적", "u": "https://example.com/103", "p": "Chosun"},
}

# Case 1: Single Ref (Current Logic passes this, but fails multi)
text_single = "엔비디아가 올랐습니다 [Ref: 101]."

# Case 2: Multi Ref (Current Logic fails this)
text_multi = "시장 전반이 상승했습니다 [Ref: 101, 102]."

# Case 3: Messy Spacing
text_messy = "혼조세입니다 [Ref:102,  103]."

def demonstrate(label, text):
    print(f"\n--- {label} ---")
    print(f"Original: '{text}'")
    
    # 1. Current Logic (Broken for Multi)
    def replace_ref_old(match):
        ref_id = match.group(1)
        if ref_id in article_map:
            meta = article_map[ref_id]
            return f"([📰 {meta['t']}]({meta['u']}) - {meta['p']})"
        return match.group(0) # or empty
        
    # Old regex only captures digits
    res_old = re.sub(r'\[Ref:\s*(\d+)\]', replace_ref_old, text)
    print(f"Current : '{res_old}'")

    # 2. Proposed Logic (Fix)
    def replace_ref_new(match):
        # Capture strictly digits and commas/spaces
        ref_ids_str = match.group(1)
        # Split by comma
        ref_ids = [rid.strip() for rid in ref_ids_str.split(',') if rid.strip()]
        
        links = []
        for ref_id in ref_ids:
            if ref_id in article_map:
                meta = article_map[ref_id]
                links.append(f"([📰 {meta['t']}]({meta['u']}) - {meta['p']})")
        
        return " ".join(links) if links else ""

    # Updated Regex to allow comma and spaces
    res_new = re.sub(r'\[Ref:\s*([\d,\s]+)\]', replace_ref_new, text)
    print(f"Proposed: '{res_new}'")

if __name__ == "__main__":
    demonstrate("Case 1: Single Ref", text_single)
    demonstrate("Case 2: Multi Ref", text_multi)
    demonstrate("Case 3: Messy Spacing", text_messy)
