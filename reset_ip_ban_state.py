#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IP 밴 상태 리셋 및 일봉 조건 테스트"""

import os
import sys

# 스크립트 디렉토리를 Python 경로에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy

def reset_and_test():
    """IP 밴 상태 리셋하고 일봉 조건 테스트"""
    print("=== IP 밴 상태 리셋 및 일봉 조건 테스트 ===")
    
    strategy = OneMinuteSurgeEntryStrategy()
    
    # IP 밴 상태 리셋
    if hasattr(strategy, '_ip_ban_detected'):
        print(f"현재 IP 밴 상태: {strategy._ip_ban_detected}")
        strategy._ip_ban_detected = False
        print("IP 밴 상태 리셋 완료")
    else:
        print("IP 밴 상태 플래그 없음")
    
    # 원래 fetch_ohlcv 메서드로 직접 테스트
    if hasattr(strategy, '_original_fetch_ohlcv'):
        print("직접 원본 API로 BTCUSDT 테스트...")
        try:
            data = strategy._original_fetch_ohlcv('BTCUSDT', '1d', limit=10)
            if data:
                import pandas as pd
                df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                print(f"SUCCESS: {len(df)}일 데이터")
                print(f"날짜: {df['datetime'].min()} ~ {df['datetime'].max()}")
                print(f"가격: ${df['low'].min():.2f} ~ ${df['high'].max():.2f}")
                
                # 40% 급등 확인
                surge_count = 0
                for i, row in df.iterrows():
                    if row['open'] > 0:
                        surge_pct = ((row['high'] - row['open']) / row['open']) * 100
                        if surge_pct >= 40.0:
                            surge_count += 1
                            print(f"SURGE: {row['datetime'].strftime('%Y-%m-%d')}: {surge_pct:.1f}%")
                
                if surge_count > 0:
                    print(f"✅ {surge_count}개 40%+ 급등일 발견")
                else:
                    max_surge = max(((row['high'] - row['open']) / row['open']) * 100 
                                  for _, row in df.iterrows() if row['open'] > 0)
                    print(f"❌ 40% 급등 없음 (최대: {max_surge:.1f}%)")
            else:
                print("ERROR: 데이터 없음")
        except Exception as e:
            print(f"ERROR: {e}")
    
    # 일봉 급등 조건 메서드 테스트
    print("\n=== 일봉 급등 조건 메서드 테스트 ===")
    test_symbols = ['BLUAIUSDT', 'RIVERUSDT', 'BTCUSDT']
    
    for symbol in test_symbols:
        print(f"\n{symbol} 테스트:")
        try:
            result = strategy._check_daily_surge_condition(symbol)
            if result[0]:
                print(f"SUCCESS: {result[1]}")
            else:
                print(f"FAIL: {result[1]}")
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    reset_and_test()