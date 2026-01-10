p4까지 진행되었음.

step1.
DB에 llm_decision,llm_category,llm_reason 을 참고하여 다음 작업을 위한 전처리 작업 진행

- llm_decision이 keep인 뉴스만 추출
- llm_category가 같은 뉴스끼리 묶고, llm_reason, title을 LLM에게 전달 한다. -> reason 만 넘겨주는 것으로 수정 완료.
- 그러면 LLM은 뉴스의 내용을 보고 구체적인 사건 단위로 분류.
- topic title과 news_id를 묶어서 DB에 저장. json 포맷

9개 카테고리에 대하여 모두 수행.

db 파일 새로 생성.
카테고리, llm이 생성한 topic title, 관련 뉴스 기사 id를 저장.

구글 스프레드 시트에는
카테고리, llm이 생성한 topic title, 관련 뉴스 기사 제목을 출력

step2.
step1에서 러프하게 묶은 결과를 한번 더 llm을 통해 정리한다.

step 2-1. 기사가 10개 이상 묶였다면, 너무 크게 묶이지 않았는지, 뷰에 따라 나눌 수 있는지 확인해본다.

step 2-2.
    1. 지금 묶는 단계에서는 global, korea, real estate 카테고리 내에서 묶을 수 있음.
      기사가 1개 또는 2개라면 topic title가 너무 상세한것은 아닌지, topic의 범위를 조금 더 넓게 보면 묶일 수 있는지 확인한다.
    2. 국채 시장 전망(topic)
        - 미국 국채 약세, 미국 국채 수익률 안정, jp 모건의 채권시장 전망. 기사의 내용이 좀 상반된다면, 이런의견도 있고, 이런 의견도 있다라로 설명해주면 좋을 것 같다.
    3. 주요 종목 동향 (topic)
        - 미국 주식 소매 투자 증가, ARK 핀테크 ETF 급등, AAOI 주식 급등, 항공우주 반도체 ETF 상승, 버크셔 주식 하락, 트럼프 미디어 공매도 관심
    4. 금 가격
        - 금, 은, 기타 금속 가격, 원자재 가격과 묶을 수 있음.
    5. 중국 AI HW 시장
        - 중국 AI 하드웨어 효율성 도약, 중국 시장에서의 AMD 확장 묶을 수 있음. (AMD가 AI HW 제공)

Step 2-3.
    1. 지엽적인 기사는 + 주요 언론사가 아닌 경우 삭제
    - HLB Management Overhaul
    - Eric Schmidt AI Venture

- NH Investment Large Loan Deal
- Apple M5 Max Performance
- US Army AI Officer Role
