#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""일봉 급등 조건 빠른 테스트"""

import os
import sys

# 스크립트 디렉토리를 Python 경로에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy

def test_daily_surge():
    """일봉 급등 조건 빠른 테스트"""
    print("일봉 급등 조건 테스트 시작 (40% 기준)")
    
    strategy = OneMinuteSurgeEntryStrategy()
    
    # 테스트용 심볼들 (인기 있는 몇 개만)
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT']
    
    passed_count = 0
    total_count = 0
    
    for symbol in test_symbols:
        try:
            print(f"\nTEST: {symbol} 테스트 중...")
            result = strategy._check_daily_surge_condition(symbol)
            
            total_count += 1
            if result[0]:  # True/False
                passed_count += 1
                print(f"SUCCESS: {symbol}: {result[1]}")
            else:
                print(f"FAIL: {symbol}: {result[1]}")
                
        except Exception as e:
            print(f"ERROR: {symbol} 오류: {e}")
            total_count += 1
    
    print(f"\nRESULT: 테스트 결과: {passed_count}/{total_count} 통과 ({passed_count/total_count*100:.1f}%)")
    
    if passed_count > 0:
        print("SUCCESS: 일봉 조건이 완화되어 일부 심볼이 통과됨")
    else:
        print("FAIL: 여전히 모든 심볼이 실패 - 조건을 더 완화하거나 데이터 문제 확인 필요")

if __name__ == "__main__":
    test_daily_surge()