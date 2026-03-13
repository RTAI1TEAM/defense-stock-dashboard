"""
services/stock_service.py — 종목 DB 조회 서비스

[ 역할 ]
  화면에 뿌릴 종목 데이터를 DB에서 꺼내오는 함수 모음입니다.
  직접 API를 호출하지 않고 배치가 저장해 둔 결과를 읽기만 합니다.

[ 사용처 ]
  routes/stock_detail.py  — 종목 상세 페이지
  app.py                  — 메인 페이지 업종 분석
"""

from datetime import datetime

from database import get_conn


def get_defense_sector_analysis():
    """
    방산 업종 전체 AI 분석 결과를 반환합니다.
    stock_id=9999 레코드에서 조회합니다.

    Returns:
        score (int), ai_summary (str), news_list (list)
    """
    import json
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT score, ai_summary, news_data FROM stock_news WHERE stock_id = 9999"
            )
            row = cursor.fetchone()
        if row:
            return row['score'], row['ai_summary'], json.loads(row['news_data'])
        return 0, "데이터 분석 대기 중...", []
    finally:
        conn.close()


def get_stock(ticker):
    """
    ticker 코드로 종목 기본 정보를 조회합니다.
    존재하지 않는 ticker면 None을 반환합니다.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, ticker, name_kr
                FROM stocks
                WHERE ticker = %s
                ORDER BY id
                LIMIT 1
                """,
                (ticker,)
            )
            return cursor.fetchone()
    finally:
        conn.close()


def get_stock_list():
    """드롭다운 메뉴용 전체 종목 목록(name_kr, ticker)을 반환합니다."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name_kr, ticker FROM stocks")
            return cur.fetchall()
    finally:
        conn.close()


def get_stock_chart_data(stock_id):
    """
    캔들차트(OHLC)용 데이터를 반환합니다.
    Chart.js의 시간축 형식에 맞춰 x값을 밀리초 타임스탬프로 변환합니다.

    Returns:
        list of dict — {x, o, h, l, c}
    """
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT price_date, open_price, high_price, low_price, close_price
                FROM stock_price_history
                WHERE stock_id = %s
                ORDER BY price_date
                """,
                (stock_id,)
            )
            rows = cursor.fetchall()

        return [
            {
                "x": int(datetime.combine(r["price_date"], datetime.min.time()).timestamp() * 1000),
                "o": float(r["open_price"]),
                "h": float(r["high_price"]),
                "l": float(r["low_price"]),
                "c": float(r["close_price"]),
            }
            for r in rows
        ]
    finally:
        conn.close()
