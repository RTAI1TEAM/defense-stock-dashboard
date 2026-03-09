from flask import Blueprint, render_template
from finance_data import get_defense_data  # 기존 수집 함수 호출

# Blueprint 생성 (이름: stocks_bp)
stocks_bp = Blueprint('stocks', __name__)

@stocks_bp.route("/stocks")
def stock_list():
    stock_data = get_defense_data()
    return render_template("stock_list.html", stocks=stock_data)