"""
config.py — 환경 변수 통합 관리

모든 os.getenv 호출을 이 파일에서 관리합니다.
load_dotenv()는 여기서 한 번만 실행됩니다.

사용법:
    from config import GEMINI_API_KEY, NAVER_CLIENT_ID, ...
"""

import os
from dotenv import load_dotenv

load_dotenv()

# 데이터베이스
DB_HOST     = os.getenv("DB_HOST")
DB_PORT     = int(os.getenv("DB_PORT", "3306"))
DB_USER     = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME     = os.getenv("DB_NAME")

# Flask
SECRET_KEY = os.getenv("SECRET_KEY", "aiquant2024")

# AI / 분석
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 네이버 뉴스 API
NAVER_CLIENT_ID     = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

# 이메일 (회원가입 인증)
MAIL_EMAIL    = os.getenv("MAIL_EMAIL")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
