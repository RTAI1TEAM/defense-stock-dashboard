# [파일 역할] 데이터베이스에 저장된 종목 및 시세 정보를 조회하여 반환하는 서비스 모듈
# - 외부 API를 직접 호출하지 않고, 배치 작업이 갱신해둔 DB 데이터를 읽는 전용 레이어입니다.
# - UI 컴포넌트나 라우트 로직에서 사용하기 적합하도록 데이터 형식을 가공하여 제공합니다.

import json
from datetime import datetime
from database import get_conn


def get_defense_sector_analysis():
    # [함수] 방산 업종 전체에 대한 AI 요약 분석 결과 및 최신 뉴스 리스트를 조회합니다.
    # - 전제 조건: 업종 종합 데이터는 DB 상에서 stock_id = 9999 레코드로 관리됩니다.
    # - Returns: (score: 점수, ai_summary: 요약문, news_list: 뉴스 객체 리스트)
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 업종 종합 분석 테이블에서 점수, 요약, 뉴스 JSON 데이터를 로드
            cursor.execute(
                "SELECT score, ai_summary, news_data FROM stock_news WHERE stock_id = 9999"
            )
            row = cursor.fetchone()
        
        if row:
            # news_data는 JSON 문자열 형식이므로 리스트로 변환하여 반환
            return row['score'], row['ai_summary'], json.loads(row['news_data'])
        
        return 0, "데이터 분석 대기 중...", []
    finally:
        conn.close()


def get_stock(ticker):
    # [함수] 티커(Ticker) 코드를 사용하여 특정 종목의 기본 정보(ID, 이름 등)를 조회합니다.
    # - ticker: 종목 코드 (예: '012450')
    # - Returns: 종목 정보 딕셔너리 또는 검색 결과 없을 시 None
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
    # [함수] 전체 종목의 이름과 티커 목록을 반환합니다.
    # - 주로 검색창의 자동완성이나 종목 선택 드롭다운 메뉴 구성 시 사용됩니다.
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name_kr, ticker FROM stocks")
            return cur.fetchall()
    finally:
        conn.close()


def get_defense_data():
    # [함수] 방산 업종에 속한 모든 종목의 실시간 시세 및 거래 정보를 가공하여 반환합니다.
    # - 가공 로직: 현재가(정수화), 등락률(소수점), 거래대금(억원 단위 변환)
    # - 정렬: 거래대금이 높은 순(내림차순)으로 정렬하여 시장 주도주를 상단에 배치
    # - Returns: 가공된 종목 데이터 리스트
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # stocks 테이블과 상세 시세 정보가 담긴 stock_details 테이블을 조인
            cursor.execute(
                """
                SELECT s.ticker, s.name_kr, d.current_price, d.change_rate, d.trading_value
                FROM stocks s
                JOIN stock_details d ON s.id = d.stock_id
                WHERE s.is_defense = 1
                """
            )
            rows = cursor.fetchall()

        # 데이터 클렌징 및 단위 변환 (원 -> 억원)
        results = [
            {
                "ticker": row["ticker"],
                "name":   row["name_kr"],
                "price":  int(float(row["current_price"])),
                "change": float(row["change_rate"]),
                "value":  round(int(row["trading_value"]) / 100_000_000, 1), # 억원 단위 반올림
            }
            for row in rows
        ]
        
        # 가공된 리스트를 거래대금(value) 기준으로 역순 정렬
        return sorted(results, key=lambda x: x["value"], reverse=True)
    finally:
        conn.close()


def get_stock_chart_data(stock_id):
    # [함수] 특정 종목의 일별 시세 이력(OHLC)을 차트 라이브러리 형식에 맞춰 조회합니다.
    # - stock_id: 조회할 종목의 고유 식별자
    # - 특이사항: 프론트엔드(Chart.js) 시간축 호환을 위해 날짜를 밀리초 타임스탬프로 변환
    # - Returns: 차트 데이터 리스트 [{x: 시간, o: 시가, h: 고가, l: 저가, c: 종가}, ...]
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

        # 각 시세 데이터를 Chart.js 금융 차트 데이터 규격으로 매핑
        return [
            {
                # 날짜 객체를 유닉스 타임스탬프(밀리초)로 변환
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