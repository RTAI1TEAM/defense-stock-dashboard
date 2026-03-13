"""
routes/portfolio.py — 포트폴리오(내 자산) 페이지 라우트

[ 역할 ]
  로그인한 사용자의 자산 현황, 보유 종목, 거래 내역을 조회하고
  수동 매도 · 전략 변경 API를 제공합니다.

[ 라우트 ]
  /portfolio                  → portfolio_view()    내 자산 대시보드 페이지
  /api/sell_stock   (POST)    → sell_stock()        보유 종목 수동 매도
  /api/change_strategy (POST) → change_strategy()   보유 포지션 전략 변경
  /api/trades                 → get_trades_api()    거래 내역 페이지네이션 API
"""

import math
from flask import Blueprint, render_template, request, jsonify, session, Response
from database import get_conn

# [블루프린트 설정]
# 이 모듈을 'portfolio'로 등록해 app.py에서 blueprint로 불러다 씁니다.
portfolio_bp = Blueprint('portfolio', __name__)

# 거래 내역 페이지당 노출 건수
PER_PAGE = 5


# ──────────────────────────────────────────────
# 내부 헬퍼 함수
# ──────────────────────────────────────────────

def _get_user_id():
    """세션에서 user_id를 반환합니다. 미로그인 시 None."""
    return session.get('user_id')


def _require_login_page():
    """비로그인 접근 시 JS alert 후 /login으로 리다이렉트하는 HTML 응답을 반환합니다."""
    return Response(
        '<script>alert("로그인이 필요한 페이지입니다."); location.href="/login";</script>',
        mimetype='text/html'
    )


def _calc_trade_profit(trade):
    """
    매도 거래의 수익금·수익률을 계산합니다.
    - 매수(BUY) 거래이거나 avg_buy_price 가 없으면 (None, None) 반환
    - 반환: (수익금, 수익률%) — 수익금은 원 단위 반올림, 수익률은 소수점 1자리
    """
    if trade['trade_type'] == 'SELL' and trade.get('avg_buy_price'):
        avg  = float(trade['avg_buy_price'])
        sell = float(trade['price'])
        qty  = int(trade['quantity'])
        return round((sell - avg) * qty), round((sell - avg) / avg * 100, 1)
    return None, None


def _fetch_trades(cursor, user_id, per_page, offset):
    """
    사용자의 거래 내역을 페이지 단위로 조회합니다.
    - 서브쿼리로 매도 시점의 평균 매수가(avg_buy_price)를 동적 계산해 수익률 산출에 활용합니다.
    """
    cursor.execute("""
        SELECT t.trade_type, t.quantity, t.price, t.total_amount,
               DATE_FORMAT(t.traded_at, '%%y.%%m.%%d %%H:%%i') AS traded_at,
               s.name_kr, s.ticker,
               CASE
                   WHEN t.trade_type = 'SELL' THEN (
                       -- 해당 매도 시점까지 누적 매수의 가중평균 단가 계산
                       SELECT SUM(b.price * b.quantity) / NULLIF(SUM(b.quantity), 0)
                       FROM trades b
                       WHERE b.user_id  = t.user_id
                         AND b.stock_id = t.stock_id
                         AND b.trade_type = 'BUY'
                         AND b.traded_at <= t.traded_at
                   )
                   ELSE NULL
               END AS avg_buy_price
        FROM trades t
        JOIN stocks s ON t.stock_id = s.id
        WHERE t.user_id = %s
        ORDER BY t.traded_at DESC
        LIMIT %s OFFSET %s
    """, (user_id, per_page, offset))
    return cursor.fetchall()


# ──────────────────────────────────────────────
# 페이지 라우트
# ──────────────────────────────────────────────

