# 📂 Google Drive Integration Guide (OAuth 2.0 User Credentials)

이 가이드는 Python 프로젝트에서 구글 드라이브에 파일을 자동으로 업로드하는 기능을 구현하는 방법을 설명합니다.
특히 **Service Account(서비스 계정)**의 저장 용량 문제(기본 0-15GB 공유 제한)를 해결하기 위해 **OAuth 2.0 User Credentials(사용자 인증)** 방식을 사용합니다.

이 방식은 로컬에서 한 번 로그인하여 토큰을 생성하고, 이를 GitHub Secrets에 저장하여 CI/CD(GitHub Actions)에서 내 계정의 구글 드라이브에 파일을 업로드할 수 있게 합니다.

---

## ✅ 1. 준비 사항 (Prerequisites)

### 1.1 Google Cloud Platform (GCP) 프로젝트 설정

1. [Google Cloud Console](https://console.cloud.google.com/)에 접속합니다.
2. 새 프로젝트를 생성하거나 기존 프로젝트를 선택합니다.
3. **APIs & Services > Library** 메뉴로 이동합니다.
4. `Google Drive API`를 검색하고 **Enable(사용 설정)**합니다.

### 1.2 OAuth Consent Screen (동의 화면) 설정

1. **APIs & Services > OAuth consent screen** 메뉴로 이동합니다.
2. **User Type**을 **External(외부)**로 선택하고 만들기 클릭.
3. 앱 이름(예: `MyDriveUploader`), 사용자 지원 이메일 등을 입력하고 저장합니다.
4. **Test users(테스트 사용자)** 단계에서 본인의 구글 계정 이메일(업로드할 계정)을 추가합니다.
   - *이 단계가 중요합니다! 테스트 사용자로 등록되지 않으면 인증 시 403 오류가 발생할 수 있습니다.*

### 1.3 OAuth Client ID 생성

1. **APIs & Services > Credentials** 메뉴로 이동합니다.
2. **+ CREATE CREDENTIALS** > **OAuth client ID**를 선택합니다.
3. **Application type**을 **Desktop app(데스크톱 앱)**으로 선택합니다.
4. 이름을 입력하고 생성합니다.
5. 생성된 **Client ID**와 **Client Secret**이 있는 팝업에서 **Download JSON**을 클릭하여 다운로드합니다.
6. 파일 이름을 `client_secret.json`으로 변경하고 프로젝트의 `credentials/` 폴더(없으면 생성)에 저장합니다.
   - *주의: `credentials/` 폴더는 `.gitignore`에 포함하여 Git에 올라가지 않도록 하세요.*

---

## 💻 2. 개발 환경 설정 & 토큰 생성

### 2.1 필요한 라이브러리 설치

`requirements.txt`에 다음 패키지를 추가하거나 설치합니다.

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 2.2 폴더 구조 생성

```
my_project/
├── credentials/          # .gitignore 등록 필수
│   ├── client_secret.json
│   └── token.json        # 스크립트로 생성될 파일
├── src/
│   └── exporters/
│       └── gdrive.py     # 어댑터 모듈
├── generate_drive_token.py # 토큰 생성 스크립트
└── test_gdrive_upload.py # 테스트 스크립트
```

### 2.3 토큰 생성 스크립트 (`generate_drive_token.py`)

이 스크립트는 로컬에서 브라우저를 띄워 로그인을 진행하고, 결과물인 `token.json`을 생성합니다.

```python
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# 권한 범위 (파일 열람, 생성, 편집)
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def main():
    print("="*60)
    print("🔐 Google Drive OAuth 2.0 Token Generator")
    print("="*60)

    client_secrets_file = "credentials/client_secret.json"
    
    if not os.path.exists(client_secrets_file):
        print(f"❌ '{client_secrets_file}' 파일이 없습니다!")
        return

    creds = None
    if os.path.exists('credentials/token.json'):
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file('credentials/token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 토큰 갱신 중...")
            creds.refresh(Request())
        else:
            print("🌐 브라우저를 열어 로그인을 진행합니다...")
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 저장
        os.makedirs('credentials', exist_ok=True)
        with open('credentials/token.json', 'w') as token:
            token.write(creds.to_json())
            
    print("\n✅ 인증 성공! 'credentials/token.json' 파일이 생성되었습니다.")

if __name__ == '__main__':
    main()
```

### 2.4 토큰 생성 실행

터미널에서 다음 명령어를 실행하고 구글 로그인 프로세스를 완료하세요.

```bash
python generate_drive_token.py
```

성공하면 `credentials/token.json` 파일이 생성됩니다.

---

## 🛠️ 3. 코드 구현 (Google Drive Adapter)

### 3.1 `src/exporters/gdrive.py`

환경변수 `GOOGLE_TOKEN_JSON`을 통해 인증 정보를 로드하거나, 로컬의 서비스 계정 파일을 사용하는 하이브리드 어댑터입니다.

```python
import os
import logging
import json
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

class GDriveAdapter:
    def __init__(self, service_account_path: str = None):
        self.creds = None
        self.service = None
        self.service_account_path = service_account_path or os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", "credentials/service_account.json")
        self.scopes = ['https://www.googleapis.com/auth/drive.file']

    def authenticate(self):
        """Authenticate with Google Drive API (Service Account or OAuth Token)"""
        if self.service:
            return

        # 1. Try OAuth Token (User Credentials) - For Personal Drive Uploads (GitHub Actions)
        token_json_str = os.getenv("GOOGLE_TOKEN_JSON")
        if token_json_str:
            try:
                # Check if it's a file path or direct JSON string
                if os.path.isfile(token_json_str):
                    self.creds = Credentials.from_authorized_user_file(token_json_str, self.scopes)
                else:
                    info = json.loads(token_json_str)
                    self.creds = Credentials.from_authorized_user_info(info, self.scopes)
                
                self.service = build('drive', 'v3', credentials=self.creds)
                logger.info("✅ Google Drive Authenticated (User OAuth)")
                return
            except Exception as e:
                logger.warning(f"⚠️ Failed to auth with GOOGLE_TOKEN_JSON: {e}")

        # 2. Fallback to Service Account
        if os.path.exists(self.service_account_path):
            try:
                self.creds = service_account.Credentials.from_service_account_file(
                    self.service_account_path, scopes=self.scopes
                )
                self.service = build('drive', 'v3', credentials=self.creds)
                logger.info("✅ Google Drive Authenticated (Service Account)")
                return
            except Exception as e:
                logger.error(f"❌ Service Account Auth Failed: {e}")
                
        if not self.service:
            raise Exception("No valid Google Drive credentials found.")

    def upload_file(self, file_path: str, folder_id: str, mime_type: str = None) -> str:
        """Upload a file to a specific Google Drive folder"""
        if not self.service:
            self.authenticate()

        filename = os.path.basename(file_path)
        metadata = {'name': filename, 'parents': [folder_id]}
        media = MediaFileUpload(file_path, mimetype=mime_type)

        try:
            file = self.service.files().create(
                body=metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = file.get('id')
            logger.info(f"📤 Uploaded to Drive: {filename} (ID: {file_id})")
            return file_id
        except Exception as e:
            logger.error(f"❌ Failed to upload {filename}: {e}")
            return None
```

---

## 🚀 4. GitHub Actions 설정

### 4.1 Secret 등록

1. 로컬에서 생성된 `credentials/token.json` 파일을 열어 **전체 내용을 복사**합니다.
2. GitHub 저장소 > **Settings** > **Secrets and variables** > **Actions**로 이동합니다.
3. **New repository secret**을 클릭합니다.
   - **Name**: `GOOGLE_TOKEN_JSON`
   - **Value**: (복사한 JSON 내용 붙여넣기)
4. 업로드할 구글 드라이브 폴더의 ID를 구합니다. (브라우저 주소창의 `drive/u/0/folders/...` 뒤에 있는 문자열)
5. **New repository secret** 추가:
   - **Name**: `GOOGLE_DRIVE_FOLDER_ID`
   - **Value**: (폴더 ID)

### 4.2 Workflow 예시 (`.github/workflows/daily_run.yml`)

```yaml
name: Daily Run
on:
  schedule:
    - cron: '0 23 * * *' # KST 08:00 (UTC 23:00)

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run Pipeline
        env:
          GOOGLE_TOKEN_JSON: ${{ secrets.GOOGLE_TOKEN_JSON }}
          GOOGLE_DRIVE_FOLDER_ID: ${{ secrets.GOOGLE_DRIVE_FOLDER_ID }}
        run: python main.py
```

---

## ❓ FAQ 및 트러블슈팅

**Q1. `RefreshError: Token has been expired or revoked` 오류가 발생해요.**

- `token.json` 안에는 `refresh_token`이 포함되어 있어 자동으로 갱신됩니다. 하지만 토큰을 생성할 때의 상태(앱이 'Testing' 모드인 경우, 토큰 유효기간이 7일로 제한됨)에 따라 만료될 수 있습니다.
- **해결책**: GCP Console > OAuth consent screen에서 **Publishing status**를 **Production(프로덕션)**으로 변경하세요. (인증 확인 필요 없음으로 넘어가면 됨). 이렇게 하면 Refresh Token이 만료되지 않습니다.

**Q2. `403 Forbidden` 오류가 발생해요.**

- 해당 구글 계정이 GCP 프로젝트의 **Test users** 목록에 추가되어 있는지 확인하세요.
- 또는 `gdrive.py`에서 `SCOPES`가 일치하는지 확인하세요.

**Q3. 파일을 덮어쓰고 싶어요.**

- 현재 코드는 새 파일을 생성합니다(`create`). 덮어쓰려면 `list`로 같은 이름의 파일 ID를 찾은 후 `update` 메서드를 사용하도록 코드를 수정해야 합니다.

---
*Generated by Antigravity Agent*
