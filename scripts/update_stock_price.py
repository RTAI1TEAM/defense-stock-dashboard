import os
import requests
from database import get_conn
from dotenv import load_dotenv

load_dotenv()

SERVICE_KEY = os.getenv("SERVICE_KEY")


# Flask 코드와 동일한 엔드포인트 형식
BASE_URL = "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"


# [데이터 정제 파트]
def safe_int(value, default=0):
    """
    '1,234' 같은 문자열도 int로 안전하게 변환
    """
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

# [데이터 수집 파트]
def fetch_stock_prices(stock_code, num_of_rows=120):
    """
    주식 시세정보 API를 호출합니다. 
    ETF와 달리 거래대금(trPrc) 정보도 함께 수집하는 것이 특징입니다.
    """
    params = {
        "serviceKey": SERVICE_KEY,
        "numOfRows": num_of_rows,
        "pageNo": 1,
        "resultType": "json",
        # 네 Flask 코드 기준
        "likeSrtnCd": stock_code
    }

    response = requests.get(BASE_URL, params=params, timeout=20)
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
        bas_dt = row.get("basDt") or row.get("BAS_DT")
        open_price = row.get("mkp") or row.get("MKP")
        high_price = row.get("hipr") or row.get("HIPR")
        low_price = row.get("lopr") or row.get("LOPR")
        close_price = row.get("clpr") or row.get("CLPR")
        volume = row.get("trqu") or row.get("TRQU")
        trading_value = row.get("trPrc") or row.get("TRPRC")

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

# [DB 조회 파트]
def get_all_stocks(conn):
    """
    현재 DB(stocks 테이블)에 등록된 모든 주식의 티커(종목코드) 목록을 가져옵니다.
    이 목록을 바탕으로 모든 종목의 시세를 차례대로 업데이트하게 됩니다.
    """
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id, ticker, name_kr
            FROM stocks
            ORDER BY id
        """)
        return cursor.fetchall()

# [시세 이력 저장 파트]
def upsert_stock_price_history(conn, stock_id, row):
    """
    개별 날짜별 시세(일봉 데이터)를 stock_price_history 테이블에 저장하거나 갱신합니다.
    """
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

# [최신 정보 요약 파트]
def upsert_stock_details(conn, stock_id, latest_row, prev_close=None):
    """
    가장 최신 날짜의 데이터를 바탕으로 '현재 상태'를 업데이트합니다.
    - 현재가, 대비(change_amount), 등락률(change_rate)을 계산하여 저장합니다.
    - 프로젝트의 대시보드나 리스트에서 실시간성 정보를 보여줄 때 사용됩니다.
    """
    current_price = latest_row["close"]
    open_price = latest_row["open"]
    high_price = latest_row["high"]
    low_price = latest_row["low"]
    volume = latest_row["volume"]
    trading_value = latest_row["trading_value"]

    change_amount = 0
    change_rate = 0.00

    if prev_close and prev_close > 0:
        change_amount = current_price - prev_close
        change_rate = round((change_amount / prev_close) * 100, 2)

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

# [개별 종목 처리 로직]
def update_one_stock(conn, stock):
    """
    한 종목에 대해 120일 치 시세를 가져와 이력을 저장하고, 
    마지막 날짜 데이터를 요약 정보(details)에 반영하는 일련의 과정을 수행합니다.
    """
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

    latest_row = price_rows[-1]
    prev_close = price_rows[-2]["close"] if len(price_rows) >= 2 else None

    upsert_stock_details(conn, stock_id, latest_row, prev_close)

    print(f"[OK] {name_kr} ({ticker}) 저장 완료 - latest: {latest_row['date']} / {latest_row['close']}")

# [메인 실행 제어 파트]
def update_all_stocks():
    """
    전체 프로세스의 컨트롤러입니다.
    1. DB에서 모든 종목을 읽어옴 -> 2. 반복문을 돌며 종목별 업데이트 실행 
    -> 3. 성공 시 Commit, 에러 발생 시 Rollback 처리를 수행합니다.
    """
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