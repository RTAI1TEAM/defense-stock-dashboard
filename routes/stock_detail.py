from dotenv import load_dotenv
from database import get_conn
from flask import Blueprint, redirect, render_template, request, session, url_for

stock_detail_bp = Blueprint('stock_detail', __name__)

def get_stock(ticker="064350"):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            sql = """
            SELECT id, ticker, name_kr
            FROM stocks
            WHERE ticker=%s
            ORDER BY id
            LIMIT 1
            """
            cursor.execute(sql,(ticker,))
            return cursor.fetchone()
    finally:
        conn.close()

def get_stock_chart_data(stock_id):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            sql = """
            SELECT price_date, close_price
            FROM stock_price_history
            WHERE stock_id = %s
            ORDER BY price_date
            """
            cursor.execute(sql, (stock_id,))
            rows = cursor.fetchall()

            labels = [row["price_date"].strftime("%Y-%m-%d") for row in rows]
            values = [float(row["close_price"]) for row in rows]

            return labels, values
    finally:
        conn.close()

@stock_detail_bp.route("/chart/<ticker>")
def show_stock_chart(ticker):
    if "nickname" not in session:
        return redirect(url_for("auth_bp.login_page"))
    stock = get_stock(ticker)
    chart_labels, chart_values = get_stock_chart_data(stock["id"])

    return render_template(
        "stock_detail.html",
        stock=stock,
        chart_labels=chart_labels,
        chart_values=chart_values
    )
