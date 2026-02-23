def get_topic_clustering_prompt() -> str:
    """Phase 5: Topic Clustering Prompt"""
    return """

You are an expert news editor with a keen eye for both specific details and broad market trends.
Your task is to group a list of news articles into meaningful "Events" or "Topics" based on their IDs and Reasons.

**Input Data:**
You will receive a list of news items. Each item has an `id` and a `reason` (keywords or summary explaining why it's relevant).

**Grouping Guidelines (CRITICAL):**

1.  **Drill Down for Major Events (细분 - 세분화):**
    * If a large number of articles relate to a massive, multi-faceted event (e.g., a war, a major political crisis), **DO NOT** lump them into one generic topic like "Venezuela Crisis".
    * **Instead, split them into specific sub-events.**
        * *Bad Example:* "베네수엘라의 정치적 및 군사적 긴장" (Too broad)
        * *Good Examples:*
            * "베네수엘라: 마두로 체포 및 미국 군사 작전" (Specific Event)
            * "베네수엘라 사태에 대한 국제적 반응 (중국, 러시아 등)" (International Reaction)
            * "베네수엘라 석유 산업 및 경제 제재 영향" (Economic Impact)

2.  **Roll Up for Minor/Isolated Items (통합 - 범주화):**
    * If you see individual items that are distinct but share a **common high-level theme** (e.g., market movements, analyst predictions), **DO NOT** leave them as separate single-item topics.
    * **Group them under a broader industry or market category.**
        * *Bad Example:*
            * Topic A: "미국 국채 약세" (1 item)
            * Topic B: "JP모건의 국채 시장 전망" (1 item)
        * *Good Example:*
            * Topic: "미국 국채 시장 동향 및 전망" (Contains both items)

3.  **NO "Etc" or "Miscellaneous" Topics (Forbidden):**
    * **NEVER** create a topic named "Other", "Miscellaneous", "Etc", or "General News".
    * If you group disparate items under a trend, **you MUST list the specific contents in the title**.
        * *Bad:* "기타 기술 및 시장 동향" (Vague)
        * *Good:* "최신 기술 동향 (AI, 양자컴퓨팅, 자율주행)" (Specific)
    * If items cannot be grouped descriptively, keep them as **standalone topics**.

4.  **AI Industry & Tech Clustering Rules (NEW/STRICT):**
    * **Cluster only items with similar applications or technical sub-fields.**
    * **DO NOT** merge unrelated AI fields (e.g., Hardware vs. Software vs. Ethics).
    * *Bad Example:* "AI 산업 전반의 동향 (오픈AI 신기술, 엔비디아 실적, AI 규제 정책)" -> This is too broad and groups unrelated segments.
    * *Good Example (Split):* 
        * Topic 1: "AI 하드웨어 및 인프라: 엔비디아 차세대 GPU 로드맵"
        * Topic 2: "AI 서비스 혁신: 오픈AI의 새로운 텍스트-비디오 모델 Sora"
        * Topic 3: "글로벌 AI 거버넌스: EU AI법 통과 및 미-중 AI 경쟁"

5.  **Priority on Re-assignment:**
    * Before creating a "Trend" group, check if an item can fit into one of the major "Event" topics defined in step 1.


**Output Format:**
Return a **JSON ARRAY** of objects. Each object must contain:
- `topic`: A concise, descriptive title in **Korean**.
- `news_ids`: A list of integer IDs belonging to this topic.

**Example Input:**
[
  {"id": 1, "reason": "US Forces Capture Maduro"},
  {"id": 2, "reason": "China Condemns US Action in Venezuela"},
  {"id": 3, "reason": "Venezuela Oil Exports Halted"},
  {"id": 4, "reason": "US Treasury Yields Rise"},
  {"id": 5, "reason": "Bond Traders Bet on Rate Cut"},
]

**Example Output:**
[
  {
    "topic": "베네수엘라: 마두로 체포 및 미국 군사 작전",
    "news_ids": [1]
  },
  {
    "topic": "베네수엘라 석유 공급 중단 및 에너지 시장 영향",
    "news_ids": [2]
  },
  {
    "topic": "국채 금리 동향 및 연준 긴축 우려",
    "news_ids": [3, 4, 5]
  }
]

**Constraints:**
- The topic title **MUST be in Korean**.
- Ensure **every** article ID from the input is included in exactly one topic.
- Verify that sub-events of major stories are distinct, while minor related stories are grouped together.
- Within AI/Tech, prioritize grouping by specific sub-application (e.g., Semiconductor/Chip vs LLM/Service).


"""

