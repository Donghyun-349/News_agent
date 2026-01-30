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

sample_md = """## 1. Executive Summary
- 미 연준 금리 동결, 트럼프와 차기 의장 압박으로 정책 불확실성 고조.
- 한국 반도체 투톱, AI 및 HBM-2나노 기술력 기반 역대 최대 실적 경신.

---

## 2. 🌍 Global Market
### 📉 Macro (Economy/Rates)
### 연준, 금리 동결 기조 유지 및 점진적 인하 전망
연방준비제도(Fed)는 당분간 기준금리를 동결할 것으로 광범위하게 예상되며 ([📰 Fed Holds Rates](https://example.com) - Bloomberg), 월가 전문가들은 올해 총 50bp의 금리 인하를 전망하고 있습니다 ([📰 Fed Survey](https://example.com) - Reuters).

### 🚀 Market (Stock/Indices)
### 미국 증시 S&P 500 사상 최고치 경신
S&P 500 지수가 사상 최고치를 경신하며 7000선에 근접했습니다 ([📰 S&P Record](https://example.com) - Bloomberg).

### 🤖 Tech (AI/Semiconductors)
### 엔비디아의 AI 인프라 전략과 시장 경쟁
엔비디아는 AI 인프라의 핵심으로 성장 중입니다 ([📰 NVIDIA Strategy](https://example.com) - TechCrunch).

---

## 3. 🇰🇷 Korea Market
### 🚀 Market (Stock/Indices)
### 코스피, 사상 첫 5천선 돌파
코스피 지수가 사상 처음으로 5,084.85를 기록했습니다 ([📰 KOSPI 5000](https://example.com) - 조선일보).

### 💸 Macro (FX/Rates)
### 원/달러 환율 상승 및 원화 약세
원/달러 환율이 상승하며 원화 가치가 하락세로 전환되었습니다 ([📰 Won Weakness](https://example.com) - 매일경제).

---

## 4. 🏢 Real Estate
### 🌐 Global Real Estate
### 미국 주택 시장 구매 철회 급증
최근 미국에서 주택 구매자들이 거래를 철회하는 현상이 급증하고 있습니다 ([📰 Home Buyers Backing Out](https://example.com) - CNBC).

### 🇰🇷 Korea Real Estate
### 서울 전세가율 하락
서울 아파트값 상승으로 전세가율이 50.92%로 하락했습니다 ([📰 Seoul Jeonse](https://example.com) - 동아일보).
"""

try:
    html = convert_and_style_html(sample_md)
    with open("debug_output.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("SUCCESS: HTML written to debug_output.html")
    
    # Check for expected elements
    checks = []
    checks.append(("Section dividers present", html.count("<hr") >= 5))
    checks.append(("Citation colors unified", 'color: #1976D2' in html))
    checks.append(("Disclaimer present", "면책 조항" in html))
    
    print("\nVerification Results:")
    for check_name, result in checks:
        status = "[OK]" if result else "[FAIL]"
        print(f"{status} {check_name}")
    
except Exception as e:
    print(f"ERROR: FAILED with error: {e}")
    import traceback
    traceback.print_exc()
