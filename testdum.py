"""
전체 프로그램 테스트용 더미데이터 생성 스크립트
- 실행: python testdum.py
- 재실행 시 기존 더미 삭제 후 새로 생성
- 생성 테이블: users, mock_accounts, portfolio_holdings, trades
- 로그인 비밀번호: Test1234!
- 이메일 패턴: test_N@test.com (고정)
"""

import random
import bcrypt
from database import get_conn

# ─────────────────────────────────────────────────────────
# 테스트 유저 목록
# 다양한 케이스를 테스트할 수 있도록 잔액 차등 설정
# ─────────────────────────────────────────────────────────
TEST_USERS = [
    {"nickname": "수익왕",       "current_balance": 14_200_000, "avatar": "👑"},
    {"nickname": "방산왕",       "current_balance": 13_150_000, "avatar": "🦊"},
    {"nickname": "AI마스터",     "current_balance": 12_840_000, "avatar": "🤖"},
    {"nickname": "코딩트레이더",  "current_balance": 11_500_000, "avatar": "👨‍💻"},
    {"nickname": "개미투자자",    "current_balance": 10_800_000, "avatar": "🐜"},
    {"nickname": "단타신",       "current_balance": 10_200_000, "avatar": "🔥"},
    {"nickname": "장기투자자",    "current_balance": 9_800_000,  "avatar": "🐢"},
    {"nickname": "차트분석가",    "current_balance": 9_200_000,  "avatar": "📈"},
    {"nickname": "배당러",       "current_balance": 8_700_000,  "avatar": "💰"},
    {"nickname": "주린이",       "current_balance": 8_100_000,  "avatar": "🐸"},
]

INITIAL_BALANCE = 10_000_000  # 초기 자본금 1000만원
PASSWORD = "Test1234!"
STRATEGIES = ["이동평균 돌파", "RSI 역추세", "볼린저 밴드", "수동 매수"]


def delete_existing(cursor):
    """기존 더미 데이터 삭제 (test_N@test.com 패턴)"""
    cursor.execute("""
        DELETE t FROM trades t
        INNER JOIN users u ON t.user_id = u.id
        WHERE u.email LIKE 'test_%@test.com'
    """)
    cursor.execute("""
        DELETE ph FROM portfolio_holdings ph
        INNER JOIN users u ON ph.user_id = u.id
        WHERE u.email LIKE 'test_%@test.com'
    """)
    cursor.execute("""
        DELETE ma FROM mock_accounts ma
        INNER JOIN users u ON ma.user_id = u.id
        WHERE u.email LIKE 'test_%@test.com'
    """)
    cursor.execute("""
        DELETE FROM users
        WHERE email LIKE 'test_%@test.com'
    """)
    print("[INFO] 기존 더미 삭제 완료")


def create_user(cursor, i, user_info, password_hash):
    """users + mock_accounts 생성, (user_id, account_id) 반환"""
    email = f"test_{i}@test.com"
    nickname = user_info["nickname"]
    current_balance = user_info["current_balance"]
    avatar = user_info.get("avatar", "🧑‍💼")

    cursor.execute("""
        INSERT INTO users (email, password_hash, nickname, is_verified, avatar)
        VALUES (%s, %s, %s, 1, %s)
    """, (email, password_hash, nickname, avatar))
    user_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO mock_accounts (user_id, initial_balance, current_balance)
        VALUES (%s, %s, %s)
    """, (user_id, INITIAL_BALANCE, current_balance))
    account_id = cursor.lastrowid

    return user_id, account_id, email


def create_holdings_and_trades(cursor, user_id, account_id, stock_ids):
    """portfolio_holdings + trades (매수/매도) 생성"""
    holding_count = random.randint(2, min(4, len(stock_ids)))
    picked_ids = random.sample(stock_ids, holding_count)

    for stock_id in picked_ids:
        quantity = random.randint(5, 20)
        avg_buy_price = random.randint(30_000, 120_000)
        strategy = random.choice(STRATEGIES)

        # portfolio_holdings
        cursor.execute("""
            INSERT INTO portfolio_holdings
                (user_id, account_id, stock_id, quantity, avg_buy_price)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, account_id, stock_id, quantity, avg_buy_price))

        # trades - 매수
        cursor.execute("""
            INSERT INTO trades
                (user_id, account_id, stock_id, trade_type,
                 price, quantity, total_amount, strategy)
            VALUES (%s, %s, %s, 'BUY', %s, %s, %s, %s)
        """, (user_id, account_id, stock_id,
              avg_buy_price, quantity, quantity * avg_buy_price, strategy))

    # trades - 매도 1건 (거래내역 탭 테스트용)
    sold_stock_id = picked_ids[0]
    sell_price = random.randint(30_000, 120_000)
    sell_qty = random.randint(1, 3)
    cursor.execute("""
        INSERT INTO trades
            (user_id, account_id, stock_id, trade_type,
             price, quantity, total_amount, strategy)
        VALUES (%s, %s, %s, 'SELL', %s, %s, %s, '사용자 수동 매도')
    """, (user_id, account_id, sold_stock_id,
          sell_price, sell_qty, sell_price * sell_qty))


def create_test_dummy():
    conn = None
    try:
        conn = get_conn()

        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE() AS db")
            print("현재 DB:", cursor.fetchone()["db"])

            # 종목 목록 조회
            cursor.execute("SELECT stock_id FROM stock_details ORDER BY stock_id")
            stock_ids = [row["stock_id"] for row in cursor.fetchall()]
            if not stock_ids:
                print("[WARN] stock_details 가 비어 있어 portfolio_holdings / trades 는 생략됩니다.")
            else:
                print(f"[INFO] 사용 가능한 종목 ID: {stock_ids}")

            # 기존 더미 삭제
            delete_existing(cursor)

            # bcrypt 해시 (한 번만 생성)
            password_hash = bcrypt.hashpw(
                PASSWORD.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")

            # 유저 생성
            for i, user_info in enumerate(TEST_USERS, start=1):
                user_id, account_id, email = create_user(cursor, i, user_info, password_hash)

                if stock_ids:
                    create_holdings_and_trades(cursor, user_id, account_id, stock_ids)

                print(
                    f"[OK] {i:2}. {user_info['nickname']:12} | "
                    f"{user_info.get('avatar', '🧑‍💼')} | "
                    f"{email} | 잔액 {user_info['current_balance']:,}원"
                )

        conn.commit()
        print(f"\n✅ 테스트 더미 {len(TEST_USERS)}명 생성 완료")
        print(f"   비밀번호: {PASSWORD}")
        print(f"   이메일:   test_1@test.com ~ test_{len(TEST_USERS)}@test.com")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[ERROR] 더미 생성 실패: {e}")
        raise

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    create_test_dummy()