# -*- coding: utf-8 -*-
"""
BARD, BULLA 확인
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
        
        print(f"=== {symbol} ===")
        print(f"데이터 개수: {len(df)}")
        
        if len(df) < 480:
            print(f"데이터 부족: {len(df)}/480")
            return
            
        # MA 계산
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma80'] = df['close'].rolling(window=80).mean()
        df['ma480'] = df['close'].rolling(window=480).mean()
        
        # 현재 값들
        current_price = df['close'].iloc[-1]
        ma5 = df['ma5'].iloc[-1]
        ma80 = df['ma80'].iloc[-1]
        ma480 = df['ma480'].iloc[-1]
        
        print(f"현재가: {current_price:.6f}")
        print(f"MA5: {ma5:.6f}")
        print(f"MA80: {ma80:.6f}")
        print(f"MA480: {ma480:.6f}")
        
        # 조건 확인
        ma80_ok = pd.notna(ma80) and pd.notna(ma480) and ma80 < ma480
        ma5_ok = pd.notna(ma5) and pd.notna(ma480) and ma5 < ma480
        condition = ma80_ok and ma5_ok
        
        print(f"MA80 < MA480: {ma80_ok} ({ma80:.6f} {'<' if ma80_ok else '>='} {ma480:.6f})")
        print(f"MA5 < MA480: {ma5_ok} ({ma5:.6f} {'<' if ma5_ok else '>='} {ma480:.6f})")
        print(f"전제조건: {condition}")
        
        if not condition:
            print("❌ A전략 신호 발생하면 안됨!")
        else:
            print("✅ A전략 신호 발생 가능")
        
        print()
        
    except Exception as e:
        print(f"{symbol}: 오류 {e}")
        print()

if __name__ == "__main__":
    # 문제 심볼들
    symbols = ["BARD", "BULLA", "LINK"]
    for symbol in symbols:
        check_symbol_ma_simple(symbol)