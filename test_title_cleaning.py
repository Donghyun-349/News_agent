# test_title_cleaning.py
import re
import html
import unittest

def normalize_title(title: str) -> str:
    """
    제목 정제 로직 테스트용 함수
    (src/processors/title_deduplicator.py 에 적용될 로직)
    """
    if not title:
        return ""
    
    # 1. HTML Unescape
    cleaned = html.unescape(title)
    
    # 2. 말머리 제거 (Regex)
    # [포토], [속보], [단독], [종합], [기획], [특징주], [현장], [인터뷰], [1보] 등
    # 대괄호 안의 단어가 2~4글자 한글이거나 숫자+보 인 경우
    # 예: [포토], [인터뷰], [1보], [2보] ...
    # 너무 광범위하게 잡으면 [삼성전자] 같은게 날아갈 수 있으므로 구체적으로 지정하거나
    # '뉴스 카테고리성' 키워드만 타겟팅.
    
    # User Request: [포토], [속보] 삭제 요청.
    # 추가: [단독], [종합], [기획], [특징주], [일문일답], [현장]
    keywords = "포토|속보|단독|종합|기획|특징주|현장|인터뷰|일문일답|영상|카드뉴스|그래픽|부고|인사|1보|2보|3보|상보"
    pattern = fr"^\[({keywords})\]\s*"
    
    # 반복해서 제거 (예: [속보] [단독] 제목)
    # 정규식으로 ^ 패턴을 쓰면 맨 앞 하나만 제거됨. loop 돌리거나 sub 한번.
    # sub로 처리하되, 맨 앞 부분만 매칭.
    
    # 루프를 돌면서 맨 앞에 매칭되는게 없을 때까지 제거?
    # 아니면 `^(\[({keywords})\]\s*)+` 패턴 사용
    full_pattern = fr"^(\[({keywords})\]\s*)+"
    
    cleaned = re.sub(full_pattern, "", cleaned)
    
    return cleaned.strip()

class TestTitleCleaning(unittest.TestCase):
    def test_basic_removal(self):
        self.assertEqual(normalize_title("[포토] 멋진 사진"), "멋진 사진")
        self.assertEqual(normalize_title("[속보] 큰일 났습니다"), "큰일 났습니다")
        self.assertEqual(normalize_title("[단독] 삼성전자 어쩌구"), "삼성전자 어쩌구")
    
    def test_nested_removal(self):
        self.assertEqual(normalize_title("[속보] [단독] 중첩된 말머리"), "중첩된 말머리")
        self.assertEqual(normalize_title("[종합] [현장] 기자의 눈"), "기자의 눈")
        
    def test_html_unescape(self):
        self.assertEqual(normalize_title("삼성이 &quot;갤럭시&quot; 출시"), '삼성이 "갤럭시" 출시')
        self.assertEqual(normalize_title("A &amp; B"), "A & B")
        self.assertEqual(normalize_title("&#39;따옴표&#39;"), "'따옴표'")

    def test_preserve_brackets(self):
        self.assertEqual(normalize_title("[삼성전자] 주가 상승"), "[삼성전자] 주가 상승")  # 키워드 아님
        self.assertEqual(normalize_title("[이슈] 이건 지우지 마"), "[이슈] 이건 지우지 마") # 키워드 목록에 없으면 유지? 이슈는 애매함. 일단 킵.
        self.assertEqual(normalize_title("기사 중간에 나오는 [포토]는 유지"), "기사 중간에 나오는 [포토]는 유지")

    def test_empty(self):
        self.assertEqual(normalize_title(""), "")
        self.assertEqual(normalize_title(None), "")

if __name__ == "__main__":
    unittest.main()
