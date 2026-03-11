"""
daily_update.py — 매일 1회 실행하는 DB 통합 업데이트 스크립트

실행 방법:
  python daily_update.py

자동 실행 (Windows 작업 스케줄러):
  - 작업 스케줄러 > 새 작업 > 트리거: 매일 오전 9:00
  - 동작: python C:\\...\\defense-stock-dashboard\\daily_update.py

포함 작업:
  1. 전체 종목 주가 업데이트  (update_stock_price.py)
  2. ETF 시세 업데이트        (update_etf_price.py)
  3. 뉴스 수집 및 저장        (news_data.py)
"""

import sys
import traceback
from datetime import datetime


def log(msg, level="INFO"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [{level}] {msg}")


def step(title, fn):
    """단계 실행 + 성공/실패 로그"""
    log(f"▶ {title} 시작")
    try:
        fn()
        log(f"✅ {title} 완료")
        return True
    except Exception as e:
        log(f"❌ {title} 실패: {e}", level="ERROR")
        traceback.print_exc()
        return False


def run_stock_update():
    from update_stock_price import update_all_stocks
    update_all_stocks()


def run_etf_update():
    from update_etf_price import update_etf_history
    update_etf_history(463250)   # KODEX 방산 ETF 코드


def run_news_update():
    from news_data import update_news
    update_news()

def run_news_analysis():
    from routes.stock_detail import update_sector_ai_analysis
    update_sector_ai_analysis()

if __name__ == "__main__":
    log("=" * 50)
    log("📅 일일 DB 업데이트 시작")
    log("=" * 50)

    results = {
        "주가 업데이트":  step("주가 업데이트  (stock_price_history / stock_details)", run_stock_update),
        "ETF 업데이트":   step("ETF 업데이트   (etf_price_history)", run_etf_update),
        "뉴스 업데이트":  step("뉴스 수집/저장 (news)", run_news_update),
        "뉴스 분석 업데이트":  step("뉴스 수집/저장 (stock_news)", run_news_analysis),
    }

    log("=" * 50)
    log("📊 업데이트 결과 요약")
    for name, ok in results.items():
        status = "✅ 성공" if ok else "❌ 실패"
        log(f"  {status}  {name}")

    failed = [k for k, v in results.items() if not v]
    if failed:
        log(f"⚠️  {len(failed)}개 항목 실패 — 로그를 확인하세요", level="WARN")
        sys.exit(1)
    else:
        log("🎉 모든 업데이트 성공!")
        sys.exit(0)