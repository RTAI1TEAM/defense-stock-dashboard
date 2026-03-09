import os

import pymysql
from dotenv import load_dotenv
from flask import Blueprint, redirect, render_template, request, session, url_for

load_dotenv()

auth_bp = Blueprint("auth_bp", __name__)

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")


def get_conn():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


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
                "SELECT * FROM users WHERE email = %s AND password_hash = %s",
                (email, password),
            )
            user = cursor.fetchone()
    finally:
        conn.close()

    if user:
        session["nickname"] = user["nickname"]
        return redirect(url_for("index"))

    return render_template(
        "index_login.html",
        error="이메일 또는 비밀번호가 일치하지 않습니다.",
    )


@auth_bp.route("/signup", methods=["GET"])
def signup():
    return render_template("signup_login.html")


@auth_bp.route("/register", methods=["POST"])
def register():
    email = request.form["email"]
    password = request.form["password"]
    nickname = request.form["nickname"]

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

            cursor.execute(
                "INSERT INTO users (email, password_hash, nickname) VALUES (%s, %s, %s)",
                (email, password, nickname),
            )
    finally:
        conn.close()

    return redirect(url_for("auth_bp.login_page"))


@auth_bp.route("/logout", methods=["GET"])
def logout():
    session.pop("nickname", None)
    return redirect(url_for("auth_bp.login_page"))
