
# utils/helpers.py — 공통 유틸리티 함수

# 여러 모듈에서 공유하는 순수 함수들을 모아둡니다.
# 외부 의존성(DB, API) 없이 입력값만으로 동작합니다.


import re
import html
import math
from urllib.parse import urlparse


def strip_html(text):
    # 뉴스 제목/내용에 섞인 HTML 태그를 제거합니다.
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text).strip()


def extract_source_name(link):
    # 뉴스 원문 URL에서 언론사 도메인을 추출합니다.
    try:
        netloc = urlparse(link).netloc.lower()
    except Exception:
        return "뉴스"
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc if netloc else "news"


def nan_to_none(val):
    """pandas NaN을 JSON 직렬화 가능한 None으로 변환합니다."""
    try:
        if val is None:
            return None
        if isinstance(val, float) and math.isnan(val):
            return None
        return val
    except Exception:
        return None
