# [파일 역할] 애플리케이션 환경 변수 및 설정값을 통합 관리하는 모듈
# - 모든 os.getenv 호출을 이 파일에서 집중 관리하여 가독성 및 유지보수성 향상
# - load_dotenv()를 통해 .env 파일의 변수를 시스템 환경 변수로 로드

import os
from dotenv import load_dotenv

# 1. 환경 변수 로드 실행 (.env 파일을 시스템 환경 변수로 로드)
load_dotenv()

# ──────────────────────────────────────────────
# 데이터베이스 접속 설정 (Database Configuration)
# ──────────────────────────────────────────────

# 2. MariaDB/MySQL 연결 정보 로드
DB_HOST     = os.getenv("DB_HOST")
DB_PORT     = int(os.getenv("DB_PORT", "3306"))
DB_USER     = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME     = os.getenv("DB_NAME")

# ──────────────────────────────────────────────
# 프레임워크 및 외부 API 설정 (App & Service Keys)
# ──────────────────────────────────────────────

# 3. Flask 세션 관리 및 보안을 위한 시크릿 키
SECRET_KEY = os.getenv("SECRET_KEY", "aiquant2024")

# 4. 분석 엔진 활용을 위한 Google Gemini AI API 키
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 5. 실시간 뉴스 수집용 네이버 검색 API 인증 정보
NAVER_CLIENT_ID     = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

# ──────────────────────────────────────────────
# 이메일 발송 설정 (Email SMTP Service)
# ──────────────────────────────────────────────

# 6. 회원가입 본인 인증을 위한 발신 전용 이메일 계정 정보
MAIL_EMAIL    = os.getenv("MAIL_EMAIL")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")