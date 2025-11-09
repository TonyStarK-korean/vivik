# -*- coding: utf-8 -*-
"""
빠른 테스트 - 몇 개 심볼만
"""
import sys
import os
import ccxt
import pandas as pd
import time

# 스크립트 디렉토리 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from alpha_z_triple_strategy import FifteenMinuteMegaStrategy
    
    def test_specific_symbols():
        """특정 심볼들만 테스트"""
        # 기본 초기화 없이 메서드만 사용
        strategy = object.__new__(FifteenMinuteMegaStrategy)  # __init__ 건너뛰기
        
        # 기본 속성만 설정
        strategy.exchange = ccxt.binance()
        
        # 테스트할 심볼들
        test_symbols = ["BARD/USDT:USDT", "LINK/USDT:USDT"]
        
        for symbol in test_symbols:
            print(f"\n=== {symbol} 테스트 ===")
            
            try:
                # 15분봉 데이터 조회
                ohlcv = strategy.exchange.fetch_ohlcv(symbol.replace(':USDT', ''), '15m', limit=600)
                df_15m = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
                print(f"데이터 개수: {len(df_15m)}")
                
                if len(df_15m) < 480:
                    print("데이터 부족")
                    continue
                
                # calculate_indicators 메서드 직접 호출
                df_calc = df_15m.copy()
                df_calc['ma5'] = df_calc['close'].rolling(window=5).mean()
                df_calc['ma80'] = df_calc['close'].rolling(window=80).mean()
                df_calc['ma480'] = df_calc['close'].rolling(window=480).mean()
                
                # 전제조건 체크 (수정된 로직과 동일)
                ma80_15m = df_calc['ma80'].iloc[-1]
                ma5_15m = df_calc['ma5'].iloc[-1]
                ma480_15m = df_calc['ma480'].iloc[-1]
                
                print(f"MA80: {ma80_15m:.6f}")
                print(f"MA5: {ma5_15m:.6f}")  
                print(f"MA480: {ma480_15m:.6f}")
                
                if pd.isna(ma480_15m) or pd.isna(ma80_15m) or pd.isna(ma5_15m):
                    print("MA 계산 실패")
                    continue
                
                basic_ma_condition = (ma80_15m < ma480_15m and ma5_15m < ma480_15m)
                
                print(f"전제조건: {basic_ma_condition}")
                
                if not basic_ma_condition:
                    print("🚫🚫🚫 SHOULD BE BLOCKED!")
                else:
                    print("✅✅✅ SHOULD BE PASSED!")
                
                print()
                
            except Exception as e:
                print(f"오류: {e}")
                import traceback
                traceback.print_exc()
                
    test_specific_symbols()

except ImportError as e:
    print(f"모듈 로드 실패: {e}")