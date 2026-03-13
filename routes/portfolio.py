# [파일 역할] 사용자의 투자 포트폴리오(자산 현황, 보유 종목, 거래 내역)를 관리하는 라우트 모듈
# - 로그인된 사용자의 실시간 자산 및 수익률 계산
# - 보유 종목에 대한 수동 매도 및 적용 전략 변경 기능 제공
# - 거래 내역 조회 및 페이지네이션 처리

import math
from flask import Blueprint, render_template, request, jsonify, session, Response
from database import get_conn

# [블루프린트 설정] 포트폴리오 관련 기능을 'portfolio' 네임스페이스로 등록
portfolio_bp = Blueprint('portfolio', __name__)

# [상수 설정] 거래 내역 페이지네이션 시 한 페이지에 보여줄 데이터 개수
PER_PAGE = 5


# ──────────────────────────────────────────────
# 내부 헬퍼 함수 (Internal Helper Functions)
# ──────────────────────────────────────────────

def _get_user_id():
    # 현재 세션에 저장된 사용자 ID를 반환 (비로그인 시 None)
    return session.get('user_id')


def _require_login_page():
    # 권한이 없는 사용자가 접근했을 때 안내 메시지를 띄우고 로그인 페이지로 이동시키는 응답 생성
    return Response(
        '<script>alert("로그인이 필요한 페이지입니다."); location.href="/login";</script>',
        mimetype='text/html'
    )


def _calc_trade_profit(trade):
    # 매도(SELL) 건에 대해 실질적인 수익금과 수익률을 계산하는 함수
    # - trade: 거래 정보가 담긴 딕셔너리
    # - 반환값: (수익금, 수익률) 튜플 / 매수 건이거나 정보 부족 시 (None, None)
    if trade['trade_type'] == 'SELL' and trade.get('avg_buy_price'):
        avg  = float(trade['avg_buy_price'])
        sell = float(trade['price'])
        qty  = int(trade['quantity'])
        # 수익금: (매도가 - 평균매수가) * 수량
        # 수익률: (매도가 - 평균매수가) / 평균매수가 * 100
        return round((sell - avg) * qty), round((sell - avg) / avg * 100, 1)
    return None, None


