# -*- coding: utf-8 -*-
"""
LINK, XRP 디버그 테스트
"""
import sys
import os
import ccxt
import pandas as pd

# 스크립트 디렉토리 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from alpha_z_triple_strategy import FifteenMinuteMegaStrategy
    
    def test_symbols():
        """LINK와 XRP 테스트"""
        symbols_to_test = ["LINK/USDT:USDT", "XRP/USDT:USDT"]
        
        try:
            strategy = FifteenMinuteMegaStrategy(sandbox=True)  # 샌드박스 모드로 테스트
            
            for symbol in symbols_to_test:
                print(f"\n=== {symbol} 테스트 ===")
                
                # 15분봉 데이터 조회
                df_15m = strategy.get_ohlcv_data(symbol, '15m', limit=600)
                if df_15m is None or len(df_15m) < 480:
                    print(f"데이터 부족: {len(df_15m) if df_15m is not None else 0}")
                    continue
                
                # 전략 조건 체크
                is_signal, conditions, details = strategy.check_fifteen_minute_mega_conditions(symbol, df_15m)
                
                print(f"신호 결과: {is_signal}")
                print(f"A전략: {details.get('strategy_a', {}).get('signal', 'N/A')}")
                print(f"B전략: {details.get('strategy_b', {}).get('signal', 'N/A')}")
                print(f"C전략: {details.get('strategy_c', {}).get('signal', 'N/A')}")
                
                # A전략 상세 조건 출력
                if 'strategy_a' in details:
                    print("\nA전략 조건:")
                    for cond in details['strategy_a'].get('conditions', []):
                        print(f"  {cond}")
                
                print()
                
        except Exception as e:
            print(f"테스트 실패: {e}")
            import traceback
            traceback.print_exc()
    
    test_symbols()

except ImportError as e:
    print(f"모듈 로드 실패: {e}")