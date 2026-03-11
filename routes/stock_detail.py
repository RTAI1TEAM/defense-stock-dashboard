import os
import re
import html
import json
import math
import requests
import google.generativeai as genai
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from database import get_conn
from flask import Blueprint, redirect, render_template, request, session, url_for, jsonify
from algorithm import strategy_golden_cross, strategy_breakout, run_backtest

stock_detail_bp = Blueprint('stock_detail', __name__)

# --- API 설정 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(model_name='gemini-2.5-flash')

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")


# --- 유틸리티 함수 ---
def strip_html(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text).strip()


# NaN → None 변환 (JSON 직렬화 안전 처리)
def nan_to_none(val):
    try:
        if val is None:
            return None
        if isinstance(val, float) and math.isnan(val):
            return None
        return val
    except Exception:
        return None


def get_live_analysis(stock_name):
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    search_query = f"{stock_name} 주가 전망"
    params = {"query": search_query, "display": 3, "sort": "sim"}
    news_list = []
    try:
        resp = requests.get("https://openapi.naver.com/v1/search/news.json", headers=headers, params=params, timeout=5)
        if resp.status_code != 200:
            return [], 50, "뉴스 데이터를 가져올 수 없습니다.", "인증 오류", "bg-dark"
        items = resp.json().get("items", [])
        for item in items:
            news_list.append({
                "title": strip_html(item.get("title", "")),
                "link": item.get("link"),
                "description_clean": strip_html(item.get("description", ""))
            })
    except Exception as e:
        print(f"뉴스 API 호출 중 예외 발생: {e}")

    if not news_list:
        return [], 50, f"'{stock_name}' 관련 최신 뉴스가 없습니다.", "데이터 부족", "bg-secondary"

    news_context = "\n".join([f"제목: {n['title']}\n내용: {n['description_clean']}" for n in news_list])
    prompt = f"""
    당신은 주식 투자 전문가입니다. 아래 제공된 '{stock_name}' 관련 뉴스 3개를 읽고 분석하세요.
    1. 투자 매력도 점수 (0~100점)를 산정하세요.
    2. 뉴스 내용을 20자 이내로 요약하세요.
    반드시 아래 JSON 형식으로만 답변하세요. 마크다운 기호(```)를 포함하지 마세요.
    {{
      "score": 숫자,
      "ai_news": "뉴스 요약"
    }}
    뉴스 내용:
    {news_context}
    """
    try:
        response = model.generate_content(prompt)
        clean_json = re.sub(r'```(?:json)?|```', '', response.text).strip()
        data = json.loads(clean_json)
        score = int(data.get("score", 50))
        ai_news = data.get("ai_news", "시장 관망 후 진입을 추천합니다.")
        if score >= 70:   status, color = "긍정", "bg-success"
        elif score >= 40: status, color = "보통", "bg-warning"
        else:             status, color = "부정", "bg-danger"
        return news_list, score, ai_news, status, color
    except Exception as e:
        print(f"Gemini 분석 에러: {e}")
        return news_list, 50, "AI 분석 엔진 일시 오류", "분석 불가", "bg-secondary"


def get_stock(ticker="064350"):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            sql = """
            SELECT id, ticker, name_kr
            FROM stocks
            WHERE ticker=%s
            ORDER BY id
            LIMIT 1
            """
            cursor.execute(sql, (ticker,))
            return cursor.fetchone()
    finally:
        conn.close()


def get_stock_chart_data(stock_id):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            sql = """
            SELECT price_date, open_price, high_price, low_price, close_price
            FROM stock_price_history
            WHERE stock_id = %s
            ORDER BY price_date
            """
            cursor.execute(sql, (stock_id,))
            rows = cursor.fetchall()
            candle_data = []
            for row in rows:
                candle_data.append({
                    "x": int(datetime.combine(row["price_date"], datetime.min.time()).timestamp() * 1000),
                    "o": float(row["open_price"]),
                    "h": float(row["high_price"]),
                    "l": float(row["low_price"]),
                    "c": float(row["close_price"])
                })
            return candle_data
    finally:
        conn.close()


