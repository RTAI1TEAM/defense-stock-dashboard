import pandas as pd

# [전략 1: 5일/20일 이동평균선 골든크로스]
def strategy_golden_cross(data, short_window=5, long_window=20):
    # 원본 데이터를 보존하기 위해 복사본을 생성합니다.
    df = data.copy()
    
    # 열 이름이 'Close'인지 'close_price'인지 확인하여 유연하게 대응합니다.
    price_col = 'Close' if 'Close' in df.columns else 'close_price'

    # 5일(단기) 및 20일(장기) 이동평균선을 계산하여 새로운 컬럼에 저장합니다.
    df['MA_short'] = df[price_col].rolling(window=short_window).mean()
    df['MA_long'] = df[price_col].rolling(window=long_window).mean()
    
    # 신호를 저장할 공간을 초기화합니다.
    df['Signal'] = ""

    # [매수 신호: 골든크로스] 
    # 어제는 단기선이 장기선 아래였는데, 오늘은 단기선이 장기선 위로 뚫고 올라왔을 때 발생합니다.
    buy_condition  = (df['MA_short'].shift(1) < df['MA_long'].shift(1)) & (df['MA_short'] > df['MA_long'])
    
    # [매도 신호: 데드크로스] 
    # 어제는 단기선이 장기선 위였는데, 오늘은 단기선이 장기선 아래로 뚫고 내려왔을 때 발생합니다.
    sell_condition = (df['MA_short'].shift(1) > df['MA_long'].shift(1)) & (df['MA_short'] < df['MA_long'])

    # 조건에 부합하는 날짜에 'B(Buy)' 또는 'S(Sell)' 신호를 입력합니다.
    df.loc[buy_condition,  'Signal'] = 'B'
    df.loc[sell_condition, 'Signal'] = 'S'
    
    return df


# [전략 2: 20일 전고점 돌파 매매]
def strategy_breakout(data, window=20):
    df = data.copy()
    price_col = 'Close' if 'Close' in df.columns else 'close_price'

    # 최근 20일간의 최고가를 계산하되, 오늘 종가는 제외(shift(1))하여 저항선을 만듭니다.
    df['High20'] = df[price_col].rolling(window=window).max().shift(1)
    # 추세 판단을 위해 20일 이동평균선을 계산합니다.
    df['MA20']   = df[price_col].rolling(window=window).mean()
    df['Signal'] = ""

    # [매수 신호] 현재가가 지난 20일간의 최고점(저항선)을 돌파했을 때 강력한 상승 신호로 간주합니다.
    buy_condition  = df[price_col] > df['High20']
    
    # [매도 신호] 현재가가 20일 이동평균선(지지선) 아래로 떨어지면 추세가 꺾인 것으로 보고 매도합니다.
    sell_condition = df[price_col] < df['MA20']

    df.loc[buy_condition,  'Signal'] = 'B'
    df.loc[sell_condition, 'Signal'] = 'S'
    
    return df


# [3. 백테스팅 수익률 계산 엔진]
def run_backtest(df, initial_cash=10_000_000):
    """
    설정된 전략에 따라 가상 매매를 수행하여 성과 지표를 산출합니다.
    초기 자본금은 기본 1,000만원으로 설정되어 있습니다. [cite: 23, 150]
    """
    price_col = 'Close' if 'Close' in df.columns else 'close_price'

    # 시뮬레이션에 필요한 상태 변수들을 초기화합니다.
    is_holding       = False # 주식 보유 여부
    buy_price        = 0     # 매수한 가격
    shares           = 0     # 보유 수량
    cash             = float(initial_cash) # 보유 현금
    total_profit_rate = 0.0  # 누적 수익률 합계
    win_count        = 0     # 수익을 본 거래 횟수
    sell_count       = 0     # 총 매도 횟수
    trades           = []    # 거래 내역 로그

    # 시세 데이터를 하루씩 순회하며 매매 신호를 체크합니다.
    for _, row in df.iterrows():
        signal        = row['Signal']
        current_price = float(row[price_col])

        # [매수 로직] 신호가 'B'이고 현재 주식이 없을 때 전량 매수합니다.
        if signal == 'B' and not is_holding:
            is_holding = True
            buy_price  = current_price
            shares     = int(cash // current_price) # 가용 현금으로 살 수 있는 최대 수량 계산
            if shares > 0:
                cash -= shares * current_price
            
            # 차트 표시를 위해 매수 기록을 남깁니다. [cite: 57, 204]
            trades.append({
                'date':  str(row['date']),
                'type':  'BUY',
                'price': current_price,
                'shares': shares
            })

        # [매도 로직] 신호가 'S'이고 주식을 보유 중일 때 전량 매도합니다.
        elif signal == 'S' and is_holding:
            is_holding  = False
            sell_price  = current_price
            # 이번 거래의 수익률을 계산합니다.
            profit_rate = ((sell_price - buy_price) / buy_price) * 100
            total_profit_rate += profit_rate
            sell_count += 1
            
            # 수익이 발생했다면 승리 횟수를 올립니다.
            if profit_rate > 0:
                win_count += 1
                
            # 매도한 대금을 현금 잔고에 합산합니다.
            if shares > 0:
                cash += shares * sell_price
                shares = 0
            
            # 매도 기록과 수익률을 남깁니다.
            trades.append({
                'date':        str(row['date']),
                'type':        'SELL',
                'price':       float(sell_price),
                'profit_rate': round(profit_rate, 2)
            })

    # [최종 청산] 데이터 마지막 날까지 주식을 팔지 못했다면 강제로 매도 처리하여 수익률을 마감합니다.
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

    # 전체 거래 중 수익을 낸 비율(승률)을 계산합니다. [cite: 216, 239]
    win_rate = round((win_count / sell_count * 100) if sell_count > 0 else 0, 1)

    # 누적 수익률, 거래 로그, 승률, 총 거래 횟수를 반환합니다.
    return round(total_profit_rate, 2), trades, win_rate, sell_count