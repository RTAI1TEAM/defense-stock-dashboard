from flask import Blueprint, redirect, render_template, request, session, url_for
from database import get_conn
from dotenv import load_dotenv
import bcrypt
import random
import smtplib
import os
import time
from email.mime.text import MIMEText

load_dotenv()

auth_bp = Blueprint("auth_bp", __name__)
verification_codes = {}


@auth_bp.route("/login", methods=["GET"])
def login_page():
    return render_template("index_login.html")


@auth_bp.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE email = %s",
                (email,),
            )
            user = cursor.fetchone()
    finally:
        conn.close()

    if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        session['nickname'] = user['nickname']
        session['avatar'] = user.get('avatar') or '🧑‍💼'
        return redirect(url_for("index"))

    return render_template(
        "index_login.html",
        error="이메일 또는 비밀번호가 일치하지 않습니다.",
    )


@auth_bp.route("/signup", methods=["GET"])
def signup():
    return render_template("signup_login.html")


def send_verification_email(email, code):
    try:
        sender = os.getenv('MAIL_EMAIL')
        password = os.getenv('MAIL_PASSWORD')

        print(f"발신자: {sender}")
        print(f"인증번호: {code}")

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
        msg = MIMEText(html, "html")
        msg["Subject"] = "[AI Quant] 이메일 인증번호 안내"
        msg["From"] = sender
        msg["To"] = email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)

        print("이메일 발송 성공!")

    except Exception as e:
        print(f"이메일 발송 실패: {e}")


@auth_bp.route("/register", methods=["POST"])
def register():
    print("register 요청 들어옴")
    email = request.form["email"]
    password = request.form["password"]
    nickname = request.form["nickname"]
    code = request.form.get("code")

    # 인증번호 확인 단계
    if code:
        data = verification_codes.get(email)
        if data:
            saved_code = data["code"]
            created_time = data["time"]

            # 5분 = 300초
            if time.time() - created_time > 300:
                return render_template(
                    "signup_login.html",
                    error="인증번호가 만료되었습니다. 다시 요청해주세요.",
                    email=email,
                    password=password,
                    nickname=nickname
                )

            if saved_code == code:
        
                conn = get_conn()
                try:
                    with conn.cursor() as cursor:
                        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode("utf-8")

                        # 1. users 테이블에 회원 추가
                        cursor.execute(
                            """
                            INSERT INTO users (email, password_hash, nickname)
                            VALUES (%s, %s, %s)
                            """,
                            (email, hashed_pw, nickname),
                        )

                        # 2. 방금 생성된 user id 가져오기
                        user_id = cursor.lastrowid

                        # 3. mock_accounts 테이블에 모의투자 계좌 생성
                        cursor.execute(
                            """
                            INSERT INTO mock_accounts (user_id, initial_balance, current_balance, total_profit_loss)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (user_id, 10000000.00, 10000000.00, 0.00),
                        )

                    conn.commit()

                except Exception as e:
                    conn.rollback()
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

            del verification_codes[email]
            return redirect(url_for("auth_bp.login_page"))

        else:
            return render_template(
                "signup_login.html",
                error="인증번호가 틀렸어요!",
                show_code=True,
                email=email,
                password=password,
                nickname=nickname
            )

    # 이메일/닉네임 중복 확인
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                return render_template(
                    "signup_login.html",
                    error="이미 사용 중인 이메일입니다.",
                )

            cursor.execute("SELECT 1 FROM users WHERE nickname = %s", (nickname,))
            if cursor.fetchone():
                return render_template(
                    "signup_login.html",
                    error="이미 사용 중인 닉네임입니다.",
                )
    finally:
        conn.close()

    # 인증번호 생성 및 발송
    code = str(random.randint(100000, 999999))
    verification_codes[email] = {
        "code": code,
        "time": time.time()
    }
    send_verification_email(email, code)

    return render_template(
        "signup_login.html",
        show_code=True,
        email=email,
        password=password,
        nickname=nickname
    )

@auth_bp.route("/logout", methods=["GET"])
def logout():
    session.pop("nickname", None)
    return redirect(url_for("auth_bp.login_page"))