@portfolio_bp.route("/portfolio")
def portfolio_view():
    """내 자산 대시보드 페이지를 렌더링합니다."""
    # 1. 로그인 확인
    user_id = _get_user_id()
    if user_id is None:
        return _require_login_page()

    page   = int(request.args.get('page', 1))
    offset = (page - 1) * PER_PAGE

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 2. 모의 계좌 잔고 조회
            cursor.execute("SELECT * FROM mock_accounts WHERE user_id = %s", (user_id,))
            account = cursor.fetchone()

            # 3. 보유 종목 조회 (현재가 포함)
            cursor.execute("""
                SELECT ph.id AS holding_id, ph.stock_id, ph.quantity,
                       ph.avg_buy_price, ph.strategy,
                       s.name_kr, s.ticker, sd.current_price
                FROM portfolio_holdings ph
                JOIN stocks        s  ON ph.stock_id = s.id
                JOIN stock_details sd ON ph.stock_id = sd.stock_id
                WHERE ph.user_id = %s
                ORDER BY s.name_kr, ph.strategy
            """, (user_id,))
            holdings = cursor.fetchall()

            # 4. 보유 종목별 평가금액 · 수익률 계산 + 도넛 차트용 비중 집계
            total_stock_value = 0.0
            pie_dict = {}
            for item in holdings:
                avg  = float(item['avg_buy_price'])
                curr = float(item['current_price'])
                qty  = int(item['quantity'])
                item['total_buy']     = avg * qty
                item['total_current'] = curr * qty
                item['profit_amount'] = item['total_current'] - item['total_buy']
                item['profit_rate']   = (
                    item['profit_amount'] / item['total_buy'] * 100
                    if item['total_buy'] > 0 else 0
                )
                total_stock_value += item['total_current']
                # 종목명 기준으로 합산 (동일 종목 여러 전략 보유 시 합쳐서 차트에 표시)
                pie_dict[item['name_kr']] = pie_dict.get(item['name_kr'], 0) + item['total_current']

            # 5. 거래 내역 조회 (페이지네이션)
            cursor.execute("SELECT COUNT(*) as cnt FROM trades WHERE user_id = %s", (user_id,))
            total_trades = cursor.fetchone()['cnt']
            total_pages  = math.ceil(total_trades / PER_PAGE) if total_trades > 0 else 1

            trades = _fetch_trades(cursor, user_id, PER_PAGE, offset)
            for trade in trades:
                trade['profit_amount'], trade['profit_rate'] = _calc_trade_profit(trade)

            # 6. 총 자산 · 총 수익 계산
            cash_balance      = float(account['current_balance']) if account else 0.0
            initial_balance   = float(account['initial_balance']) if account else 0.0
            total_assets      = cash_balance + total_stock_value
            total_profit      = total_assets - initial_balance
            total_profit_rate = total_profit / initial_balance * 100 if initial_balance > 0 else 0

    finally:
        conn.close()

    return render_template(
        "portfolio.html",
        total_assets=total_assets,
        total_profit=total_profit,
        total_profit_rate=total_profit_rate,
        holdings=holdings,
        trades=trades,
        pie_labels=list(pie_dict.keys()),
        pie_values=list(pie_dict.values()),
        page=page,
        total_pages=total_pages,
        cash_balance=cash_balance,
        stock_value=total_stock_value,
    )


# ──────────────────────────────────────────────
# API 엔드포인트
# ──────────────────────────────────────────────

