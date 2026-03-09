import os
import pymysql
from flask import Blueprint, render_template

rank_bp = Blueprint('rank', __name__)

def get_db_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        db=os.getenv('DB_NAME'),
        charset=os.getenv('DB_CHARSET'),
        cursorclass=pymysql.cursors.DictCursor
    )

@rank_bp.route("/rank")
def ranking():
    conn = get_db_connection()
    
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT 
                    u.nickname,
                    (ma.current_balance + IFNULL(p_sum.stock_eval, 0)) AS total_asset,
                    CASE 
                        WHEN ma.initial_balance = 0 THEN 0
                        ELSE ((ma.current_balance + IFNULL(p_sum.stock_eval, 0) - ma.initial_balance) / ma.initial_balance * 100)
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
                ORDER BY total_asset DESC;
            """
            cursor.execute(sql)
            rankings = cursor.fetchall()
            
            for row in rankings:
                row['total_asset'] = float(row['total_asset'])
                row['profit_rate'] = float(row['profit_rate'])

    except Exception as e:
        print(f"랭킹 조회 중 오류 발생: {e}")
        rankings = []
    finally:
        conn.close()

    return render_template('rank.html', rankings=rankings)