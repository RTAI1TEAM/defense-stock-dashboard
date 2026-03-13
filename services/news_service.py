"""
services/news_service.py — 뉴스 수집 및 처리 서비스

기능: 
1. 네이버 뉴스 검색 API를 호출하여 데이터 수집
2. 뉴스 원문 페이지에서 크롤링을 통해 대표 이미지(썸네일) 추출
3. 전처리 후 MySQL 데이터베이스에 저장 및 업데이트
"""

import requests
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup

from database import get_conn
from utils.helpers import strip_html, extract_source_name
from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

# 네이버 뉴스 검색 API 엔드포인트
NEWS_URL = "https://openapi.naver.com/v1/search/news.json"

# HTTP 연결 재사용을 위한 세션 객체 생성
_session = requests.Session()


def extract_image_from_html(url):
    """
    뉴스 원문 URL에 접속하여 og:image 태그를 찾아 대표 이미지 URL을 반환합니다.
    """
    try:
        # 뉴스 본문 페이지 요청 (10초 타임아웃 설정)
        resp = _session.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        
        # HTML 파싱 후 Open Graph 이미지 태그 탐색
        soup = BeautifulSoup(resp.text, "html.parser")
        meta = soup.find("meta", property="og:image")
        
        if meta and meta.get("content"):
            return meta["content"]
    except Exception:
        # 네트워크 오류나 파싱 실패 시 None 반환 (프로세스 중단 방지)
        pass
    return None


def fetch_news(query):
    """
    네이버 뉴스 검색 API를 호출하여 뉴스 아이템 리스트를 가져옵니다.
    """
    headers = {
        "X-Naver-Client-Id":     NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    # 검색어(query), 출력 개수(60개), 정렬(날짜순) 설정
    params = {"query": query, "display": 60, "sort": "date"}
    
    response = requests.get(NEWS_URL, headers=headers, params=params, timeout=8)
    response.raise_for_status()  # API 응답 에러 발생 시 예외 발생
    
    return response.json().get("items", [])


def save_news(conn, item):
    """
    수집한 뉴스 항목을 전처리한 후 DB(news 테이블)에 저장합니다.
    URL(source_url)을 Unique Key로 사용하여 중복 시 내용을 업데이트합니다.
    """
    # 1. HTML 태그 제거 및 텍스트 정제
    title      = strip_html(item.get("title"))
    summary    = strip_html(item.get("description"))
    
    # 2. 뉴스 링크 및 언론사 명 추출
    source_url = item.get("originallink") or item.get("link")
    source     = extract_source_name(source_url)
    
    # 3. 썸네일 이미지 크롤링 (별도 HTTP 요청 발생)
    thumbnail  = extract_image_from_html(source_url)

    # 4. 발행일 포맷 변경 (RFC 2822 -> Python datetime)
    published_at = None
    pub_date = item.get("pubDate")
    if pub_date:
        try:
            published_at = parsedate_to_datetime(pub_date)
        except Exception:
            pass

    # 5. DB 쿼리 실행: 중복된 URL이 존재하면 최신 정보로 UPDATE
    sql = """
    INSERT INTO news
        (title, summary, content, source, source_url, thumbnail_url, published_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        title         = VALUES(title),
        summary       = VALUES(summary),
        source        = VALUES(source),
        thumbnail_url = VALUES(thumbnail_url),
        published_at  = VALUES(published_at)
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (title, summary, None, source, source_url, thumbnail, published_at))


def update_news():
    """
    주요 방산 종목 키워드로 뉴스를 수집하는 메인 실행 함수입니다.
    """
    conn = None
    try:
        conn = get_conn()
        
        # 검색 키워드 설정 (주요 종목명과 '방산' 키워드 조합)
        query = "(한화에어로스페이스 | 현대로템 | LIG넥스원 | KAI | 빅텍 | 퍼스텍 | 풍산) 방산"
        
        # 1. API를 통해 뉴스 목록 수집
        news_list = fetch_news(query)

        # 2. 수집된 각 뉴스를 순회하며 DB 저장 시도
        for item in news_list:
            try:
                save_news(conn, item)
            except Exception as e:
                # 개별 뉴스 저장 실패 시 로그를 남기고 다음 뉴스 진행
                print(f"뉴스 저장 실패 (URL: {item.get('link')}): {e}")

        # 모든 작업 완료 시 트랜잭션 커밋
        conn.commit()
        print(f"[{len(news_list)}건] 뉴스 수집 및 저장 완료")
        
    finally:
        # DB 연결 해제
        if conn:
            conn.close()


if __name__ == "__main__":
    # 직접 실행 시 즉시 업데이트 시작
    update_news()