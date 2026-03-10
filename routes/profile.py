from flask import Blueprint, redirect, render_template, request, session, url_for
from database import get_conn

profile_bp = Blueprint("profile_bp", __name__)


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
                "SELECT id, nickname, email FROM users WHERE nickname = %s",
                (session["nickname"],)
            )
            user_info = cur.fetchone()
    finally:
        conn.close()

    if not user_info:
        return redirect(url_for("auth_bp.login_page"))

    return render_template("profile.html", user_info=user_info)


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
        session["nickname"] = new_nickname  # 세션도 함께 갱신
    finally:
        conn.close()

    return redirect(url_for("profile_bp.show_profile"))


# ──────────────────────────────────────────────
# 비밀번호 변경 (POST)
# ──────────────────────────────────────────────
@profile_bp.post('/profile/change_password')
def change_password():
    if "nickname" not in session:
        return redirect(url_for("auth_bp.login_page"))

    current_pw = request.form.get("current_password", "")
    new_pw     = request.form.get("new_password", "")
    confirm_pw = request.form.get("confirm_password", "")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 현재 비밀번호 확인
            cur.execute(
                "SELECT 1 FROM users WHERE nickname = %s AND password_hash = %s",
                (session["nickname"], current_pw)
            )
            if not cur.fetchone():
                return _render_with_error(error_password="현재 비밀번호가 올바르지 않습니다.")

            if new_pw != confirm_pw:
                return _render_with_error(error_password="새 비밀번호가 일치하지 않습니다.")

            if len(new_pw) < 4:
                return _render_with_error(error_password="비밀번호는 4자 이상이어야 합니다.")

            cur.execute(
                "UPDATE users SET password_hash = %s WHERE nickname = %s",
                (new_pw, session["nickname"])
            )
        conn.commit()
    finally:
        conn.close()

    # 비밀번호 변경 후 보안을 위해 로그아웃 처리
    session.clear()
    return redirect(url_for("auth_bp.login_page"))


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
                "SELECT id FROM users WHERE nickname = %s AND password_hash = %s",
                (session["nickname"], password)
            )
            user = cur.fetchone()

            if not user:
                return _render_with_error(error_delete="비밀번호가 올바르지 않습니다.")

            user_id = user["id"]
            # 외래키 제약 때문에 연관 데이터부터 순서대로 삭제
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
# 내부 헬퍼: 에러 메시지와 함께 프로필 페이지 렌더링
# ──────────────────────────────────────────────
def _render_with_error(**kwargs):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, nickname, email FROM users WHERE nickname = %s",
                (session["nickname"],)
            )
            user_info = cur.fetchone()
    finally:
        conn.close()
    return render_template("profile.html", user_info=user_info, **kwargs)