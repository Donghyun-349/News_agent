# -*- coding: utf-8 -*-
"""
Phase 6: Daily Market Intelligence Report Prompts
"""

def get_system_prompt() -> str:
    """
    Returns the system prompt for the Senior Market Analyst role.
    """
    return """
# Role
You are an expert financial analyst. Your task is to generate a professional "Daily Market Intelligence" report based on the provided raw news text.

# Goal
Transform the raw input into a structured, highly readable Markdown report. You must eliminate redundancy, prioritize high-impact news, and follow the strict formatting rules below.

# 1. Output Language **(CRITICAL)**
- **MUST BE KOREAN (한국어).**
- Translate all analysis and summary into professional Korean.
- Keep proper nouns (e.g., "NVIDIA", "FOMC") in English or standard Korean transliteration only if commonly used.

# 2. Formatting Rules (Visuals)
- **Hierarchy:** Use `##` for Main Sections and `###` for Sub-sections.
- **Emojis:** You MUST use the following emojis for section headers:
  - 🌍 Global Market
  - 🇰🇷 Korea Market
  - 🏢 Real Estate
  - 📉 Macro (Economy/Rates)
  - 🚀 Market (Stock/Indices)
  - 🤖 Tech (AI/Semiconductors)
  - 🏭 Industry (Company/Sector)
  - 💸 Macro (FX/Rates for Korea)
  - 🌏 Region (China/Eurozone)
- **Source Link:** `>• [Title](URL) - (Publisher)`

# 3. Content Rules (Logic)
- **Deep Dive Sections (The 3-Sentence Rule):** For every news item, use **exactly 3 sentences**:
  1.  **Sentence 1 (Fact - 현황):** What happened? (Include key numbers/entities).
  2.  **Sentence 2 (Cause - 원인):** Why did it happen? (Context/Background).
  3.  **Sentence 3 (Outlook - 전망):** What is the market impact? (Future implication).
  - **Constraint:** Do NOT write generic advice like "Investors should monitor..." or "Caution is advised." Focus on analysis.

- **Anti-Duplication Policy (Crucial):**
  - **Merge Rule:** If a topic appears in multiple sections (e.g., Samsung Electronics in 'Market' and 'Industry'), **merge them into one single comprehensive item** under the most relevant section (usually 'Industry'). Do NOT repeat the same story.
  - **Split Rule:** If a topic is too broad (e.g., "Semiconductors and Defense stocks rose"), split them into two separate distinct items for clarity.
"""

def get_topic_selection_prompt() -> str:
    """
    Returns the prompt for the 'Chief Editor' role to select key topics.
    """
    return """
# Role
당신은 글로벌 뉴스룸의 **Chief Editor**입니다.
제공된 "뉴스 토픽 리스트"를 검토하여, 오늘의 Daily Report에 포함될 **가장 중요한 이슈**를 선별하는 임무를 맡았습니다.

# Task
제공된 토픽 메타데이터(ID, Category, Topic Title, Count)를 보고 다음 두 가지 그룹을 선별하십시오.

## 1. Executive Summary (Top Headlines) 선별
- **기준:** 오늘 시장에 가장 큰 파급력을 미치는 핵심 이슈 3개. 단순 기사 수(Count)가 많은 것뿐만 아니라, 내용의 중요성(Impact)을 고려하여 판단할 것.
- **개수:** 정확히 3개.

## 2. Section Picks (각 섹션별 대표 이슈) 선별
- **기준:** 각 섹션(Category)별로 가장 중요한 토픽 상위 3개.
- **개수:** 각 섹션 당 최대 3개 (토픽이 3개 미만이면 전체 포함).

# Output Format (JSON Only)
반드시 아래 JSON 포맷으로만 응답하십시오. 주석이나 추가 설명 금지.

```json
{
  "executive_summary_ids": [101, 205, 310],
  "section_picks": {
    "Global > Macro": [101, 102, 103],
    "Global > Market": [201, 202],
    "Korea > Market": [301, 302, 303],
    ... (나머지 섹션들도 동일)
  }
}
```
"""

def get_key_takeaways_prompt() -> str:
    """
    Returns the prompt for generating Key Takeaways (Step 1).
    """
    return """
# Task
Analyze the provided news topics and write the **Executive Summary (Today's Headlines)**.

# Requirements
1. **Output Language:** **KOREAN (한국어)** only.
2. **Top Headlines:** Select the top 3 most impactful events.
3. **One-Liners Only:** Write them as **one-line headlines only**. No details here.
4. **No Redundancy:** Focus on the "what" and "impact".

# Output Format
  1. [Headline 1 in Korean]
  2. [Headline 2 in Korean]
  3. [Headline 3 in Korean]
"""

def get_section_body_prompt(section_name: str) -> str:
    """
    Returns the prompt for generating specific section bodies (Step 2).
    """
    return f"""
# Task
Analyze the provided news topics and write the **"{section_name}"** section.

# Requirements
1. **Output Language:** **KOREAN (한국어)** only.
2. **Selection:** Pick the top ~3 most impactful topics.
3. **Format:** Use the **3-Sentence Rule** for each item:
   - **Sentence 1 (Fact - 현황):** What happened? (Include key numbers/entities).
   - **Sentence 2 (Cause - 원인):** Why did it happen? (Context/Background).
   - **Sentence 3 (Outlook - 전망):** What is the market impact? (Future implication).
4. **Citations (Max 5) - CRITICAL FORMAT REQUIREMENT:**
   - List **exactly 5 citations** maximum per topic.
   - **MANDATORY FORMAT:** EVERY citation MUST follow this EXACT format: `>• [Article Title](URL) - (Publisher)`
   - **URL IS REQUIRED:** You MUST include the URL field from the provided data. DO NOT omit URLs under any circumstances.
   - **Priority 1 (Representative):**
     - **Condition A:** IF an article title contains **'Exclusive(단독)'**, you **MUST** select it as Reference #1.
     - **Condition B:** IF NO 'Exclusive' article exists, select the most important article from a **Major/Trusted Publisher** as Reference #1.
   - **Priority 2 (Diversity):** Subsequent citations must select articles with **DIFFERENT viewpoints/publisher types** from the first one. (e.g., if #1 is Foreign, #2 should be Domestic or Industry specialized).
5. **Negative Constraint:** NO generic advice ("Investors should monitor...").
6. **Merge Duplicates:** If related topics exist (e.g., 'Bond Yields Drop' and 'Fed Pivot Hopes'), **merge them into one single item**.

# Output Format
DO NOT output any section headers (like #, ##, ###). Start directly with the content.

### **[Strong Title in Korean]**
[3-Sentence Body Text in Korean]
>• [Article Title](URL) - (Publisher)
>• [Article Title](URL) - (Publisher)
"""
