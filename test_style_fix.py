
import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from run_p6_2 import convert_and_style_html
except ImportError as e:
    print(f"FAILED to import: {e}")
    sys.exit(1)

sample_md = """
## 1. Executive Summary
- Item 1
- Item 2

---

## 2. Global Market
### Macro
- Content 1
"""

try:
    html = convert_and_style_html(sample_md)
    print("SUCCESS: Function ran without error.")
    
    if "briefing_box" in html:
        print("CHECK: Briefing format applied.")
    else:
        print("FAIL: Briefing format NOT detected.")
        
    if "면책 조항" in html:
        print("CHECK: Disclaimer applied.")
    else:
        print("FAIL: Disclaimer NOT detected.")
        
except Exception as e:
    print(f"FAILED with error: {e}")
