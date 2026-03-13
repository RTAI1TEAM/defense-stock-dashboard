from flask import Blueprint, render_template
from finance_data import get_defense_data

# [파트 1] 블루프린트 설정
# 설명: 이 파일(stocks.py)을 Flask 메인 서버(app.py)에 연결하기 위한 통로를 만듭니다.
# 'stocks'라는 이름으로 기능을 묶어서 관리하겠다는 선언입니다.
stocks_bp = Blueprint('stocks', __name__)

# [파트 2] 주식 목록 페이지 경로(/stocks) 정의
# 설명: 사용자가 웹사이트 주소 뒤에 /stocks를 붙여서 들어오면 아래 함수를 실행합니다.
@stocks_bp.route("/stocks")
def stock_list():

    # [파트 3] 데이터베이스 연결 및 데이터 가져오기
    # 설명: DB에 접속해서 우리 프로젝트의 핵심인 '방산 종목(K-방산)' 데이터를 불러옵니다. [cite: 4]
    from app import get_conn # 메인 앱에서 설정한 DB 연결 함수를 가져옴

    conn = get_conn()
    # finance_data.py에 정의된 로직을 실행해 전일 기준 종목 정보를 가져옵니다.
    stock_data = get_defense_data(conn) 
    conn.close() # 작업이 끝났으므로 DB 연결 해제

    # [파트 4] 화면 렌더링
    # 설명: 앞서 주석을 달았던 'stock_list.html' 파일에 
    # 위에서 가져온 주식 데이터(stock_data)를 담아서 사용자에게 보여줍니다.
    return render_template("stock_list.html", stocks=stock_data)