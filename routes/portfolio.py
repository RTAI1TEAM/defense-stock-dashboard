import math
import os
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, Response
from database import get_conn

portfolio_bp = Blueprint('portfolio', __name__)


def get_user_id_from_session():
    if 'nickname' not in session:
        return None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE nickname = %s", (session['nickname'],))
            user = cur.fetchone()
            return user['id'] if user else None
    finally:
        conn.close()


@portfolio_bp.route("/portfolio")
def portfolio_view():
    user_id = get_user_id_from_session()
    if user_id is None:
        return Response("""
        <script>
        alert("로그인이 필요한 페이지입니다.");
        location.href="/login";
        </script>
        """, mimetype='text/html')

    conn = get_conn()
    page     = int(request.args.get('page', 1))
    per_page = 5
    offset   = (page - 1) * per_page

    try:
        with conn.cursor() as cursor:
            # 1. 계좌 정보
            cursor.execute("SELECT * FROM mock_accounts WHERE user_id = %s", (user_id,))
            account = cursor.fetchone()

            # 2. 보유 종목 — holding_id + strategy 컬럼 직접 조회
            sql_holdings = """
                SELECT
                    ph.id            AS holding_id,
                    ph.stock_id,
                    ph.quantity,
                    ph.avg_buy_price,
                    ph.strategy,
                    s.name_kr,
                    s.ticker,
                    sd.current_price
                FROM portfolio_holdings ph
                JOIN stocks        s  ON ph.stock_id = s.id
                JOIN stock_details sd ON ph.stock_id = sd.stock_id
                WHERE ph.user_id = %s
                ORDER BY s.name_kr, ph.strategy
            """
            cursor.execute(sql_holdings, (user_id,))
            holdings = cursor.fetchall()

            # 3. 수익 계산
            total_stock_value = 0.0
            for item in holdings:
                avg   = float(item['avg_buy_price'])
                curr  = float(item['current_price'])
                qty   = int(item['quantity'])
                item['total_buy']     = avg * qty
                item['total_current'] = curr * qty
                item['profit_amount'] = item['total_current'] - item['total_buy']
                item['profit_rate']   = (
                    item['profit_amount'] / item['total_buy'] * 100
                    if item['total_buy'] > 0 else 0
                )
                total_stock_value += item['total_current']

            # 4. 파이차트 — 종목명 기준으로 합산 (전략별로 쪼개지지 않게)
            pie_dict = {}
            for item in holdings:
                pie_dict[item['name_kr']] = (
                    pie_dict.get(item['name_kr'], 0) + item['total_current']
                )
            pie_labels = list(pie_dict.keys())
            pie_values = list(pie_dict.values())

            # 5. 거래 내역 (페이지네이션)
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM trades WHERE user_id = %s", (user_id,)
            )
            total_trades = cursor.fetchone()['cnt']
            total_pages  = math.ceil(total_trades / per_page) if total_trades > 0 else 1

            sql_trades = """
                SELECT t.stock_id, t.trade_type, t.quantity, t.price,
                       t.total_amount, t.traded_at, s.name_kr, s.ticker,
                       CASE
                           WHEN t.trade_type = 'SELL' THEN (
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
            """
            cursor.execute(sql_trades, (user_id, per_page, offset))
            trades = cursor.fetchall()

            # 매도 거래에 한해 수익금/수익률 계산
            for trade in trades:
                if trade['trade_type'] == 'SELL' and trade.get('avg_buy_price'):
                    avg  = float(trade['avg_buy_price'])
                    sell = float(trade['price'])
                    qty  = int(trade['quantity'])
                    trade['profit_amount'] = (sell - avg) * qty
                    trade['profit_rate']   = (sell - avg) / avg * 100
                else:
                    trade['profit_amount'] = None
                    trade['profit_rate']   = None

            # 6. 최종 자산 합산
            initial_balance  = float(account['initial_balance']) if account else 0.0
            current_balance  = float(account['current_balance']) if account else 0.0
            total_assets     = current_balance + total_stock_value
            total_profit     = total_assets - initial_balance
            total_profit_rate = (
                total_profit / initial_balance * 100 if initial_balance > 0 else 0
            )
            cash_balance = current_balance
            stock_value  = total_stock_value

    finally:
        conn.close()

    return render_template(
        "portfolio.html",
        total_assets=total_assets,
        total_profit=total_profit,
        total_profit_rate=total_profit_rate,
        holdings=holdings,
        trades=trades,
        pie_labels=pie_labels,
        pie_values=pie_values,
        page=page,
        total_pages=total_pages,
        cash_balance=cash_balance,
        stock_value=stock_value
    )