@portfolio_bp.route("/api/sell_stock", methods=["POST"])
def sell_stock():
    """
    보유 종목 수동 매도 API
    - 요청 JSON: { holding_id, sell_qty }
    - 처리 순서: 수량 검증 → 잔고 증가 → 거래 기록 → 보유 수량 차감/삭제
    """
    # 1. 로그인 확인
    user_id = _get_user_id()
    if user_id is None:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    data       = request.json
    holding_id = data.get('holding_id')
    sell_qty   = int(data.get('sell_qty', 0))

    # 2. 입력값 검증
    if sell_qty <= 0:
        return jsonify({"success": False, "message": "매도 수량은 1주 이상이어야 합니다."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 3. 보유 종목 조회 (현재가 포함)
            cursor.execute("""
                SELECT ph.id, ph.quantity, ph.strategy, ph.stock_id,
                       ph.account_id, sd.current_price
                FROM portfolio_holdings ph
                JOIN stock_details sd ON ph.stock_id = sd.stock_id
                WHERE ph.id = %s AND ph.user_id = %s
            """, (holding_id, user_id))
            holding = cursor.fetchone()

            if not holding:
                return jsonify({"success": False, "message": "보유 종목 없음"}), 400
            if sell_qty > holding['quantity']:
                return jsonify({
                    "success": False,
                    "message": f"최대 {holding['quantity']}주까지만 매도할 수 있습니다."
                }), 400

            sell_price  = float(holding['current_price'])
            sell_amount = sell_qty * sell_price

            # 4. 계좌 잔고 복원
            cursor.execute(
                "UPDATE mock_accounts SET current_balance = current_balance + %s WHERE user_id = %s",
                (sell_amount, user_id)
            )

            # 5. 거래 내역 기록
            cursor.execute("""
                INSERT INTO trades
                    (user_id, account_id, stock_id, trade_type, price, quantity, total_amount, strategy)
                VALUES (%s, %s, %s, 'SELL', %s, %s, %s, %s)
            """, (
                user_id, holding['account_id'], holding['stock_id'],
                sell_price, sell_qty, sell_amount,
                f"{holding['strategy']} (수동 매도)"
            ))

            # 6. 보유 수량 차감 (전량 매도 시 레코드 삭제)
            if sell_qty == holding['quantity']:
                cursor.execute("DELETE FROM portfolio_holdings WHERE id = %s", (holding_id,))
            else:
                cursor.execute(
                    "UPDATE portfolio_holdings SET quantity = quantity - %s WHERE id = %s",
                    (sell_qty, holding_id)
                )

        conn.commit()
        return jsonify({"success": True, "message": f"{sell_qty}주 매도가 완료되었습니다."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()


@portfolio_bp.route("/api/change_strategy", methods=["POST"])
def change_strategy():
    """
    보유 포지션의 투자 전략을 변경하는 API
    - 요청 JSON: { holding_id, strategy }
    - 동일 종목에 같은 전략이 이미 있으면 중복 방지 오류 반환
    """
    # 1. 로그인 확인
    user_id = _get_user_id()
    if user_id is None:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    data         = request.json
    holding_id   = data.get('holding_id')
    new_strategy = data.get('strategy')

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 2. 변경 대상 포지션 존재 여부 확인
            cursor.execute(
                "SELECT id, stock_id, strategy FROM portfolio_holdings WHERE id = %s AND user_id = %s",
                (holding_id, user_id)
            )
            holding = cursor.fetchone()
            if not holding:
                return jsonify({"success": False, "message": "포지션을 찾을 수 없습니다."}), 404

            # 3. 동일 종목 · 동일 전략 중복 체크
            cursor.execute(
                "SELECT id FROM portfolio_holdings "
                "WHERE user_id = %s AND stock_id = %s AND strategy = %s AND id != %s",
                (user_id, holding['stock_id'], new_strategy, holding_id)
            )
            if cursor.fetchone():
                return jsonify({
                    "success": False,
                    "message": f"이미 '{new_strategy}' 전략으로 보유 중인 포지션이 있습니다."
                }), 400

            # 4. 전략 업데이트
            cursor.execute(
                "UPDATE portfolio_holdings SET strategy = %s WHERE id = %s",
                (new_strategy, holding_id)
            )
        conn.commit()
        return jsonify({"success": True, "message": f"전략이 '{new_strategy}'(으)로 변경되었습니다."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()


@portfolio_bp.route("/api/trades")
def get_trades_api():
    """
    거래 내역 페이지네이션 API — 프론트엔드 AJAX 전용
    - GET 파라미터: page (기본값 1)
    - 응답 JSON: { success, trades[], total_pages, current_page }
    """
    # 1. 로그인 확인
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"success": False}), 401

    page   = int(request.args.get('page', 1))
    offset = (page - 1) * PER_PAGE

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 2. 거래 내역 조회 및 수익 계산
            trades = []
            for trade in _fetch_trades(cursor, user_id, PER_PAGE, offset):
                t = dict(trade)
                t['profit_amount'], t['profit_rate'] = _calc_trade_profit(t)
                t.pop('avg_buy_price', None)          # 내부 계산용 컬럼은 응답에서 제거
                t['price']        = float(t['price'])
                t['total_amount'] = float(t['total_amount'])
                trades.append(t)

            # 3. 전체 페이지 수 계산 (프론트 페이지네이션 UI용)
            cursor.execute("SELECT COUNT(*) as cnt FROM trades WHERE user_id = %s", (user_id,))
            total_trades = cursor.fetchone()['cnt']
            total_pages  = math.ceil(total_trades / PER_PAGE) if total_trades > 0 else 1

            return jsonify({
                "success":      True,
                "trades":       trades,
                "total_pages":  total_pages,
                "current_page": page,
            })
    finally:
        conn.close()
