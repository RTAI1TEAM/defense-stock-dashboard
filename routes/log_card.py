from flask import Blueprint, render_template, session
from database import get_conn

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return render_template("dashboard.html", yesterday_trades=[], buy_count=0, sell_count=0, total_count=0)

    user_id = session["user_id"]
    conn = get_conn()

    try:
        with conn.cursor() as cur:
            # 어제 거래내역 조회
            cur.execute("""
                SELECT 
                    t.id,
                    t.trade_type,
                    t.price,
                    t.quantity,
                    t.total_amount,
                    t.strategy,
                    t.traded_at,
                    s.name_kr AS stock_name
                FROM trades t
                JOIN stocks s ON t.stock_id = s.id
                WHERE t.user_id = %s
                  AND DATE(t.traded_at) = CURDATE() - INTERVAL 1 DAY
                ORDER BY t.traded_at DESC
                LIMIT 5
            """, (user_id,))
            yesterday_trades = cur.fetchall()

            # 어제 매수/매도 개수 요약
            cur.execute("""
                SELECT
                    SUM(CASE WHEN trade_type = 'BUY' THEN 1 ELSE 0 END) AS buy_count,
                    SUM(CASE WHEN trade_type = 'SELL' THEN 1 ELSE 0 END) AS sell_count,
                    COUNT(*) AS total_count
                FROM trades
                WHERE user_id = %s
                  AND DATE(traded_at) = CURDATE() - INTERVAL 1 DAY
            """, (user_id,))
            summary = cur.fetchone()

        buy_count = summary["buy_count"] or 0
        sell_count = summary["sell_count"] or 0
        total_count = summary["total_count"] or 0

    finally:
        conn.close()

    return render_template(
        "components/log_card.html",
        yesterday_trades=yesterday_trades,
        buy_count=buy_count,
        sell_count=sell_count,
        total_count=total_count
    )