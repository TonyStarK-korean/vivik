# -*- coding: utf-8 -*-
"""
MUBARAK, MELANIA MA 조건 확인
"""
import ccxt
import pandas as pd

def check_symbol_ma(symbol):
    """심볼의 MA 조건 확인"""
    print(f"=== {symbol} 15분봉 MA 조건 확인 ===")
    
    try:
        exchange = ccxt.binance()
        
        # 15분봉 데이터 가져오기
        ohlcv = exchange.fetch_ohlcv(f'{symbol}/USDT', '15m', limit=500)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        if len(df) < 480:
            print(f"데이터 부족: {len(df)}개")
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
        ma80_vs_ma480 = ma80 < ma480
        ma5_vs_ma480 = ma5 < ma480
        condition1 = ma80_vs_ma480 and ma5_vs_ma480
        
        print(f"MA80 < MA480: {ma80_vs_ma480} ({ma80:.6f} < {ma480:.6f})")
        print(f"MA5 < MA480: {ma5_vs_ma480} ({ma5:.6f} < {ma480:.6f})")
        print(f"A전략 조건1: {condition1}")
        
        # 전제조건 체크 (코드와 동일)
        basic_ma_condition = (pd.notna(ma80) and pd.notna(ma480) and pd.notna(ma5) and
                            ma80 < ma480 and ma5 < ma480)
        
        print(f"전제조건: {basic_ma_condition}")
        
        if not condition1:
            print("❌ A전략 조건1 미충족 - 신호 발생하면 안됨")
        else:
            print("✅ A전략 조건1 충족 - 신호 발생 가능")
        
        print()
        
    except Exception as e:
        print(f"{symbol} 확인 실패: {e}")
        print()

if __name__ == "__main__":
    # MUBARAK과 MELANIA 확인
    symbols = ["MUBARAK", "MELANIA"]
    for symbol in symbols:
        check_symbol_ma(symbol)