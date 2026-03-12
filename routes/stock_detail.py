"""
stock_detail.py — 종목 상세 페이지 라우트 및 관련 비즈니스 로직

[ 이 파일의 역할 ]
  사용자가 특정 종목 페이지를 열었을 때 필요한 모든 데이터를 준비합니다.
  크게 4가지 영역으로 나뉩니다.

  1. 유틸리티     : 텍스트 정리, NaN 처리 등 공통 도우미 함수
  2. AI 분석      : 네이버 뉴스 수집 → Gemini AI 분석 → DB 저장
  3. DB 조회 헬퍼 : 화면에 뿌릴 데이터를 DB에서 꺼내오는 함수 모음
  4. 라우트       : Flask URL 핸들러 (페이지 렌더링 / API 응답)

[ 호출 흐름 ]
  daily_update.py (배치)
      └─ update_sector_ai_analysis()   : 업종 전체 뉴스 분석
      └─ update_all_stocks_ai_analysis(): 전 종목 뉴스 분석

  브라우저 요청
      └─ /stocks/<ticker>    → show_stock_chart()
      └─ /invest/execute     → execute_trade()
      └─ /api/strategy/<ticker> → strategy_api()
"""

import os
import re
import html
import json
import math
import time
import requests
import pandas as pd
from google import genai
from datetime import datetime
from dotenv import load_dotenv
from flask import Blueprint, redirect, render_template, request, session, url_for, jsonify, abort

from database import get_conn
from algorithm import strategy_golden_cross, strategy_breakout, run_backtest


# Flask Blueprint 등록 — app.py에서 register_blueprint() 로 연결됩니다
stock_detail_bp = Blueprint('stock_detail', __name__)


# =============================================================
# 외부 API 키 설정
#   .env 파일에서 불러옵니다. 키가 없으면 API 호출이 실패합니다.
# =============================================================

GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY")       # Google Gemini AI
NAVER_CLIENT_ID     = os.getenv("NAVER_CLIENT_ID")      # 네이버 검색 API
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

MODEL_ID = "gemini-2.5-flash"                           # 사용할 Gemini 모델
client   = genai.Client(api_key=GEMINI_API_KEY)         # Gemini 클라이언트 초기화


# =============================================================
# 유틸리티 함수
# =============================================================

def strip_html(text):
    """
    뉴스 제목/내용에 섞인 HTML 태그를 제거합니다.
    예) '<b>LIG넥스원</b>' → 'LIG넥스원'
    """
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text).strip()


def nan_to_none(val):
    """
    pandas 연산 후 생기는 NaN을 JSON 직렬화 가능한 None으로 바꿉니다.
    (MA 초반 구간처럼 값이 없는 경우 차트에서 null로 표시됩니다)
    """
    try:
        if val is None:
            return None
        if isinstance(val, float) and math.isnan(val):
            return None
        return val
    except Exception:
        return None


# =============================================================
# AI 분석 함수
#   뉴스 수집 → Gemini 분석 → DB 저장 흐름을 담당합니다.
# =============================================================

