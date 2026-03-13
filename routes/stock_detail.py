# routes/stock_detail.py — 종목 상세 페이지 라우트

# [ 역할 ]
#   브라우저 요청을 받아 HTML 또는 JSON을 응답하는 Flask 핸들러만 담습니다.
#   비즈니스 로직은 services 패키지로 분리되어 있습니다.

#   - AI 분석 로직  : services/ai_analysis.py
#   - DB 조회 헬퍼  : services/stock_service.py

# [ 라우트 ]
#   /stocks/<ticker>       → show_stock_chart()  종목 상세 페이지 렌더링
#   /invest/execute        → execute_trade()     모의 매수/매도 처리
#   /api/strategy/<ticker> → strategy_api()      전략 신호 및 백테스트 JSON

# [라이브러리 임포트 파트]
# 데이터 분석을 위한 pandas와 Flask 프레임워크의 핵심 기능들을 불러옵니다.
import pandas as pd
from flask import Blueprint, redirect, render_template, request, session, url_for, jsonify, abort

# [내부 모듈 연동 파트]
# DB 연결, 투자 알고리즘(골든크로스, 돌파매매), 뉴스 분석 서비스 등 프로젝트 내 다른 기능들을 가져옵니다.
from database import get_conn
from algorithm import strategy_golden_cross, strategy_breakout, run_backtest
from services.ai_analysis import get_db_or_api_stock_news
from services.stock_service import get_stock, get_stock_list, get_stock_chart_data
from utils.helpers import nan_to_none

# [블루프린트 생성]
# 종목 상세 페이지와 관련된 라우트들을 'stock_detail'이라는 그룹으로 묶어 관리합니다.
stock_detail_bp = Blueprint('stock_detail', __name__)

# [종목 상세 페이지 렌더링 라우트]
@stock_detail_bp.route("/stocks/<ticker>")
def show_stock_chart(ticker):
    # 종목 상세 페이지를 렌더링합니다.
    # URL 예시: /stocks/064350
    # 1. 사용자 인증 확인: 로그인이 되어 있지 않으면 로그인 페이지로 이동시킵니다.
    if "nickname" not in session:
        return redirect(url_for("auth_bp.login_page"))

    user_id = session.get('user_id')

    # 2. 종목 정보 및 시세 데이터 조회: 해당 티커에 맞는 주식 정보와 차트 데이터를 가져옵니다.
    stock   = get_stock(ticker)

    # 2. 종목 기본 정보 조회
    # 해당 티커(예: 064350)에 해당하는 종목 정보를 DB에서 가져옵니다.
    stock = get_stock(ticker)
    if stock is None:
        abort(404) # 종목이 존재하지 않으면 404 에러 발생

    # 사이드바에 표시할 전체 종목 리스트를 가져옵니다.
    stock_list = get_stock_list()

    # 3. 차트 데이터 및 AI 뉴스 분석 결과 조회
    # 기존에 저장된 차트용 데이터와 AI가 분석한 뉴스 리스트, 감성 점수, 요약 내용을 가져옵니다.
    chart_data = get_stock_chart_data(stock["id"])
    # 3. AI 분석 및 뉴스 조회: 해당 종목의 최신 뉴스 정보를 가져와 AI 점수와 브리핑을 생성합니다.
    news_list, score, ai_news = get_db_or_api_stock_news(stock["id"], stock["name_kr"])

    account       = None
    current_price = 0

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 4. 사용자 계좌 정보 조회: 현재 사용자의 모의 투자 잔액을 확인합니다.
            cursor.execute(
                "SELECT current_balance FROM mock_accounts WHERE user_id = %s",
                (user_id,)
            )
            account = cursor.fetchone()

            # 5. 실시간 가격 계산: 가장 최근 시가(종가) 정보를 가져와 현재가로 설정합니다.
            cursor.execute(
                """
                SELECT close_price
                FROM stock_price_history
                WHERE stock_id = %s
                ORDER BY price_date DESC
                LIMIT 1
                """,
                (stock["id"],)
            )
            latest        = cursor.fetchone()
            current_price = float(latest["close_price"]) if latest else 0

            # 6. 백테스트 데이터 준비: 전체 시세 기록을 가져와 알고리즘 연산에 투입합니다.
            cursor.execute(
                """
                SELECT price_date AS date, close_price
                FROM stock_price_history
                WHERE stock_id = %s
                ORDER BY price_date
                """,
                (stock["id"],)
            )
            rows = cursor.fetchall()

        # 7. 전략별 성과 계산: 골든크로스와 돌파매매 전략을 각각 적용하여 지난 수익률을 비교합니다.
        df = pd.DataFrame(rows)

        # 7-1. [골든크로스 전략] 적용 및 백테스트
        # 5일/20일 이동평균선을 이용해 수익률을 계산합니다.
        df_gc = strategy_golden_cross(df)
        profit_gc, _, _, _ = run_backtest(df_gc)

        # 7-2. [돌파 매매 전략] 적용 및 백테스트
        # 20일 전고점 돌파 시점을 기준으로 수익률을 계산합니다.
        df_bo = strategy_breakout(df)
        profit_bo, _, _, _ = run_backtest(df_bo)

        strategies = {
            "GOLDEN_CROSS": {"name": "5/20 골든크로스",   "profit": profit_gc},
            "BREAKOUT":     {"name": "20일 전고점 돌파", "profit": profit_bo},
        }

        chart_labels = [str(r["date"])          for r in rows]
        chart_values = [float(r["close_price"]) for r in rows]

    finally:
        conn.close()

    # 8. 화면 렌더링: 수집된 모든 데이터를 HTML 템플릿(stock_detail.html)에 전달합니다.
    return render_template(
        "stock_detail.html",
        stock_list=stock_list,
        stock=stock,
        ticker=stock["ticker"],
        stock_id=stock["id"],
        strategies=strategies,
        chart_data=chart_data,
        chart_labels=chart_labels,
        chart_values=chart_values,
        news_list=news_list,
        score=score,
        ai_news=ai_news,
        account=account,
        current_price=current_price,
    )

