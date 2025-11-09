# -*- coding: utf-8 -*-
"""
최소한의 테스트
"""
import sys
import os
import ccxt
import pandas as pd

# 스크립트 디렉토리 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

def calculate_indicators(df):
    """기술적 지표 계산"""
    if df is None or len(df) == 0:
        return None
    
    df = df.copy()
    
    # 기본 이동평균선
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma80'] = df['close'].rolling(window=80).mean()
    df['ma480'] = df['close'].rolling(window=480).mean()
    
    return df

def test_prerequisite(symbol):
    """전제조건 테스트"""
    print(f"=== {symbol} 전제조건 테스트 ===")
    
    try:
        exchange = ccxt.binance()
        
        # 15분봉 데이터 조회 (600개)
        ohlcv = exchange.fetch_ohlcv(f'{symbol}/USDT', '15m', limit=600)
        df_15m = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        print(f"데이터 개수: {len(df_15m)}")
        
        if len(df_15m) < 480:
            print(f"❌ 데이터 부족: {len(df_15m)}개 (480개 필요)")
            return
        
        # 지표 계산
        df_calc = calculate_indicators(df_15m)
        
        # 전제조건 체크
        ma80_15m = df_calc['ma80'].iloc[-1]
        ma5_15m = df_calc['ma5'].iloc[-1]
        ma480_15m = df_calc['ma480'].iloc[-1]
        
        print(f"MA80: {ma80_15m:.6f}")
        print(f"MA5: {ma5_15m:.6f}")
        print(f"MA480: {ma480_15m:.6f}")
        
        # 전제조건 체크
        if pd.isna(ma480_15m) or pd.isna(ma80_15m) or pd.isna(ma5_15m):
            print("❌ MA 계산 실패")
            return
        
        basic_ma_condition = (ma80_15m < ma480_15m and ma5_15m < ma480_15m)
        
        if not basic_ma_condition:
            print(f"🚫 전제조건 차단: {symbol} - MA80:{ma80_15m:.6f} vs MA480:{ma480_15m:.6f}, MA5:{ma5_15m:.6f}")
            print("❌ A전략 신호 발생하면 안됨!")
        else:
            print(f"✅ 전제조건 통과: {symbol} - MA80:{ma80_15m:.6f} < MA480:{ma480_15m:.6f}, MA5:{ma5_15m:.6f}")
            print("✅ A전략 신호 발생 가능")
        
        print()
        
    except Exception as e:
        print(f"❌ {symbol} 테스트 실패: {e}")
        print()

if __name__ == "__main__":
    # 문제 심볼들 테스트
    symbols = ["LINK", "XRP", "BANK"]
    for symbol in symbols:
        test_prerequisite(symbol)