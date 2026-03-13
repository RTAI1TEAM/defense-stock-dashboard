from flask import Blueprint, render_template, session
from database import get_conn

# [블루프린트 설정] 
# 이 코드를 'dashboard'라는 이름의 모듈로 등록해서 메인 서버(app.py)에서 불러다 쓸 수 있게 해줘.
dashboard_bp = Blueprint("dashboard", __name__)


def get_yesterday_trade_summary(user_id):
    # [어제 거래 데이터 추출 헬퍼 함수]
    # 이 함수는 실제 DB에 접속해서 어제의 기록만 쏙쏙 골라오는 역할을 담당해.
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 1. 어제 발생한 개별 거래 리스트 조회 (최근 5개만)
            # CURDATE() - INTERVAL 1 DAY 를 써서 정확히 '어제' 날짜의 데이터만 가져와.
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

            # 2. 어제 거래 통계 계산 (매수 횟수, 매도 횟수, 총 횟수)
            # CASE 문을 써서 한 번의 쿼리로 매수/매도 각각의 개수를 효율적으로 계산해.
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

        # 가져온 결과들을 튜플 형태로 깔끔하게 반환!
        return (
            yesterday_trades,
            summary["buy_count"] or 0,
            summary["sell_count"] or 0,
            summary["total_count"] or 0,
        )
    finally:
        # DB 연결은 작업이 끝나면 반드시 닫아줘야 서버가 안 지쳐잇!
        conn.close()


@dashboard_bp.route("/dashboard")
def dashboard():
    # [/dashboard 경로 접속 시 실행되는 함수]
    # 사용자 화면에 '어제 요약 카드'를 렌더링해서 보여주는 창구야.

    # 1. 로그인 확인
    # 로그인이 안 되어 있으면 빈 데이터를 보내서 에러가 안 나게 방어해줘.
    if "user_id" not in session:
        return render_template("components/log_card.html", yesterday_trades=[], buy_count=0, sell_count=0, total_count=0)

    # 2. 데이터 수집
    # 위에서 만든 헬퍼 함수를 호출해서 세션에 저장된 유저의 어제 기록을 가져와.
    yesterday_trades, buy_count, sell_count, total_count = get_yesterday_trade_summary(session["user_id"])

    # 3. 화면 전달
    # 수집한 따끈따끈한 데이터를 'log_card.html' 템플릿에 실어서 보낸다잇!
    return render_template(
        "components/log_card.html",
        yesterday_trades=yesterday_trades,
        buy_count=buy_count,
        sell_count=sell_count,
        total_count=total_count
    )