# services/autotrade.py — 전략 기반 자동 매매 서비스

# [역할]
# daily_update.py에서 호출되며, 모든 유저의 포트폴리오를 순회하여
# 설정된 전략의 신호(B:매수 / S:매도)를 확인하고 자동으로 매매를 실행합니다.

# [지원 전략 및 규칙]
# 1. 골든크로스 전략 : 단기 이평선(MA5)이 장기 이평선(MA20)을 상향 돌파 시 매수, 하향 돌파 시 매도합니다[cite: 99].
# 2. 돌파매매 전략   : 종가가 최근 20일 최고가를 돌파 시 매수, MA20 선을 하회 시 매도합니다[cite: 100].
# 3. 수동 운용       : 사용자가 직접 매매하는 모드로, 자동 매매 로직에서 제외됩니다.

import pandas as pd
from datetime import datetime
from database import get_conn
from algorithm import strategy_golden_cross, strategy_breakout

# [전략 매핑 파트]
# 알고리즘 모듈에 정의된 함수들을 명칭에 맞게 매핑하여 확장성을 확보합니다.
STRATEGY_MAP = {
    "5/20 골든크로스":  strategy_golden_cross,
    "20일 전고점 돌파": strategy_breakout,
}
# 이동평균선(MA20) 계산을 위해 필요한 최소 과거 데이터 일수입니다.
HISTORY_DAYS = 60  


def _fetch_price_history(cursor, stock_id: int) -> pd.DataFrame:
    # [데이터 수집 헬퍼 함수]
    # 특정 종목의 최근 시세 이력을 조회하여 Pandas DataFrame으로 변환합니다.
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


def _get_latest_signal(df: pd.DataFrame, strategy_fn) -> tuple[str, float]:
    # [신호 판별 헬퍼 함수]
    # 전달받은 전략 함수를 시세 데이터에 적용하여 가장 최근 발생한 신호(B/S)를 추출합니다.
    if df.empty or len(df) < 21:  # MA20 계산을 위한 최소 데이터 개수를 검증합니다.
        return "", 0.0

    last = strategy_fn(df).iloc[-1]
    return last.get("Signal", ""), float(last["close_price"])


def _auto_sell(cursor) -> list[dict]:
    # [자동 매도 실행 로직]
    # 전략이 설정된 보유 종목들을 검사하여 매도 신호(S) 발생 시 전량 매도 처리를 수행합니다.
    results = []

    # 자동 매매 대상인 보유 종목과 해당 종목의 최신 매수 전략 정보를 조회합니다.
    cursor.execute(
        """
        SELECT
            ph.user_id, ph.account_id, ph.stock_id,
            ph.quantity, ph.avg_buy_price,
            s.name_kr, s.ticker,
            sd.current_price,
            t.strategy
        FROM portfolio_holdings ph
        JOIN stocks s          ON ph.stock_id  = s.id
        JOIN stock_details sd  ON ph.stock_id  = sd.stock_id
        JOIN (
            SELECT t1.user_id, t1.stock_id, t1.strategy
            FROM trades t1
            INNER JOIN (
                SELECT user_id, stock_id, MAX(traded_at) AS max_at
                FROM trades
                WHERE trade_type = 'BUY'
                GROUP BY user_id, stock_id
            ) t2 ON t1.user_id   = t2.user_id
                 AND t1.stock_id  = t2.stock_id
                 AND t1.traded_at = t2.max_at
            WHERE t1.trade_type = 'BUY'
        ) t ON ph.user_id = t.user_id AND ph.stock_id = t.stock_id
        WHERE t.strategy != '수동 운용'
          AND t.strategy IN ({placeholders})
        """.format(placeholders=",".join(["%s"] * len(STRATEGY_MAP))),
        list(STRATEGY_MAP.keys()),
    )

    for h in cursor.fetchall():
        strategy_fn = STRATEGY_MAP.get(h["strategy"])
        if strategy_fn is None:
            continue

        # 최신 시세 데이터를 가져와 매도 신호 여부를 확인합니다.
        signal, _ = _get_latest_signal(_fetch_price_history(cursor, h["stock_id"]), strategy_fn)
        if signal != "S":
            continue

        # [매도 처리] 잔고 업데이트, 보유 종목 삭제, 거래 내역 기록을 수행합니다.
        qty         = int(h["quantity"])
        sell_price  = float(h["current_price"])
        sell_amount = qty * sell_price
        profit_rate = (sell_price - float(h["avg_buy_price"])) / float(h["avg_buy_price"]) * 100

        cursor.execute(
            "UPDATE mock_accounts SET current_balance = current_balance + %s WHERE user_id = %s",
            (sell_amount, h["user_id"]),
        )
        cursor.execute(
            "DELETE FROM portfolio_holdings WHERE user_id = %s AND stock_id = %s",
            (h["user_id"], h["stock_id"]),
        )
        cursor.execute(
            """
            INSERT INTO trades
                (user_id, account_id, stock_id, trade_type, price, quantity, total_amount, strategy)
            VALUES (%s, %s, %s, 'SELL', %s, %s, %s, %s)
            """,
            (h["user_id"], h["account_id"], h["stock_id"],
             sell_price, qty, sell_amount, f"[자동] {h['strategy']}"),
        )

        results.append({
            "action":      "SELL",
            "user_id":     h["user_id"],
            "stock":       h["name_kr"],
            "ticker":      h["ticker"],
            "qty":         qty,
            "price":       sell_price,
            "amount":      sell_amount,
            "profit_rate": round(profit_rate, 2),
            "strategy":    h["strategy"],
        })

    return results


