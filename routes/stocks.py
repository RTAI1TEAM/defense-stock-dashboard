from flask import Blueprint, render_template
from services.stock_service import get_defense_data

# 'stocks'라는 이름의 블루프린트 객체 생성
# 블루프린트를 사용하면 라우트를 모듈별로 분리하여 관리할 수 있습니다.
stocks_bp = Blueprint('stocks', __name__)

# 주식 목록 페이지 라우트
# 경로: /stocks
# 설명: 방산주 데이터를 서비스 레이어에서 가져와 HTML 템플릿에 전달

@stocks_bp.route("/stocks")
def stock_list():
    # 1. 비즈니스 로직 처리: 서비스 클래스에서 방산주 관련 데이터를 가져옴
    stock_data = get_defense_data()
    
    # 2. 렌더링: 가져온 데이터를 'stocks'라는 변수명으로 stock_list.html에 전달하여 화면을 구성
    return render_template("stock_list.html", stocks=stock_data)