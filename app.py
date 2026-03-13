# app.py — Flask 애플리케이션 메인 실행 파일

# 기능:
# 1. 애플리케이션 초기화 및 블루프린트(Route) 등록
# 2. 메인 대시보드 페이지(/) 데이터 집계 (ETF 차트, AI 분석, 거래 요약)
# 3. 템플릿 필터 및 컨텍스트 프로세서 설정


from datetime import datetime
from flask import Flask, render_template, session

from database import get_conn
from routes.log_card import dashboard_bp, get_yesterday_trade_summary
from routes.app_login import auth_bp
from routes.rank import rank_bp
from routes.news import news_bp
from routes.stocks import stocks_bp
from routes.portfolio import portfolio_bp
from routes.stock_detail import stock_detail_bp
from routes.profile import profile_bp
from routes.stock_chat import stock_chat_bp
from services.stock_service import get_defense_sector_analysis, get_stock_list, get_defense_data
from config import SECRET_KEY

# 1. Flask 앱 초기화 및 설정
app = Flask(__name__)
app.secret_key = SECRET_KEY  # 세션 암호화 등을 위한 비밀키

# 2. 블루프린트 등록 (기능별 라우트 분리)
app.register_blueprint(auth_bp)         # 로그인/회원가입
app.register_blueprint(rank_bp)         # 랭킹 시스템
app.register_blueprint(news_bp)         # 뉴스 모아보기
app.register_blueprint(stocks_bp)       # 주식 목록
app.register_blueprint(portfolio_bp)    # 내 포트폴리오
app.register_blueprint(stock_detail_bp) # 종목 상세 및 주문
app.register_blueprint(profile_bp)      # 프로필 관리
app.register_blueprint(stock_chat_bp)   # 종목 토론방
app.register_blueprint(dashboard_bp)    # 대시보드 로그카드

def get_main_etf():
    # DB에서 메인으로 표시할 첫 번째 ETF 정보를 가져옵니다.
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, ticker, name_kr FROM etfs ORDER BY id LIMIT 1")
            return cursor.fetchone()
    finally:
        conn.close()


def get_etf_chart_data(etf_id):
    # 특정 ETF의 가격 히스토리를 가져와 차트 라이브러리(Chart.js) 형식으로 변환합니다.
    # - x: 타임스탬프 (ms)
    # - o, h, l, c: 시가, 고가, 저가, 종가
    
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT price_date, open_price, high_price, low_price, close_price
                FROM etf_price_history
                WHERE etf_id = %s
                ORDER BY price_date
                """,
                (etf_id,)
            )
            rows = cursor.fetchall()

        # 데이터 가공: 날짜를 밀리초 단위 타임스탬프로 변환
        return [
            {
                "x": int(datetime.combine(row["price_date"], datetime.min.time()).timestamp() * 1000),
                "o": float(row["open_price"]),
                "h": float(row["high_price"]),
                "l": float(row["low_price"]),
                "c": float(row["close_price"]),
            }
            for row in rows
        ]
    finally:
        conn.close()


def get_color_class(score):
    # AI 분석 점수에 따라 UI에 표시할 부트스트랩 배경 색상 클래스를 반환합니다.
    if score >= 70:
        return "bg-success"  # 초록색 (긍정)
    elif score >= 40:
        return "bg-warning"  # 노란색 (중립)
    else:
        return "bg-danger"   # 빨간색 (부정)


@app.template_filter('comma')
def comma_filter(value):
    # 숫자에 천 단위 콤마를 찍어주는 템플릿 필터 (예: 1,000)
    return format(int(value), ',')

@app.context_processor
def inject_stock_list():
    # 모든 템플릿에서 'stock_list' 변수를 사용할 수 있도록 주입합니다 (네비게이션 바 검색용 등).
    try:
        return dict(stock_list=get_stock_list())
    except Exception:
        return dict(stock_list=[])

@app.route("/")
def index():
    # 메인 페이지 로직: 대시보드에 필요한 모든 데이터를 집계하여 index.html로 전달합니다.
    
    # 1. 메인 ETF 및 차트 데이터 수집
    etf = get_main_etf()
    chart_data = get_etf_chart_data(etf["id"])

    # 2. 방산 섹터 AI 분석 결과 (점수, 코멘트, 관련 뉴스) 가져오기
    score, ai_news, news_list = get_defense_sector_analysis()

    # 3. 로그인 사용자 정보 확인 및 어제자 거래 요약 추출
    user_id = session.get("user_id")
    if user_id:
        # log_card 서비스에서 요약 통계 가져오기
        yesterday_trades, buy_count, sell_count, total_count = get_yesterday_trade_summary(user_id)
    else:
        yesterday_trades, buy_count, sell_count, total_count = [], 0, 0, 0

    # AI 점수 정수화 및 UI 컬러 결정
    try:
        final_score = int(score) if score is not None else 0
    except (ValueError, TypeError):
        final_score = 0
    color_class = get_color_class(final_score)

    # 4. 방산 종목 실시간 시세 및 기본 종목 설정
    defense_stocks = get_defense_data()
    account = None
    current_price = 0
    default_stock = {"ticker": "", "name_kr": ""}

    if defense_stocks:
        default_stock = {
            "ticker": defense_stocks[0]["ticker"],
            "name_kr": defense_stocks[0]["name"],
        }
        current_price = defense_stocks[0]["price"]

    # 5. 로그인 사용자일 경우 현재 가용 잔고 조회
    if user_id:
        conn = get_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT current_balance FROM mock_accounts WHERE user_id = %s",
                    (user_id,),
                )
                account = cursor.fetchone()
        finally:
            conn.close()

    # 6. 최종 렌더링
    return render_template(
        "index.html",
        etf=etf,
        chart_data=chart_data,
        score=score,
        ai_news=ai_news,
        news_list=news_list[:3], # 최신 뉴스 3개만 표시
        color_class=color_class,
        defense_stocks=defense_stocks,
        stock_id=9999,           # 대시보드용 임시 ID
        strategies={},           # 향후 확장용 전략 데이터
        stock=default_stock,     # 기본 표시 종목
        account=account,         # 계좌 잔고
        current_price=current_price,
        yesterday_trades=yesterday_trades,
        buy_count=buy_count,
        sell_count=sell_count,
        total_count=total_count,
    )


if __name__ == "__main__":
    # 개발 서버 실행 (debug=True 설정 시 코드 수정 시 자동 재시작)
    app.run(debug=True)