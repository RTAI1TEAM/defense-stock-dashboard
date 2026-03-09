from flask import Blueprint, render_template
from finance_data import get_defense_data

stocks_bp = Blueprint('stocks', __name__)

@stocks_bp.route("/stocks")
def stock_list():

    from app import get_conn

    conn = get_conn()
    stock_data = get_defense_data(conn)
    conn.close()

    return render_template("stock_list.html", stocks=stock_data)