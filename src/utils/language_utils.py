import re

def is_korean_article(title: str, publisher: str) -> bool:
    """
    주어진 기사 제목(title)과 출처(publisher)를 바탕으로 한국어 기사인지 여부를 판별하는 유틸리티.
    한국 언론사에 포함되거나 기사 제목에 한글이 포함되어 있는지 확인합니다.
    """
    kr_publishers = [
        "chosun", "dong-a", "joongang", "korea herald", "korea times",
        "maeil", "korea economic", "hankyung", "seoul economic", 
        "asia economic", "financial news", "herald economy",
        "businesswatch", "the bell", "korea financial times",
        "seoul finance", "e-today", "newspim", "moneytoday",
        "yonhap", "infomax", "news1", "newsis", "genews",
        "edaily", "digital times", "electronic times", "zdnet",
        "bloter", "byline", "sbs", "mbn", "ytn", "mk news",
        "조선", "동아", "중앙", "한국경제", "매일경제", "매경", "한경", 
        "서울경제", "아경", "아시아경제", "파이낸셜뉴스", "헤럴드경제", 
        "비즈니스워치", "더벨", "한국금융", "서울파이낸스", "이투데이", 
        "뉴스핌", "머니투데이", "이데일리", "연합", "인포맥스", "뉴스1", 
        "뉴시스", "전자신문", "디지털타임스", "지디넷", "블로터", 
        "바이라인", "sbs비즈", "매경tv", "mbn", "ytn", "naver"
    ]
    pub_lower = publisher.lower() if publisher else ""
    
    if any(kp in pub_lower for kp in kr_publishers):
        return True
    
    # Fallback: Check for Hangul in title
    if title and re.search(r'[가-힣]', title):
        return True
        
    return False
