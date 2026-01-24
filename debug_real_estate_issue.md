# Real Estate 섹션 "특이사항 없음" 문제 분석

## 발견 사항

### 1. DB에는 Real Estate topic이 존재

- **Real_G (Global)**: 2개 topic
  - ID=560: "미국 부동산: 회복, 안정 및 대출"
  - ID=561: "주택 임대"
- **Real_K (Korea)**: 1개 topic
  - ID=562: "한국 부동산: 트렌드, 정책 및 트렌드"

### 2. 기사는 LLM에 전달됨

로그 확인:

```
[Real Estate > Global] Sending 7 articles to LLM (URLs stripped)
[Real Estate > Korea] Sending 5 articles to LLM (URLs stripped)
```

### 3. 하지만 결과는 "특이사항 없음"

이는 `process_section_task` 함수의 Line 351-352:

```python
if not topic_ids:
    return section_name, "특이사항 없음."
```

**결론**: **Topic Selection 단계에서 LLM이 Real Estate topic을 선택하지 않음**

---

## 근본 원인

### Topic Selection Prompt 문제

현재 프롬프트 (`get_topic_selection_prompt`):

```
## 2. Section Picks (각 섹션별 대표 이슈) 선별
- **기준:** 각 섹션(c)별로 가장 중요한 토픽 상위 3개.
- **개수:** 각 섹션 당 정확히 3개 (단, 해당 섹션의 토픽이 3개 미만이면 전체 포함).
```

**문제점:**

1. LLM에게 전달되는 topic 메타데이터에서 **카테고리가 `Real_G`, `Real_K` 형태**
2. 프롬프트 예시에는 **"Global > Macro", "Korea > Market"** 같은 long name 사용
3. LLM이 short code와 full name의 매핑을 이해하지 못함
4. 결과적으로 LLM이 Real Estate를 **별도 섹션으로 인식하지 못함**

### 증거

`run_p6.py` Line 766-772:

```python
selection_input_list.append({
    "i": tm['id'],
    "c": tm['category'],  # ← 여기가 'Real_G', 'Real_K'
    "t": tm['topic_title'],
    "n": tm['count']
})
```

`run_p6.py` Line 753:

```python
"category": t_meta['original_category'],  # ← Short code 사용
```

---

## 해결 방안

### 옵션 1: Display Category 사용 (추천)

**수정 위치**: `run_p6.py` Line 753

**현재:**

```python
topic_metadata_list.append({
    "id": t_meta['id'],
    "category": t_meta['original_category'],  # 'Real_G'
    "topic_title": t_meta['title'],
    "count": t_meta['count']
})
```

**수정 후:**

```python
topic_metadata_list.append({
    "id": t_meta['id'],
    "category": t_meta['display_category'],  # 'Real Estate > Global'
    "topic_title": t_meta['title'],
    "count": t_meta['count']
})
```

**장점:**

- ✅ LLM이 섹션 이름을 명확히 인식
- ✅ 프롬프트 예시와 일치
- ✅ 코드 수정 1줄로 해결

---

### 옵션 2: Prompt에 Short Code 매핑 추가

프롬프트에 카테고리 매핑 테이블 추가:

```
# Category Codes:
- G_mac = Global > Macro
- Real_G = Real Estate > Global
- Real_K = Real Estate > Korea
... (전체 매핑 테이블)
```

**단점:**

- ⚠️  프롬프트가 길어짐
- ⚠️  토큰 낭비
- ⚠️  유지보수 어려움

---

## 권장 수정

**옵션 1 (Display Category 사용)**을 적용하는 것이 가장 간단하고 효과적입니다.
