제공해주신 CSV 데이터(입력값)와 PDF 리포트(목표 결과물)를 바탕으로, Cursor(AI 코드 에디터)가 즉시 개발에 착수할 수 있도록 구체적인 **PRD(제품 요구사항 정의서)**를 작성해 드립니다.

이 PRD는 Python과 LLM(OpenAI GPT-4o 또는 Claude 3.5 Sonnet)을 활용하여 **뉴스 데이터를 분석하고, 중요도를 판단하여, 전문적인 금융 리포트 톤으로 요약 및 포맷팅하는 자동화 파이프라인**을 구축하는 것을 목표로 합니다.

---

# PRD: Daily Market Intelligence 자동 생성 시스템

## 1. 프로젝트 개요

* **프로젝트명:** Auto-DMI (Daily Market Intelligence) Generator
* **목표:** 뉴스 클리핑 데이터(topics.db)를 입력받아, LLM을 통해 중요 뉴스 선별 및 인사이트 요약을 수행한 뒤, 전문 애널리스트 수준의 일일 리포트(Markdown/PDF)를 자동 생성한다.
* **입력 데이터:** `topics.db` (카테고리, 토픽, 기사 수, 원문 제목, 출처 등 포함)
* **출력 데이터:** `Daily_Market_Intelligence_YYYY-MM-DD.md` (PDF 변환 가능한 마크다운 형식)

## 2. 기술 스택 (권장)

* **Language:**
* **Data Processing:**
* **AI Engine:** gemini 2.0 flash
* **Env Management:** `.env` (API Key 관리)

## 3. 기능 요구사항 (Functional Requirements)

### 3.1. 데이터 수집 및 전처리 (Data Ingestion)

1. **db:** `Category`, `Topic Title`, `News Count`, `Reason`, `Publisher`, `Title` 컬럼을 포함한 db 내용을 로드한다.
2. **데이터 정제:**

* `News Count`는 정수형으로 변환하여 정렬 기준으로 사용한다.
* `Reason`, `Publisher`, `Title` 컬럼 내의 개행 문자(`\n`, `-`)를 처리하여 리스트 형태로 파싱한다.

1. **카테고리 매핑:** CSV의 시스템 카테고리를 리포트 섹션명으로 매핑한다.

* `G_macro` → **2. Global > Global Macro**
* `G_market` → **1. Global > Market**
* `G_tech` → **2. Global > Tech**
* `G_region` → **2. Global > Region** (또는 별도 Region 섹션)
* `K_macro`, → **3. Korea > Macro** (내부에서 Macro/Market/Industry로 소분류)
* `K_market` → **3. Korea > Market** (내부에서 Macro/Market/Industry로 소분류)
* `K_industry` → **3. Korea > Industry** (내부에서 Macro/Market/Industry로 소분류)
* `RealEstate_G` → **4. Real Estate > Global**
* `RealEstate_K` → **4. Real Estate > Korea**

### 3.2. 콘텐츠 생성 로직 (LLM Processing)

시스템은 LLM에게 다음과 같은 단계로 프롬프트를 전송하여 원고를 작성해야 한다.

#### **Step 1: Key Takeaways 선정 및 작성**

* **로직:** 전체 데이터 중 `News Count`가 가장 높거나, `Category`가 `G_macro`, `G_market`인 항목 중 가장 파급력이 큰 이슈 3가지를 선정한다. 유사한 내용이 top3가 선정된다면, 하나로 묶고 여러 시선에서 분석한다.
ex) 베네수엘라: 석유 산업 및 경제 제재 영향, 베네수엘라: 마두로 체포 및 미국 군사 작전, 베네수엘라: 정치적 충격 및 국제적 반응
Top 3라면, 하나의 토픽으로 묶고 여러 시선에서 분석한다.
이후 파급력이 큰 것을 찾아서 top3로 추가한다.

* **출력 요건:**
* 각 항목은 굵은 제목과 2~3문장의 요약으로 구성.
* 요약은 단순 사실 나열이 아니라, **"배경/현상 → 원인 → 시장 영향/전망"** 구조의 인사이트를 포함해야 함.
* 관련 기사 출처 2~3개를 `Title (Publisher)` 형식으로 하단에 명기.

#### **Step 2: 섹션별 본문 작성**

* **구조:** Global Macro, Global Market, Global Tech, Global Region, Korea Macro, Korea Market, Korea Industry, Real Estate Global, Real Estate Korea 순서로 작성.
* **작성 기준:**
* 각 카테고리별로 `News Count`가 높은 상위 토픽 중 시장 임팩트가 큰 토픽일 3개 선정
* **제목:** 해당 토픽의 기사들을 종합하여 핵심을 찌르는 제목 (예: "미 연준(Fed) 유동성 경고" vs "연준 금리 이야기")
* **본문:** DB의 `Title`, 기사 본문을  종합하여 투자에 영향을 미칠 수 있는 인사이트를 포함한 투자자에게 유익한 내용으로 요약.
    요약은 단순 사실 나열이 아니라, **"배경/현상 → 원인 → 시장 영향/전망"** 구조의 인사이트를 포함해야 함.
