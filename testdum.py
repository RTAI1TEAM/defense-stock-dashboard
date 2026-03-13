"""
전체 프로그램 테스트용 더미데이터 생성 스크립트
- 실행: python testdum.py
- 재실행 시 기존 더미 삭제 후 새로 생성
- 생성 테이블: users, mock_accounts
- 로그인 비밀번호: Test1234!
- 이메일 패턴: test_N@test.com
- 포트폴리오/거래내역 없음 → 직접 로그인해서 모의투자
"""

import bcrypt # 비밀번호 암호화를 위한 라이브러리
from database import get_conn

# [테스트 유저 정의 파트]
# 실제 가입하기 귀찮으니까 미리 만들어둘 유저 목록이야. 닉네임이랑 아이콘(아바타)이 아주 귀엽지? [cite: 170, 173]
TEST_USERS = [
    {"nickname": "수익왕",      "avatar": "👑"},
    {"nickname": "방산왕",      "avatar": "🦊"},
    {"nickname": "AI마스터",    "avatar": "🤖"},
    {"nickname": "코딩트레이더","avatar": "👨‍💻"},
    {"nickname": "개미투자자",  "avatar": "🐜"},
    {"nickname": "단타신",      "avatar": "🔥"},
    {"nickname": "장기투자자",  "avatar": "🐢"},
    {"nickname": "차트분석가",  "avatar": "📈"},
    {"nickname": "배당러",      "avatar": "💰"},
    {"nickname": "주린이",      "avatar": "🐸"},
]

INITIAL_BALANCE = 10_000_000  # 모든 유저에게 공평하게 주는 시드머니 1,000만원! [cite: 23, 38, 149]
PASSWORD        = "Test1234!" # 로그인할 때 공통으로 쓸 비밀번호야.


def delete_existing(cursor):
    """
    [데이터 초기화 파트]
    스크립트를 다시 실행할 때 데이터가 꼬이지 않도록 
    기존에 생성했던 테스트용 유저, 계좌, 거래 내역 등을 싹 다 밀어버려. (깔끔!)
    """
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
    cursor.execute("DELETE FROM users WHERE email LIKE 'test_%@test.com'")
    print("[INFO] 기존 더미 삭제 완료")


def create_test_dummy():
    """
    [더미 생성 메인 로직]
    1. 비밀번호를 보안을 위해 bcrypt로 암호화해. 
    2. TEST_USERS 목록을 돌면서 'users' 테이블에 정보를 집어넣어. [cite: 151, 389]
    3. 유저마다 'mock_accounts' 테이블에 1,000만원 잔고를 가진 계좌를 하나씩 만들어줘. [cite: 151, 310]
    """
    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE() AS db")
            print("현재 DB:", cursor.fetchone()["db"])

            delete_existing(cursor)

            password_hash = bcrypt.hashpw(
                PASSWORD.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")

            for i, user_info in enumerate(TEST_USERS, start=1):
                email    = f"test_{i}@test.com"
                nickname = user_info["nickname"]
                avatar   = user_info["avatar"]

                # 유저 생성
                cursor.execute("""
                    INSERT INTO users (email, password_hash, nickname, is_verified, avatar)
                    VALUES (%s, %s, %s, 1, %s)
                """, (email, password_hash, nickname, avatar))
                user_id = cursor.lastrowid

                # 모의투자 계좌 생성 (시드 1,000만원)
                cursor.execute("""
                    INSERT INTO mock_accounts (user_id, initial_balance, current_balance)
                    VALUES (%s, %s, %s)
                """, (user_id, INITIAL_BALANCE, INITIAL_BALANCE))

                print(f"[OK] {i:2}. {avatar} {nickname:12} | {email} | 잔액 {INITIAL_BALANCE:,}원")

        conn.commit()
        print(f"\n✅ 테스트 유저 {len(TEST_USERS)}명 생성 완료")
        print(f"   비밀번호 : {PASSWORD}")
        print(f"   이메일   : test_1@test.com ~ test_{len(TEST_USERS)}@test.com")
        print(f"   시드머니 : {INITIAL_BALANCE:,}원")
        print(f"   포트폴리오: 비어있음 (직접 로그인 후 모의투자 시작)")

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