def get_live_analysis(stock_name):
    """
    [실시간] 네이버 뉴스 3개를 가져와 Gemini AI로 분석합니다.

    일반적으로는 DB에 저장된 분석 결과(get_db_or_api_stock_news)를 쓰고,
    배치가 실패해 DB에 데이터가 없을 때만 이 함수를 직접 호출합니다.

    Returns:
        news_list  : 뉴스 목록 (title, link, description_clean)
        score      : AI 투자 매력도 점수 (0~100)
        ai_news    : AI 요약 문구
        status     : 긍정 / 보통 / 부정
        color      : Bootstrap 배지 색상 클래스
    """
    headers = {
        "X-Naver-Client-Id":     NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params    = {"query": f"{stock_name} 주가 전망", "display": 3, "sort": "sim"}
    news_list = []

    # ── 1단계: 네이버 뉴스 API 호출 ──────────────────────────
    try:
        resp = requests.get(
            "https://openapi.naver.com/v1/search/news.json",
            headers=headers, params=params, timeout=5
        )
        if resp.status_code != 200:
            return [], 50, "뉴스 데이터를 가져올 수 없습니다.", "인증 오류", "bg-dark"

        for item in resp.json().get("items", []):
            news_list.append({
                "title":             strip_html(item.get("title", "")),
                "link":              item.get("link"),
                "description_clean": strip_html(item.get("description", ""))
            })
    except Exception as e:
        print(f"뉴스 API 호출 중 예외 발생: {e}")

    # 뉴스를 하나도 못 가져온 경우 기본값 반환
    if not news_list:
        return [], 50, f"'{stock_name}' 관련 최신 뉴스가 없습니다.", "데이터 부족", "bg-secondary"

    # ── 2단계: Gemini 프롬프트 구성 ──────────────────────────
    news_context = "\n".join(
        [f"제목: {n['title']}\n내용: {n['description_clean']}" for n in news_list]
    )
    prompt = f"""
    당신은 주식 투자 전문가입니다. 아래 제공된 '{stock_name}' 관련 뉴스 3개를 읽고 분석하세요.
    - score: 투자 매력도 (0~100 숫자)
    - ai_news: 뉴스 요약 (20자 이내)
    반드시 JSON 형식으로만 답변하세요.
    뉴스 내용:
    {news_context}
    """

    # ── 3단계: Gemini AI 응답 수신 및 파싱 ───────────────────
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config={'response_mime_type': 'application/json'}
        )

        data = json.loads(response.text.strip())
        # Gemini가 간혹 배열로 응답할 때 첫 번째 원소를 사용합니다
        if isinstance(data, list):
            data = data[0] if data else {}

        score   = int(data.get("score", 50))
        ai_news = data.get("ai_news", "시장 관망 후 진입을 추천합니다.")

        # 점수 구간별 화면 표시 색상 결정
        if score >= 70:   status, color = "긍정", "bg-success"
        elif score >= 40: status, color = "보통", "bg-warning"
        else:             status, color = "부정", "bg-danger"

        return news_list, score, ai_news, status, color

    except Exception as e:
        print(f"Gemini 분석 에러: {e}")
        return news_list, 50, "AI 분석 엔진 일시 오류", "분석 불가", "bg-secondary"


