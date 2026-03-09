import yfinance as yf
import pandas as pd

# 방산주 목록 관리 [cite: 4]
DEFENSE_MAP = {
    "현대로템": "064350.KS",
    "한화에어로스페이스": "012450.KS",
    "LIG넥스원": "079550.KS",
    "한화시스템": "272210.KS",
    "한국항공우주": "047810.KS",
    "STX엔진": "077970.KS",
    "한일단조" : "024740.KQ",
    "한화시스템": "272210.KS",
    "루멘스": "038060.KQ",
    "미래아이앤지": "007120.KS",
    "우리기술": "032820.KQ",
    "파이버프로": "368770.KQ",
    "비유테크놀러지": "230980.KQ",
    "HD한국조선해양": "009540.KS",
    "SNT다이내믹스": "003570.KS",
    "풍산홀딩스": "005810.KS",
    "대양전기공업": "108380.KQ",
    "한컴라이프케어": "372910.KS",
    "국영지앤엠": "006050.KQ",
    "이엠코리아": "095190.KQ",
    "한화오션": "042660.KS",
    "퍼스텍": "010820.KS",
    "코콤": "015710.KQ",
    "스페코": "013810.KQ",
    "YTN": "040300.KQ",
    "혜인": "003010.KS",
    "켄코아에어로스페이스": "274090.KQ",
    "포메탈": "119500.KQ",
    "기산텔레콤": "035460.KQ",
    "제노코": "361390.KQ",
    "SNT모티브": "064960.KS",
    "에스코넥": "096630.KQ",
    "한국항공우주": "047810.KS",
    "이지트로닉스": "377330.KQ",
    "웰크론": "065950.KQ",
    "웨이브일렉트로": "095270.KQ",
    "비츠로테크": "042370.KQ",
    "풍산": "103140.KS",
    "아이티센엔텍": "010280.KQ",
    "솔디펜스": "215090.KQ",
    "한화": "000880.KS",
    "휴니드": "005870.KS",
    "덕산하이메탈": "077360.KQ",
    "빅텍": "065450.KQ",
    "기아": "000270.KS",
    "에이스테크": "088800.KQ",
    "대한항공": "003490.KS",
    "아이쓰리시스템": "214430.KQ",
    "현대위아": "011210.KS",
    "DMS": "068790.KQ"
}

def get_defense_data():
    """yfinance를 통해 방산주 데이터를 수집하고 정렬하여 반환합니다. [cite: 91, 94]"""
    results = []
    for name, ticker in DEFENSE_MAP.items():
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="2d")
            if not df.empty and len(df) >= 2:
                current_price = df['Close'].iloc[-1]
                prev_price = df['Close'].iloc[-2]
                volume = df['Volume'].iloc[-1]
                
                trading_value = current_price * volume
                change_rate = ((current_price - prev_price) / prev_price) * 100
                
                results.append({
                    "name": name,
                    "ticker": ticker,
                    "price": int(current_price),
                    "change": round(change_rate, 2),
                    "value": round(trading_value / 100000000, 1) # 미리 '억' 단위 숫자로 변환
                })
        except Exception as e:
            print(f"{name} 데이터 수집 실패: {e}")

    final_df = pd.DataFrame(results)
    if not final_df.empty:
        # 거래대금 순으로 정렬 [cite: 85]
        final_df = final_df.sort_values(by='value', ascending=False)
        return final_df.to_dict('records')
    return []