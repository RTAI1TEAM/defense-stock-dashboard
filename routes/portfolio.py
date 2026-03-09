from flask import Blueprint, render_template

# Blueprint 생성 (이름: portfolio_bp)
portfolio_bp = Blueprint('portfolio', __name__)

@portfolio_bp.route("/portfolio")
def portfolio_view():
    # 임시 유저 정보
    user_info = {"username": "팀원", "balance": 10532000}
    return render_template("portfolio.html", user=user_info)