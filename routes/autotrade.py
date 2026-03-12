"""
auto_trade.py — 전략 기반 자동 매매 실행 스크립트

daily_update.py에서 호출되며, 모든 유저의 포트폴리오를 순회하여
설정된 전략의 신호(B/S)를 확인하고 자동으로 매수·매도를 실행합니다.

지원 전략:
  - 골든크로스 전략 : MA5 > MA20 상향돌파 → 매수 / 하향돌파 → 매도
  - 돌파매매 전략   : 종가 > 20일 최고가 → 매수 / 종가 < MA20  → 매도
  - 수동 운용       : 자동 매매 미적용 (건너뜀)
"""

import pandas as pd
from datetime import datetime
from database import get_conn
from algorithm import strategy_golden_cross, strategy_breakout


# ─────────────────────────────────────────────
# 내부 상수
# ─────────────────────────────────────────────
STRATEGY_MAP = {
    "골든크로스 전략": strategy_golden_cross,
    "돌파매매 전략":   strategy_breakout,
}
HISTORY_DAYS = 60   # 신호 계산에 필요한 최소 과거 데이터 (MA20 기준 여유 있게)


# ─────────────────────────────────────────────
# 헬퍼: 종목별 주가 히스토리 조회
# ─────────────────────────────────────────────
def _fetch_price_history(cursor, stock_id: int) -> pd.DataFrame:
    """최근 HISTORY_DAYS일 종가 이력을 DataFrame으로 반환"""
    cursor.execute(
        """
        SELECT price_date AS date, close_price
        FROM stock_price_history
        WHERE stock_id = %s
        ORDER BY price_date ASC
        LIMIT %s
        """,
        (stock_id, HISTORY_DAYS),
    )
    rows = cursor.fetchall()
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["close_price"] = df["close_price"].astype(float)
    return df


# ─────────────────────────────────────────────
# 헬퍼: 최신 신호 계산
# ─────────────────────────────────────────────
def _get_latest_signal(df: pd.DataFrame, strategy_fn) -> tuple[str, float]:
    """
    전략 함수를 적용한 뒤 가장 마지막 행의 신호와 종가를 반환.
    반환값: (signal, price)  — signal: 'B' | 'S' | ''
    """
    if df.empty or len(df) < 21:   # MA20 계산 최소 21행 필요
        return "", 0.0

    df_sig = strategy_fn(df)
    last   = df_sig.iloc[-1]
    signal = last.get("Signal", "")
    price  = float(last["close_price"])
    return signal, price


