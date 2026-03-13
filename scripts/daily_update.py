# [파일 역할] 매일 1회 실행하여 데이터베이스와 비즈니스 로직을 최신 상태로 유지하는 통합 업데이트 스크립트
# - 주요 작업: 주가 및 ETF 시세 갱신, 뉴스 수집, AI 시장 분석, 자동 매매 시뮬레이션 실행
# - 실행 환경: 프로젝트 루트 디렉토리에서 실행 권장 (Windows 작업 스케줄러 연동 가능)

import sys
import traceback
from pathlib import Path
from datetime import datetime

# [경로 설정] 프로젝트 루트 디렉토리를 시스템 경로(sys.path)에 추가
# - scripts/ 하위 폴더에서 스크립트를 직접 실행할 때 상위 모듈(services 등)을 참조하기 위해 필요
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def log(msg, level="INFO"):
    # [유틸리티] 표준 출력에 시간대별 로그를 남기는 함수
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [{level}] {msg}")


def step(title, fn):
    # [실행 제어] 개별 작업 단계를 실행하고, 성공/실패 여부를 로그로 기록하는 헬퍼 함수
    # - title: 작업 명칭
    # - fn: 실행할 콜백 함수
    # - 반환값: 성공 시 True, 예외 발생 시 False
    log(f"▶ {title} 시작")
    try:
        fn()
        log(f"✅ {title} 완료")
        return True
    except Exception as e:
        log(f"❌ {title} 실패: {e}", level="ERROR")
        traceback.print_exc()
        return False


# ──────────────────────────────────────────────
# 개별 작업 래퍼 함수 (Task Wrappers)
# ──────────────────────────────────────────────

def run_stock_update():
    # [단계 1] 전 종목의 주가 데이터를 갱신
    from scripts.update_stock_price import update_all_stocks
    update_all_stocks()


def run_etf_update():
    # [단계 2] KODEX 방산 ETF(코드: 463250)의 시세 이력을 업데이트
    from scripts.update_etf_price import update_etf_history
    update_etf_history(463250)


def run_news_update():
    # [단계 3] 주요 경제 뉴스 및 종목 관련 뉴스를 수집하여 DB에 저장
    from services.news_service import update_news
    update_news()


def run_news_analysis():
    # [단계 4] 수집된 뉴스를 바탕으로 방산 업종 전반에 대한 AI 분석 수행 (Gemini 활용)
    from services.ai_analysis import update_sector_ai_analysis
    update_sector_ai_analysis()


def run_stock_ai_batch():
    # [단계 5] 개별 종목별로 수집된 뉴스를 분석하여 AI 투자 매력도 산출
    from services.ai_analysis import update_all_stocks_ai_analysis
    update_all_stocks_ai_analysis()


def run_auto_trade():
    # [단계 6] 업데이트된 데이터를 기반으로 사용자가 설정한 전략(골든크로스 등)에 따라 자동 매매 실행
    from services.autotrade import run_auto_trade as _run
    _run()


# ──────────────────────────────────────────────
# 메인 실행부 (Main Entry Point)
# ──────────────────────────────────────────────

if __name__ == "__main__":
    log("=" * 50)
    log("일일 DB 및 서비스 통합 업데이트 시작")
    log("=" * 50)

    # 정의된 순서에 따라 순차적으로 배치 작업 수행
    results = {
        "주가 업데이트":      step("주가 업데이트  (stock_price_history / stock_details)", run_stock_update),
        "ETF 업데이트":       step("ETF 업데이트   (etf_price_history)", run_etf_update),
        "뉴스 업데이트":      step("뉴스 수집/저장 (news)", run_news_update),
        "뉴스 분석 업데이트": step("업종 AI 분석   (sector_analysis)", run_news_analysis),
        "자동 매매 실행":     step("전략 기반 자동 매매 (autotrade)", run_auto_trade),
        "전종목 AI 분석":     step("전 종목 뉴스 분석 및 점수화 (stock_news)", run_stock_ai_batch),
    }

    log("=" * 50)
    log("전체 업데이트 결과 요약 보고")
    log("=" * 50)

    # 각 단계별 실행 결과 출력
    for name, ok in results.items():
        status = "성공" if ok else "실패"
        log(f"  [{status}]  {name}")

    # 하나라도 실패한 항목이 있는 경우 종료 코드 1 반환 (모니터링 도구 연동용)
    failed = [k for k, v in results.items() if not v]
    if failed:
        log(f"  {len(failed)}개 항목 실패 — 상세 로그를 확인하십시오.", level="WARN")
        sys.exit(1)
    else:
        log("모든 배치 업데이트가 성공적으로 완료되었습니다.")
        sys.exit(0)