def update_all_stocks_ai_analysis():
    """
    [배치 전용] 전 종목 AI 분석을 일괄 실행해 DB에 저장합니다.
    daily_update.py에서 매일 1회 호출합니다.

    각 종목마다 get_live_analysis()를 호출한 뒤,
    결과를 stock_news 테이블에 UPSERT(있으면 갱신, 없으면 삽입)합니다.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name_kr FROM stocks")
            stocks = cursor.fetchall()

            print(f"🚀 총 {len(stocks)}개 종목 AI 전수 분석 시작...")

            for stock in stocks:
                stock_id   = stock['id']
                stock_name = stock['name_kr']

                try:
                    news_list, score, ai_news, _, _ = get_live_analysis(stock_name)

                    # 이미 오늘 데이터가 있으면 덮어쓰고, 없으면 새로 삽입합니다
                    cursor.execute(
                        """
                        INSERT INTO stock_news (stock_id, score, ai_summary, news_data, updated_at)
                        VALUES (%s, %s, %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                            score      = VALUES(score),
                            ai_summary = VALUES(ai_summary),
                            news_data  = VALUES(news_data),
                            updated_at = NOW()
                        """,
                        (stock_id, score, ai_news, json.dumps(news_list, ensure_ascii=False))
                    )
                    conn.commit()
                    print(f"✅ {stock_name} 업데이트 완료")

                    time.sleep(1)  # Gemini 무료 티어 분당 호출 한도 초과 방지

                except Exception as e:
                    print(f"❌ {stock_name} 분석 오류: {e}")
                    continue   # 한 종목 실패해도 나머지는 계속 진행
    finally:
        conn.close()


def update_sector_ai_analysis():
    """
    [배치 전용] 방산 업종 전체 AI 분석을 실행해 DB에 저장합니다.
    daily_update.py에서 매일 1회 호출합니다.

    최신 뉴스 10개를 종합해 업종 대표 레코드(stock_id=9999)에 저장합니다.
    stock_id=9999는 실제 종목이 아닌 '업종 전체'를 나타내는 가상 ID입니다.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 가장 최근 방산 뉴스 10개 조회
            cursor.execute("""
                SELECT title, summary AS description_clean, source_url AS link
                FROM news
                ORDER BY published_at DESC
                LIMIT 10
            """)
            news_items = cursor.fetchall()

            if not news_items:
                print("분석할 뉴스가 없습니다.")
                return

            news_context = "\n".join(
                [f"제목: {n['title']}\n내용: {n['description_clean']}" for n in news_items]
            )
            prompt = f"""
            당신은 대한민국 방위산업 투자 전문가입니다.
            아래 10개의 최신 방산 뉴스를 종합하여 업종 전체의 투자 점수와 핵심 요약을 작성하세요.
            반드시 JSON 형식으로 응답하세요:
            {{
                "score": 0~100 사이 숫자,
                "ai_news": "업종 전체의 흐름을 보여주는 한 줄 요약 (25자 이내)"
            }}
            뉴스 데이터:
            {news_context}
            """

            response = client.models.generate_content(
                model=MODEL_ID,
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            data = json.loads(response.text.strip())

            print(f"[DEBUG] news 개수: {len(news_items)}")
            print("[DEBUG] Gemini 응답 원문:", response.text)

            # stock_id=9999 → 업종 전체를 나타내는 가상 레코드
            cursor.execute(
                """
                INSERT INTO stock_news (stock_id, score, ai_summary, news_data, updated_at)
                VALUES (9999, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                    score      = VALUES(score),
                    ai_summary = VALUES(ai_summary),
                    news_data  = VALUES(news_data),
                    updated_at = NOW()
                """,
                (data['score'], data['ai_news'], json.dumps(news_items, ensure_ascii=False))
            )
            conn.commit()
            print("[DEBUG] commit 완료")

    except Exception as e:
        print(f"업종 분석 중 오류: {e}")
    finally:
        conn.close()


# =============================================================
# DB 조회 헬퍼
#   화면에 뿌릴 데이터를 DB에서 꺼내오는 함수 모음입니다.
#   직접 API를 호출하지 않고 배치가 저장해 둔 결과를 읽기만 합니다.
# =============================================================

def get_db_or_api_stock_news(stock_id, stock_name):
    """
    [웹 요청용] 종목 AI 분석 결과를 DB에서 조회해 반환합니다.

    배치(update_all_stocks_ai_analysis)가 매일 저장해 두기 때문에
    보통은 DB 결과를 바로 반환합니다.
    배치가 실패해 DB에 데이터가 없으면 실시간 분석(get_live_analysis)으로 대체합니다.

    Returns:
        news_list, score, ai_news, status, color
    """
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT score, ai_summary, news_data FROM stock_news WHERE stock_id = %s",
                (stock_id,)
            )
            row = cursor.fetchone()

        if not row:
            # DB에 데이터가 없는 경우 — 실시간 분석으로 폴백
            return get_live_analysis(stock_name)

        news_list = json.loads(row['news_data'])
        score     = row['score']
        ai_news   = row['ai_summary']

        # 점수 구간별 화면 표시 색상 결정 (get_live_analysis와 동일 기준)
        if score >= 70:   status, color = "긍정", "bg-success"
        elif score >= 40: status, color = "보통", "bg-warning"
        else:             status, color = "부정", "bg-danger"

        return news_list, score, ai_news, status, color
    finally:
        conn.close()


def get_defense_sector_analysis():
    """
    [웹 요청용] 방산 업종 전체 AI 분석 결과를 반환합니다.
    stock_id=9999 레코드에서 조회합니다.

    Returns:
        score (int), ai_summary (str), news_list (list)
    """
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT score, ai_summary, news_data FROM stock_news WHERE stock_id = 9999"
            )
            row = cursor.fetchone()
        if row:
            return row['score'], row['ai_summary'], json.loads(row['news_data'])
        return 0, "데이터 분석 대기 중...", []
    finally:
        conn.close()


def get_stock(ticker="064350"):
    """
    ticker 코드로 종목 기본 정보를 조회합니다.
    존재하지 않는 ticker면 None을 반환합니다.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, ticker, name_kr
                FROM stocks
                WHERE ticker = %s
                ORDER BY id
                LIMIT 1
                """,
                (ticker,)
            )
            return cursor.fetchone()
    finally:
        conn.close()


