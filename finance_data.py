def get_defense_data(conn):

    results = []

    with conn.cursor() as cursor:

        sql = """
        SELECT
            s.ticker,
            s.name_kr,
            d.current_price,
            d.change_rate,
            d.volume
        FROM stocks s
        JOIN stock_details d
        ON s.id = d.stock_id
        WHERE s.is_defense = 1
        """

        cursor.execute(sql)
        rows = cursor.fetchall()

        for row in rows:

            price = float(row["current_price"])
            volume = int(row["volume"])

            trading_value = price * volume

            results.append({
                "ticker":row["ticker"],
                "name": row["name_kr"],
                "price": int(price),
                "change": float(row["change_rate"]),
                "value": round(trading_value / 100000000, 1)
            })

    results = sorted(results, key=lambda x: x["value"], reverse=True)

    return results