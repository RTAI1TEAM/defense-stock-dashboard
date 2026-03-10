import random
import time
from database import get_conn


def create_rank_dummy():
    conn = None

    try:
        conn = get_conn()

        base_nicknames = [
            "주린이황",
            "방산왕",
            "AI마스터",
            "코딩트레이더",
            "개미투자자",
            "단타신",
            "장기투자자",
            "차트분석가",
            "배당러",
            "주식고수"
        ]

        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE() AS db")
            print("현재 DB:", cursor.fetchone())

            # stock_details 조회
            cursor.execute("SELECT stock_id FROM stock_details ORDER BY stock_id")
            stock_rows = cursor.fetchall()
            stock_ids = [row["stock_id"] for row in stock_rows]

            if not stock_ids:
                print("stock_details가 비어 있어서 portfolio_holdings 생성은 건너뜁니다.")

            # 기존 더미 삭제
            cursor.execute("""
                DELETE ph
                FROM portfolio_holdings ph
                INNER JOIN users u ON ph.user_id = u.id
                WHERE u.email LIKE 'dummy_%@test.com'
            """)

            cursor.execute("""
                DELETE ma
                FROM mock_accounts ma
                INNER JOIN users u ON ma.user_id = u.id
                WHERE u.email LIKE 'dummy_%@test.com'
            """)

            cursor.execute("""
                DELETE FROM users
                WHERE email LIKE 'dummy_%@test.com'
            """)

            seed = int(time.time())

            for i, base_nickname in enumerate(base_nicknames, start=1):
                email = f"dummy_{seed}_{i}@test.com"
                nickname = f"{base_nickname}_{i}"
                password_hash = "dummy_hash"
                is_verified = 1

                # users
                cursor.execute("""
                    INSERT INTO users (email, password_hash, nickname, is_verified)
                    VALUES (%s, %s, %s, %s)
                """, (email, password_hash, nickname, is_verified))

                user_id = cursor.lastrowid

                # mock_accounts
                initial_balance = 10_000_000

                # 상위권이 눈에 띄게 나오도록 약간 차등
                if i == 1:
                    current_balance = 14_200_000
                elif i == 2:
                    current_balance = 13_150_000
                elif i == 3:
                    current_balance = 12_840_000
                else:
                    current_balance = random.randint(8_500_000, 11_800_000)

                cursor.execute("""
                    INSERT INTO mock_accounts (user_id, initial_balance, current_balance)
                    VALUES (%s, %s, %s)
                """, (user_id, initial_balance, current_balance))

                # stock_details 데이터가 있을 때만 portfolio_holdings 생성
                if stock_ids:
                    holding_count = random.randint(1, min(2, len(stock_ids)))
                    picked_stock_ids = random.sample(stock_ids, holding_count)

                    for stock_id in picked_stock_ids:
                        quantity = random.randint(5, 30)

                        cursor.execute("""
                            INSERT INTO portfolio_holdings (user_id, stock_id, quantity)
                            VALUES (%s, %s, %s)
                        """, (user_id, stock_id, quantity))

                print(f"생성 완료: id={user_id}, email={email}, nickname={nickname}")

        conn.commit()
        print("랭크 더미 데이터 10명 생성 완료")

    except Exception as e:
        if conn:
            conn.rollback()
        print("더미 생성 실패:", e)

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    create_rank_dummy()