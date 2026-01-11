import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# 권한 범위 (전체 Drive 접근 - 파일 업로드/다운로드)
SCOPES = ['https://www.googleapis.com/auth/drive']

def main():
    print("="*60)
    print("🔐 Google Drive OAuth 2.0 Token Generator")
    print("="*60)
    print("이 스크립트는 로컬에서 사용자의 구글 계정으로 로그인하여")
    print("GitHub Actions에서 사용할 'token.json'을 생성합니다.\n")

    client_secrets_file = "credentials/client_secret.json"
    
    if not os.path.exists(client_secrets_file):
        print(f"❌ '{client_secrets_file}' 파일이 없습니다!")
        print("1. Google Cloud Console > APIs & Services > Credentials")
        print("2. [+ CREATE CREDENTIALS] > OAuth client ID")
        print("3. Application type: 'Desktop app'")
        print("4. JSON 다운로드 후 'credentials/client_secret.json'으로 저장해주세요.")
        return

    creds = None
    # 기존 토큰이 있다면 로드 (갱신용)
    if os.path.exists('credentials/token.json'):
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file('credentials/token.json', SCOPES)

    # 유효하지 않으면 새로 로그인
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 토큰 갱신 중...")
            creds.refresh(Request())
        else:
            print("🌐 브라우저를 열어 로그인을 진행합니다...")
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 저장
        with open('credentials/token.json', 'w') as token:
            token.write(creds.to_json())
            
    print("\n✅ 인증 성공! 'credentials/token.json' 파일이 생성되었습니다.")
    print("\n[다음 단계]")
    print("1. 'credentials/token.json' 파일을 메모장으로 여세요.")
    print("2. 전체 내용을 복사하세요.")
    print("3. GitHub Repository > Settings > Secrets and variables > Actions")
    print("4. New repository secret 클릭")
    print("   - Name: GOOGLE_TOKEN_JSON")
    print("   - Value: (복사한 내용 붙여넣기)")
    print("="*60)

if __name__ == '__main__':
    main()
