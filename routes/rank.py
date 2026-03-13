from flask import Blueprint, render_template
from database import get_conn

rank_bp = Blueprint('rank', __name__)

@rank_bp.route("/rank")
def rank():
    conn = get_conn()
    rankings = []

    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    u.avatar,
                    u.nickname,
                    (ma.current_balance + IFNULL(p_sum.stock_eval, 0)) AS total_asset,
                    CASE 
                        WHEN ma.initial_balance = 0 THEN 0
                        ELSE (
                            (ma.current_balance + IFNULL(p_sum.stock_eval, 0) - ma.initial_balance)
                            / ma.initial_balance * 100
                        )
                    END AS profit_rate
                FROM users u
                JOIN mock_accounts ma ON u.id = ma.user_id
                LEFT JOIN (
                    SELECT 
                        ph.user_id,
                        SUM(ph.quantity * sd.current_price) AS stock_eval
                    FROM portfolio_holdings ph
                    JOIN stock_details sd ON ph.stock_id = sd.stock_id
                    GROUP BY ph.user_id
                ) p_sum ON u.id = p_sum.user_id
                ORDER BY total_asset DESC
            """
            cursor.execute(sql)
            rankings = cursor.fetchall()

            for row in rankings:
                row["avatar"] = row.get("avatar") or "🧑‍💼"
                row["total_asset"] = float(row["total_asset"] or 0)
                row["profit_rate"] = float(row["profit_rate"] or 0)

    except Exception as e:
        print(f"rank 조회 오류: {e}")
        rankings = []

    finally:
        conn.close()

    top3 = rankings[:3]
    others = rankings[3:]

    return render_template("rank.html", top3=top3, others=others)