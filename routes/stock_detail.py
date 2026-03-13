"""
routes/stock_detail.py — 종목 상세 페이지 라우트

[ 역할 ]
  브라우저 요청을 받아 HTML 또는 JSON을 응답하는 Flask 핸들러만 담습니다.
  비즈니스 로직은 services 패키지로 분리되어 있습니다.

  - AI 분석 로직  : services/ai_analysis.py
  - DB 조회 헬퍼  : services/stock_service.py

[ 라우트 ]
  /stocks/<ticker>       → show_stock_chart()  종목 상세 페이지 렌더링
  /invest/execute        → execute_trade()     모의 매수/매도 처리
  /api/strategy/<ticker> → strategy_api()      전략 신호 및 백테스트 JSON
"""

import math
import pandas as pd
from flask import Blueprint, redirect, render_template, request, session, url_for, jsonify, abort

from database import get_conn
from algorithm import strategy_golden_cross, strategy_breakout, run_backtest
from services.ai_analysis import get_db_or_api_stock_news
from services.stock_service import get_stock, get_stock_list, get_stock_chart_data


stock_detail_bp = Blueprint('stock_detail', __name__)


def nan_to_none(val):
    """pandas NaN을 JSON 직렬화 가능한 None으로 변환합니다."""
    try:
        if val is None:
            return None
        if isinstance(val, float) and math.isnan(val):
            return None
        return val
    except Exception:
        return None


@stock_detail_bp.route("/stocks/<ticker>")
def show_stock_chart(ticker):
    """
    [종목 상세 페이지 렌더링]
    사용자가 종목을 클릭했을 때 차트, 뉴스, AI 분석, 백테스트 결과를 종합하여 
    상세 화면(stock_detail.html)을 보여줍니다.
    """

    # 1. 사용자 인증 확인
    # 세션에 닉네임이 없으면 로그인되지 않은 상태로 간주하고 로그인 페이지로 리다이렉트합니다.
    if "nickname" not in session:
        return redirect(url_for("auth_bp.login_page"))

    user_id = session.get('user_id')

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
    news_list, score, ai_news = get_db_or_api_stock_news(stock["id"], stock["name_kr"])

    account       = None
    current_price = 0

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 4. 사용자의 모의투자 계좌 잔액 조회
            # 매수/매도 UI에서 보여줄 현재 사용자의 투자 가능 금액을 가져옵니다.
            cursor.execute(
                "SELECT current_balance FROM mock_accounts WHERE user_id = %s",
                (user_id,)
            )
            account = cursor.fetchone()

            # 5. 해당 종목의 최신 가격(현재가) 조회
            # 가장 최근 날짜의 종가를 가져와 현재 시세로 활용합니다.
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

            # 6. 백테스트를 위한 전체 가격 히스토리 조회
            # 전략 검증을 위해 과거부터 현재까지의 모든 가격 데이터를 날짜순으로 가져옵니다.
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

        # 7. 투자 전략 알고리즘 적용 (Pandas 활용)
        # DB에서 가져온 로우 데이터를 데이터프레임으로 변환합니다.
        df = pd.DataFrame(rows)

        # 7-1. [골든크로스 전략] 적용 및 백테스트
        # 5일/20일 이동평균선을 이용해 수익률을 계산합니다.
        df_gc = strategy_golden_cross(df)
        profit_gc, _, _, _ = run_backtest(df_gc)

        # 7-2. [돌파 매매 전략] 적용 및 백테스트
        # 20일 전고점 돌파 시점을 기준으로 수익률을 계산합니다.
        df_bo = strategy_breakout(df)
        profit_bo, _, _, _ = run_backtest(df_bo)

        # 8. 화면 요약 정보 구성
        # HTML 템플릿에서 반복문으로 보여줄 수 있도록 전략별 결과를 딕셔너리로 저장합니다.
        strategies = {
            "GOLDEN_CROSS": {"name": "5/20 골든크로스",   "profit": profit_gc},
            "BREAKOUT":     {"name": "20일 전고점 돌파", "profit": profit_bo},
        }

        # 9. 프론트엔드 차트 라이브러리(Chart.js)용 데이터 추출
        # x축 라벨(날짜)과 y축 값(종가)을 리스트 형태로 준비합니다.
        chart_labels = [str(r["date"])          for r in rows]
        chart_values = [float(r["close_price"]) for r in rows]

    finally:
        # DB 연결 종료
        conn.close()

    # 10. 최종 렌더링
    # 수집한 모든 데이터를 템플릿 엔진(Jinja2)에 전달하여 페이지를 완성합니다.
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

