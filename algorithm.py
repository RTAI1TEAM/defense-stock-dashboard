import pandas as pd

# 1. 5일/20일 이동평균선 골든크로스 전략
def strategy_golden_cross(data, short_window=5, long_window=20):
    df = data.copy()
    price_col = 'Close' if 'Close' in df.columns else 'close_price'

    df['MA_short'] = df[price_col].rolling(window=short_window).mean()
    df['MA_long'] = df[price_col].rolling(window=long_window).mean()
    df['Signal'] = ""

    buy_condition  = (df['MA_short'].shift(1) < df['MA_long'].shift(1)) & (df['MA_short'] > df['MA_long'])
    sell_condition = (df['MA_short'].shift(1) > df['MA_long'].shift(1)) & (df['MA_short'] < df['MA_long'])

    df.loc[buy_condition,  'Signal'] = 'B'
    df.loc[sell_condition, 'Signal'] = 'S'
    return df

# 2. 20일 전고점 돌파 매매 전략
def strategy_breakout(data, window=20):
    df = data.copy()
    price_col = 'Close' if 'Close' in df.columns else 'close_price'

    df['High20'] = df[price_col].rolling(window=window).max().shift(1)
    df['MA20']   = df[price_col].rolling(window=window).mean()
    df['Signal'] = ""

    buy_condition  = df[price_col] > df['High20']
    sell_condition = df[price_col] < df['MA20']

    df.loc[buy_condition,  'Signal'] = 'B'
    df.loc[sell_condition, 'Signal'] = 'S'
    return df

# 3. 백테스팅 수익률 계산 함수
def run_backtest(df, initial_cash=10_000_000):
    """
    반환값: (total_profit_rate, trades, win_rate, trade_count)
    - total_profit_rate : 누적 수익률 (%)
    - trades            : 거래 내역 리스트 (차트 표시용)
    - win_rate          : 승률 (%)
    - trade_count       : 총 매도 횟수
    """
    price_col = 'Close' if 'Close' in df.columns else 'close_price'

    is_holding       = False
    buy_price        = 0
    shares           = 0
    cash             = float(initial_cash)
    total_profit_rate = 0.0
    win_count        = 0
    sell_count       = 0
    trades           = []

    for _, row in df.iterrows():
        signal        = row['Signal']
        current_price = float(row[price_col])

        # 매수
        if signal == 'B' and not is_holding:
            is_holding = True
            buy_price  = current_price
            shares     = int(cash // current_price)
            if shares > 0:
                cash -= shares * current_price
            trades.append({
                'date':  str(row['date']),
                'type':  'BUY',
                'price': current_price,
                'shares': shares
            })

        # 매도
        elif signal == 'S' and is_holding:
            is_holding  = False
            sell_price  = current_price
            profit_rate = ((sell_price - buy_price) / buy_price) * 100
            total_profit_rate += profit_rate
            sell_count += 1
            if profit_rate > 0:
                win_count += 1
            if shares > 0:
                cash += shares * sell_price
                shares = 0
            trades.append({
                'date':        str(row['date']),
                'type':        'SELL',
                'price':       float(sell_price),
                'profit_rate': round(profit_rate, 2)
            })

    # 마지막까지 보유 중이면 최종 종가로 청산
    if is_holding:
        final_price = float(df.iloc[-1][price_col])
        profit_rate = ((final_price - buy_price) / buy_price) * 100
        total_profit_rate += profit_rate
        sell_count += 1
        if profit_rate > 0:
            win_count += 1
        trades.append({
            'date':        str(df.iloc[-1]['date']),
            'type':        'SELL (End)',
            'price':       final_price,
            'profit_rate': round(profit_rate, 2)
        })

    win_rate = round((win_count / sell_count * 100) if sell_count > 0 else 0, 1)

    return round(total_profit_rate, 2), trades, win_rate, sell_count