def _auto_buy(cursor) -> list[dict]:
    # [자동 매수 실행 로직]
    # 유저가 이전에 전략으로 거래했던 종목 중 매수 신호(B)가 포착된 종목을 자동으로 매수합니다.
    results = []
    strategy_keys = list(STRATEGY_MAP.keys())

    # 이미 보유 중인 종목은 제외하고, 과거에 해당 전략으로 매수했던 종목 후보를 추출합니다.
    cursor.execute(
        """
        SELECT DISTINCT
            t.user_id, t.stock_id, t.strategy,
            ma.id AS account_id, ma.current_balance,
            s.name_kr, s.ticker, sd.current_price
        FROM trades t
        JOIN mock_accounts ma  ON t.user_id  = ma.user_id
        JOIN stocks s          ON t.stock_id = s.id
        JOIN stock_details sd  ON t.stock_id = sd.stock_id
        LEFT JOIN portfolio_holdings ph
               ON ph.user_id  = t.user_id
              AND ph.stock_id = t.stock_id
        WHERE t.trade_type = 'BUY'
          AND t.strategy   IN ({placeholders})
          AND ph.stock_id  IS NULL
        """.format(placeholders=",".join(["%s"] * len(strategy_keys) * 2)),
        [f"[자동] {k}" for k in strategy_keys] + strategy_keys,
    )

    for c in cursor.fetchall():
        raw_strategy = c["strategy"].replace("[자동] ", "").strip()
        strategy_fn  = STRATEGY_MAP.get(raw_strategy)
        if strategy_fn is None:
            continue

        # 최신 시세 데이터를 분석하여 매수 신호 발생 여부를 확인합니다.
        signal, _ = _get_latest_signal(_fetch_price_history(cursor, c["stock_id"]), strategy_fn)
        if signal != "B":
            continue

        # [리스크 관리] 가용 현금의 20% 한도 내에서만 매수를 진행하도록 설정되어 있습니다.
        balance   = float(c["current_balance"])
        buy_price = float(c["current_price"])
        if buy_price <= 0:
            continue

        qty = int(balance * 0.20 // buy_price)  
        if qty <= 0:
            continue

        total_amount = qty * buy_price

        # [매수 처리] 잔액 차감, 포트폴리오 추가, 거래 내역 기록을 수행합니다.
        cursor.execute(
            "UPDATE mock_accounts SET current_balance = current_balance - %s WHERE user_id = %s",
            (total_amount, c["user_id"]),
        )
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
            (c["user_id"], c["account_id"], c["stock_id"], qty, buy_price, total_amount),
        )
        cursor.execute(
            """
            INSERT INTO trades
                (user_id, account_id, stock_id, trade_type, price, quantity, total_amount, strategy)
            VALUES (%s, %s, %s, 'BUY', %s, %s, %s, %s)
            """,
            (c["user_id"], c["account_id"], c["stock_id"],
             buy_price, qty, total_amount, f"[자동] {raw_strategy}"),
        )

        results.append({
            "action":   "BUY",
            "user_id":  c["user_id"],
            "stock":    c["name_kr"],
            "ticker":   c["ticker"],
            "qty":      qty,
            "price":    buy_price,
            "amount":   total_amount,
            "strategy": raw_strategy,
        })

    return results


def run_auto_trade():
    # [메인 실행 함수]
    # 전체 자동 매매 프로세스를 제어하며, 트랜잭션의 완결성을 보장합니다.
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"[자동매매] 실행 시작 — {today_str}")

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 매도 로직을 먼저 수행하여 가용 현금을 확보한 후 매수 로직을 진행합니다.
            sell_results = _auto_sell(cursor)
            buy_results  = _auto_buy(cursor)

        # 모든 처리가 정상일 경우 DB에 최종 반영합니다.
        conn.commit()

        # [실행 결과 로그 출력]
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
        # 오류 발생 시 데이터 무결성을 위해 모든 작업을 취소하고 롤백합니다.
        conn.rollback()
        print(f"[자동매매] 오류 발생, 롤백 처리: {e}")
        raise
    finally:
        conn.close()

    print("[자동매매] 완료")


if __name__ == "__main__":
    # 스크립트 단독 실행 시 자동 매매 함수를 호출합니다.
    run_auto_trade()