@stock_detail_bp.route("/invest/execute", methods=['POST'])
def execute_trade():
    """
    [모의 투자 실행 API]
    사용자의 매수 요청을 받아 계좌 잔액 확인, 포트폴리오 업데이트, 거래 내역 기록을 수행합니다.
    """
    # 1. 사용자 세션 확인 (로그인 여부 체크)
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

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cursor:
            # --- [단계 1] 해당 종목의 최신 현재 가격 조회 ---
            # stock_price_history 테이블에서 가장 최근(오늘/최근일)의 종가(close_price)를 가져옴
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

            # --- [단계 2] 사용자 모의 계좌 조회 및 생성 ---
            # 계좌가 없는 신규 사용자의 경우 기본 자산 1,000만원으로 자동 생성
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

            # --- [단계 3] 매수(BUY) 로직 처리 ---
            if trade_type == 'BUY':
                # 3-1. 잔액 검증
                if float(account['current_balance']) < total_amount:
                    return jsonify({"success": False, "message": f"잔액 부족 (필요: {total_amount:,.0f}원)"})

                # 3-2. 계좌 잔액 차감
                cursor.execute(
                    "UPDATE mock_accounts SET current_balance = current_balance - %s WHERE id = %s",
                    (total_amount, account['id'])
                )

                # 3-3. 포트폴리오(보유 종목) 업데이트
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

            # --- [단계 4] 거래 내역(trades) 기록 ---
            # 나중에 매매 일지나 수익률 분석을 위해 모든 거래 로그를 남김
            cursor.execute(
                """
                INSERT INTO trades (user_id, account_id, stock_id, trade_type, price, quantity, total_amount, strategy)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, account['id'], stock_id, trade_type, price, quantity, total_amount, strategy_name)
            )

            # --- [단계 5] 트랜잭션 확정 ---
            conn.commit()

            # --- [단계 6] 성공 응답 반환 ---
            # 프론트엔드에서 즉시 UI 업데이트를 할 수 있도록 계산된 새 잔액을 함께 전달
            new_balance = float(account['current_balance']) - total_amount
            return jsonify({
                "success":     True,
                "message":     f"{stock_res['name_kr']} {quantity}주 {trade_type} 완료!",
                "new_balance": format(int(new_balance), ','),
            })

    except Exception as e:
        # 오류 발생 시 모든 데이터 변경 사항 취소 (원자성 보장)
        if conn:
            conn.rollback()
        print(f"Transaction Error: {e}")
        return jsonify({"success": False, "message": f"시스템 오류: {str(e)}"})
    finally:
        # DB 연결 종료
        if conn:
            conn.close()


@stock_detail_bp.route("/api/strategy/<ticker>")
def strategy_api(ticker):
    """
    [전략 데이터 전용 API]
    프론트엔드에서 실시간으로 전략을 바꿀 때(예: 버튼 클릭) 차트 데이터와 백테스트 결과를 JSON으로 반환합니다.

    Query params:
        strategy : 'golden_cross' | 'breakout'  (기본: golden_cross)
        days     : 조회 기간 일수            (기본: 90일)
    """
    # 1. 쿼리 파라미터 추출 및 기본값 설정
    strategy = request.args.get("strategy", "golden_cross")  # 요청 전략
    days     = int(request.args.get("days", 90))             # 조회 기간

    try:
        # 2. 데이터베이스 연결 및 종목 ID 조회
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM stocks WHERE ticker = %s", (ticker,))
            stock = cur.fetchone()
            if not stock:
                return jsonify({"success": False, "message": "종목 없음"})
            
            # 3. 지정된 기간만큼의 가격 역사 데이터 조회 (최신순으로 가져온 뒤 역순 정렬 예정)
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
        conn.close()

        # 4. 데이터 가공: 최신순 데이터를 과거순으로 뒤집고 Pandas DataFrame으로 변환
        rows = list(reversed(rows))
        df   = pd.DataFrame(rows)

        # 5. 전략별 로직 실행 (전략에 따라 다른 지표 계산 및 백테스트 수행)

        # [A] 골든크로스 전략 처리
        if strategy == "golden_cross":
            # 이평선(MA) 계산 및 신호 생성
            df = strategy_golden_cross(df)
            # 생성된 신호를 기반으로 백테스트 실행 (수익률, 매매내역, 승률, 매매횟수 반환)
            total_profit, trades, win_rate, trade_count = run_backtest(df)
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

        # [B] 돌파 매매(Breakout) 전략 처리
        elif strategy == "breakout":
            # 20일 최고점, 20일 이평선 등 지표 계산
            df = strategy_breakout(df)
            # 백테스트 실행
            total_profit, trades, win_rate, trade_count = run_backtest(df)
            
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

        # [C] 정의되지 않은 전략 요청 시 예외 처리
        else:
            return jsonify({"success": False, "message": "알 수 없는 전략"})

    except Exception as e:
        # DB 연결 오류나 계산 중 발생하는 에러 포착
        return jsonify({"success": False, "message": str(e)})
