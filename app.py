import os
from flask import Flask, render_template, redirect, url_for, session, request
from database import get_conn
from routes.app_login import auth_bp
from routes.rank import rank_bp
from routes.news import news_bp
from routes.stocks import stocks_bp
from routes.portfolio import portfolio_bp
from routes.stock_detail import stock_detail_bp
from routes.profile import profile_bp
from routes.rank2 import rank2_bp

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "aiquant2024")

app.register_blueprint(auth_bp)
app.register_blueprint(rank_bp)
app.register_blueprint(news_bp)
app.register_blueprint(stocks_bp)
app.register_blueprint(portfolio_bp)
app.register_blueprint(stock_detail_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(rank2_bp)

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

@app.template_filter('comma')
def comma_filter(value):
    return format(int(value), ',')

@app.route("/")
def index():
    etf = get_main_etf()
    chart_labels, chart_values = get_etf_chart_data(etf["id"])

    return render_template(
        "index.html",
        etf=etf,
        chart_labels=chart_labels,
        chart_values=chart_values
    )
    # conn = get_conn()
    # try:
    #     with conn.cursor() as cur:
    #         cur.execute("SELECT * FROM stocks")
    #         stocks = cur.fetchall()
    #     return render_template("index.html", stocks=stocks)
    # finally:
    #     conn.close()


if __name__ == "__main__":
    app.run(debug=True)
