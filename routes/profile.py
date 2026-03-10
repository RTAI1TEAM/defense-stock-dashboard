from flask import Blueprint, redirect, render_template, request, session, url_for
from database import get_conn
from dotenv import load_dotenv

profile_bp = Blueprint("profile_bp", __name__)

@profile_bp.get('/profile')
def show_profile():
    if "nickname" in session:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                sql = "SELECT nickname, email FROM users WHERE nickname = %s"
                cur.execute(sql, (session["nickname"],))
                userInfo = cur.fetchone()
                return render_template("profile.html", userInfo=userInfo)
        finally:
            conn.close()
