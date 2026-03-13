"""
services/news_service.py — 뉴스 수집 서비스
(구 news_data.py)

네이버 뉴스 API에서 방산 관련 뉴스를 수집하여 DB에 저장합니다.
daily_update.py의 배치 작업에서 호출됩니다.
"""

import requests
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup

from database import get_conn
from utils.helpers import strip_html, extract_source_name
from config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

NEWS_URL = "https://openapi.naver.com/v1/search/news.json"

_session = requests.Session()


def extract_image_from_html(url):
    """뉴스 원문 URL에서 og:image 태그를 찾아 대표 이미지를 반환합니다."""
    try:
        resp = _session.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        meta = soup.find("meta", property="og:image")
        if meta and meta.get("content"):
            return meta["content"]
    except Exception:
        pass
    return None


def fetch_news(query):
    """네이버 뉴스 API에서 키워드로 뉴스를 검색합니다."""
    headers = {
        "X-Naver-Client-Id":     NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": query, "display": 60, "sort": "date"}
    response = requests.get(NEWS_URL, headers=headers, params=params, timeout=8)
    response.raise_for_status()
    return response.json().get("items", [])


def save_news(conn, item):
    """수집한 뉴스 항목을 DB에 저장합니다. 중복은 UPDATE 처리합니다."""
    title      = strip_html(item.get("title"))
    summary    = strip_html(item.get("description"))
    source_url = item.get("originallink") or item.get("link")
    source     = extract_source_name(source_url)
    thumbnail  = extract_image_from_html(source_url)

    published_at = None
    pub_date = item.get("pubDate")
    if pub_date:
        try:
            published_at = parsedate_to_datetime(pub_date)
        except Exception:
            pass

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
    """방산 관련 키워드로 뉴스를 수집하여 DB에 저장합니다."""
    conn = None
    try:
        conn = get_conn()
        query = "(한화에어로스페이스 | 현대로템 | LIG넥스원 | KAI | 빅텍 | 퍼스텍 | 풍산) 방산"
        news_list = fetch_news(query)

        for item in news_list:
            try:
                save_news(conn, item)
            except Exception as e:
                print(f"뉴스 저장 실패: {e}")

        conn.commit()
        print("뉴스 저장 완료")
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    update_news()
