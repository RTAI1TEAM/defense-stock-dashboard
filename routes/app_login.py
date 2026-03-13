import bcrypt
import random
import smtplib
import time
from email.mime.text import MIMEText

from flask import Blueprint, redirect, render_template, request, session, url_for

from database import get_conn
from config import MAIL_EMAIL, MAIL_PASSWORD

# Blueprint 등록 - URL prefix 없이 auth 관련 라우트를 모듈화
auth_bp = Blueprint("auth_bp", __name__)

# 이메일 인증번호를 임시 저장하는 딕셔너리 { email: { code, time } }
# 서버 메모리에만 저장되므로 재시작 시 초기화됨
verification_codes = {}


# ──────────────────────────────────────────────
# 로그인 페이지 (GET)
# ──────────────────────────────────────────────
@auth_bp.route("/login", methods=["GET"])
def login_page():
    # 이미 세션이 있으면 메인 페이지로 리다이렉트
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("index_login.html")


# ──────────────────────────────────────────────
# 로그인 처리 (POST)
# ──────────────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 이메일로 사용자 조회
            cursor.execute(
                "SELECT * FROM users WHERE email = %s",
                (email,),
            )
            user = cursor.fetchone()
    finally:
        conn.close()

    # 사용자가 존재하고 bcrypt로 비밀번호 일치 여부 확인
    if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        # 세션에 사용자 정보 저장
        session['nickname'] = user['nickname']
        session['avatar'] = user.get('avatar') or '🧑‍💼'  # 아바타 없으면 기본값 사용
        session['user_id'] = user['id']

        return redirect(url_for("index"))

    # 로그인 실패 시 에러 메시지와 함께 로그인 페이지 재렌더링
    return render_template(
        "index_login.html",
        error="이메일 또는 비밀번호가 일치하지 않습니다.",
    )


# ──────────────────────────────────────────────
# 회원가입 페이지 (GET)
# ──────────────────────────────────────────────
@auth_bp.route("/signup", methods=["GET"])
def signup():
    return render_template("signup_login.html")


# ──────────────────────────────────────────────
# 이메일 인증번호 발송 함수
# ──────────────────────────────────────────────
def send_verification_email(email, code):
    try:
        sender   = MAIL_EMAIL
        password = MAIL_PASSWORD

        # 인증 이메일 HTML 템플릿 (인라인 스타일 적용)
        html = f"""
        <html>
        <body style="margin:0; padding:0; background:#f5f7fb; font-family:Arial, Helvetica, sans-serif;">

        <table width="100%" cellspacing="0" cellpadding="0" style="background:#f5f7fb; padding:40px 0;">
        <tr>
        <td align="center">

        <table width="520" cellspacing="0" cellpadding="0"
        style="background:white; border-radius:16px; overflow:hidden;
        box-shadow:0 10px 30px rgba(0,0,0,0.08);">

        <tr>
        <td style="background:linear-gradient(135deg,#4e73df,#1cc88a);
        padding:30px; text-align:center; color:white;">

        <h1 style="margin:0; font-size:26px;">🚀 AI Quant</h1>
        <p style="margin:8px 0 0 0; font-size:14px; opacity:0.9;">
        AI 기반 투자 플랫폼
        </p>

        </td>
        </tr>

        <tr>
        <td style="padding:40px 35px; text-align:center;">

        <h2 style="margin-top:0; color:#333;">
        이메일 인증
        </h2>

        <p style="color:#666; font-size:15px; line-height:1.6;">
        회원가입을 완료하려면 아래 인증번호를 입력해주세요.
        </p>

        <div style="
        margin:35px auto;
        display:inline-block;
        background:#f1f4ff;
        padding:18px 35px;
        border-radius:12px;
        border:2px dashed #4e73df;
        ">

        <span style="
        font-size:40px;
        letter-spacing:8px;
        font-weight:700;
        color:#4e73df;
        ">
        {code}
        </span>

        </div>

        <p style="color:#888; font-size:13px;">
        이 인증번호는 <b>5분 동안</b> 유효합니다.
        </p>

        </td>
        </tr>

        <tr>
        <td style="background:#fafafa; padding:20px; text-align:center;
        font-size:12px; color:#999;">
        이 메일은 AI Quant 시스템에서 자동으로 발송되었습니다.<br>
        </td>
        </tr>

        </table>

        </td>
        </tr>
        </table>

        </body>
        </html>
        """

        # MIME HTML 메시지 구성
        msg = MIMEText(html, "html")
        msg["Subject"] = "[AI Quant] 이메일 인증번호 안내"
        msg["From"] = sender
        msg["To"] = email

        # Gmail SMTP SSL(465포트)로 연결 후 메일 발송
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)

        print("이메일 발송 성공!")

    except Exception as e:
        print(f"이메일 발송 실패: {e}")


