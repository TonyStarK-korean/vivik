# -*- coding: utf-8 -*-
"""
최종 테스트 - LINK와 XRP MA 확인
"""
import ccxt
import pandas as pd

def check_symbol_ma_simple(symbol):
    """심볼의 MA 조건 간단 확인"""
    try:
        exchange = ccxt.binance()
        
        # 15분봉 데이터 가져오기 (600개)
        ohlcv = exchange.fetch_ohlcv(f'{symbol}/USDT', '15m', limit=600)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        if len(df) < 480:
            print(f"{symbol}: 데이터 부족 {len(df)}")
            return
            
        # MA 계산
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma80'] = df['close'].rolling(window=80).mean()
        df['ma480'] = df['close'].rolling(window=480).mean()
        
        # 현재 값들
        ma5 = df['ma5'].iloc[-1]
        ma80 = df['ma80'].iloc[-1]
        ma480 = df['ma480'].iloc[-1]
        
        # 조건 확인
        ma80_ok = pd.notna(ma80) and pd.notna(ma480) and ma80 < ma480
        ma5_ok = pd.notna(ma5) and pd.notna(ma480) and ma5 < ma480
        condition = ma80_ok and ma5_ok
        
        print(f"{symbol}: MA80({ma80:.4f}) < MA480({ma480:.4f}) = {ma80_ok}")
        print(f"{symbol}: MA5({ma5:.4f}) < MA480({ma480:.4f}) = {ma5_ok}")
        print(f"{symbol}: 전제조건 = {condition}")
        print()
        
    except Exception as e:
        print(f"{symbol}: 오류 {e}")

if __name__ == "__main__":
    # 문제 심볼들
    symbols = ["LINK", "XRP", "BANK"]
    for symbol in symbols:
        check_symbol_ma_simple(symbol)