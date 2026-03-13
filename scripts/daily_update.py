"""
scripts/daily_update.py — 매일 1회 실행하는 DB 통합 업데이트 스크립트

실행 방법 (프로젝트 루트에서):
  python scripts/daily_update.py

자동 실행 (Windows 작업 스케줄러):
  - 작업 스케줄러 > 새 작업 > 트리거: 매일 오전 9:00
  - 동작: python C:\\...\\defense-stock-dashboard\\scripts\\daily_update.py

포함 작업:
  1. 전체 종목 주가 업데이트  (scripts/update_stock_price.py)
  2. ETF 시세 업데이트        (scripts/update_etf_price.py)
  3. 뉴스 수집 및 저장        (services/news_service.py)
  4. 업종 AI 분석 업데이트    (services/ai_analysis.py)
  5. 전략 기반 자동 매매 실행 (services/autotrade.py)
  6. 전종목 AI 분석 배치      (services/ai_analysis.py)
"""

import sys
import traceback
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가 (scripts/ 하위에서 실행 시 필요)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
    from scripts.update_stock_price import update_all_stocks
    update_all_stocks()


def run_etf_update():
    from scripts.update_etf_price import update_etf_history
    update_etf_history(463250)   # KODEX 방산 ETF 코드


def run_news_update():
    from services.news_service import update_news
    update_news()


def run_news_analysis():
    from services.ai_analysis import update_sector_ai_analysis
    update_sector_ai_analysis()


def run_stock_ai_batch():
    from services.ai_analysis import update_all_stocks_ai_analysis
    update_all_stocks_ai_analysis()


def run_auto_trade():
    from services.autotrade import run_auto_trade as _run
    _run()


if __name__ == "__main__":
    log("=" * 50)
    log("일일 DB 업데이트 시작")
    log("=" * 50)

    results = {
        "주가 업데이트":      step("주가 업데이트  (stock_price_history / stock_details)", run_stock_update),
        "ETF 업데이트":       step("ETF 업데이트   (etf_price_history)", run_etf_update),
        "뉴스 업데이트":      step("뉴스 수집/저장 (news)", run_news_update),
        "뉴스 분석 업데이트": step("뉴스 AI 분석  (stock_news)", run_news_analysis),
        "자동 매매 실행":     step("전략 기반 자동 매매 (autotrade)", run_auto_trade),
        "전종목 AI 분석":     step("전 종목 뉴스 수집 및 AI 분석", run_stock_ai_batch),
    }

    log("=" * 50)
    log("업데이트 결과 요약")
    for name, ok in results.items():
        status = "성공" if ok else "실패"
        log(f"  [{status}]  {name}")

    failed = [k for k, v in results.items() if not v]
    if failed:
        log(f"  {len(failed)}개 항목 실패 — 로그를 확인하세요", level="WARN")
        sys.exit(1)
    else:
        log("모든 업데이트 성공!")
        sys.exit(0)
