import os
import re
import html
import requests
import pymysql
from flask import Blueprint, render_template, request, redirect, url_for
from dotenv import load_dotenv

load_dotenv()

stock_recommend_bp = Blueprint('stock_recommend', __name__)

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
API_URL = "https://openapi.naver.com/v1/search/news.json"

def get_db_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        db=os.getenv('DB_NAME'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def strip_html(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text).strip()

def get_live_stock_news(stock_name):
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {
        "query": f"{stock_name} 방산", 
        "display": 3,
        "sort": "sim"
    }
    try:
        resp = requests.get(API_URL, headers=headers, params=params, timeout=5)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        
        for item in items:
            item["title_clean"] = strip_html(item.get("title", ""))
            item["description_clean"] = strip_html(item.get("description", ""))
        return items
    except Exception as e:
        print(f"뉴스 API 호출 중 에러 발생: {e}")
        return []

# --- 수정된 부분: 함수명과 렌더링 템플릿명 변경 ---
@stock_recommend_bp.route("/stock_detail/<int:stock_id>")
def stock_detail(stock_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 수정된 부분: 테이블명 'stocks', 컬럼명 'name_kr'
            cursor.execute("SELECT name_kr FROM stocks WHERE id = %s", (stock_id,))
            stock_info = cursor.fetchone()
            
            # DB 결과에서 'name_kr'을 꺼내옵니다.
            stock_name = stock_info['name_kr'] if stock_info else "방산주"

            # 2. 해당 종목의 최신 AI 점수 가져오기 (이 테이블 컬럼명도 확인 필요)
            cursor.execute("""
                SELECT ai_score FROM news_analysis 
                WHERE stock_id = %s 
                ORDER BY id DESC LIMIT 1
            """, (stock_id,))
            score_res = cursor.fetchone()

            score, status, color_class = 0, "데이터 없음", "bg-secondary"
            if score_res:
                score = int(score_res['ai_score'])
                if score >= 65:
                    status, color_class = "긍정", "bg-success"
                elif score >= 35:
                    status, color_class = "보통", "bg-warning"
                else:
                    status, color_class = "부정", "bg-danger"

            # 3. 실시간 뉴스 크롤링 실행
            live_news = get_live_stock_news(stock_name)

        # [중요] 조립된 메인 파일인 'stock_detail.html'을 렌더링합니다.
        return render_template("stock_detail.html", 
                               stock_name=stock_name,
                               news_list=live_news, 
                               score=score, 
                               status=status, 
                               color_class=color_class,
                               stock_id=stock_id,
                               ai_strategy=f"{stock_name} 맞춤형 트렌드 대응 전략")
    finally:
        conn.close()

# 2. 투자 실행 처리 (기존과 동일)
@stock_recommend_bp.route("/invest/execute", methods=['POST'])
def execute_trade():
    stock_id = request.form.get('stock_id')
    quantity = int(request.form.get('quantity') or 0)
    strategy = request.form.get('strategy')
    user_id = 1  

    if quantity <= 0:
        return "<script>alert('주수를 입력해주세요.'); history.back();</script>"

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_price FROM stock_details WHERE stock_id = %s", (stock_id,))
            price_res = cursor.fetchone()
            if not price_res:
                return "<script>alert('가격을 찾을 수 없습니다.'); history.back();</script>"
            
            price = price_res['current_price']
            total_amount = price * quantity

            cursor.execute("SELECT id, current_balance FROM mock_accounts WHERE user_id = %s", (user_id,))
            account = cursor.fetchone()
            if not account or account['current_balance'] < total_amount:
                return "<script>alert('잔액이 부족합니다!'); history.back();</script>"

            cursor.execute("UPDATE mock_accounts SET current_balance = current_balance - %s WHERE id = %s", (total_amount, account['id']))
            cursor.execute("""
                INSERT INTO trades (user_id, account_id, stock_id, trade_type, price, quantity, total_amount, strategy)
                VALUES (%s, %s, %s, 'BUY', %s, %s, %s, %s)
            """, (user_id, account['id'], stock_id, price, quantity, total_amount, strategy))
            
            conn.commit()
        return "<script>alert('모의투자가 완료되었습니다!'); location.href='/';</script>"
    except Exception as e:
        conn.rollback()
        return f"에러 발생: {str(e)}"
    finally:
        conn.close()