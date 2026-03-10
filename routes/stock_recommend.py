import os
from flask import Blueprint, render_template, request, redirect, url_for
import pymysql
from dotenv import load_dotenv
from database import get_conn

# Blueprint 정의 (이름: stock_recommend)
stock_recommend_bp = Blueprint('stock_recommend', __name__)

# 1. AI 분석 상세 및 투자 입력 페이지
@stock_recommend_bp.route("/stock_analysis/<int:stock_id>")
def stock_analysis(stock_id):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT n.title, na.ai_score, na.ai_summary 
                FROM news_analysis na
                JOIN news n ON na.news_id = n.id
                WHERE na.stock_id = %s
                ORDER BY n.published_at DESC LIMIT 3
            """
            cursor.execute(sql, (stock_id,))
            news_list = cursor.fetchall()

            score, status, color_class = 0, "데이터 없음", "bg-secondary"
            if news_list:
                score = int(news_list[0]['ai_score'])
                if score >= 65:
                    status, color_class = "긍정", "bg-success"
                elif score >= 35:
                    status, color_class = "보통", "bg-warning"
                else:
                    status, color_class = "부정", "bg-danger"

            return render_template("stock_analysis.html", 
                                   news_list=news_list, 
                                   score=score, 
                                   status=status, 
                                   color_class=color_class,
                                   stock_id=stock_id)
    finally:
        conn.close()

# 2. 투자 실행 처리 (이 함수가 있어야 BuildError가 해결됩니다!)
@stock_recommend_bp.route("/invest/execute", methods=['POST'])
def execute_trade():
    stock_id = request.form.get('stock_id')
    quantity = int(request.form.get('quantity'))
    strategy = request.form.get('strategy')
    user_id = 1  # 임시 사용자 ID

    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # 주가 확인
            cursor.execute("SELECT current_price FROM stock_details WHERE stock_id = %s", (stock_id,))
            price_res = cursor.fetchone()
            if not price_res:
                return "<script>alert('가격을 찾을 수 없습니다.'); history.back();</script>"
            
            price = price_res['current_price']
            total_amount = price * quantity

            # 잔액 확인
            cursor.execute("SELECT id, current_balance FROM mock_accounts WHERE user_id = %s", (user_id,))
            account = cursor.fetchone()
            if not account or account['current_balance'] < total_amount:
                return "<script>alert('잔액이 부족합니다!'); history.back();</script>"

            # 매수 처리 (잔액 차감 및 거래 기록)
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