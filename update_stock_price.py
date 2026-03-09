import os
import requests
import pymysql
from dotenv import load_dotenv

load_dotenv()

SERVICE_KEY = os.getenv("SERVICE_KEY")

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = int(os.getenv("DB_PORT", 3306))

# Flask 코드와 동일한 엔드포인트 형식
BASE_URL = "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo"


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


def get_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )


def fetch_stock_prices(stock_code, num_of_rows=120):
    """
    금융위원회_주식시세정보 API 호출 후
    [{date, open, high, low, close, volume}] 형태로 반환
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
        volume = row.get("accTrdvol") or row.get("ACC_TRDVOL")

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
        })

    chart_data.sort(key=lambda x: x["date"])
    return chart_data


def get_all_stocks(conn):
    """
    DB에 저장된 종목 목록 조회
    ticker 기준으로 API 호출
    """
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id, ticker, name_kr
            FROM stocks
            ORDER BY id
        """)
        return cursor.fetchall()


def upsert_stock_price_history(conn, stock_id, row):
    """
    stock_price_history 저장/갱신
    (stock_id, price_date) UNIQUE 전제
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


def upsert_stock_details(conn, stock_id, latest_row, prev_close=None):
    """
    stock_details 최신값 저장/갱신
    stock_id UNIQUE 전제
    """
    current_price = latest_row["close"]
    open_price = latest_row["open"]
    high_price = latest_row["high"]
    low_price = latest_row["low"]
    volume = latest_row["volume"]

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
        high_price,
        low_price,
        open_price,
        updated_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
    ON DUPLICATE KEY UPDATE
        current_price = VALUES(current_price),
        change_amount = VALUES(change_amount),
        change_rate = VALUES(change_rate),
        volume = VALUES(volume),
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
            high_price,
            low_price,
            open_price
        ))


def update_one_stock(conn, stock):
    """
    종목 1개 업데이트
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


def update_all_stocks():
    conn = None
    try:
        conn = get_connection()

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