def get_stock_list():
    """드롭다운 메뉴용 전체 종목 목록(name_kr, ticker)을 반환합니다."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name_kr, ticker FROM stocks")
            return cur.fetchall()
    finally:
        conn.close()


def get_stock_chart_data(stock_id):
    """
    캔들차트(OHLC)용 데이터를 반환합니다.
    Chart.js의 시간축 형식에 맞춰 x값을 밀리초 타임스탬프로 변환합니다.

    Returns:
        list of dict — {x, o, h, l, c}
    """
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT price_date, open_price, high_price, low_price, close_price
                FROM stock_price_history
                WHERE stock_id = %s
                ORDER BY price_date
                """,
                (stock_id,)
            )
            rows = cursor.fetchall()

        return [
            {
                "x": int(datetime.combine(r["price_date"], datetime.min.time()).timestamp() * 1000),
                "o": float(r["open_price"]),
                "h": float(r["high_price"]),
                "l": float(r["low_price"]),
                "c": float(r["close_price"]),
            }
            for r in rows
        ]
    finally:
        conn.close()


# =============================================================
# 라우트 (Flask URL 핸들러)
#   브라우저 요청을 받아 HTML 또는 JSON을 응답합니다.
# =============================================================

@stock_detail_bp.route("/stocks/<ticker>")
def show_stock_chart(ticker):
    """
    종목 상세 페이지를 렌더링합니다.
    URL 예시: /stocks/064350

    준비하는 데이터:
      - 캔들차트 OHLC 데이터
      - AI 뉴스 분석 결과 (score, ai_news)
      - 골든크로스 / 돌파매매 전략 백테스트 수익률
      - 모의 계좌 잔액 (투자 폼에서 사용)
      - 현재 주가
    """
    if "nickname" not in session:
        return redirect(url_for("auth_bp.login_page"))

    user_id = session.get('user_id')
    stock   = get_stock(ticker)

    if stock is None:
        abort(404)  # 존재하지 않는 종목 접근 시 404 반환

    stock_list = get_stock_list()
    chart_data = get_stock_chart_data(stock["id"])
    news_list, score, ai_news, status, color_class = get_db_or_api_stock_news(
        stock["id"], stock["name_kr"]
    )

    account       = None
    current_price = 0

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 모의 계좌 잔액 — 투자 가능 금액 표시에 사용
            cursor.execute(
                "SELECT current_balance FROM mock_accounts WHERE user_id = %s",
                (user_id,)
            )
            account = cursor.fetchone()

            # 가장 최근 종가 — 매수/매도 폼의 기준 가격
            cursor.execute(
                """
                SELECT close_price
                FROM stock_price_history
                WHERE stock_id = %s
                ORDER BY price_date DESC
                LIMIT 1
                """,
                (stock["id"],)
            )
            latest        = cursor.fetchone()
            current_price = float(latest["close_price"]) if latest else 0

            # 전략 백테스트를 위한 전체 가격 이력
            cursor.execute(
                """
                SELECT price_date AS date, close_price
                FROM stock_price_history
                WHERE stock_id = %s
                ORDER BY price_date
                """,
                (stock["id"],)
            )
            rows = cursor.fetchall()

        df = pd.DataFrame(rows)

        # 두 전략 모두 백테스트해서 과거 수익률을 계산합니다
        df_gc = strategy_golden_cross(df)
        profit_gc, _, _, _ = run_backtest(df_gc)

        df_bo = strategy_breakout(df)
        profit_bo, _, _, _ = run_backtest(df_bo)

        # 템플릿에서 전략 선택 드롭다운과 수익률 표시에 사용됩니다
        strategies = {
            "GOLDEN_CROSS": {"name": "5/20 골든크로스",   "profit": profit_gc},
            "BREAKOUT":     {"name": "20일 전고점 돌파", "profit": profit_bo},
        }

        chart_labels = [str(r["date"])          for r in rows]
        chart_values = [float(r["close_price"]) for r in rows]

    finally:
        conn.close()

    return render_template(
        "stock_detail.html",
        stock_list=stock_list,
        stock=stock,
        ticker=stock["ticker"],
        stock_id=stock["id"],
        strategies=strategies,
        chart_data=chart_data,
        chart_labels=chart_labels,
        chart_values=chart_values,
        news_list=news_list,
        score=score,
        ai_news=ai_news,
        status=status,
        color_class=color_class,
        account=account,
        current_price=current_price,
    )


