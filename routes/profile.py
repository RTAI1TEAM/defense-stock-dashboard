from flask import Blueprint, redirect, render_template, request, session, url_for, jsonify
from database import get_conn
import bcrypt

profile_bp = Blueprint("profile_bp", __name__)

ALLOWED_AVATARS = {
    "🧑‍💼", "😀", "😎", "🤓", "🦊",
    "🐼", "🐯", "🐸", "🐶", "🐱",
    "🐻", "🐰", "🐧", "🦁", "🤖",
    "👨‍💻", "👩‍💻", "🔥", "⭐", "🚀"
}


# ──────────────────────────────────────────────
# 프로필 페이지 (GET)
# ──────────────────────────────────────────────
@profile_bp.get('/profile')
def show_profile():
    if "nickname" not in session:
        return redirect(url_for("auth_bp.login_page"))

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nickname, email, avatar FROM users WHERE nickname = %s",
                (session["nickname"],)
            )
            user_info = cur.fetchone()
    finally:
        conn.close()

    if not user_info:
        return redirect(url_for("auth_bp.login_page"))

    return render_template("profile.html", user_info=user_info)


# ──────────────────────────────────────────────
# 아바타 변경 (POST / AJAX)
# ──────────────────────────────────────────────
@profile_bp.post('/profile/change_avatar')
def change_avatar():
    if "nickname" not in session:
        return jsonify({"status": "error", "message": "로그인이 필요합니다."}), 401

    data = request.get_json(silent=True) or {}
    avatar = (data.get("avatar") or "").strip()

    if avatar not in ALLOWED_AVATARS:
        return jsonify({"status": "error", "message": "허용되지 않은 아바타입니다."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET avatar = %s WHERE nickname = %s",
                (avatar, session["nickname"])
            )
        conn.commit()
    finally:
        conn.close()

        session["avatar"] = avatar #프로필 아바타변경 적용

    return jsonify({"status": "ok", "avatar": avatar})


# ──────────────────────────────────────────────
# 닉네임 변경 (POST)
# ──────────────────────────────────────────────
@profile_bp.post('/profile/change_nickname')
def change_nickname():
    if "nickname" not in session:
        return redirect(url_for("auth_bp.login_page"))

    new_nickname = request.form.get("new_nickname", "").strip()

    if not new_nickname:
        return _render_with_error(error_nickname="닉네임을 입력해주세요.")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE nickname = %s", (new_nickname,))
            if cur.fetchone():
                return _render_with_error(error_nickname="이미 사용 중인 닉네임입니다.")

            cur.execute(
                "UPDATE users SET nickname = %s WHERE nickname = %s",
                (new_nickname, session["nickname"])
            )
        conn.commit()
        session["nickname"] = new_nickname
    finally:
        conn.close()

    return redirect(url_for("profile_bp.show_profile"))


# ──────────────────────────────────────────────
# 비밀번호 변경 (POST)
# ──────────────────────────────────────────────
@profile_bp.post('/profile/change_password')
def change_password():
    if "nickname" not in session:
        return jsonify({
            "status": "error",
            "message": "로그인이 필요합니다.",
            "redirect_url": url_for("auth_bp.login_page")
        }), 401

    current_pw = request.form.get("current_password", "")
    new_pw = request.form.get("new_password", "")
    confirm_pw = request.form.get("confirm_password", "")

    if new_pw != confirm_pw:
        return jsonify({
            "status": "error",
            "message": "새 비밀번호가 일치하지 않습니다."
        }), 400

    if len(new_pw) < 8:
        return jsonify({
            "status": "error",
            "message": "비밀번호는 8자 이상이어야 합니다."
        }), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT password_hash FROM users WHERE nickname = %s",
                (session["nickname"],)
            )
            user = cur.fetchone()

            if not user or not bcrypt.checkpw(
                current_pw.encode('utf-8'),
                user['password_hash'].encode('utf-8')
            ):
                return jsonify({
                    "status": "error",
                    "message": "현재 비밀번호가 올바르지 않습니다."
                }), 400


            hashed_pw = bcrypt.hashpw(new_pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            cur.execute(
                "UPDATE users SET password_hash = %s WHERE nickname = %s",
                (hashed_pw, session["nickname"])
            )
        conn.commit()
    finally:
        conn.close()

    session.clear()
    return jsonify({
        "status": "ok",
        "message": "비밀번호가 변경되었습니다. 다시 로그인해주세요.",
        "redirect_url": url_for("auth_bp.login_page")
    })


# ──────────────────────────────────────────────
# 이메일 변경 (POST)
# ──────────────────────────────────────────────
@profile_bp.post('/profile/change_email')
def change_email():
    if "nickname" not in session:
        return redirect(url_for("auth_bp.login_page"))

    new_email = request.form.get("new_email", "").strip()

    if not new_email or "@" not in new_email:
        return _render_with_error(error_email="올바른 이메일을 입력해주세요.")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE email = %s", (new_email,))
            if cur.fetchone():
                return _render_with_error(error_email="이미 사용 중인 이메일입니다.")

            cur.execute(
                "UPDATE users SET email = %s WHERE nickname = %s",
                (new_email, session["nickname"])
            )
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("profile_bp.show_profile"))


# ──────────────────────────────────────────────
# 회원 탈퇴 (POST)
# ──────────────────────────────────────────────
@profile_bp.post('/profile/delete_account')
def delete_account():
    if "nickname" not in session:
        return redirect(url_for("auth_bp.login_page"))

    password = request.form.get("delete_password", "")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, password_hash FROM users WHERE nickname = %s",
                (session["nickname"],)
            )
            user = cur.fetchone()

            if not user or not bcrypt.checkpw(
                password.encode('utf-8'),
                user['password_hash'].encode('utf-8')
            ):
                return _render_with_error(error_delete="비밀번호가 올바르지 않습니다.")

            user_id = user["id"]

            cur.execute("DELETE FROM trades WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM portfolio_holdings WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM mock_accounts WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))

        conn.commit()
    finally:
        conn.close()

    session.clear()
    return redirect(url_for("auth_bp.login_page"))


# ──────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────
def _render_with_error(**kwargs):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nickname, email, avatar FROM users WHERE nickname = %s",
                (session["nickname"],)
            )
            user_info = cur.fetchone()
    finally:
        conn.close()

    return render_template("profile.html", user_info=user_info, **kwargs)