import os
import re
import html
import json
import requests
from urllib.parse import urlparse, urljoin
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup # HTML 분석용 라이브러리

from database import get_conn
from dotenv import load_dotenv

load_dotenv()

# [환경 변수 로드]
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID") # 네이버 API 쓰기 위한 신분증 1
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET") # 네이버 API 쓰기 위한 신분증 2

NEWS_URL = "https://openapi.naver.com/v1/search/news.json"

session = requests.Session()


def strip_html(text):
    """[데이터 정제 파트] 뉴스 제목이나 본문에 섞인 <b>...</b> 같은 HTML 태그를 제거해."""
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text).strip()


def extract_source_name(link):
    """
    [언론사 이름 추출 파트]
    뉴스 원문 URL(link)을 분석해서 출처(언론사 이름)를 뽑아내는 함수야.
    """
    try:
        netloc = urlparse(link).netloc.lower()
    except Exception:
        return "뉴스"

    
    if netloc.startswith("www."):
        netloc = netloc[4:]

    return netloc if netloc else "news"


def extract_image_from_html(url):
    """
    [썸네일 추출 파트] 
    뉴스 원문 링크에 직접 들어가서 'og:image' 태그를 찾아 뉴스 대표 이미지를 가져와. 
    덕분에 우리 사이트에 사진이 예쁘게 나오지!
    """
    try:
        resp = session.get(url, timeout=10)

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
    """
    [네이버 API 호출 파트]
    전달받은 키워드(query)로 네이버 뉴스 검색 API를 때려서 JSON 데이터를 받아와.
    """
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }

    params = {
        "query": query,
        "display":60,
        "sort": "date"
    }

    response = requests.get(NEWS_URL, headers=headers, params=params, timeout=8)

    response.raise_for_status()

    return response.json().get("items", [])


def save_news(conn, item):
    """
    [DB 저장 및 업데이트 파트]
    가져온 뉴스 제목, 요약, 출처, 이미지 URL, 발행 시간 등을 'news' 테이블에 넣어.
    이미 있는 뉴스는 새로운 정보로 업데이트(ON DUPLICATE KEY UPDATE)해줘.
    """
    title = strip_html(item.get("title"))
    summary = strip_html(item.get("description"))

    source_url = item.get("originallink") or item.get("link")

    source = extract_source_name(source_url)

    thumbnail = extract_image_from_html(source_url)

    pub_date = item.get("pubDate")

    published_at = None

    if pub_date:
        try:
            published_at = parsedate_to_datetime(pub_date)
        except Exception:
            pass

    sql = """
    INSERT INTO news
    (title, summary, content, source, source_url, thumbnail_url, published_at)
    VALUES (%s,%s,%s,%s,%s,%s,%s)
    ON DUPLICATE KEY UPDATE
        title=VALUES(title),
        summary=VALUES(summary),
        source=VALUES(source),
        thumbnail_url=VALUES(thumbnail_url),
        published_at=VALUES(published_at)
    """

    with conn.cursor() as cursor:
        cursor.execute(sql, (
            title,
            summary,
            None,
            source,
            source_url,
            thumbnail,
            published_at
        ))


def update_news():
    """
    [뉴스 수집 실행 파트]
    우리 프로젝트의 핵심 키워드인 '한화에어로스페이스, 현대로템' 등 
    방산 관련 키워드를 조합해서 최신 뉴스를 싹 긁어오도록 명령하는 곳이야! [cite: 382]
    """

    conn = None

    try:

        conn = get_conn()

        query = "(한화에어로스페이스 | 현대로템 | LIG넥스원 | KAI | 빅텍 | 퍼스텍 | 풍산) 방산"

        news_list = fetch_news(query)

        for item in news_list:

            try:
                save_news(conn, item)

            except Exception as e:
                print("뉴스 저장 실패:", e)

        conn.commit()

        print("뉴스 저장 완료")

    finally:

        if conn:
            conn.close()


if __name__ == "__main__":
    update_news()