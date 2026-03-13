from datetime import datetime
from flask import Blueprint, Flask, render_template, session

from database import get_conn
from routes.log_card import get_yesterday_trade_summary
from services.stock_service import get_defense_sector_analysis, get_defense_data

home_bp = Blueprint("home", __name__)

def get_main_etf():
    # DB에서 메인으로 표시할 첫 번째 ETF 정보를 가져옵니다.
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, ticker, name_kr FROM etfs ORDER BY id LIMIT 1")
            return cursor.fetchone()
    finally:
        conn.close()


def get_etf_chart_data(etf_id):
    # 특정 ETF의 가격 히스토리를 가져와 차트 라이브러리(Chart.js) 형식으로 변환합니다.
    # - x: 타임스탬프 (ms)
    # - o, h, l, c: 시가, 고가, 저가, 종가
    
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT price_date, open_price, high_price, low_price, close_price
                FROM etf_price_history
                WHERE etf_id = %s
                ORDER BY price_date
                """,
                (etf_id,)
            )
            rows = cursor.fetchall()

        # 데이터 가공: 날짜를 밀리초 단위 타임스탬프로 변환
        return [
            {
                "x": int(datetime.combine(row["price_date"], datetime.min.time()).timestamp() * 1000),
                "o": float(row["open_price"]),
                "h": float(row["high_price"]),
                "l": float(row["low_price"]),
                "c": float(row["close_price"]),
            }
            for row in rows
        ]
    finally:
        conn.close()


def get_color_class(score):
    # AI 분석 점수에 따라 UI에 표시할 부트스트랩 배경 색상 클래스를 반환합니다.
    if score >= 70:
        return "bg-success"  # 초록색 (긍정)
    elif score >= 40:
        return "bg-warning"  # 노란색 (중립)
    else:
        return "bg-danger"   # 빨간색 (부정)

def get_index_datas() :
    # 1. 메인 ETF 및 차트 데이터 수집
    etf = get_main_etf()
    chart_data = get_etf_chart_data(etf["id"])

    # 2. 방산 섹터 AI 분석 결과 (점수, 코멘트, 관련 뉴스) 가져오기
    score, ai_news, news_list = get_defense_sector_analysis()

    # 3. 로그인 사용자 정보 확인 및 어제자 거래 요약 추출
    user_id = session.get("user_id")
    if user_id:
        # log_card 서비스에서 요약 통계 가져오기
        yesterday_trades, buy_count, sell_count, total_count = get_yesterday_trade_summary(user_id)
    else:
        yesterday_trades, buy_count, sell_count, total_count = [], 0, 0, 0

    # AI 점수 정수화 및 UI 컬러 결정
    try:
        final_score = int(score) if score is not None else 0
    except (ValueError, TypeError):
        final_score = 0
    color_class = get_color_class(final_score)

    # 4. 방산 종목 실시간 시세 및 기본 종목 설정
    defense_stocks = get_defense_data()
    account = None
    current_price = 0
    default_stock = {"ticker": "", "name_kr": ""}

    if defense_stocks:
        default_stock = {
            "ticker": defense_stocks[0]["ticker"],
            "name_kr": defense_stocks[0]["name"],
        }
        current_price = defense_stocks[0]["price"]

    # 5. 로그인 사용자일 경우 현재 가용 잔고 조회
    if user_id:
        conn = get_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT current_balance FROM mock_accounts WHERE user_id = %s",
                    (user_id,),
                )
                account = cursor.fetchone()
        finally:
            conn.close()
    return {
        "etf":etf,
        "chart_data":chart_data,
        "score":score,
        "ai_news":ai_news,
        "news_list":news_list[:3], # 최신 뉴스 3개만 표시
        "yesterday_trades":yesterday_trades,
        "buy_count":buy_count,
        "sell_count":sell_count,
        "total_count":total_count,
        "color_class":color_class,
        "defense_stocks":defense_stocks,
        "account":account,         # 계좌 잔고
        "current_price":current_price,
        "stock":default_stock,     # 기본 표시 종목
        "stock_id":9999,           # 대시보드용 임시 ID
        "strategies":{},           # 향후 확장용 전략 데이터
    }


@home_bp.route("/")
def index():
    # 메인 페이지 로직: 대시보드에 필요한 모든 데이터를 집계하여 index.html로 전달합니다.
    context = get_index_datas()
    # 최종 렌더링
    return render_template("index.html", **context)