# ──────────────────────────────────────────────
# 회원가입 처리 (POST)
# 1단계: 이메일/닉네임 중복 확인 → 인증번호 발송
# 2단계: 인증번호 검증 → DB에 사용자 등록
# ──────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
def register():
    print("register 요청 들어옴")
    email = request.form["email"]
    password = request.form["password"]
    nickname = request.form["nickname"]
    code = request.form.get("code")  # 인증번호 입력값 (없으면 None)

    # ── 2단계: 인증번호가 제출된 경우 ──
    if code:
        data = verification_codes.get(email)
        if data:
            saved_code = data["code"]
            created_time = data["time"]

            # 인증번호 유효시간 초과 여부 확인 (5분 = 300초)
            if time.time() - created_time > 300:
                return render_template(
                    "signup_login.html",
                    error="인증번호가 만료되었습니다. 다시 요청해주세요.",
                    email=email,
                    password=password,
                    nickname=nickname
                )

            # 인증번호 일치 → DB에 사용자 등록
            if saved_code == code:
                conn = get_conn()
                try:
                    with conn.cursor() as cursor:
                        # 비밀번호 bcrypt 해싱
                        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode("utf-8")

                        # 1. users 테이블에 신규 회원 추가
                        cursor.execute(
                            """
                            INSERT INTO users (email, password_hash, nickname)
                            VALUES (%s, %s, %s)
                            """,
                            (email, hashed_pw, nickname),
                        )

                        # 2. 방금 INSERT된 user_id 가져오기
                        user_id = cursor.lastrowid

                        # 3. 신규 회원에게 모의투자 계좌 자동 생성 (초기 잔액 1,000만원)
                        cursor.execute(
                            """
                            INSERT INTO mock_accounts (user_id, initial_balance, current_balance, total_profit_loss)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (user_id, 10000000.00, 10000000.00, 0.00),
                        )

                    conn.commit()

                except Exception as e:
                    conn.rollback()  # 오류 발생 시 트랜잭션 롤백
                    print(f"회원가입 실패: {e}")
                    return render_template(
                        "signup_login.html",
                        error="회원가입 처리 중 오류가 발생했습니다.",
                        show_code=True,
                        email=email,
                        password=password,
                        nickname=nickname
                    )
                finally:
                    conn.close()

                # 인증 완료 후 사용한 인증번호 삭제
                del verification_codes[email]
                return redirect(url_for("auth_bp.login_page"))

        else:
            # 인증번호 불일치
            return render_template(
                "signup_login.html",
                error="인증번호가 틀렸어요!",
                show_code=True,
                email=email,
                password=password,
                nickname=nickname
            )

    # ── 1단계: 인증번호가 없는 경우 → 중복 확인 후 인증번호 발송 ──

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 이메일 중복 확인
            cursor.execute("SELECT 1 FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                return render_template(
                    "signup_login.html",
                    error="이미 사용 중인 이메일입니다.",
                )

            # 닉네임 중복 확인
            cursor.execute("SELECT 1 FROM users WHERE nickname = %s", (nickname,))
            if cursor.fetchone():
                return render_template(
                    "signup_login.html",
                    error="이미 사용 중인 닉네임입니다.",
                )
    finally:
        conn.close()

    # 6자리 랜덤 인증번호 생성 후 메모리에 저장 및 이메일 발송
    code = str(random.randint(100000, 999999))
    verification_codes[email] = {
        "code": code,
        "time": time.time()  # 만료 시간 계산을 위해 현재 시각 저장
    }
    send_verification_email(email, code)

    # 인증번호 입력 폼을 보여주도록 show_code=True 전달
    return render_template(
        "signup_login.html",
        show_code=True,
        email=email,
        password=password,
        nickname=nickname
    )


# ──────────────────────────────────────────────
# 로그아웃 (GET)
# ──────────────────────────────────────────────
@auth_bp.route("/logout", methods=["GET"])
def logout():
    session.clear()  # 세션 전체 삭제
    return redirect(url_for("auth_bp.login_page"))