@stock_detail_bp.route("/invest/execute", methods=['POST'])
def execute_trade():
    """
    모의 투자 매수/매도를 처리합니다.
    폼 전송 → JSON 응답 방식(AJAX)으로 동작합니다.

    처리 순서:
      1. 입력값 검증 (로그인, 수량, ticker 누락 확인)
      2. 종목 현재가 조회
      3. 모의 계좌 확인 (없으면 1,000만원으로 신규 생성)
      4. BUY: 잔액 차감 → 보유 종목 추가/평단 갱신
         SELL: 보유 확인 → 잔액 환원 → 수량 감소 → 0주면 포지션 삭제
      5. 거래 내역 기록 → commit
    """
    if "nickname" not in session:
        return jsonify({"success": False, "message": "로그인이 필요합니다."})

    ticker_from_form = request.form.get('stock_id')
    trade_type       = request.form.get('trade_type', 'BUY')
    strategy_name    = request.form.get('strategy') or "일반 매매"
    user_id          = session.get('user_id')

    try:
        quantity = int(request.form.get('quantity') or 0)
    except ValueError:
        return jsonify({"success": False, "message": "수량 형식이 올바르지 않습니다."})

    # ── 입력값 검증 ───────────────────────────────────────────
    if not user_id:
        return jsonify({"success": False, "message": "세션이 만료되었습니다. 다시 로그인해주세요."})
    if not ticker_from_form:
        return jsonify({"success": False, "message": "종목 코드가 누락되었습니다."})
    if quantity <= 0:
        return jsonify({"success": False, "message": "수량을 1주 이상 입력하세요."})

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cursor:

            # ── 종목 현재가 조회 ──────────────────────────────
            cursor.execute(
                """
                SELECT s.id, h.close_price, s.name_kr
                FROM stocks s
                INNER JOIN stock_price_history h ON s.id = h.stock_id
                WHERE s.ticker = %s
                ORDER BY h.price_date DESC
                LIMIT 1
                """,
                (ticker_from_form,)
            )
            stock_res = cursor.fetchone()
            if not stock_res:
                return jsonify({"success": False, "message": "해당 종목의 시세 데이터를 찾을 수 없습니다."})

            stock_id     = stock_res['id']
            price        = float(stock_res['close_price'])
            total_amount = price * quantity   # 총 거래 금액

            # ── 모의 계좌 조회 (없으면 1,000만원으로 신규 생성) ──
            cursor.execute(
                "SELECT id, current_balance FROM mock_accounts WHERE user_id = %s",
                (user_id,)
            )
            account = cursor.fetchone()
            if not account:
                cursor.execute(
                    """
                    INSERT INTO mock_accounts (user_id, initial_balance, current_balance)
                    VALUES (%s, 10000000.00, 10000000.00)
                    """,
                    (user_id,)
                )
                conn.commit()
                cursor.execute(
                    "SELECT id, current_balance FROM mock_accounts WHERE user_id = %s",
                    (user_id,)
                )
                account = cursor.fetchone()

            # ── 매수 처리 ─────────────────────────────────────
            if trade_type == 'BUY':
                if float(account['current_balance']) < total_amount:
                    return jsonify({"success": False, "message": f"잔액 부족 (필요: {total_amount:,.0f}원)"})

                cursor.execute(
                    "UPDATE mock_accounts SET current_balance = current_balance - %s WHERE id = %s",
                    (total_amount, account['id'])
                )
                # 같은 전략으로 같은 종목을 추가 매수하면 평균 단가가 자동으로 재계산됩니다
                cursor.execute(
                    """
                    INSERT INTO portfolio_holdings
                        (user_id, account_id, stock_id, quantity, avg_buy_price, total_invested, strategy)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        avg_buy_price  = (total_invested + VALUES(total_invested)) / (quantity + VALUES(quantity)),
                        quantity       = quantity + VALUES(quantity),
                        total_invested = total_invested + VALUES(total_invested)
                    """,
                    (user_id, account['id'], stock_id, quantity, price, total_amount, strategy_name)
                )

            # ── 매도 처리 ─────────────────────────────────────
            elif trade_type == 'SELL':
                # 같은 전략으로 매수했던 포지션에서만 매도할 수 있습니다
                cursor.execute(
                    "SELECT id, quantity FROM portfolio_holdings "
                    "WHERE user_id = %s AND stock_id = %s AND strategy = %s",
                    (user_id, stock_id, strategy_name)
                )
                holding = cursor.fetchone()
                if not holding or holding['quantity'] < quantity:
                    return jsonify({"success": False, "message": "보유 수량이 부족합니다."})

                cursor.execute(
                    "UPDATE mock_accounts SET current_balance = current_balance + %s WHERE id = %s",
                    (total_amount, account['id'])
                )
                cursor.execute(
                    "UPDATE portfolio_holdings "
                    "SET quantity = quantity - %s, total_invested = total_invested - (%s * avg_buy_price) "
                    "WHERE id = %s",
                    (quantity, quantity, holding['id'])
                )
                # 잔여 수량이 0 이하면 포지션 행 자체를 삭제합니다
                cursor.execute(
                    "DELETE FROM portfolio_holdings WHERE id = %s AND quantity <= 0",
                    (holding['id'],)
                )

            # ── 거래 내역 기록 ────────────────────────────────
            cursor.execute(
                """
                INSERT INTO trades (user_id, account_id, stock_id, trade_type, price, quantity, total_amount, strategy)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, account['id'], stock_id, trade_type, price, quantity, total_amount, strategy_name)
            )

            conn.commit()

            # 거래 후 남은 잔액 계산 (화면 즉시 갱신용)
            new_balance = float(account['current_balance']) + (
                total_amount if trade_type == 'SELL' else -total_amount
            )
            return jsonify({
                "success":     True,
                "message":     f"{stock_res['name_kr']} {quantity}주 {trade_type} 완료!",
                "new_balance": format(int(new_balance), ','),
            })

    except Exception as e:
        if conn:
            conn.rollback()   # 오류 발생 시 모든 변경사항 롤백
        print(f"Transaction Error: {e}")
        return jsonify({"success": False, "message": f"시스템 오류: {str(e)}"})
    finally:
        if conn:
            conn.close()


@stock_detail_bp.route("/api/strategy/<ticker>")
def strategy_api(ticker):
    """
    전략 신호 및 백테스트 결과를 JSON으로 반환합니다.
    차트 페이지에서 전략을 변경할 때 AJAX로 호출됩니다.

    Query params:
        strategy : 'golden_cross' | 'breakout'  (기본: golden_cross)
        days     : 조회 기간 일수            (기본: 90일)

    Response:
        labels, close, 이동평균선 배열, backtest 거래 목록,
        total_profit(%), win_rate(%), trade_count
    """
    strategy = request.args.get("strategy", "golden_cross")
    days     = int(request.args.get("days", 90))

    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM stocks WHERE ticker = %s", (ticker,))
            stock = cur.fetchone()
            if not stock:
                return jsonify({"success": False, "message": "종목 없음"})

            # DESC로 최근 N일치를 가져온 뒤 아래에서 다시 오름차순으로 뒤집습니다
            cur.execute(
                """
                SELECT price_date AS date, close_price
                FROM stock_price_history
                WHERE stock_id = %s
                ORDER BY price_date DESC
                LIMIT %s
                """,
                (stock["id"], days)
            )
            rows = cur.fetchall()
        conn.close()

        rows = list(reversed(rows))  # 날짜 오름차순으로 정렬 (차트 x축 방향)
        df   = pd.DataFrame(rows)

        if strategy == "golden_cross":
            df = strategy_golden_cross(df)
            total_profit, trades, win_rate, trade_count = run_backtest(df)
            return jsonify({
                "success":      True,
                "strategy":     "golden_cross",
                "labels":       [str(r["date"])          for r in rows],
                "close":        [float(r["close_price"]) for r in rows],
                "ma_short":     [nan_to_none(v)          for v in df["MA_short"].tolist()],
                "ma_long":      [nan_to_none(v)          for v in df["MA_long"].tolist()],
                "backtest":     trades,
                "total_profit": total_profit,
                "win_rate":     win_rate,
                "trade_count":  trade_count,
            })

        elif strategy == "breakout":
            df = strategy_breakout(df)
            total_profit, trades, win_rate, trade_count = run_backtest(df)
            return jsonify({
                "success":      True,
                "strategy":     "breakout",
                "labels":       [str(r["date"])          for r in rows],
                "close":        [float(r["close_price"]) for r in rows],
                "high20":       [nan_to_none(v)          for v in df["High20"].tolist()],
                "ma20":         [nan_to_none(v)          for v in df["MA20"].tolist()],
                "backtest":     trades,
                "total_profit": total_profit,
                "win_rate":     win_rate,
                "trade_count":  trade_count,
            })

        else:
            return jsonify({"success": False, "message": "알 수 없는 전략"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
