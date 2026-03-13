from flask import Blueprint, render_template
from services.stock_service import get_defense_data

stocks_bp = Blueprint('stocks', __name__)


@stocks_bp.route("/stocks")
def stock_list():
    stock_data = get_defense_data()
    return render_template("stock_list.html", stocks=stock_data)