import os
import json
from flask import Flask, render_template, redirect, url_for, session, request
from datetime import datetime
from database import get_conn
from finance_data import get_defense_data
from routes.app_login import auth_bp
from routes.rank import rank_bp
from routes.news import news_bp
from routes.stocks import stocks_bp
from routes.portfolio import portfolio_bp
from routes.stock_detail import stock_detail_bp, get_defense_sector_analysis
from routes.profile import profile_bp
from routes.stock_chat import stock_chat_bp

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "aiquant2024")

app.register_blueprint(auth_bp)
app.register_blueprint(rank_bp)
app.register_blueprint(news_bp)
app.register_blueprint(stocks_bp)
app.register_blueprint(portfolio_bp)
app.register_blueprint(stock_detail_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(stock_chat_bp)


def get_main_etf():
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            sql = """
            SELECT id, ticker, name_kr
            FROM etfs
            ORDER BY id
            LIMIT 1
            """
            cursor.execute(sql)
            return cursor.fetchone()
    finally:
        conn.close()


def get_etf_chart_data(etf_id):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            sql = """
            SELECT price_date, open_price, high_price, low_price, close_price
            FROM etf_price_history
            WHERE etf_id = %s
            ORDER BY price_date
            """
            cursor.execute(sql, (etf_id,))
            rows = cursor.fetchall()

            candle_data = []
            for row in rows:
                candle_data.append({
                    "x": int(datetime.combine(row["price_date"], datetime.min.time()).timestamp() * 1000),
                    "o": float(row["open_price"]),
                    "h": float(row["high_price"]),
                    "l": float(row["low_price"]),
                    "c": float(row["close_price"])
                })

            return candle_data
    finally:
        conn.close()


def get_main_stock_analysis():
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 분석 데이터가 있는 종목 하나 선택
            cursor.execute("""
                SELECT stock_id
                FROM news_analysis
                WHERE stock_id IS NOT NULL
                GROUP BY stock_id
                ORDER BY stock_id
                LIMIT 1
            """)
            stock_row = cursor.fetchone()

            if not stock_row:
                return None, [], None

            stock_id = stock_row["stock_id"]

            cursor.execute("""
                SELECT 
                    ROUND(AVG(ai_score), 1) AS avg_score
                FROM news_analysis
                WHERE stock_id = %s
            """, (stock_id,))
            score_row = cursor.fetchone()
            avg_score = float(score_row["avg_score"]) if score_row and score_row["avg_score"] is not None else 0

            cursor.execute("""
                SELECT 
                    ai_score,
                    sentiment,
                    ai_summary,
                    keywords,
                    created_at
                FROM news_analysis
                WHERE stock_id = %s
                ORDER BY created_at DESC, id DESC
            """, (stock_id,))
            analysis_list = cursor.fetchall()

            return stock_id, analysis_list, avg_score
    finally:
        conn.close()


def get_color_class(score):
    if score >= 70:
        return "bg-success"
    elif score >= 40:
        return "bg-warning"
    else:
        return "bg-danger"


@app.template_filter('comma')
def comma_filter(value):
    return format(int(value), ',')

@app.context_processor
def inject_stock_list():

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT ticker, name_kr FROM stocks")
    stock_list = cursor.fetchall()

    conn.close()

    return dict(stock_list=stock_list)

@app.route("/")
def index():
    # 1. ETF 데이터 (기존 유지)
    etf = get_main_etf()
    chart_data = get_etf_chart_data(etf["id"])

    # 2. 업종 분석 데이터 가져오기 (수정됨!)
    # stock_detail.py에서 만든 9999번 데이터를 읽어오는 함수 호출
    score, ai_news, news_list = get_defense_sector_analysis()

    # # 조건문을 좀 더 널널하게 변경 (내용이 "데이터 분석 대기 중..."인 경우도 포함)
    # if score == 0 or not news_list or "대기 중" in ai_news:
    #     print("Gemini 업종 분석을 실행합니다...")
    #     update_sector_ai_analysis()
    #     score, ai_news, news_list = get_defense_sector_analysis()
    
    # 🚀 [수정 포인트] 점수 타입 확인 및 색상 결정
    try:
        # score가 None이거나 계산 불가능한 경우를 대비
        final_score = int(score) if score is not None else 0
    except (ValueError, TypeError):
        final_score = 0

    color_class = get_color_class(final_score)

    # 3. 방산주 리스트 (기존 유지)
    conn = get_conn()
    try:
        defense_stocks = get_defense_data(conn)
    finally:
        conn.close()

    # 4. 템플릿으로 전달 (변수 이름 맞춤)
    return render_template(
        "index.html",
        etf=etf,
        chart_data=chart_data,
        score=score,
        ai_news=ai_news,      # 템플릿에서 요약문으로 사용
        news_list=news_list[:3],  # 템플릿에서 뉴스 목록으로 사용, 뉴스 목록 5개로 제한
        color_class=color_class,
        ai_strategy=ai_news,  # 기존 ai_strategy 변수명도 대응
        defense_stocks=defense_stocks,
        stock_id=9999,        # 업종 종합 ID
        strategies={}, 
        stock={'ticker': 'DEFENSE'} # 에러 방지용 가상 객체
    )


if __name__ == "__main__":
    app.run(debug=True)