def _fetch_trades(cursor, user_id, per_page, offset):
    # 사용자의 거래 내역을 DB에서 조회하는 핵심 쿼리 함수
    # - 특이사항: 매도 거래 시, 해당 시점까지의 '평균 매수가'를 서브쿼리로 동적 계산하여 가져옴
    cursor.execute("""
        SELECT t.trade_type, t.quantity, t.price, t.total_amount,
               DATE_FORMAT(t.traded_at, '%%y.%%m.%%d %%H:%%i') AS traded_at,
               s.name_kr, s.ticker,
               CASE
                   WHEN t.trade_type = 'SELL' THEN (
                       -- 해당 매도 시점(traded_at) 이전까지의 모든 매수 건에 대한 가중평균 단가 산출
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
# 페이지 라우트 (Page Routes)
# ──────────────────────────────────────────────

@portfolio_bp.route("/portfolio")
def portfolio_view():
    # [GET] 내 자산 대시보드 페이지 메인 화면
    
    # 1. 사용자 인증 확인
    user_id = _get_user_id()
    if user_id is None:
        return _require_login_page()

    # 2. 페이지네이션 파라미터 수신 (기본값 1페이지)
    page   = int(request.args.get('page', 1))
    offset = (page - 1) * PER_PAGE

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 3. 사용자 계좌 정보(예수금 등) 조회
            cursor.execute("SELECT * FROM mock_accounts WHERE user_id = %s", (user_id,))
            account = cursor.fetchone()

            # 4. 현재 보유 중인 종목 리스트 조회 (종목 정보 및 현재가 Join)
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

            # 5. 보유 종목별 실시간 평가 현황 및 차트 데이터 가공
            total_stock_value = 0.0
            pie_dict = {} # 도넛 차트용 (종목별 비중)
            
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
                # 같은 종목을 다른 전략으로 가졌더라도 차트에서는 하나로 합산하여 표시
                pie_dict[item['name_kr']] = pie_dict.get(item['name_kr'], 0) + item['total_current']

            # 6. 전체 거래 내역 조회 및 페이지네이션 계산
            cursor.execute("SELECT COUNT(*) as cnt FROM trades WHERE user_id = %s", (user_id,))
            total_trades = cursor.fetchone()['cnt']
            total_pages  = math.ceil(total_trades / PER_PAGE) if total_trades > 0 else 1

            trades = _fetch_trades(cursor, user_id, PER_PAGE, offset)
            for trade in trades:
                # 각 거래 건별 수익 데이터 추가 계산
                trade['profit_amount'], trade['profit_rate'] = _calc_trade_profit(trade)

            # 7. 전체 자산 요약 정보 산출 (예수금 + 주식 평가금)
            cash_balance      = float(account['current_balance']) if account else 0.0
            initial_balance   = float(account['initial_balance']) if account else 0.0
            total_assets      = cash_balance + total_stock_value
            total_profit      = total_assets - initial_balance
            total_profit_rate = total_profit / initial_balance * 100 if initial_balance > 0 else 0

    finally:
        conn.close()

    # 데이터 바인딩 후 템플릿 렌더링
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
# API 엔드포인트 (AJAX 통신용)
# ──────────────────────────────────────────────

@portfolio_bp.route("/api/sell_stock", methods=["POST"])
def sell_stock():
    # [POST] 특정 보유 종목을 지정한 수량만큼 수동으로 즉시 매도 처리
    
    # 1. 로그인 확인
    user_id = _get_user_id()
    if user_id is None:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    # 2. 요청 데이터 수신 및 수량 검증
    data       = request.json
    holding_id = data.get('holding_id')
    sell_qty   = int(data.get('sell_qty', 0))

    if sell_qty <= 0:
        return jsonify({"success": False, "message": "매도 수량은 1주 이상이어야 합니다."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 3. 매도 대상 종목의 실제 보유 여부 및 수량 확인
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

            # 4. 매도 금액 계산 및 예수금(잔고) 업데이트
            sell_price  = float(holding['current_price'])
            sell_amount = sell_qty * sell_price

            cursor.execute(
                "UPDATE mock_accounts SET current_balance = current_balance + %s WHERE user_id = %s",
                (sell_amount, user_id)
            )

            # 5. 거래 내역(trades 테이블) 기록 추가
            cursor.execute("""
                INSERT INTO trades
                    (user_id, account_id, stock_id, trade_type, price, quantity, total_amount, strategy)
                VALUES (%s, %s, %s, 'SELL', %s, %s, %s, %s)
            """, (
                user_id, holding['account_id'], holding['stock_id'],
                sell_price, sell_qty, sell_amount,
                f"{holding['strategy']} (수동 매도)"
            ))

            # 6. 보유 현황(portfolio_holdings 테이블) 업데이트
            # - 전량 매도 시 레코드 삭제, 일부 매도 시 수량만 차감
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
    # [POST] 보유 중인 포지션의 자동 매매 알고리즘 전략을 변경
    
    # 1. 로그인 및 데이터 수신
    user_id = _get_user_id()
    if user_id is None:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    data         = request.json
    holding_id   = data.get('holding_id')
    new_strategy = data.get('strategy')

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 2. 대상 포지션 존재 확인
            cursor.execute(
                "SELECT id, stock_id, strategy FROM portfolio_holdings WHERE id = %s AND user_id = %s",
                (holding_id, user_id)
            )
            holding = cursor.fetchone()
            if not holding:
                return jsonify({"success": False, "message": "포지션을 찾을 수 없습니다."}), 404

            # 3. 중복 전략 체크 (동일 종목 내에서 다른 포지션이 이미 같은 전략을 쓰고 있는지 확인)
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

            # 4. 전략 필드 업데이트
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
    # [GET] 거래 내역 페이지네이션을 위한 데이터 제공 API (주로 무한 스크롤이나 비동기 페이징에 사용)
    
    user_id = _get_user_id()
    if not user_id:
        return jsonify({"success": False}), 401

    page   = int(request.args.get('page', 1))
    offset = (page - 1) * PER_PAGE

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 1. 거래 데이터 조회 및 JSON 변환을 위한 가공
            trades = []
            for trade in _fetch_trades(cursor, user_id, PER_PAGE, offset):
                t = dict(trade)
                t['profit_amount'], t['profit_rate'] = _calc_trade_profit(t)
                t.pop('avg_buy_price', None) # 응답 본문에서는 불필요한 계산용 컬럼 제거
                # JSON 직렬화를 위해 Decimal/Float 타입 처리
                t['price']        = float(t['price'])
                t['total_amount'] = float(t['total_amount'])
                trades.append(t)

            # 2. 전체 데이터 개수 기반 총 페이지 수 재계산
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