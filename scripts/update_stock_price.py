import os
import requests
from database import get_conn
from dotenv import load_dotenv

load_dotenv()

SERVICE_KEY = os.getenv("SERVICE_KEY")

# 금융위원회 주식시세정보 AIP 엔드포인트
BASE_URL = "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"

# 데이터 정제 파트
# 데이터를 int타입으로 정제하는 함수
def safe_int(value, default=0):
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    value = str(value).replace(",", "").strip()
    if value == "":
        return default
    try:
        return int(float(value))
    except ValueError:
        return default

# 최신 정보 업데이트(stock_details 테이블)
# 가장 최신 날짜 데이터를 바탕으로 현재 상태를 업데이트
# API에서 제공하는 데이터 상 가장 최신 데이터는 전일 데이터입니다.
# 대시보드와 종목 리스트에서 가장 최신 데이터를 보여줄 때 사용
def upsert_stock_details(conn, stock_id, latest_row, prev_close=None):
    current_price = latest_row["close"]
    open_price = latest_row["open"]
    high_price = latest_row["high"]
    low_price = latest_row["low"]
    volume = latest_row["volume"]
    trading_value = latest_row["trading_value"]

    change_amount = 0
    change_rate = 0.00

    if prev_close and prev_close > 0:   # 전전일 데이터가 있고, 0보다 크면
        change_amount = current_price - prev_close  # 변화량 전일 데이터 - 전전일 데이터
        change_rate = round((change_amount / prev_close) * 100, 2)  # 등락율 계산

    sql = """
    INSERT INTO stock_details
    (
        stock_id,
        current_price,
        change_amount, 
        change_rate,
        volume,
        trading_value,
        high_price,
        low_price,
        open_price,
        updated_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    ON DUPLICATE KEY UPDATE
        current_price = VALUES(current_price),
        change_amount = VALUES(change_amount),
        change_rate = VALUES(change_rate),
        volume = VALUES(volume),
        trading_value = VALUES(trading_value),
        high_price = VALUES(high_price),
        low_price = VALUES(low_price),
        open_price = VALUES(open_price),
        updated_at = NOW()
    """

    with conn.cursor() as cursor:
        cursor.execute(sql, (
            stock_id,
            current_price,
            change_amount,
            change_rate,
            volume,
            trading_value,
            high_price,
            low_price,
            open_price
        ))

# 시세 이력 저장 파트(stock_price_history 테이블)
# 차트 생성 시 필요한 시세 정보 이력을 저장
def upsert_stock_price_history(conn, stock_id, row):
    sql = """
    INSERT INTO stock_price_history
    (stock_id, price_date, open_price, high_price, low_price, close_price, volume)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        open_price = VALUES(open_price),
        high_price = VALUES(high_price),
        low_price = VALUES(low_price),
        close_price = VALUES(close_price),
        volume = VALUES(volume)
    """

    with conn.cursor() as cursor:
        cursor.execute(sql, (
            stock_id,
            row["date"],
            row["open"],
            row["high"],
            row["low"],
            row["close"],
            row["volume"]
        ))

# 데이터 수집 파트
# API로 주식 시세 정보 데이터를 요청하여 json 형태로 받아옴
def fetch_stock_prices(stock_code, num_of_rows=120):
    params = {
        "serviceKey": SERVICE_KEY,
        "numOfRows": num_of_rows,
        "pageNo": 1,
        "resultType": "json",
        "likeSrtnCd": stock_code    # 주식 종목 단축 코드
    }
    # API로 데이터 요청
    response = requests.get(BASE_URL, params=params, timeout=20)
    # 응답 상태 코드 확인
    response.raise_for_status()

    data = response.json()

    items = (
        data.get("response", {})
            .get("body", {})
            .get("items", {})
            .get("item", [])
    )

    if not isinstance(items, list):
        items = [items] if items else []

    chart_data = []

    for row in items:
        bas_dt = row.get("basDt") or row.get("BAS_DT")          # 기준 일자 예시) 20220919
        open_price = row.get("mkp") or row.get("MKP")           # 시가
        high_price = row.get("hipr") or row.get("HIPR")         # 고가
        low_price = row.get("lopr") or row.get("LOPR")          # 저가
        close_price = row.get("clpr") or row.get("CLPR")        # 종가
        volume = row.get("trqu") or row.get("TRQU")             # 거래량
        trading_value = row.get("trPrc") or row.get("TRPRC")    # 거래대금

        if not bas_dt:
            continue

        bas_dt = str(bas_dt).strip()

        # YYYYMMDD -> YYYY-MM-DD
        if len(bas_dt) == 8 and bas_dt.isdigit():
            formatted_date = f"{bas_dt[:4]}-{bas_dt[4:6]}-{bas_dt[6:]}"
        else:
            formatted_date = bas_dt

        chart_data.append({
            "date": formatted_date,
            "open": safe_int(open_price),
            "high": safe_int(high_price),
            "low": safe_int(low_price),
            "close": safe_int(close_price),
            "volume": safe_int(volume),
            "trading_value": safe_int(trading_value)
        })
    
    chart_data.sort(key=lambda x: x["date"])
    return chart_data

# 개별 종목 처리
# 한 종목에 대해 120일 치 시세를 가져와 이력을 저장
# 마지막 날짜 데이터를 요약 정보에 반영
def update_one_stock(conn, stock):
    stock_id = stock["id"]
    ticker = stock["ticker"]
    name_kr = stock["name_kr"]

    print(f"[INFO] {name_kr} ({ticker}) 조회 시작")

    price_rows = fetch_stock_prices(ticker, num_of_rows=120)

    if not price_rows:
        print(f"[WARN] {name_kr} ({ticker}) 데이터 없음")
        return

    for row in price_rows:
        upsert_stock_price_history(conn, stock_id, row)

    latest_row = price_rows[-1]  # 가장 최근 데이터(전일 데이터) 저장
    prev_close = price_rows[-2]["close"] if len(price_rows) >= 2 else None  # 전전일 종가

    upsert_stock_details(conn, stock_id, latest_row, prev_close)

    print(f"[OK] {name_kr} ({ticker}) 저장 완료 - latest: {latest_row['date']} / {latest_row['close']}")

# DB 조회 파트
# 현재 stocks 테이블에 등록된 모든 주식의 종목 코드 목록을 가져옴
# 이 목록을 바탕으로 모든 종목의 시세를 업데이트
def get_all_stocks(conn):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id, ticker, name_kr
            FROM stocks
            ORDER BY id
        """)
        return cursor.fetchall()

# 메인 실행 제어 파트
# 1. DB에서 모든 종목을 읽어옴
# 2. 종목별 업데이트 실행
# 3. 성공 시 커밋, 에러 발생 시 rollback
def update_all_stocks():
    conn = None
    try:
        conn = get_conn()

        stocks = get_all_stocks(conn)

        if not stocks:
            print("[WARN] stocks 테이블에 종목 데이터가 없습니다.")
            return

        for stock in stocks:
            try:
                update_one_stock(conn, stock)
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"[ERROR] {stock['name_kr']} ({stock['ticker']}) 실패: {e}")

        print("[DONE] 전체 종목 업데이트 완료")

    except Exception as e:
        print(f"[FATAL] 실행 실패: {e}")

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    update_all_stocks()