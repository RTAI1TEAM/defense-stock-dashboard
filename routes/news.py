from dotenv import load_dotenv
import os
import re
import html
import json
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from flask import Blueprint, render_template, request

load_dotenv()

news_bp = Blueprint('news', __name__)

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

API_URL = "https://openapi.naver.com/v1/search/news.json"

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
})


def strip_html(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text).strip()


def normalize_image(value, base_url):
    if isinstance(value, str) and value.strip():
        return urljoin(base_url, value.strip())

    if isinstance(value, list):
        for v in value:
            image = normalize_image(v, base_url)
            if image:
                return image

    if isinstance(value, dict):
        for key in ("url", "contentUrl"):
            if value.get(key):
                return urljoin(base_url, value[key])

    return None


def extract_image_from_html(html_text, base_url):
    soup = BeautifulSoup(html_text, "html.parser")

    # 1) 가장 우선: 메타 태그
    meta_candidates = [
        ("property", "og:image"),
        ("property", "og:image:url"),
        ("name", "og:image"),
        ("name", "twitter:image"),
        ("name", "twitter:image:src"),
    ]

    for attr, key in meta_candidates:
        tag = soup.find("meta", attrs={attr: key})
        content = tag.get("content").strip() if tag and tag.get("content") else None
        if content:
            return urljoin(base_url, content)

    # 2) JSON-LD(schema.org)
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw or not raw.strip():
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        objects = data if isinstance(data, list) else [data]
        for obj in objects:
            if not isinstance(obj, dict):
                continue

            image = normalize_image(obj.get("image"), base_url)
            if image:
                return image

            graph = obj.get("@graph")
            if isinstance(graph, list):
                for node in graph:
                    if isinstance(node, dict):
                        image = normalize_image(node.get("image"), base_url)
                        if image:
                            return image

    # 3) 마지막 fallback: article 안 첫 이미지
    article = soup.select_one("article")
    if article:
        img = article.find("img")
        if img:
            src = img.get("src") or img.get("data-src")
            if src:
                return urljoin(base_url, src)

    return None


def fetch_article_image(article_url):
    if not article_url:
        return None, None

    try:
        # link가 네이버 뉴스 URL이거나 openapi redirect일 수 있으니 redirect 허용
        resp = session.get(article_url, timeout=8, allow_redirects=True)
        if resp.status_code != 200:
            return None, resp.url

        content_type = resp.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            return None, resp.url

        image_url = extract_image_from_html(resp.text, resp.url)
        return image_url, resp.url

    except requests.RequestException:
        return None, None

def extract_source_name(item):
    link = item.get("originallink") or item.get("link") or ""

    try:
        netloc = urlparse(link).netloc.lower()
    except Exception:
        return "뉴스"

    source_map = {
        "mk.co.kr": "매일경제",
        "www.mk.co.kr": "매일경제",
        "hankyung.com": "한국경제",
        "www.hankyung.com": "한국경제",
        "yna.co.kr": "연합뉴스",
        "www.yna.co.kr": "연합뉴스",
        "edaily.co.kr": "이데일리",
        "www.edaily.co.kr": "이데일리",
        "newsis.com": "뉴시스",
        "www.newsis.com": "뉴시스",
        "mt.co.kr": "머니투데이",
        "www.mt.co.kr": "머니투데이",
        "fnnews.com": "파이낸셜뉴스",
        "www.fnnews.com": "파이낸셜뉴스",
        "sedaily.com": "서울경제",
        "www.sedaily.com": "서울경제",
        "asiae.co.kr": "아시아경제",
        "www.asiae.co.kr": "아시아경제",
        "etnews.com": "전자신문",
        "www.etnews.com": "전자신문",
        "joongang.co.kr": "중앙일보",
        "www.joongang.co.kr": "중앙일보",
        "chosun.com": "조선일보",
        "www.chosun.com": "조선일보",
        "donga.com": "동아일보",
        "www.donga.com": "동아일보",
    }

    for domain, name in source_map.items():
        if domain in netloc:
            return name

    if netloc.startswith("www."):
        netloc = netloc[4:]

    return netloc if netloc else "뉴스"



def enrich_items_with_extra(items):
    for item in items:
        item["source_name"] = extract_source_name(item)
        item["pubDate_raw"] = item.get("pubDate", "")
    return items

def enrich_items_with_image(items):
    for item in items:
        item["title_clean"] = strip_html(item.get("title", ""))
        item["description_clean"] = strip_html(item.get("description", ""))
        item["image_url"] = None
        item["resolved_url"] = None

        # link 우선: 네이버 뉴스 URL일 수 있어서 원문 차단을 피할 때 더 유리
        for candidate in [item.get("link"), item.get("originallink")]:
            image_url, resolved_url = fetch_article_image(candidate)
            if image_url:
                item["image_url"] = image_url
                item["resolved_url"] = resolved_url
                break

    return items


def get_combined_news(query=None):
    if not query:
        majors = "한화에어로스페이스 | 현대로템 | LIG넥스원 | KAI"
        smids = "빅텍 | 퍼스텍 | 코츠테크놀로지 | 제노코 | 휴니드 | 풍산 | 스페코"
        query = f"({majors} | {smids}) + (방산 | 국방 | 수주)"

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {
        "query": query,
        "display": 13,
        "sort": "sim"
    }

    try:
        resp = session.get(API_URL, headers=headers, params=params, timeout=8)
        resp.raise_for_status()

        items = resp.json().get("items", [])
        items = enrich_items_with_image(items)
        items = enrich_items_with_extra(items)

        print(f"\n[종합 순위 뉴스 수집 결과 - 키워드: {query}]")
        for item in items:
            print(f"Title: {item['title_clean']}")
            print(f"Summary: {item['description_clean']}")
            print(f"Time: {item.get('pubDate')}")
            print(f"Image: {item.get('image_url')}")
            print("-" * 50)

        return items

    except Exception as e:
        print(f"Error: {e}")
        return []


@news_bp.route("/news")
def show_news():
    search_query = request.args.get("q")
    all_news = get_combined_news(search_query)   # 13개 받아오기

    top3_news = all_news[:3]
    list_news = all_news[3:13]

    return render_template(
        "news.html",
        top3_news=top3_news,
        list_news=list_news,
        total_count=len(all_news),
        current_query=search_query if search_query else ""
    )
