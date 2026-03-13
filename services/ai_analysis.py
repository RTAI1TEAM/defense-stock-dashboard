"""
services/ai_analysis.py — AI 분석 서비스

[ 역할 ]
  네이버 뉴스 수집 → Gemini AI 분석 → DB 저장 흐름을 담당합니다.

[ 호출 흐름 ]
  daily_update.py (배치)
      └─ update_sector_ai_analysis()    : 업종 전체 뉴스 분석
      └─ update_all_stocks_ai_analysis(): 전 종목 뉴스 분석

  routes/stock_detail.py (웹 요청)
      └─ get_db_or_api_stock_news()     : 종목 AI 분석 결과 조회 (DB 우선, 없으면 실시간)
"""

import json
import time
import requests
from google import genai

from database import get_conn
from utils.helpers import strip_html
from config import GEMINI_API_KEY, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

MODEL_ID = "gemini-2.5-flash"
client   = genai.Client(api_key=GEMINI_API_KEY)


def get_live_analysis(stock_name):
    """
    [실시간] 네이버 뉴스 3개를 가져와 Gemini AI로 분석합니다.

    배치가 실패해 DB에 데이터가 없을 때만 직접 호출합니다.

    Returns:
        news_list, score, ai_news
    """
    headers = {
        "X-Naver-Client-Id":     NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params    = {"query": f"{stock_name} 주가 전망", "display": 3, "sort": "sim"}
    news_list = []

    try:
        resp = requests.get(
            "https://openapi.naver.com/v1/search/news.json",
            headers=headers, params=params, timeout=5
        )
        if resp.status_code != 200:
            return [], 50, "뉴스 데이터를 가져올 수 없습니다."

        for item in resp.json().get("items", []):
            news_list.append({
                "title":             strip_html(item.get("title", "")),
                "link":              item.get("link"),
                "description_clean": strip_html(item.get("description", ""))
            })
    except Exception as e:
        print(f"뉴스 API 호출 중 예외 발생: {e}")

    if not news_list:
        return [], 50, f"'{stock_name}' 관련 최신 뉴스가 없습니다."

    news_context = "\n".join(
        [f"제목: {n['title']}\n내용: {n['description_clean']}" for n in news_list]
    )
    prompt = f"""
    당신은 주식 투자 전문가입니다. 아래 제공된 '{stock_name}' 관련 뉴스 3개를 읽고 분석하세요.
    - score: 투자 매력도 (0~100 숫자)
    - ai_news: 뉴스 요약 (20자 이내)
    반드시 JSON 형식으로만 답변하세요.
    뉴스 내용:
    {news_context}
    """

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )

        data = json.loads(response.text.strip())
        if isinstance(data, list):
            data = data[0] if data else {}

        score   = int(data.get("score", 50))
        ai_news = data.get("ai_news", "시장 관망 후 진입을 추천합니다.")

        return news_list, score, ai_news

    except Exception as e:
        print(f"Gemini 분석 에러: {e}")
        return news_list, 50, "AI 분석 엔진 일시 오류"


def get_db_or_api_stock_news(stock_id, stock_name):
    """
    [웹 요청용] 종목 AI 분석 결과를 DB에서 조회합니다.
    DB에 데이터가 없으면 실시간 분석(get_live_analysis)으로 대체합니다.

    Returns:
        news_list, score, ai_news
    """
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT score, ai_summary, news_data FROM stock_news WHERE stock_id = %s",
                (stock_id,)
            )
            row = cursor.fetchone()

        if not row:
            return get_live_analysis(stock_name)

        return json.loads(row['news_data']), row['score'], row['ai_summary']
    finally:
        conn.close()


def update_all_stocks_ai_analysis():
    """
    [배치 전용] 전 종목 AI 분석을 일괄 실행해 DB에 저장합니다.
    daily_update.py에서 매일 1회 호출합니다.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name_kr FROM stocks")
            stocks = cursor.fetchall()

            print(f"🚀 총 {len(stocks)}개 종목 AI 전수 분석 시작...")
            for stock in stocks:
                stock_id   = stock['id']
                stock_name = stock['name_kr']

                try:
                    news_list, score, ai_news = get_live_analysis(stock_name)

                    cursor.execute(
                        """
                        INSERT INTO stock_news (stock_id, score, ai_summary, news_data, updated_at)
                        VALUES (%s, %s, %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                            score      = VALUES(score),
                            ai_summary = VALUES(ai_summary),
                            news_data  = VALUES(news_data),
                            updated_at = NOW()
                        """,
                        (stock_id, score, ai_news, json.dumps(news_list, ensure_ascii=False))
                    )
                    conn.commit()
                    print(f"✅ {stock_name} 업데이트 완료")

                    time.sleep(1)  # Gemini 무료 티어 분당 호출 한도 초과 방지

                except Exception as e:
                    print(f"❌ {stock_name} 분석 오류: {e}")
                    continue
    finally:
        conn.close()


def update_sector_ai_analysis():
    """
    [배치 전용] 방산 업종 전체 AI 분석을 실행해 DB에 저장합니다.
    daily_update.py에서 매일 1회 호출합니다.

    stock_id=9999는 실제 종목이 아닌 '업종 전체'를 나타내는 가상 ID입니다.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT title, summary AS description_clean, source_url AS link
                FROM news
                ORDER BY published_at DESC
                LIMIT 10
            """)
            news_items = cursor.fetchall()

            if not news_items:
                print("분석할 뉴스가 없습니다.")
                return

            news_context = "\n".join(
                [f"제목: {n['title']}\n내용: {n['description_clean']}" for n in news_items]
            )
            prompt = f"""
            당신은 대한민국 방위산업 투자 전문가입니다.
            아래 10개의 최신 방산 뉴스를 종합하여 업종 전체의 투자 점수와 핵심 요약을 작성하세요.
            반드시 JSON 형식으로 응답하세요:
            {{
                "score": 0~100 사이 숫자,
                "ai_news": "업종 전체의 흐름을 보여주는 한 줄 요약 (25자 이내)"
            }}
            뉴스 데이터:
            {news_context}
            """

            response = client.models.generate_content(
                model=MODEL_ID,
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            data = json.loads(response.text.strip())

            cursor.execute(
                """
                INSERT INTO stock_news (stock_id, score, ai_summary, news_data, updated_at)
                VALUES (9999, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                    score      = VALUES(score),
                    ai_summary = VALUES(ai_summary),
                    news_data  = VALUES(news_data),
                    updated_at = NOW()
                """,
                (data['score'], data['ai_news'], json.dumps(news_items, ensure_ascii=False))
            )
            conn.commit()
            print("[업종분석] 업데이트 완료")

    except Exception as e:
        print(f"업종 분석 중 오류: {e}")
    finally:
        conn.close()
