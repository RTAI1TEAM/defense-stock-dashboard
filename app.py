from datetime import datetime

from flask import Flask, render_template, session

from database import get_conn
from routes.log_card import dashboard_bp, get_yesterday_trade_summary
from routes.app_login import auth_bp
from routes.rank import rank_bp
from routes.news import news_bp
from routes.stocks import stocks_bp
from routes.portfolio import portfolio_bp
from routes.stock_detail import stock_detail_bp
from routes.profile import profile_bp
from routes.stock_chat import stock_chat_bp
from services.stock_service import get_defense_sector_analysis, get_stock_list, get_defense_data
from config import SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY

app.register_blueprint(auth_bp)
app.register_blueprint(rank_bp)
app.register_blueprint(news_bp)
app.register_blueprint(stocks_bp)
app.register_blueprint(portfolio_bp)
app.register_blueprint(stock_detail_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(stock_chat_bp)
app.register_blueprint(dashboard_bp)

def get_main_etf():
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, ticker, name_kr FROM etfs ORDER BY id LIMIT 1")
            return cursor.fetchone()
    finally:
        conn.close()


def get_etf_chart_data(etf_id):
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
    try:
        return dict(stock_list=get_stock_list())
    except Exception:
        return dict(stock_list=[])

@app.route("/")
def index():
    # 1. ETF 데이터 (기존 유지)
    etf = get_main_etf()
    chart_data = get_etf_chart_data(etf["id"])

    score, ai_news, news_list = get_defense_sector_analysis()

    user_id = session.get("user_id")
    if user_id:
        yesterday_trades, buy_count, sell_count, total_count = get_yesterday_trade_summary(user_id)
    else:
        yesterday_trades, buy_count, sell_count, total_count = [], 0, 0, 0

    try:
        final_score = int(score) if score is not None else 0
    except (ValueError, TypeError):
        final_score = 0

    color_class = get_color_class(final_score)

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

    return render_template(
        "index.html",
        etf=etf,
        chart_data=chart_data,
        score=score,
        ai_news=ai_news,
        news_list=news_list[:3],
        color_class=color_class,
        defense_stocks=defense_stocks,
        stock_id=9999,
        strategies={},
        stock=default_stock,
        account=account,
        current_price=current_price,
        yesterday_trades=yesterday_trades,
        buy_count=buy_count,
        sell_count=sell_count,
        total_count=total_count,
    )


if __name__ == "__main__":
    app.run(debug=True)