# ── 매도 API — holding_id 기반 ─────────────────────────────────
@portfolio_bp.route("/api/sell_stock", methods=["POST"])
def sell_stock():
    user_id = get_user_id_from_session()
    if user_id is None:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    data       = request.json
    holding_id = data.get('holding_id')
    sell_qty   = int(data.get('sell_qty', 0))

    if sell_qty <= 0:
        return jsonify({"success": False, "message": "매도 수량은 1주 이상이어야 합니다."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # holding_id + user_id 검증
            cursor.execute(
                """
                SELECT ph.id, ph.quantity, ph.strategy, ph.stock_id,
                       ph.account_id, sd.current_price
                FROM portfolio_holdings ph
                JOIN stock_details sd ON ph.stock_id = sd.stock_id
                WHERE ph.id = %s AND ph.user_id = %s
                """,
                (holding_id, user_id)
            )
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

            cursor.execute(
                "UPDATE mock_accounts SET current_balance = current_balance + %s WHERE user_id = %s",
                (sell_amount, user_id)
            )
            cursor.execute(
                """
                INSERT INTO trades
                    (user_id, account_id, stock_id, trade_type, price, quantity, total_amount, strategy)
                VALUES (%s, %s, %s, 'SELL', %s, %s, %s, %s)
                """,
                (user_id, holding['account_id'], holding['stock_id'],
                 sell_price, sell_qty, sell_amount,
                 f"{holding['strategy']} (수동 매도)")
            )

            if sell_qty == holding['quantity']:
                cursor.execute(
                    "DELETE FROM portfolio_holdings WHERE id = %s", (holding_id,)
                )
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


# ── 전략 변경 API — holding_id 기반 ───────────────────────────
@portfolio_bp.route("/api/change_strategy", methods=["POST"])
def change_strategy():
    user_id = get_user_id_from_session()
    if user_id is None:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    data         = request.json
    holding_id   = data.get('holding_id')
    new_strategy = data.get('strategy')

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, stock_id, strategy FROM portfolio_holdings "
                "WHERE id = %s AND user_id = %s",
                (holding_id, user_id)
            )
            holding = cursor.fetchone()
            if not holding:
                return jsonify({"success": False, "message": "포지션을 찾을 수 없습니다."}), 404

            # 같은 종목에 동일 전략이 이미 있으면 거부
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
    user_id = get_user_id_from_session()
    if not user_id:
        return jsonify({"success": False}), 401

    page = int(request.args.get('page', 1))
    per_page = 5
    offset = (page - 1) * per_page

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 거래 내역 조회 (매도 시 수익 계산용 avg_buy_price 서브쿼리 포함)
            sql_trades = """
                SELECT t.trade_type, t.quantity, t.price, t.total_amount,
                       DATE_FORMAT(t.traded_at, '%%y.%%m.%%d %%H:%%i') AS traded_at,
                       s.name_kr, s.ticker,
                       CASE
                           WHEN t.trade_type = 'SELL' THEN (
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
            """
            cursor.execute(sql_trades, (user_id, per_page, offset))
            raw_trades = cursor.fetchall()

            # 매도 거래에 한해 수익금/수익률 계산 후 JSON 직렬화 가능 형태로 변환
            trades = []
            for trade in raw_trades:
                t = dict(trade)
                if t['trade_type'] == 'SELL' and t.get('avg_buy_price'):
                    avg  = float(t['avg_buy_price'])
                    sell = float(t['price'])
                    qty  = int(t['quantity'])
                    t['profit_amount'] = round((sell - avg) * qty)
                    t['profit_rate']   = round((sell - avg) / avg * 100, 1)
                else:
                    t['profit_amount'] = None
                    t['profit_rate']   = None
                t.pop('avg_buy_price', None)  # 내부 계산용이므로 응답에서 제거
                # price, total_amount를 float으로 변환 (Decimal 직렬화 오류 방지)
                t['price']        = float(t['price'])
                t['total_amount'] = float(t['total_amount'])
                trades.append(t)

            # 전체 페이지 수 계산
            cursor.execute("SELECT COUNT(*) as cnt FROM trades WHERE user_id = %s", (user_id,))
            total_trades = cursor.fetchone()['cnt']
            total_pages = math.ceil(total_trades / per_page) if total_trades > 0 else 1

            return jsonify({
                "success":      True,
                "trades":       trades,
                "total_pages":  total_pages,
                "current_page": page
            })
    finally:
        conn.close()