def get_stock_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("select name_kr, ticker from stocks")
            return cur.fetchall()
    finally:
        conn.close()


@stock_detail_bp.route("/stocks/<ticker>")
def show_stock_chart(ticker):
    if "nickname" not in session:
        return redirect(url_for("auth_bp.login_page"))

    user_id = session.get('user_id')
    stock = get_stock(ticker)
    stock_list = get_stock_list()
    chart_data = get_stock_chart_data(stock["id"])
    news_list, score, ai_news, status, color_class = get_live_analysis(stock["name_kr"])
    account = None
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_balance FROM mock_accounts WHERE user_id = %s", (user_id,))
            account = cursor.fetchone()

            sql = """
                SELECT price_date as date, close_price
                FROM stock_price_history
                WHERE stock_id = %s
                ORDER BY price_date
            """
            cursor.execute(sql, (stock["id"],))
            rows = cursor.fetchall()

        df = pd.DataFrame(rows)

        # ✅ run_backtest는 4개 값 반환: (total_profit, trades, win_rate, trade_count)
        df_gc = strategy_golden_cross(df)
        profit_gc, _, _, _ = run_backtest(df_gc)

        df_bo = strategy_breakout(df)
        profit_bo, _, _, _ = run_backtest(df_bo)

        strategies = {
            "GOLDEN_CROSS": {"name": "5/20 골든크로스", "profit": profit_gc},
            "BREAKOUT":     {"name": "20일 전고점 돌파", "profit": profit_bo}
        }

        chart_labels = [str(r["date"]) for r in rows]
        chart_values = [float(r["close_price"]) for r in rows]

    finally:
        conn.close()

    return render_template(
        "stock_detail.html",
        stock_list=stock_list,
        stock=stock,
        strategies=strategies,
        chart_data=chart_data,
        chart_labels=chart_labels,
        chart_values=chart_values,
        news_list=news_list,
        score=score,
        ai_news=ai_news,
        status=status,
        color_class=color_class,
        account=account
    )