# ─────────────────────────────────────────────
# 핵심: 자동 매도 (보유 종목 기준)
# ─────────────────────────────────────────────
def _auto_sell(cursor, conn, today_str: str) -> list[dict]:
    """
    전략이 적용된 보유 종목에서 매도 신호(S) 발생 시 전량 자동 매도.
    실행된 거래 요약 리스트를 반환.
    """
    results = []

    # 전략이 설정된 보유 종목 전체 조회 (수동 운용 제외)
    cursor.execute(
        """
        SELECT
            ph.user_id,
            ph.account_id,
            ph.stock_id,
            ph.quantity,
            ph.avg_buy_price,
            s.name_kr,
            s.ticker,
            sd.current_price,
            t.strategy
        FROM portfolio_holdings ph
        JOIN stocks s          ON ph.stock_id  = s.id
        JOIN stock_details sd  ON ph.stock_id  = sd.stock_id
        JOIN (
            -- 각 (user_id, stock_id) 별 가장 최근 BUY 거래의 전략
            SELECT t1.user_id, t1.stock_id, t1.strategy
            FROM trades t1
            INNER JOIN (
                SELECT user_id, stock_id, MAX(traded_at) AS max_at
                FROM trades
                WHERE trade_type = 'BUY'
                GROUP BY user_id, stock_id
            ) t2 ON t1.user_id = t2.user_id
                 AND t1.stock_id = t2.stock_id
                 AND t1.traded_at = t2.max_at
            WHERE t1.trade_type = 'BUY'
        ) t ON ph.user_id = t.user_id AND ph.stock_id = t.stock_id
        WHERE t.strategy != '수동 운용'
          AND t.strategy IN ({placeholders})
        """.format(placeholders=",".join(["%s"] * len(STRATEGY_MAP))),
        list(STRATEGY_MAP.keys()),
    )
    holdings = cursor.fetchall()

    for h in holdings:
        strategy_fn = STRATEGY_MAP.get(h["strategy"])
        if strategy_fn is None:
            continue

        df = _fetch_price_history(cursor, h["stock_id"])
        signal, price = _get_latest_signal(df, strategy_fn)

        if signal != "S":
            continue  # 매도 신호 없으면 패스

        qty          = int(h["quantity"])
        sell_price   = float(h["current_price"])  # 당일 종가 기준
        sell_amount  = qty * sell_price
        profit_rate  = ((sell_price - float(h["avg_buy_price"])) / float(h["avg_buy_price"])) * 100

        # 1) 현금 반환
        cursor.execute(
            "UPDATE mock_accounts SET current_balance = current_balance + %s WHERE user_id = %s",
            (sell_amount, h["user_id"]),
        )
        # 2) 보유 종목 삭제
        cursor.execute(
            "DELETE FROM portfolio_holdings WHERE user_id = %s AND stock_id = %s",
            (h["user_id"], h["stock_id"]),
        )
        # 3) 거래 내역 기록
        cursor.execute(
            """
            INSERT INTO trades
                (user_id, account_id, stock_id, trade_type, price, quantity, total_amount, strategy)
            VALUES (%s, %s, %s, 'SELL', %s, %s, %s, %s)
            """,
            (
                h["user_id"],
                h["account_id"],
                h["stock_id"],
                sell_price,
                qty,
                sell_amount,
                f"[자동] {h['strategy']}",
            ),
        )

        results.append(
            {
                "action":      "SELL",
                "user_id":     h["user_id"],
                "stock":       h["name_kr"],
                "ticker":      h["ticker"],
                "qty":         qty,
                "price":       sell_price,
                "amount":      sell_amount,
                "profit_rate": round(profit_rate, 2),
                "strategy":    h["strategy"],
            }
        )

    return results


