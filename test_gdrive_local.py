#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Google Drive 업로드 로컬 테스트 스크립트
"""

import os
import sys
from pathlib import Path

# UTF-8 출력 설정 (Windows 콘솔 호환)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 프로젝트 루트 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.exporters.gdrive import GDriveAdapter

def main():
    print("=" * 80)
    print("🧪 Google Drive Upload Test (Local)")
    print("=" * 80)
    
    # 1. 테스트 파일 생성
    test_file = "test_upload.txt"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("This is a test file for Google Drive upload.\n")
        f.write(f"Created at: {os.environ.get('COMPUTERNAME', 'Local Machine')}\n")
    
    print(f"✅ Created test file: {test_file}")
    
    # 2. Folder ID 확인 (환경 변수 또는 기본값)
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "1cz9Jf5xlZeJN190s5Pt7yQqmqkzop6JH")
    print(f"📁 Target Folder ID: {folder_id}")
    
    # 3. GDrive Adapter 초기화 및 업로드
    try:
        adapter = GDriveAdapter()
        print("\n🔑 Authenticating with Google Drive...")
        adapter.authenticate()
        
        print("\n📤 Uploading test file...")
        file_id = adapter.upload_file(
            file_path=test_file,
            folder_id=folder_id,
            mime_type="text/plain"
        )
        
        if file_id:
            print(f"\n✅ SUCCESS! File uploaded successfully")
            print(f"   File ID: {file_id}")
            print(f"   View at: https://drive.google.com/file/d/{file_id}/view")
        else:
            print("\n❌ FAILED! Upload returned None")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 4. 테스트 파일 정리
        if os.path.exists(test_file):
            os.remove(test_file)
            print(f"\n🧹 Cleaned up test file: {test_file}")
    
    print("\n" + "=" * 80)
    print("Test Complete")
    print("=" * 80)

if __name__ == "__main__":
    main()
