import math
import os
from flask import Blueprint, render_template, request, jsonify, session
from database import get_conn

portfolio_bp = Blueprint('portfolio', __name__)

@portfolio_bp.route("/portfolio")
def portfolio_view():
    conn = get_conn()
    
    # 📌 로그인 세션 대비 (로그인 안 되어 있으면 테스트 유저 1번 사용)
    user_id = session.get('user_id', 1) 
    
    # 페이지네이션 설정
    page = int(request.args.get('page', 1))
    per_page = 5
    offset = (page - 1) * per_page

    try:
        with conn.cursor() as cursor:
            # 1. 계좌 정보
            cursor.execute("SELECT * FROM mock_accounts WHERE user_id = %s", (user_id,))
            account = cursor.fetchone()

            # 2. 보유 종목 리스트
            sql_holdings = """
                SELECT 
                    s.name_kr, ph.quantity, ph.avg_buy_price, sd.current_price, ph.stock_id
                FROM portfolio_holdings ph
                JOIN stocks s ON ph.stock_id = s.id
                JOIN stock_details sd ON ph.stock_id = sd.stock_id
                WHERE ph.user_id = %s
            """
            cursor.execute(sql_holdings, (user_id,))
            holdings = cursor.fetchall()

            # 3. 종목별 최근 AI 전략 매핑 (가장 최근 BUY 거래 기준)
            strategy_dict = {}
            if holdings:
                stock_ids = [str(h['stock_id']) for h in holdings]
                ids_str = ",".join(stock_ids)
                sql_strategy = f"""
                    SELECT t.stock_id, t.strategy 
                    FROM trades t
                    WHERE t.user_id = %s AND t.trade_type = 'BUY' AND t.stock_id IN ({ids_str})
                    ORDER BY t.traded_at ASC
                """
                cursor.execute(sql_strategy, (user_id,))
                strategies = cursor.fetchall()
                for s in strategies:
                    strategy_dict[s['stock_id']] = s['strategy']

            # 4. 수익금 계산 및 차트 데이터 
            total_stock_value = 0.0
            pie_labels = []
            pie_values = []
            
            for item in holdings:
                avg_price = float(item['avg_buy_price'])
                curr_price = float(item['current_price'])
                qty = int(item['quantity'])

                item['total_buy'] = avg_price * qty
                item['total_current'] = curr_price * qty
                item['profit_amount'] = item['total_current'] - item['total_buy']
                item['profit_rate'] = (item['profit_amount'] / item['total_buy']) * 100 if item['total_buy'] > 0 else 0
                
                total_stock_value += item['total_current']
                item['strategy'] = strategy_dict.get(item['stock_id'], '수동 운용')
                
                pie_labels.append(item['name_kr'])
                pie_values.append(item['total_current'])

            # 5. 거래 내역 (페이지네이션)
            cursor.execute("SELECT COUNT(*) as cnt FROM trades WHERE user_id = %s", (user_id,))
            total_trades = cursor.fetchone()['cnt']
            total_pages = math.ceil(total_trades / per_page) if total_trades > 0 else 1

            sql_trades = """
                SELECT t.trade_type, t.quantity, t.price, t.total_amount, t.traded_at, s.name_kr
                FROM trades t
                JOIN stocks s ON t.stock_id = s.id
                WHERE t.user_id = %s
                ORDER BY t.traded_at DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(sql_trades, (user_id, per_page, offset))
            trades = cursor.fetchall()

            # 6. 최종 자산 합산
            initial_balance = float(account['initial_balance']) if account else 0.0
            current_balance = float(account['current_balance']) if account else 0.0
            
            total_assets = current_balance + total_stock_value
            total_profit = total_assets - initial_balance
            total_profit_rate = (total_profit / initial_balance) * 100 if initial_balance > 0 else 0

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
        total_pages=total_pages
    )

# 🚀 [추가됨] 부분 매도 기능을 지원하는 API
@portfolio_bp.route("/api/sell_stock", methods=["POST"])
def sell_stock():
    data = request.json
    stock_id = data.get('stock_id')
    sell_qty = int(data.get('sell_qty', 0))
    user_id = session.get('user_id', 1)

    if sell_qty <= 0:
        return jsonify({"success": False, "message": "매도 수량은 1주 이상이어야 합니다."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            sql_check = """
                SELECT ph.quantity, sd.current_price, ph.account_id
                FROM portfolio_holdings ph
                JOIN stock_details sd ON ph.stock_id = sd.stock_id
                WHERE ph.user_id = %s AND ph.stock_id = %s
            """
            cursor.execute(sql_check, (user_id, stock_id))
            holding = cursor.fetchone()

            if not holding:
                return jsonify({"success": False, "message": "보유 종목 없음"}), 400

            current_qty = holding['quantity']
            if sell_qty > current_qty:
                return jsonify({"success": False, "message": f"최대 {current_qty}주까지만 매도할 수 있습니다."}), 400

            sell_amount = sell_qty * float(holding['current_price'])
            
            # 현금 증가 및 거래 내역 추가
            cursor.execute("UPDATE mock_accounts SET current_balance = current_balance + %s WHERE user_id = %s", (sell_amount, user_id))
            cursor.execute("INSERT INTO trades (user_id, account_id, stock_id, trade_type, price, quantity, total_amount, strategy) VALUES (%s, %s, %s, 'SELL', %s, %s, %s, '사용자 수동 매도')", 
                        (user_id, holding['account_id'], stock_id, holding['current_price'], sell_qty, sell_amount))
            
            # 보유량 차감 (전량 매도면 삭제, 부분 매도면 수량 업데이트)
            if sell_qty == current_qty:
                cursor.execute("DELETE FROM portfolio_holdings WHERE user_id = %s AND stock_id = %s", (user_id, stock_id))
            else:
                cursor.execute("UPDATE portfolio_holdings SET quantity = quantity - %s WHERE user_id = %s AND stock_id = %s", (sell_qty, user_id, stock_id))

        conn.commit()
        return jsonify({"success": True, "message": f"{sell_qty}주 매도가 완료되었습니다."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

# 🚀 [추가됨] AI 전략 변경 API
@portfolio_bp.route("/api/change_strategy", methods=["POST"])
def change_strategy():
    data = request.json
    stock_id = data.get('stock_id')
    new_strategy = data.get('strategy')
    user_id = session.get('user_id', 1)

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 해당 주식의 가장 최근 매수 기록의 전략 이름을 업데이트합니다.
            sql_update = """
                UPDATE trades SET strategy = %s 
                WHERE id = (
                    SELECT id FROM (
                        SELECT id FROM trades 
                        WHERE user_id = %s AND stock_id = %s AND trade_type = 'BUY' 
                        ORDER BY traded_at DESC LIMIT 1
                    ) as tmp
                )
            """
            cursor.execute(sql_update, (new_strategy, user_id, stock_id))
        conn.commit()
        return jsonify({"success": True, "message": f"전략이 '{new_strategy}'(으)로 변경되었습니다."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()