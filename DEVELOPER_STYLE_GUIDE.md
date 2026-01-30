# 🎨 Blog Post Formatting Implementation Guide

이 가이드는 **랜선 애널리스트 블로그 게시물**의 일관된 디자인과 포맷팅을 다른 프로그램이나 플랫폼에서도 동일하게 구현하기 위한 개발자 가이드입니다.

---

## 1. 디자인 철학 (Design Philosophy)

* **Clean & Professional**: 가독성을 최우선으로 하며, 불필요한 장식을 배제합니다.
* **Green & Gray Theme**: 신뢰감을 주는 녹색(`#2E7D32`)과 모던한 회색(`#333333`, `#666666`)을 주조색으로 사용합니다.
* **Card-Based Layout**: 핵심 요약, 코멘트 등은 카드 형태의 레이아웃으로 시각적 구분을 둡니다.
* **Inline Styling**: WordPress 등 다양한 플랫폼 호환성을 위해 **모든 스타일은 Inline CSS**로 주입합니다.

---

## 2. 컬러 팔레트 (Color Palette)

모든 UI 요소는 아래의 정의된 색상 상수를 참조하여야 합니다.

| 변수명 | 색상 코드 | 용도 |
|:---:|:---:|:---|
| `primary` | `#2E7D32` (진한 녹색) | **제목(H1, H2..)**, 강조선, 주요 아이콘 |
| `primary_light` | `#4CAF50` (밝은 녹색) | **랜선 브리핑 블릿**, 인용구 테두리 |
| `primary_bg` | `#E8F5E9` (민트 배경) | 인용구/박스 배경 그라디언트 시작 |
| `text_primary` | `#333333` (진한 회색) | **본문 텍스트**, **본문 리스트 블릿** |
| `text_secondary`| `#666666` (연한 회색) | **볼드(Bold) 텍스트**, 부가 설명 |
| `border` | `#E0E0E0` (연한 회색) | 구분선, 테이블 테두리 |
| `accent` | `#FF9800` (주황색) | **랜선 애널리스트 코멘트** 테두리 |
| `warning` | `#F57C00` (진한 주황색) | disclaimer 제목, 코멘트 제목 |

### 💻 Python Dictionary 예시

```python
COLORS = {
    'primary': '#2E7D32',       # Dark green
    'primary_light': '#4CAF50', # Light green
    'primary_bg': '#E8F5E9',    # Mint background
    'primary_bg_alt': '#D5F4E6',
    
    'secondary': '#1976D2',     # Blue (Links)
    'secondary_light': '#42A5F5',
    
    'accent': '#FF9800',        # Orange
    'accent_bg': '#FFF3E0',
    
    'warning': '#F57C00',       # Dark orange
    'warning_bg': '#FFF8E1',
    
    'text_dark': '#1B5E20',     # Dark green text
    'text_primary': '#333333',  # Main Body Text
    'text_secondary': '#666666',# Bold Text
    
    'bg_light': '#F5F5F5',
    'bg_white': '#FFFFFF',
    'border': '#E0E0E0',
}
```

---

## 3. 타이포그래피 (Typography)

폰트 크기와 스타일 규칙은 **엄격하게** 준수해야 합니다. 특히 모든 제목 크기는 **20px**로 통일되었습니다(H1 제외).

| 태그 | 폰트 크기 | 스타일 규칙 | CSS 속성 예시 |
|:---:|:---:|:---|:---|
| **H1** | 28px | `#2E7D32`, 800 weight, 하단 3px 선 | `border-bottom: 3px solid #4CAF50;` |
| **H2** | 20px | `#2E7D32`, 700 weight, 하단 2px 선 | `border-bottom: 2px solid #4CAF50;` |
| **H3** | 20px | `#2E7D32`, 600 weight, 밑줄 없음 | `margin: 20px 0 12px 0;` |
| **H4** | 20px | `#2E7D32`, 600 weight, 하단 2px 선 | **H2와 동일한 스타일 적용** |
| **P** | 16px | `#333333`, line-height 1.8 | `line-height: 1.8; margin: 0 0 16px 0;` |
| **Strong**| - | `#666666` (회색), 700 weight | `color: #666666; font-weight: 700;` |

---

## 4. 리스트(Lists) & 블릿 포인트 스타일

리스트는 **위치**에 따라 다른 스타일을 가집니다.

### A. 랜선 브리핑 (Briefing Box)