@stock_detail_bp.route("/invest/execute", methods=['POST'])
def execute_trade():
    if "nickname" not in session:
        return jsonify({"success": False, "message": "로그인이 필요합니다."})

    ticker_from_form = request.form.get('stock_id')
    try:
        quantity = int(request.form.get('quantity') or 0)
    except ValueError:
        return jsonify({"success": False, "message": "수량 형식이 올바르지 않습니다."})

    trade_type = request.form.get('trade_type', 'BUY')
    strategy_name = request.form.get('strategy') or "일반 매매"
    user_id = session.get('user_id')

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
            sql_stock = """
                SELECT s.id, h.close_price, s.name_kr
                FROM stocks s
                INNER JOIN stock_price_history h ON s.id = h.stock_id
                WHERE s.ticker = %s
                ORDER BY h.price_date DESC
                LIMIT 1
            """
            cursor.execute(sql_stock, (ticker_from_form,))
            stock_res = cursor.fetchone()
            if not stock_res:
                return jsonify({"success": False, "message": "해당 종목의 시세 데이터를 찾을 수 없습니다."})

            stock_id = stock_res['id']
            price = float(stock_res['close_price'])
            total_amount = price * quantity

            cursor.execute("SELECT id, current_balance FROM mock_accounts WHERE user_id = %s", (user_id,))
            account = cursor.fetchone()
            if not account:
                cursor.execute("""
                    INSERT INTO mock_accounts (user_id, initial_balance, current_balance)
                    VALUES (%s, 10000000.00, 10000000.00)
                """, (user_id,))
                conn.commit()
                cursor.execute("SELECT id, current_balance FROM mock_accounts WHERE user_id = %s", (user_id,))
                account = cursor.fetchone()

            if trade_type == 'BUY':
                if float(account['current_balance']) < total_amount:
                    return jsonify({"success": False, "message": f"잔액 부족 (필요: {total_amount:,.0f}원)"})
                cursor.execute("UPDATE mock_accounts SET current_balance = current_balance - %s WHERE id = %s", (total_amount, account['id']))
                cursor.execute("""
                    INSERT INTO portfolio_holdings (user_id, account_id, stock_id, quantity, avg_buy_price, total_invested)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        avg_buy_price = (total_invested + VALUES(total_invested)) / (quantity + VALUES(quantity)),
                        quantity = quantity + VALUES(quantity),
                        total_invested = total_invested + VALUES(total_invested)
                """, (user_id, account['id'], stock_id, quantity, price, total_amount))

            elif trade_type == 'SELL':
                cursor.execute("SELECT id, quantity FROM portfolio_holdings WHERE user_id = %s AND stock_id = %s", (user_id, stock_id))
                holding = cursor.fetchone()
                if not holding or holding['quantity'] < quantity:
                    return jsonify({"success": False, "message": "보유 수량이 부족합니다."})
                cursor.execute("UPDATE mock_accounts SET current_balance = current_balance + %s WHERE id = %s", (total_amount, account['id']))
                cursor.execute("UPDATE portfolio_holdings SET quantity = quantity - %s, total_invested = total_invested - (%s * avg_buy_price) WHERE id = %s", (quantity, quantity, holding['id']))
                cursor.execute("DELETE FROM portfolio_holdings WHERE id = %s AND quantity <= 0", (holding['id'],))

            cursor.execute("""
                INSERT INTO trades (user_id, account_id, stock_id, trade_type, price, quantity, total_amount, strategy)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, account['id'], stock_id, trade_type, price, quantity, total_amount, strategy_name))

            conn.commit()
            return jsonify({
                "success": True,
                "message": f"{stock_res['name_kr']} {quantity}주 {trade_type} 완료!",
                "new_balance": format(int(float(account['current_balance']) + (total_amount if trade_type == 'SELL' else -total_amount)), ',')
            })

    except Exception as e:
        if conn: conn.rollback()
        print(f"Transaction Error: {e}")
        return jsonify({"success": False, "message": f"시스템 오류: {str(e)}"})
    finally:
        if conn: conn.close()


@stock_detail_bp.route("/api/strategy/<ticker>")
def strategy_api(ticker):
    """전략 분석 API — 프론트엔드 차트에서 AJAX로 호출"""
    strategy = request.args.get("strategy", "golden_cross")
    days     = int(request.args.get("days", 90))

    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM stocks WHERE ticker = %s", (ticker,))
            stock = cur.fetchone()
            if not stock:
                return jsonify({"success": False, "message": "종목 없음"})

            cur.execute("""
                SELECT price_date as date, close_price
                FROM stock_price_history
                WHERE stock_id = %s
                ORDER BY price_date DESC
                LIMIT %s
            """, (stock["id"], days))
            rows = cur.fetchall()
        conn.close()

        rows = list(reversed(rows))
        df   = pd.DataFrame(rows)

        # ✅ run_backtest 4개 반환값 모두 언패킹
        if strategy == "golden_cross":
            df = strategy_golden_cross(df)
            total_profit, trades, win_rate, trade_count = run_backtest(df)
            result = {
                "success":     True,
                "strategy":    "golden_cross",
                "labels":      [str(r["date"]) for r in rows],
                "close":       [float(r["close_price"]) for r in rows],
                "ma_short":    [nan_to_none(v) for v in df["MA_short"].tolist()],
                "ma_long":     [nan_to_none(v) for v in df["MA_long"].tolist()],
                "backtest":    trades,
                "total_profit": total_profit,
                "win_rate":    win_rate,
                "trade_count": trade_count
            }

        elif strategy == "breakout":
            df = strategy_breakout(df)
            total_profit, trades, win_rate, trade_count = run_backtest(df)
            result = {
                "success":     True,
                "strategy":    "breakout",
                "labels":      [str(r["date"]) for r in rows],
                "close":       [float(r["close_price"]) for r in rows],
                "high20":      [nan_to_none(v) for v in df["High20"].tolist()],
                "ma20":        [nan_to_none(v) for v in df["MA20"].tolist()],
                "backtest":    trades,
                "total_profit": total_profit,
                "win_rate":    win_rate,
                "trade_count": trade_count
            }

        else:
            return jsonify({"success": False, "message": "알 수 없는 전략"})

        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})