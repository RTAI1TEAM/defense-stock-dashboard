import os
import re
import html
import json
import requests
from urllib.parse import urlparse, urljoin
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup

from database import get_conn
from dotenv import load_dotenv

load_dotenv()

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

NEWS_URL = "https://openapi.naver.com/v1/search/news.json"

session = requests.Session()


def strip_html(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text).strip()


def extract_source_name(link):
    try:
        netloc = urlparse(link).netloc.lower()
    except Exception:
        return "뉴스"

    
    if netloc.startswith("www."):
        netloc = netloc[4:]

    return netloc if netloc else "news"


def extract_image_from_html(url):
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

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }

    params = {
        "query": query,
        "display": 30,
        "sort": "date"
    }

    response = requests.get(NEWS_URL, headers=headers, params=params, timeout=8)

    response.raise_for_status()

    return response.json().get("items", [])


def save_news(conn, item):

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