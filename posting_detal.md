
어차피 `Executive Summary`가 그날의 **가장 중요한 3가지 팩트**를 요약해 놓은 것이니까요. 이걸 그대로 AI에게 던져주고, 우리가 원하는 **'정석형 템플릿'**에 맞춰서 키워드만 갈아 끼우게 시키면 됩니다.

이렇게 하면 복잡하게 전체 데이터를 다 뒤질 필요 없이, 아주 적은 토큰(비용)으로 완벽한 제목을 뽑을 수 있습니다.

---

### 🛠️ 구현 로직 (Logic Flow)

1. **Input (JSON):** PDF에서 추출한 `Executive Summary` 리스트 (3줄).
2. **Processing (LLM):** AI에게 3문장을 주고, 각각을 **'핵심 단어(5글자 내외)'**로 요약하라고 시킴.
3. **Output (Title):** 요약된 단어를 `[날짜 브리핑] {1번}! {2번}와 {3번}` 공식에 대입.

---

### 💻 파이썬 코드 (Python Code)

바로 쓰실 수 있도록 코드를 짜드렸습니다.

```python
import openai
from datetime import datetime
import json

# 1. 가정: PDF에서 추출되어 JSON으로 저장된 Executive Summary 데이터
# (실제로는 파일에서 로드하시면 됩니다)
daily_data = {
    "date": "2026-01-28",
    "executive_summary": [
        "1. 코스피, 사상 첫 5,000선 돌파 및 시총 4,200조원 신기록 달성",
        "2. 연준, 금리 동결 예상 속 올해 50bp 인하 전망 우세 및 차기 의장 후보 거론",
        "3. 엔비디아의 AI 인프라 장악력 강화, 낸드플래시 산업의 위상 변화 예고"
    ]
}

def generate_standard_title(data):
    # 날짜 포맷팅 (2026-01-28 -> 1/28)
    date_obj = datetime.strptime(data['date'], "%Y-%m-%d")
    formatted_date = date_obj.strftime("%-m/%-d") # 윈도우는 text_date.strftime("%#m/%#d")
    
    summary_text = "\n".join(data['executive_summary'])

    # 2. 프롬프트: 3가지 요약 문장을 '단어'로 압축해달라고 요청
    system_prompt = """
    너는 금융 뉴스 편집자다. 
    제공된 3개의 요약 문장을 보고, 제목에 들어갈 '핵심 키워드' 3개를 추출해라.
    
    [규칙]
    1. 각 문장을 2~4단어 이내의 명사형으로 요약할 것. (조사 생략)
    2. 자극적이지 않고 드라이한 팩트 위주로.
    3. JSON 형식으로 반환: {"main": "1번요약", "sub1": "2번요약", "sub2": "3번요약"}
    """

    user_prompt = f"""
    [요약 문장들]
    {summary_text}
    """

    # 3. AI 호출
    response = openai.ChatCompletion.create(
        model="gpt-4-turbo", # 혹은 gpt-3.5-turbo (충분함)
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.3 # 창의성 낮게 (팩트 중심)
    )

    # 4. 결과 파싱 및 조립
    keywords = json.loads(response.choices[0].message.content)
    
    # 5. 정석형 템플릿 적용
    # 포맷: [날짜 브리핑] {Main}! {Sub1}와 {Sub2}
    final_title = f"[{formatted_date} 브리핑] {keywords['main']}! {keywords['sub1']}와 {keywords['sub2']}"
    
    return final_title

# --- 실행 결과 확인 ---
title = generate_standard_title(daily_data)
print(title)

```

---

### 📊 예상 출력 결과

AI가 내부적으로 이렇게 요약할 겁니다:

* 문장 1 (코스피 5000...) -> **"코스피 5,000 돌파"**
* 문장 2 (연준 금리...) -> **"연준 금리 동결"** (또는 50bp 인하)
* 문장 3 (엔비디아...) -> **"엔비디아 독주"** (또는 낸드 위상 변화)

**최종 완성된 제목:**

> **[1/28 브리핑] 코스피 5,000 돌파! 연준 금리 동결와 엔비디아 독주**

*(조사 '와/과' 처리가 한국어 특성상 어색할 수 있는데, 파이썬 라이브러리 `josa`를 쓰거나, 프롬프트에서 "자연스럽게 연결되도록 조사 포함해서 출력해"라고 하면 해결됩니다.)*

### 💡 이 방식의 장점

1. **일관성:** 매일 다른 뉴스가 와도 제목 형식이 `[날짜] 대장! 부대장1과 부대장2`로 딱 떨어집니다.
2. **가성비:** 긴 뉴스 전문을 다 넣을 필요 없이 딱 3줄만 처리하므로 API 비용이 매우 저렴합니다.
3. **정확성:** `Executive Summary`는 이미 한 번 정제된 정보라, 엉뚱한 제목이 나올 확률이 0에 가깝습니다.