# ─────────────────────────────────────────────
# 핵심: 자동 매수 (전략 종목 중 매수 신호 발생)
# ─────────────────────────────────────────────
def _auto_buy(cursor, conn, today_str: str) -> list[dict]:
    """
    각 유저가 과거에 전략으로 거래했던 종목에 매수 신호(B) 발생 시
    현금의 20% 한도로 자동 매수 (이미 보유 중인 종목은 건너뜀).
    실행된 거래 요약 리스트를 반환.
    """
    results = []

    # 유저별로 과거 전략 BUY 거래가 있었던 (user, stock, strategy) 목록 수집
    # 단, 현재 이미 보유 중인 종목은 제외
    cursor.execute(
        """
        SELECT DISTINCT
            t.user_id,
            t.stock_id,
            t.strategy,
            ma.id        AS account_id,
            ma.current_balance,
            s.name_kr,
            s.ticker,
            sd.current_price
        FROM trades t
        JOIN mock_accounts ma  ON t.user_id   = ma.user_id
        JOIN stocks s          ON t.stock_id  = s.id
        JOIN stock_details sd  ON t.stock_id  = sd.stock_id
        LEFT JOIN portfolio_holdings ph
               ON ph.user_id  = t.user_id
              AND ph.stock_id = t.stock_id
        WHERE t.trade_type = 'BUY'
          AND t.strategy   IN ({placeholders})
          AND ph.stock_id  IS NULL   -- 현재 미보유
        """.format(placeholders=",".join(["%s"] * len(STRATEGY_MAP))),
        [f"[자동] {k}" for k in STRATEGY_MAP.keys()]
        + list(STRATEGY_MAP.keys()),
        # strategy 컬럼이 "[자동] XXX" 형태일 수도 있어서 두 패턴 모두 포함
    )
    candidates = cursor.fetchall()

    for c in candidates:
        # strategy 값 정규화 ("[자동] 골든크로스 전략" → "골든크로스 전략")
        raw_strategy = c["strategy"].replace("[자동] ", "").strip()
        strategy_fn  = STRATEGY_MAP.get(raw_strategy)
        if strategy_fn is None:
            continue

        df = _fetch_price_history(cursor, c["stock_id"])
        signal, _ = _get_latest_signal(df, strategy_fn)

        if signal != "B":
            continue  # 매수 신호 없으면 패스

        balance    = float(c["current_balance"])
        buy_price  = float(c["current_price"])
        if buy_price <= 0:
            continue

        # 현금의 20% 한도로 매수 (최소 1주)
        budget = balance * 0.20
        qty    = int(budget // buy_price)
        if qty <= 0:
            continue

        total_amount = qty * buy_price

        # 1) 현금 차감
        cursor.execute(
            "UPDATE mock_accounts SET current_balance = current_balance - %s WHERE user_id = %s",
            (total_amount, c["user_id"]),
        )
        # 2) 보유 종목 추가 / 평단 업데이트
        cursor.execute(
            """
            INSERT INTO portfolio_holdings
                (user_id, account_id, stock_id, quantity, avg_buy_price, total_invested)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                avg_buy_price  = (total_invested + VALUES(total_invested))
                                 / (quantity + VALUES(quantity)),
                quantity       = quantity + VALUES(quantity),
                total_invested = total_invested + VALUES(total_invested)
            """,
            (
                c["user_id"],
                c["account_id"],
                c["stock_id"],
                qty,
                buy_price,
                total_amount,
            ),
        )
        # 3) 거래 내역 기록
        cursor.execute(
            """
            INSERT INTO trades
                (user_id, account_id, stock_id, trade_type, price, quantity, total_amount, strategy)
            VALUES (%s, %s, %s, 'BUY', %s, %s, %s, %s)
            """,
            (
                c["user_id"],
                c["account_id"],
                c["stock_id"],
                buy_price,
                qty,
                total_amount,
                f"[자동] {raw_strategy}",
            ),
        )

        results.append(
            {
                "action":   "BUY",
                "user_id":  c["user_id"],
                "stock":    c["name_kr"],
                "ticker":   c["ticker"],
                "qty":      qty,
                "price":    buy_price,
                "amount":   total_amount,
                "strategy": raw_strategy,
            }
        )

    return results


# ─────────────────────────────────────────────
# 공개 진입점
# ─────────────────────────────────────────────
def run_auto_trade():
    """
    daily_update.py 에서 호출하는 메인 함수.
    전체 실행 결과 요약을 출력하고 예외 발생 시 롤백합니다.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"[자동매매] 실행 시작 — {today_str}")

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            sell_results = _auto_sell(cursor, conn, today_str)
            buy_results  = _auto_buy(cursor, conn, today_str)

        conn.commit()

        # ── 결과 요약 출력 ──────────────────────────
        all_results = sell_results + buy_results
        if not all_results:
            print("[자동매매] 오늘 발생한 신호 없음 — 거래 없음")
        else:
            print(f"[자동매매] 총 {len(all_results)}건 실행")
            for r in all_results:
                if r["action"] == "SELL":
                    sign = "+" if r["profit_rate"] >= 0 else ""
                    print(
                        f"  ▼ SELL | user={r['user_id']} | {r['stock']}({r['ticker']}) "
                        f"| {r['qty']}주 × {r['price']:,.0f}원 "
                        f"| 수익률 {sign}{r['profit_rate']}% "
                        f"| 전략: {r['strategy']}"
                    )
                else:
                    print(
                        f"  ▲ BUY  | user={r['user_id']} | {r['stock']}({r['ticker']}) "
                        f"| {r['qty']}주 × {r['price']:,.0f}원 "
                        f"| 전략: {r['strategy']}"
                    )

    except Exception as e:
        conn.rollback()
        print(f"[자동매매] ❌ 오류 발생, 롤백 처리: {e}")
        raise
    finally:
        conn.close()

    print("[자동매매] 완료")


# 단독 실행 지원
if __name__ == "__main__":
    run_auto_trade()