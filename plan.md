뉴스 수집기를 만들거야.

1. 뉴스를 수집
    A. 수집 항목: 발행일, 제목, 스니펫, 발행기관, url
    -> sample 폴더의 main_n_p1.py 참고하여 동일하게 구현
2. 제목 중복 검사를 해서 중복 제거
    A. 중복은 제목 기준으로 하며, 동일한 것 제거.
    B. 제거 이후에 weight 값 유지
    C. 언론사 신뢰도 가장 높은 것을 남겨 놓음.
    -> sample 폴더의 main_n_p2.py 참고하여 동일하게 구현
3. 광고, 불필요한 키워드 검사 및 제거
    A. Rule base로 불필요한 키워드 제거
    -> sample 폴더의 main_n_p3.py 참고하여 동일하게 구현
4. LLM 통한 Tag 및 필터링
    A. 9개 tag 설정
        i. G_macro
        ii. G_market
        iii. G_tech
        iv. G_region
        v. RealEstate_G
        vi. RealEstate_K
        vii. K_macro
        viii. K_market
        ix. K_industry
    B. LLM은 검토후 리턴값을 보낸다. 카테고리와 간단한 이유. 설명 보다는 결론 위주로 결과값 리턴. 5단어 이내.
        i. Ex) noise, not relevant topic,

-> sample 폴더의 main_n_p4.py 참고하여 동일하게 구현
