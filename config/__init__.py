"""Configuration module"""

# .env 파일 자동 로드
try:
    from dotenv import load_dotenv
    from pathlib import Path
    
    # 프로젝트 루트에서 .env 파일 로드
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
    else:
        # .env 파일이 없으면 현재 디렉토리에서 시도
        load_dotenv(override=False)
except ImportError:
    # python-dotenv가 없어도 환경 변수는 작동함
    pass