* **블릿 색상**: 🟢 `COLORS['primary_light']` (#4CAF50)
* **줄 간격**: `1.4` (약간 좁게)
* **HTML 구조**:

    ```html
    <div style="position: relative; padding-left: 24px; margin: 4px 0; line-height: 1.4;">
        <span style="position: absolute; left: 0; top: 0; color: #4CAF50; font-weight: bold; font-size: 18px;">•</span>
        {내용}
    </div>
    ```

### B. 본문 리스트 (Body Content)

* **블릿 색상**: ⚫ `COLORS['text_primary']` (#333333)
* **줄 간격**: `1.8`
* **구현 방법**: `<ul>` 태그 내 `<li>`의 기본 마커를 제거하고 `<span>`으로 블릿을 직접 주입합니다.

    ```python
    # BeautifulSoup 구현 예시
    bullet = soup.new_tag('span', style=f"position: absolute; left: 12px; color: {COLORS['text_primary']}; font-weight: bold; font-size: 20px;")
    bullet.string = '•'
    li.insert(0, bullet)
    ```

---

## 5. 주요 컴포넌트 명세 (Components Specs)

### ⚡ 랜선 브리핑 (Summary Box)

그라디언트 배경과 굵은 왼쪽 테두리가 특징입니다.

* **배경**: `linear-gradient(135deg, #E8F5E9 0%, #D5F4E6 100%)`
* **테두리**: `border-left: 5px solid #4CAF50`
* **그림자**: `box-shadow: 0 2px 8px rgba(0,0,0,0.1)`
* **Padding**: `24px 28px`

### 💡 애널리스트 코멘트 (Footer)

주황색 테마를 사용합니다. 제목과 내용 사이의 **여백(margin)을 0으로 설정**하여 밀착시킵니다.

* **배경**: `linear-gradient(to right, #FFF3E0, #FFFFFF)`
* **테두리**: `border-left: 4px solid #FF9800`
* **제목 스타일**: `color: #F57C00; margin-bottom: 0;` (중요: margin-bottom 0)

### ⚠️ 면책 조항 (Disclaimer)

하단에 위치하며 옅은 주황색 배경을 가집니다.

* **배경**: `linear-gradient(to right, #FFF8E1, #FFFFFF)`
* **테두리**: `border-left: 4px solid #FF9800`

---

## 6. 구현 로직 (Implementation Logic)

### 1단계: 마크다운 전처리 (Setext Heading Fix)

마크다운의 Horizontal Rule (`---`)이 제목으로 오인되는 것을 방지하기 위해, 내용과 `---` 사이에 강제로 빈 줄을 삽입해야 합니다.

```python
lines = text.split('\n')
processed = []
for i, line in enumerate(lines):
    # 이전 줄에 내용이 있고 현재 줄이 구분선이면 빈 줄 추가
    if line.strip() in ['---', '***', '___'] and i > 0 and lines[i-1].strip():
        processed.append('')
    processed.append(line)
text = '\n'.join(processed)
```

### 2단계: 스타일 주입 (Style Injection)

`BeautifulSoup` 등을 사용하여 HTML 태그를 순회하며 인라인 스타일을 적용합니다.

```python
def apply_styles(html):
    soup = BeautifulSoup(html, 'html.parser')
    
    # 예: 모든 H2 태그에 스타일 적용
    for h2 in soup.find_all('h2'):
        h2['style'] = STYLES['h2']
        
    # 예: H4 태그 (마치며 등)에도 H2와 유사한 테두리 적용
    for h4 in soup.find_all('h4'):
        h4['style'] = "color: #2E7D32; font-size: 20px; font-weight: 600; padding-bottom: 8px; border-bottom: 2px solid #4CAF50;"

    return str(soup)
```

### 3단계: 넘버링 리스트 변환 (Numbered List to Bullets)

`1.`, `2.` 등으로 시작하는 텍스트를 감지하여 커스텀 블릿 포맷으로 변환합니다.

```python
if re.match(r'^\d+\.\s+', line):
    content = re.sub(r'^\d+\.\s+', '', line) # 숫자 제거
    # 여기서 마크다운 변환 및 스타일 적용
    output = f'<div style="..."><span style="top: 0; color: #4CAF50;">•</span>{content}</div>'
```

---

## 7. 체크리스트 (Verification Checklist)

구현 후 다음 사항을 반드시 확인하세요.

* [ ] **H1**을 제외한 모든 제목(H2, H3, H4)의 크기가 **20px**인가?
* [ ] **H2**와 **H4**에 녹색 하단 구분선이 있는가?
* [ ] **본문(bold)** 텍스트가 회색(`#666666`)으로 표시되는가?
* [ ] **랜선 브리핑**의 블릿은 **녹색**, **본문**의 블릿은 **검은색**인가?
* [ ] 블릿 포인트가 텍스트의 **맨 위(top: 0)**에 정렬되어 있는가?
* [ ] **애널리스트 코멘트**의 제목과 내용 사이에 불필요한 공백이 없는가?
* [ ] `---` 구분선 바로 윗줄의 텍스트가 거대하게(제목으로) 변하지 않는가?
