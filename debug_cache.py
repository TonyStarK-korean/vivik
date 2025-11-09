# -*- coding: utf-8 -*-
"""
캐시 문제 디버그
"""
import ccxt
import pandas as pd
import time

def check_symbol_realtime(symbol):
    """실시간 데이터로 심볼 확인"""
    try:
        exchange = ccxt.binance()
        
        print(f"=== {symbol} 실시간 체크 ===")
        
        # 매번 새로운 데이터 가져오기 (캐시 무시)
        ohlcv = exchange.fetch_ohlcv(f'{symbol}/USDT', '15m', limit=600)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        print(f"데이터 개수: {len(df)}")
        print(f"최신 타임스탬프: {pd.to_datetime(df['timestamp'].iloc[-1], unit='ms')}")
        
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
        
        # 전제조건
        ma80_check = pd.notna(ma80) and pd.notna(ma480) and ma80 < ma480
        ma5_check = pd.notna(ma5) and pd.notna(ma480) and ma5 < ma480
        basic_condition = ma80_check and ma5_check
        
        print(f"MA80 < MA480: {ma80_check}")
        print(f"MA5 < MA480: {ma5_check}")
        print(f"전제조건: {basic_condition}")
        
        if basic_condition:
            print("✅ 전제조건 통과 - A전략 가능")
        else:
            print("❌ 전제조건 차단 - A전략 불가")
        
        # 최근 5개 MA80 값 확인 (변동성 체크)
        recent_ma80 = df['ma80'].tail(5).values
        recent_ma480 = df['ma480'].tail(5).values
        
        print("\n최근 5개 MA 값:")
        for i, (m80, m480) in enumerate(zip(recent_ma80, recent_ma480)):
            if pd.notna(m80) and pd.notna(m480):
                print(f"  {i+1}: MA80={m80:.4f}, MA480={m480:.4f}, 차이={m80-m480:.4f}")
        
        print()
        
    except Exception as e:
        print(f"{symbol} 체크 실패: {e}")
        import traceback
        traceback.print_exc()
        print()

if __name__ == "__main__":
    # 문제 심볼들 재확인
    symbols = ["BARD", "LINK", "BULLA"]
    for symbol in symbols:
        check_symbol_realtime(symbol)
        time.sleep(1)  # API 제한 방지