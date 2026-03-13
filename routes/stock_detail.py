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
    종목 상세 페이지를 렌더링합니다.
    URL 예시: /stocks/064350
    """
    if "nickname" not in session:
        return redirect(url_for("auth_bp.login_page"))

    user_id = session.get('user_id')
    stock   = get_stock(ticker)

    if stock is None:
        abort(404)

    stock_list = get_stock_list()
    chart_data = get_stock_chart_data(stock["id"])
    news_list, score, ai_news = get_db_or_api_stock_news(stock["id"], stock["name_kr"])

    account       = None
    current_price = 0

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT current_balance FROM mock_accounts WHERE user_id = %s",
                (user_id,)
            )
            account = cursor.fetchone()

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

        df = pd.DataFrame(rows)

        df_gc = strategy_golden_cross(df)
        profit_gc, _, _, _ = run_backtest(df_gc)

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
    모의 투자 매수/매도를 처리합니다.

    처리 순서:
      1. 입력값 검증
      2. 종목 현재가 조회
      3. 모의 계좌 확인 (없으면 1,000만원으로 신규 생성)
      4. BUY: 잔액 차감 → 보유 종목 추가/평단 갱신
         SELL: 보유 확인 → 잔액 환원 → 수량 감소 → 0주면 포지션 삭제
      5. 거래 내역 기록 → commit
    """
    if "nickname" not in session:
        return jsonify({"success": False, "message": "로그인이 필요합니다."})

    ticker_from_form = request.form.get('stock_id')
    trade_type       = request.form.get('trade_type', 'BUY')
    strategy_name    = request.form.get('strategy') or "일반 매매"
    user_id          = session.get('user_id')

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
            total_amount = price * quantity

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
                conn.commit()
                cursor.execute(
                    "SELECT id, current_balance FROM mock_accounts WHERE user_id = %s",
                    (user_id,)
                )
                account = cursor.fetchone()

            if trade_type == 'BUY':
                if float(account['current_balance']) < total_amount:
                    return jsonify({"success": False, "message": f"잔액 부족 (필요: {total_amount:,.0f}원)"})

                cursor.execute(
                    "UPDATE mock_accounts SET current_balance = current_balance - %s WHERE id = %s",
                    (total_amount, account['id'])
                )
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

            cursor.execute(
                """
                INSERT INTO trades (user_id, account_id, stock_id, trade_type, price, quantity, total_amount, strategy)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, account['id'], stock_id, trade_type, price, quantity, total_amount, strategy_name)
            )

            conn.commit()

            new_balance = float(account['current_balance']) - total_amount
            return jsonify({
                "success":     True,
                "message":     f"{stock_res['name_kr']} {quantity}주 {trade_type} 완료!",
                "new_balance": format(int(new_balance), ','),
            })

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Transaction Error: {e}")
        return jsonify({"success": False, "message": f"시스템 오류: {str(e)}"})
    finally:
        if conn:
            conn.close()


@stock_detail_bp.route("/api/strategy/<ticker>")
def strategy_api(ticker):
    """
    전략 신호 및 백테스트 결과를 JSON으로 반환합니다.

    Query params:
        strategy : 'golden_cross' | 'breakout'  (기본: golden_cross)
        days     : 조회 기간 일수            (기본: 90일)
    """
    strategy = request.args.get("strategy", "golden_cross")
    days     = int(request.args.get("days", 90))

    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM stocks WHERE ticker = %s", (ticker,))
            stock = cur.fetchone()
            if not stock:
                return jsonify({"success": False, "message": "종목 없음"})

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

        rows = list(reversed(rows))
        df   = pd.DataFrame(rows)

        if strategy == "golden_cross":
            df = strategy_golden_cross(df)
            total_profit, trades, win_rate, trade_count = run_backtest(df)
            return jsonify({
                "success":      True,
                "strategy":     "golden_cross",
                "labels":       [str(r["date"])          for r in rows],
                "close":        [float(r["close_price"]) for r in rows],
                "ma_short":     [nan_to_none(v)          for v in df["MA_short"].tolist()],
                "ma_long":      [nan_to_none(v)          for v in df["MA_long"].tolist()],
                "backtest":     trades,
                "total_profit": total_profit,
                "win_rate":     win_rate,
                "trade_count":  trade_count,
            })

        elif strategy == "breakout":
            df = strategy_breakout(df)
            total_profit, trades, win_rate, trade_count = run_backtest(df)
            return jsonify({
                "success":      True,
                "strategy":     "breakout",
                "labels":       [str(r["date"])          for r in rows],
                "close":        [float(r["close_price"]) for r in rows],
                "high20":       [nan_to_none(v)          for v in df["High20"].tolist()],
                "ma20":         [nan_to_none(v)          for v in df["MA20"].tolist()],
                "backtest":     trades,
                "total_profit": total_profit,
                "win_rate":     win_rate,
                "trade_count":  trade_count,
            })

        else:
            return jsonify({"success": False, "message": "알 수 없는 전략"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
