# -*- coding: utf-8 -*-
"""
전제조건 수정 테스트
"""
import sys
import os
import ccxt
import pandas as pd

# 스크립트 디렉토리 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

def test_symbol_condition_check(symbol):
    """심볼의 전제조건 체크 테스트"""
    print(f"=== {symbol} 전제조건 체크 ===")
    
    try:
        exchange = ccxt.binance()
        symbol_full = f"{symbol}/USDT:USDT"
        
        # 15분봉 데이터 조회
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
        ma80_current = df['ma80'].iloc[-1]
        ma480_current = df['ma480'].iloc[-1]
        ma5_current = df['ma5'].iloc[-1]
        
        print(f"MA80: {ma80_current:.4f}")
        print(f"MA480: {ma480_current:.4f}")
        print(f"MA5: {ma5_current:.4f}")
        
        # 전제조건 체크 (수정된 로직과 동일)
        basic_ma_condition = (pd.notna(ma80_current) and pd.notna(ma480_current) and pd.notna(ma5_current) and
                            ma80_current < ma480_current and ma5_current < ma480_current)
        
        print(f"basic_ma_condition: {basic_ma_condition}")
        
        if not basic_ma_condition:
            print(f"🚫 전제조건 차단: {symbol} - MA80:{ma80_current:.4f} >= MA480:{ma480_current:.4f}")
            print("   → 결과: is_signal = False")
        else:
            print(f"✅ 전제조건 통과: {symbol} - MA80:{ma80_current:.4f} < MA480:{ma480_current:.4f}")
            print("   → 결과: A,B,C 전략 체크 진행")
        
        print()
        
    except Exception as e:
        print(f"{symbol} 테스트 실패: {e}")
        print()

if __name__ == "__main__":
    # 문제가 되는 심볼들 테스트
    symbols = ["METIS", "TRADOOR", "APR", "BLUAI"]
    for symbol in symbols:
        test_symbol_condition_check(symbol)