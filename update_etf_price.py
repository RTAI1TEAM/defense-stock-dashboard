import os
import requests
import pymysql
from dotenv import load_dotenv

load_dotenv() # .env 파일에서 환경 변수(DB 접속 정보, API 키)를 로드합니다.

SERVICE_KEY = os.getenv("SERVICE_KEY") # 공공데이터 API 인증키

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = int(os.getenv("DB_PORT", 3306))

# [API 엔드포인트]
# 금융위원회 ETF 시세정보 API 주소입니다.
# Flask 코드와 동일한 엔드포인트 형식
BASE_URL = "https://apis.data.go.kr/1160100/service/GetSecuritiesProductInfoService/getETFPriceInfo"


def safe_int(value, default=0):
    """
    [데이터 정제 파트]
    API에서 제공하는 '1,234' 같은 콤마 포함 문자열이나 빈 값을 
    안전하게 정수(int) 형태로 변환하여 데이터 오류를 방지합니다.
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
    """
    [DB 연결 파트]
    PyMySQL을 사용해 데이터베이스에 접속 설정을 생성합니다.
    """
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


def fetch_etf_prices(eft_code, num_of_rows=120):
    """
    [데이터 수집 및 가공 파트]
    1. requests를 통해 공공데이터 API에 ETF 시세를 요청합니다.
    2. 응답받은 JSON 데이터에서 날짜, 시가, 고가, 저가, 종가, 거래량을 추출합니다.
    3. 'YYYYMMDD' 형식을 'YYYY-MM-DD'로 변환하여 리스트로 반환합니다.
    """
    params = {
        "serviceKey": SERVICE_KEY,
        "numOfRows": num_of_rows,
        "pageNo": 1,
        "resultType": "json",
        "likeSrtnCd": eft_code
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
    # print(type(chart_data))
    return chart_data


def update_etf_history(eft_id):
    """
    [DB 반영 파트]
    1. fetch_etf_prices에서 가져온 데이터를 루프 돌며 DB에 삽입합니다.
    2. 'ON DUPLICATE KEY UPDATE' 구문을 사용하여, 
       이미 해당 날짜의 데이터가 있으면 새로운 값으로 업데이트(갱신)합니다.
    """
    conn = get_connection()
    rows = fetch_etf_prices(463250)
    sql = """
    INSERT INTO etf_price_history
    (etf_id, price_date, open_price, high_price, low_price, close_price, volume)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        open_price = VALUES(open_price),
        high_price = VALUES(high_price),
        low_price = VALUES(low_price),
        close_price = VALUES(close_price),
        volume = VALUES(volume)
    """
    try:
        with conn.cursor() as cursor:
            for row in rows:
                print(row)
                cursor.execute(sql, (
                    1,
                    row["date"],
                    row["open"],
                    row["high"],
                    row["low"],
                    row["close"],
                    row["volume"]
                ))
        print("입력 완료")
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    update_etf_history(463250)