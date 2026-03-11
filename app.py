import os
from flask import Flask, render_template, redirect, url_for, session, request
from database import get_conn
from finance_data import get_defense_data
from routes.app_login import auth_bp
from routes.rank import rank_bp
from routes.news import news_bp
from routes.stocks import stocks_bp
from routes.portfolio import portfolio_bp
from routes.stock_detail import stock_detail_bp
from routes.profile import profile_bp

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "aiquant2024")

app.register_blueprint(auth_bp)
app.register_blueprint(rank_bp)
app.register_blueprint(news_bp)
app.register_blueprint(stocks_bp)
app.register_blueprint(portfolio_bp)
app.register_blueprint(stock_detail_bp)
app.register_blueprint(profile_bp)


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
            SELECT price_date, close_price
            FROM etf_price_history
            WHERE etf_id = %s
            ORDER BY price_date
            """
            cursor.execute(sql, (etf_id,))
            rows = cursor.fetchall()

            labels = [row["price_date"].strftime("%Y-%m-%d") for row in rows]
            values = [float(row["close_price"]) for row in rows]

            return labels, values
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
    if score >= 80:
        return "bg-success"
    elif score >= 60:
        return "bg-warning"
    else:
        return "bg-danger"


@app.template_filter('comma')
def comma_filter(value):
    return format(int(value), ',')


@app.route("/")
def index():
    etf = get_main_etf()
    chart_labels, chart_values = get_etf_chart_data(etf["id"])

    stock_id, analysis_list, score = get_main_stock_analysis()
    color_class = get_color_class(score if score is not None else 0)

    # 투자 폼에 넣을 전략 문구
    ai_strategy = analysis_list[0]["ai_summary"] if analysis_list else "AI 분석 데이터 없음"

    conn = get_conn()
    try:
        defense_stocks = get_defense_data(conn)
    finally:
        conn.close()

    return render_template(
        "index.html",
        etf=etf,
        chart_labels=chart_labels,
        chart_values=chart_values,
        stock_id=stock_id,
        news_list=analysis_list,
        score=score if score is not None else 0,
        color_class=color_class,
        ai_strategy=ai_strategy,
        defense_stocks=defense_stocks,
        strategies={},  # 템플릿의 for문을 통과시키기 위함
        stock=None      # stock.ticker 에러를 방지하기 위함
    )


if __name__ == "__main__":
    app.run(debug=True)