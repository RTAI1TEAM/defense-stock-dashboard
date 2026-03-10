import pandas as pd

# 1. 5일/20일 이동평균선 골든크로스 전략
def strategy_golden_cross(data, short_window=5, long_window=20):
    df = data.copy()
    
    # DB에서 불러올 때 컬럼명이 close_price일 수 있으므로 통일 (또는 Close 사용)
    price_col = 'Close' if 'Close' in df.columns else 'close_price'

    df['MA_short'] = df[price_col].rolling(window=short_window).mean()
    df['MA_long'] = df[price_col].rolling(window=long_window).mean()
    df['Signal'] = ""
    
    # 골든크로스 (단기가 장기를 상향 돌파)
    buy_condition = (df['MA_short'].shift(1) < df['MA_long'].shift(1)) & (df['MA_short'] > df['MA_long'])
    # 데드크로스 (단기가 장기를 하향 돌파)
    sell_condition = (df['MA_short'].shift(1) > df['MA_long'].shift(1)) & (df['MA_short'] < df['MA_long'])
    
    df.loc[buy_condition, 'Signal'] = 'B'
    df.loc[sell_condition, 'Signal'] = 'S'
    return df

# 2. 20일 전고점 돌파 매매 전략
def strategy_breakout(data, window=20):
    df = data.copy()
    price_col = 'Close' if 'Close' in df.columns else 'close_price'

    df['High20'] = df[price_col].rolling(window=window).max().shift(1)
    df['MA20'] = df[price_col].rolling(window=window).mean()
    df['Signal'] = ""
    
    # 종가가 20일 최고가를 돌파
    buy_condition = df[price_col] > df['High20']
    # 종가가 20일 이동평균선 아래로 이탈 (손절/익절)
    sell_condition = df[price_col] < df['MA20']
    
    df.loc[buy_condition, 'Signal'] = 'B'
    df.loc[sell_condition, 'Signal'] = 'S'
    return df

# 3. [추가] 백테스팅 수익률 계산 함수
def run_backtest(df):
    """
    B(매수)와 S(매도) 신호를 바탕으로 최종 수익률과 거래 내역을 계산합니다.
    """
    price_col = 'Close' if 'Close' in df.columns else 'close_price'
    
    is_holding = False  # 주식 보유 여부
    buy_price = 0
    total_profit_rate = 0.0
    trades = [] # 웹 화면 차트에 표시할 거래 내역

    for index, row in df.iterrows():
        signal = row['Signal']
        current_price = row[price_col]

        # 매수 로직 (안 가지고 있을 때 B 신호가 뜨면 산다)
        if signal == 'B' and not is_holding:
            is_holding = True
            buy_price = current_price
            trades.append({'date': row['date'], 'type': 'BUY', 'price': current_price})

        # 매도 로직 (가지고 있을 때 S 신호가 뜨면 판다)
        elif signal == 'S' and is_holding:
            is_holding = False
            sell_price = current_price
            
            # 수익률 계산: (매도가 - 매수가) / 매수가 * 100
            profit_rate = ((sell_price - buy_price) / buy_price) * 100
            total_profit_rate += profit_rate
            
            trades.append({'date': row['date'], 'type': 'SELL', 'price': current_price, 'profit_rate': round(profit_rate, 2)})

    # 만약 마지막 날까지 들고 있다면, 마지막 날 종가로 팔았다고 가정하고 수익률 계산
    if is_holding:
        final_price = df.iloc[-1][price_col]
        profit_rate = ((final_price - buy_price) / buy_price) * 100
        total_profit_rate += profit_rate
        trades.append({'date': df.iloc[-1]['date'], 'type': 'SELL (End)', 'price': final_price, 'profit_rate': round(profit_rate, 2)})

    return round(total_profit_rate, 2), trades