# [모의 투자 실행 라우트]
@stock_detail_bp.route("/invest/execute", methods=['POST'])
def execute_trade():
    # 모의 투자 매수/매도를 처리합니다.

    # 처리 순서:
    #   1. 입력값 검증
    #   2. 종목 현재가 조회
    #   3. 모의 계좌 확인 (없으면 1,000만원으로 신규 생성)
    #   4. BUY: 잔액 차감 → 보유 종목 추가/평단 갱신
    #      SELL: 보유 확인 → 잔액 환원 → 수량 감소 → 0주면 포지션 삭제
    #   5. 거래 내역 기록 → commit

    # 1. 입력 데이터 검증: 종목 ID, 매수/매도 유형, 수량 등을 확인합니다.
    if "nickname" not in session:
        return jsonify({"success": False, "message": "로그인이 필요합니다."})

    # 2. 클라이언트로부터 전달받은 폼 데이터 추출
    ticker_from_form = request.form.get('stock_id')           # 종목 티커 (예: 005930)
    trade_type       = request.form.get('trade_type', 'BUY')  # 거래 종류 (기본값: BUY)
    strategy_name    = request.form.get('strategy') or "일반 매매" # 투자 전략 명칭
    user_id          = session.get('user_id')                 # 세션의 사용자 고유 ID

    # 3. 입력값(수량) 유효성 검사
    try:
        quantity = int(request.form.get('quantity') or 0)
    except ValueError:
        return jsonify({"success": False, "message": "수량 형식이 올바르지 않습니다."})

    if not user_id:
        return jsonify({"success": False, "message": "세션이 만료되었습니다. 다시 로그인해주세요."})
    if not ticker_from_form:
        return jsonify({"success": False, "message": "종목 코드가 누락되었습니다."})
    if quantity <= 0:
        return jsonify({"success": False, "message": "수량을 1주 이상 입력하세요."})

    # 2. 거래 트랜잭션 시작: DB 연결 후 매수 또는 매도 로직을 안전하게 처리합니다.
    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cursor:
            # 시세 확인: 현재 해당 주식의 가격을 다시 조회합니다.
            cursor.execute(
                """
                SELECT s.id, h.close_price, s.name_kr
                FROM stocks s
                INNER JOIN stock_price_history h ON s.id = h.stock_id
                WHERE s.ticker = %s
                ORDER BY h.price_date DESC
                LIMIT 1
                """,
                (ticker_from_form,)
            )
            stock_res = cursor.fetchone()
            if not stock_res:
                return jsonify({"success": False, "message": "해당 종목의 시세 데이터를 찾을 수 없습니다."})

            stock_id     = stock_res['id']
            price        = float(stock_res['close_price'])
            total_amount = price * quantity # 총 매수 금액 계산

            # 계좌 확인: 잔액이 부족하면 매수를 차단하고, 처음인 유저는 1,000만원을 자동 지급합니다.
            cursor.execute(
                "SELECT id, current_balance FROM mock_accounts WHERE user_id = %s",
                (user_id,)
            )
            account = cursor.fetchone()
            if not account:
                cursor.execute(
                    """
                    INSERT INTO mock_accounts (user_id, initial_balance, current_balance)
                    VALUES (%s, 10000000.00, 10000000.00)
                    """,
                    (user_id,)
                )
                conn.commit() # 계좌 생성 확정
                # 생성된 계좌 정보 재조회
                cursor.execute(
                    "SELECT id, current_balance FROM mock_accounts WHERE user_id = %s",
                    (user_id,)
                )
                account = cursor.fetchone()

            if trade_type == 'BUY':
                # 매수 로직: 잔액 차감 및 포트폴리오(portfolio_holdings)에 추가하거나 평단가를 갱신합니다.
                if float(account['current_balance']) < total_amount:
                    return jsonify({"success": False, "message": f"잔액 부족 (필요: {total_amount:,.0f}원)"})

                cursor.execute(
                    "UPDATE mock_accounts SET current_balance = current_balance - %s WHERE id = %s",
                    (total_amount, account['id'])
                )

                # 포트폴리오(보유 종목) 업데이트
                # 이미 보유 중이면 평단가(avg_buy_price)와 수량 갱신, 없으면 새로 삽입 (Upsert 방식)
                cursor.execute(
                    """
                    INSERT INTO portfolio_holdings
                        (user_id, account_id, stock_id, quantity, avg_buy_price, total_invested, strategy)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        avg_buy_price  = (total_invested + VALUES(total_invested)) / (quantity + VALUES(quantity)),
                        quantity       = quantity + VALUES(quantity),
                        total_invested = total_invested + VALUES(total_invested)
                    """,
                    (user_id, account['id'], stock_id, quantity, price, total_amount, strategy_name)
                )
                new_balance = float(account['current_balance']) - total_amount

            elif trade_type == 'SELL':
                # 매도 로직: 보유 수량 확인 후 잔액 증가 및 포트폴리오에서 수량을 차감하거나 삭제합니다.
                cursor.execute(
                    "SELECT quantity FROM portfolio_holdings WHERE user_id = %s AND stock_id = %s AND account_id = %s",
                    (user_id, stock_id, account['id'])
                )
                holding = cursor.fetchone()
                if not holding:
                    return jsonify({"success": False, "message": "보유하지 않은 종목입니다."})
                if holding['quantity'] < quantity:
                    return jsonify({"success": False, "message": f"보유 수량 부족 (보유: {holding['quantity']}주)"})

                cursor.execute(
                    "UPDATE mock_accounts SET current_balance = current_balance + %s WHERE id = %s",
                    (total_amount, account['id'])
                )
                if holding['quantity'] == quantity:
                    cursor.execute(
                        "DELETE FROM portfolio_holdings WHERE user_id = %s AND stock_id = %s AND account_id = %s",
                        (user_id, stock_id, account['id'])
                    )
                else:
                    cursor.execute(
                        "UPDATE portfolio_holdings SET quantity = quantity - %s WHERE user_id = %s AND stock_id = %s AND account_id = %s",
                        (quantity, user_id, stock_id, account['id'])
                    )
                new_balance = float(account['current_balance']) + total_amount

            else:
                return jsonify({"success": False, "message": "잘못된 거래 유형입니다."})

            # 거래 기록: 모든 과정이 끝나면 trades 테이블에 이력을 남깁니다.
            cursor.execute(
                """
                INSERT INTO trades (user_id, account_id, stock_id, trade_type, price, quantity, total_amount, strategy)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, account['id'], stock_id, trade_type, price, quantity, total_amount, strategy_name)
            )

            conn.commit() # 모든 처리가 정상일 때만 DB에 영구 반영합니다.

            return jsonify({
                "success":     True,
                "message":     f"{stock_res['name_kr']} {quantity}주 {trade_type} 완료!",
                "new_balance": format(int(new_balance), ','),
            })

    except Exception as e:
        # 오류 발생 시 모든 데이터 변경 사항 취소 (원자성 보장)
        if conn:
            conn.rollback() # 오류 발생 시 모든 작업을 취소(되돌리기)합니다.
        print(f"Transaction Error: {e}")
        return jsonify({"success": False, "message": f"시스템 오류: {str(e)}"})
    finally:
        # DB 연결 종료
        if conn:
            conn.close()

# 오류 발생 시 모든 작업을 취소(되돌리기)합니다.
@stock_detail_bp.route("/api/strategy/<ticker>")
def strategy_api(ticker):
    # 전략 신호 및 백테스트 결과를 JSON으로 반환합니다.

    # Query params:
    #     strategy : 'golden_cross' | 'breakout'  (기본: golden_cross)
    #     days     : 조회 기간 일수            (기본: 90일)

    # 차트에서 사용자가 전략(골든크로스/돌파)이나 조회 기간을 변경할 때 호출되는 API입니다.
    strategy = request.args.get("strategy", "golden_cross")
    days     = int(request.args.get("days", 90))

    # [데이터베이스 연결 및 원천 데이터 조회]
    try:
        # 2. 데이터베이스 연결 및 종목 ID 조회
        conn = get_conn()
        with conn.cursor() as cur:
            # 1. 입력받은 티커(종목코드)를 사용하여 해당 종목의 고유 ID를 조회합니다.
            cur.execute("SELECT id FROM stocks WHERE ticker = %s", (ticker,))
            stock = cur.fetchone()

            # 종목 정보가 없을 경우 에러 메시지를 반환합니다.
            if not stock:
                return jsonify({"success": False, "message": "종목 없음"})

            # 2. 해당 종목의 과거 시세 기록(날짜, 종가)을 설정된 기간(days)만큼 가져옵니다.
            # 최신순(DESC)으로 가져오되, 요청한 개수(LIMIT)만큼 제한합니다.
            cur.execute(
                """
                SELECT price_date AS date, close_price
                FROM stock_price_history
                WHERE stock_id = %s
                ORDER BY price_date DESC
                LIMIT %s
                """,
                (stock["id"], days)
            )
            rows = cur.fetchall()
        conn.close() # 데이터 조회가 완료되면 연결을 해제합니다.

        # [데이터 가공 및 분석 준비]
        # 3. 시간 순서대로 분석하기 위해 최신순이었던 데이터를 과거순으로 뒤집습니다.
        rows = list(reversed(rows))
        # 4. 효율적인 수치 계산을 위해 리스트 데이터를 Pandas의 DataFrame 구조로 변환합니다.
        df   = pd.DataFrame(rows)

        # [전략 1: 골든크로스(Golden Cross) 처리 파트]
        if strategy == "golden_cross":
            # 단기/장기 이동평균선을 계산하여 골든크로스 신호를 발생시킵니다.
            df = strategy_golden_cross(df)
            # 계산된 신호를 바탕으로 과거에 매매했을 때의 가상 성과를 측정합니다.
            total_profit, trades, win_rate, trade_count = run_backtest(df)
            # 차트 시각화를 위한 지표(MA_short, MA_long)와 백테스트 결과를 JSON으로 반환합니다.
            return jsonify({
                "success":      True,
                "strategy":     "golden_cross",
                "labels":       [str(r["date"])          for r in rows], # 날짜 라벨
                "close":        [float(r["close_price"]) for r in rows], # 종가 데이터
                "ma_short":     [nan_to_none(v)          for v in df["MA_short"].tolist()], # 단기 이평선
                "ma_long":      [nan_to_none(v)          for v in df["MA_long"].tolist()], # 장기 이평선
                "backtest":     trades,        # 상세 매매 내역 (진입/청산 시점 등)
                "total_profit": total_profit,  # 총 누적 수익률
                "win_rate":     win_rate,      # 승률
                "trade_count":  trade_count,   # 총 거래 횟수
            })

        # [전략 2: 돌파매매(Breakout) 처리 파트]
        elif strategy == "breakout":
            # 20일 전고점을 돌파하는 지점을 계산하여 매매 신호를 발생시킵니다.
            df = strategy_breakout(df)
            # 발생한 신호를 바탕으로 백테스팅을 수행하여 성과 데이터를 산출합니다.
            total_profit, trades, win_rate, trade_count = run_backtest(df)
            # 돌파 기준선(High20)과 이동평균선(MA20)을 포함하여 결과를 반환합니다.
            return jsonify({
                "success":      True,
                "strategy":     "breakout",
                "labels":       [str(r["date"])          for r in rows],
                "close":        [float(r["close_price"]) for r in rows],
                "high20":       [nan_to_none(v)          for v in df["High20"].tolist()], # 20일 최고가 라인
                "ma20":         [nan_to_none(v)          for v in df["MA20"].tolist()],   # 20일 이동평균선
                "backtest":     trades,
                "total_profit": total_profit,
                "win_rate":     win_rate,
                "trade_count":  trade_count,
            })
    # DB에서 조회 기간만큼의 시세 데이터를 가져와 전략 알고리즘을 실행한 뒤, 
    # 차트의 보조지표(이동평균선 등)와 백테스트 결과를 JSON으로 반환합니다.
        else:
            return jsonify({"success": False, "message": "알 수 없는 전략"})

    except Exception as e:
        # DB 연결 오류나 계산 중 발생하는 에러 포착
        return jsonify({"success": False, "message": str(e)})
