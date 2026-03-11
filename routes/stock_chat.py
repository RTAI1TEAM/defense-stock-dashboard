from flask import Blueprint, render_template, request, session, redirect, url_for, abort
from database import get_conn

stock_chat_bp = Blueprint("stock_chat", __name__)

@stock_chat_bp.route("/stocks/<ticker>/chat-box")
def render_chat_box(ticker):
    conn = get_conn()
    cur = conn.cursor()

    stock_sql = """
    SELECT id, ticker, name_kr
    FROM stocks
    WHERE ticker = %s
    """
    cur.execute(stock_sql, (ticker,))
    stock = cur.fetchone()

    if stock is None:
        cur.close()
        conn.close()
        abort(404)

    chat_sql = """
    SELECT
        sc.id,
        sc.user_id,
        sc.stock_id,
        sc.message,
        DATE_FORMAT(sc.created_at, '%%Y-%%m-%%d %%H:%%i') AS created_at,
        u.nickname
    FROM stock_chats sc
    JOIN users u ON sc.user_id = u.id
    WHERE sc.stock_id = %s
    ORDER BY sc.created_at DESC
    LIMIT 20
    """
    cur.execute(chat_sql, (stock["id"],))
    chat_messages = list(cur.fetchall())

    cur.close()
    conn.close()

    chat_messages.reverse()

    return render_template(
        "components/_stock_chat.html",
        ticker=stock["ticker"],
        chat_messages=chat_messages
    )


@stock_chat_bp.route("/chat/create", methods=["POST"])
def create_chat():
    if "user_id" not in session:
        return redirect(url_for("auth_bp.login_page"))

    user_id = session["user_id"]
    ticker = request.form.get("ticker", "").strip()
    message = request.form.get("message", "").strip()

    if not ticker or not message:
        return redirect(request.referrer or url_for("stocks.stock_list"))

    conn = get_conn()
    cur = conn.cursor()

    stock_sql = """
    SELECT id, ticker
    FROM stocks
    WHERE ticker = %s
    """
    cur.execute(stock_sql, (ticker,))
    stock = cur.fetchone()

    if stock is None:
        cur.close()
        conn.close()
        abort(404)

    insert_sql = """
    INSERT INTO stock_chats (user_id, stock_id, message)
    VALUES (%s, %s, %s)
    """
    cur.execute(insert_sql, (user_id, stock["id"], message))
    conn.commit()

    cur.close()
    conn.close()

    return redirect(request.referrer or url_for("stocks.stock_list"))