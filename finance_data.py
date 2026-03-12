def get_defense_data(conn):
    """
    이 함수는 DB에서 K-방산 종목의 최신 데이터를 가져와서 
    화면에 보여주기 좋게 가공하는 '데이터 공장' 역할을 합니다.
    """
    results = []

    with conn.cursor() as cursor:
        # [파트 1] SQL 쿼리 작성 (데이터 골라내기)
        # 설명: stocks 테이블과 stock_details 테이블을 합쳐서(JOIN)
        # 방산 종목(is_defense = 1)인 데이터만 골라서 가져옵니다. [cite: 4]
        sql = """
        SELECT
            s.ticker,
            s.name_kr,
            d.current_price,
            d.change_rate,
            d.trading_value
        FROM stocks s
        JOIN stock_details d
        ON s.id = d.stock_id
        WHERE s.is_defense = 1
        """

        cursor.execute(sql)
        rows = cursor.fetchall()

        # [파트 2] 데이터 가공 (보기 편하게 만들기)
        # 설명: DB에서 가져온 날것의 데이터를 우리 웹사이트 형식에 맞게 변환합니다.
        for row in rows:
            price = float(row["current_price"])
            trading_value = int(row["trading_value"])

            results.append({
                "ticker": row["ticker"],
                "name": row["name_kr"],
                "price": int(price), # 소수점 떼고 정수로 변환
                "change": float(row["change_rate"]),
                # 거래대금을 '원' 단위에서 '억원' 단위로 변경하고 소수점 첫째자리까지 반올림합니다.
                "value": round(trading_value / 100000000, 1) 
            })

    # [파트 3] 정렬 작업 (거래대금 순)
    # 설명: 사용자에게 보여줄 때 거래대금이 가장 높은 종목이 위로 오도록 내림차순 정렬합니다.
    results = sorted(results, key=lambda x: x["value"], reverse=True)

    # [파트 4] 최종 결과 반환
    # 설명: 가공과 정렬이 끝난 데이터를 stocks.py로 넘겨줍니다.
    return results