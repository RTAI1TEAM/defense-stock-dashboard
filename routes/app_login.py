from flask import Blueprint, redirect, render_template, request, session, url_for
from database import get_conn
from dotenv import load_dotenv
import bcrypt
import random
import smtplib
import os
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

        msg = MIMEText(f'인증번호: {code}')
        msg['Subject'] = 'AI Quant 이메일 인증'
        msg['From'] = sender
        msg['To'] = email

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        print("이메일 발송 성공!")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")


@auth_bp.route("/register", methods=["POST"])
def register():
    email = request.form["email"]
    password = request.form["password"]
    nickname = request.form["nickname"]
    code = request.form.get("code")

    # 인증번호 확인 단계
    if code:
        if verification_codes.get(email) == code:
            conn = get_conn()
            try:
                with conn.cursor() as cursor:
                    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
                    cursor.execute(
                        "INSERT INTO users (email, password_hash, nickname) VALUES (%s, %s, %s)",
                        (email, hashed_pw, nickname),
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
    verification_codes[email] = code
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