import os
import re
import html
import json
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from database import get_conn
from flask import Blueprint, redirect, render_template, request, session, url_for, jsonify

stock_detail_bp = Blueprint('stock_detail', __name__)

# --- API 설정 ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(model_name='gemini-2.5-flash') # flash로 변경하면 잘 나옵니다.


NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

# --- 유틸리티 함수 ---
def strip_html(text):
    """HTML 태그 제거 및 특수문자 변환"""
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text).strip()

def get_live_analysis(stock_name):
    """실시간 뉴스 3개 검색 및 Gemini AI 분석"""
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    
    # 검색 정확도를 높이기 위해 '주가 전망' 키워드 추가
    search_query = f"{stock_name} 주가 전망"
    params = {"query": search_query, "display": 3, "sort": "sim"}
    
    news_list = []
    try:
        resp = requests.get("https://openapi.naver.com/v1/search/news.json", headers=headers, params=params, timeout=5)
        
        if resp.status_code != 200:
            print(f"네이버 API 에러: {resp.status_code}")
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

    # 뉴스가 없을 경우 처리
    if not news_list:
        return [], 50, f"'{stock_name}' 관련 최신 뉴스가 없습니다.", "데이터 부족", "bg-secondary"

    # Gemini AI 분석 프롬프트
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
        # 답변에서 JSON 외의 마크다운 태그(```json 등) 제거
        clean_json = re.sub(r'```(?:json)?|```', '', response.text).strip()
        data = json.loads(clean_json)
        
        score = int(data.get("score", 50))
        ai_news = data.get("ai_news", "시장 관망 후 진입을 추천합니다.")
        
        # 점수에 따른 UI 상태 결정
        if score >= 70: status, color = "긍정", "bg-success"
        elif score >= 40: status, color = "보통", "bg-warning"
        else: status, color = "부정", "bg-danger"
        
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
            cursor.execute(sql,(ticker,))
            return cursor.fetchone()
    finally:
        conn.close()

def get_stock_chart_data(stock_id):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            sql = """
            SELECT price_date, close_price
            FROM stock_price_history
            WHERE stock_id = %s
            ORDER BY price_date
            """
            cursor.execute(sql, (stock_id,))
            rows = cursor.fetchall()

            labels = [row["price_date"].strftime("%Y-%m-%d") for row in rows]
            values = [float(row["close_price"]) for row in rows]

            return labels, values
    finally:
        conn.close()

@stock_detail_bp.route("/chart/<ticker>")
def show_stock_chart(ticker):
    if "nickname" not in session:
        return redirect(url_for("auth_bp.login_page"))
    
    stock = get_stock(ticker)
    chart_labels, chart_values = get_stock_chart_data(stock["id"])
    news_list, score, ai_news, status, color_class = get_live_analysis(stock["name_kr"])

    return render_template(
        "stock_detail.html",
        stock=stock,
        chart_labels=chart_labels,
        chart_values=chart_values,
        news_list=news_list,
        score=score,
        ai_news=ai_news,
        status=status,
        color_class=color_class
    )


@stock_detail_bp.route("/invest/execute", methods=['POST'])
def execute_trade():
    if "nickname" not in session:
        return jsonify({"success": False, "message": "로그인이 필요합니다."})

    # 변수 초기화
    ticker_from_form = request.form.get('stock_id')
    quantity = int(request.form.get('quantity') or 0)
    ai_news = request.form.get('ai_news') or request.form.get('strategy') or "전략 없음"
    user_id = session.get('user_id', 1) 
    
    conn = None # ★ 중요: conn 변수를 미리 선언해서 NameError 방지

    if quantity <= 0:
        return jsonify({"success": False, "message": "구매할 수량을 입력하세요."})

    try:
        conn = get_conn() # 여기서 연결 시도
        with conn.cursor() as cursor:
            # 1. 시세 및 종목 ID 조회
            sql_stock = """
                SELECT s.id, h.close_price 
                FROM stocks s 
                JOIN stock_price_history h ON s.id = h.stock_id 
                WHERE s.ticker = %s 
                ORDER BY h.price_date DESC 
                LIMIT 1
            """
            cursor.execute(sql_stock, (ticker_from_form,))
            stock_res = cursor.fetchone()

            if not stock_res:
                return jsonify({"success": False, "message": "시세 정보를 찾을 수 없습니다."})
            
            real_db_stock_id = stock_res['id']
            price = float(stock_res['close_price'])
            total_cost = price * quantity

            # 2. 계좌 확인
            cursor.execute("SELECT id, current_balance FROM mock_accounts WHERE user_id = %s", (user_id,))
            account = cursor.fetchone()

            if not account:
                return jsonify({"success": False, "message": "계좌가 존재하지 않습니다."})

            if float(account['current_balance']) < total_cost:
                return jsonify({"success": False, "message": f"잔액 부족! (필요: {total_cost:,.0f}원)"})

            # 3. DB 업데이트 (잔액 차감 및 기록)
            cursor.execute("UPDATE mock_accounts SET current_balance = current_balance - %s WHERE id = %s", (total_cost, account['id']))
            
            sql_insert = """
                INSERT INTO trades (user_id, account_id, stock_id, trade_type, price, quantity, total_amount, strategy)
                VALUES (%s, %s, %s, 'BUY', %s, %s, %s, %s)
            """
            cursor.execute(sql_insert, (user_id, account['id'], real_db_stock_id, price, quantity, total_cost, ai_news))
            
            conn.commit()
            
            return jsonify({
                "success": True, 
                "message": f"{quantity}주 매수 완료! (총 {total_cost:,.0f}원)",
                "new_balance": float(account['current_balance']) - total_cost
            })

    except Exception as e:
        if conn: # conn이 정의되어 있을 때만 실행
            conn.rollback()
        return jsonify({"success": False, "message": f"거래 에러: {str(e)}"})
    finally:
        if conn: # conn이 정의되어 있을 때만 실행
            conn.close()