* **출처:** 본문 바로 아래에 `• 기사제목 (언론사)` 포맷으로 기재. (영문 기사는 영문 유지, 국문 기사는 국문 유지)
    제목에 인링크로 기사 URL을 포함.

#### **Step 3: VIP/Breaking News (선택 사항)**

* `News Count`는 적더라도 기사 제목의 가장 앞에 Exclusive, breaking 등 키워드를 포함하는 기사들을 VIP/Breaking News로 묶어본다. (영어 기사만 해당)

### 3.3. 출력 포맷팅 (Output Generation)

생성된 텍스트는 **Obsidian 호환 Markdown**으로 저장되어야 하며, PDF 변환 시 깔끔하게 보이도록 다음 규칙을 따른다.

* **헤더:** `## 1. Key Takeaways`, `## 2. Macro` 등 계층 구조 사용.
* **강조:** 핵심 키워드나 수치는 볼드체(`**...**`) 처리할 것. (예: **사상 최대치**, **1,447원**)
* **출처 스타일:** 기사 링크는 제목에 인링크로 기사 URL을 포함하고, 텍스트로만 표기하되, 불렛 포인트(`•`)를 사용하여 가독성 확보.

## 4. 프롬프트 전략 (System Prompt Guide)

Cursor에게 코드를 짤 때 다음 **시스템 프롬프트**를 코드 내에 포함시키라고 지시하십시오.

```markdown
# Role
당신은 월스트리트의 시니어 마켓 애널리스트입니다. 제공된 뉴스 데이터를 바탕으로 기관 투자자를 위한 "Daily Market Intelligence" 리포트를 작성합니다.

# Tone & Manner
- 전문적이고 객관적이며 통찰력 있는 어조를 유지하십시오.
- "~함", "~임" 등의 개조식 어미 대신, "~했습니다.", "~전망입니다."와 같은 정중하지만 단호한 문체를 사용하되, 가독성을 위해 간결하게 끊어 쓰십시오.
- 단순한 사실 전달을 넘어, 해당 뉴스가 시장에 미칠 영향(Implication)을 한 문장 이상 반드시 포함하십시오.

# Writing Rules
1. **헤드라인:** 독자의 주의를 끌 수 있는 임팩트 있는 문구 사용.
2. **요약:** 제공된 'Title'과 스니펫 들을 종합하여 하나의 완성된 문단으로 재구성 (복사-붙여넣기 금지).
3. **참조:** 각 섹션 끝에는 반드시 근거가 된 기사 제목과 언론사를 명시. 포맷: `• 기사 제목 (언론사명)`


```

## 5. 입출력 예시

**Input (CSV Row Example):**

```db
Category: G_macro
Topic Title: 연준 금리 인하 신호
News Count: 4
Publisher: - Reuters - Bloomberg ...
Title: - Fed's Paulson signals another rate cut ...

```

Reason: - 정보는 빼고 보낸다. title만 가지고 파악
기사 중 가장 주요 기사 (신뢰도 높은 기사)는 본문 내용을 참고한다.
**Output (Markdown Example):**

```markdown
### 2. 미 연준(Fed) 금리 인하 신호 재점화
필라델피아 연은 총재 등 주요 위원들이 연내 추가 금리 인하 가능성을 시사했습니다. 이는 고금리 장기화에 대한 시장의 우려를 완화시키는 신호로, 국채 금리 안정화와 위험 자산 선호 심리 회복에 기여할 것으로 전망됩니다.
* Fed’s Paulson Says Additional Rate Cuts Possible Later This Year (Bloomberg)
* Philly Fed’s Paulson Sees Room for Cuts ‘Later in the Year’ (WSJ)

```

## 6. 개발 마일스톤 (Cursor 지시용)

1. **Step 1:** db파일을 읽고, 카테고리별로 데이터를 그룹화하여 JSON 객체로 변환하는 Python 스크립트 작성.
2. **Step 2:** gemini-2.0-flash를 연동하고, 위에서 정의한 `System Prompt`를 적용하여 섹션별(Key Takeaways, Macro, Tech 등)로 원고를 생성하는 함수 구현.
3. **Step 3:** 생성된 텍스트를 정해진 포맷의 Markdown 파일로 결합하고 저장하는 기능 구현.
4. **Step 4:** `Report_sample.pdf`의 스타일을 참고하여, Markdown 내의 공백, 볼드 처리, 계층 구조가 시각적으로 유사하도록 후처리 로직 추가.

---
