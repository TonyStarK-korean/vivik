#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick C전략 실전 테스트 (업데이트된 조건4 포함)
"""

import sys
import os

# 현재 디렉토리를 PATH에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from alpha_z_triple_strategy import FifteenMinuteMegaStrategy
    
    print("C전략 실전 테스트 (업데이트된 조건4)")
    print("=" * 50)
    
    # 전략 인스턴스 생성 (sandbox 모드)
    strategy = FifteenMinuteMegaStrategy(sandbox=True)
    
    # 테스트 심볼들
    test_symbols = ['API3/USDT:USDT', 'APR/USDT:USDT', 'PLAY/USDT:USDT']
    
    print(f"\n업데이트된 조건4: (3분봉 or 15분봉 or 30분봉) 30봉이내 시가대비고가 3%이상 1회이상")
    
    for symbol in test_symbols:
        try:
            print(f"\n{'='*30}")
            print(f"심볼: {symbol}")
            print(f"{'='*30}")
            
            # C전략 체크
            c_signal, c_conditions = strategy._check_strategy_c_3min_precision(symbol)
            
            print(f"C전략 신호: {c_signal}")
            print("조건 상세:")
            for condition in c_conditions:
                print(f"  {condition}")
                
            if c_signal:
                print("✅ C전략 진입 신호!")
            else:
                print("❌ C전략 진입 실패")
                
        except Exception as e:
            print(f"❌ {symbol} 테스트 실패: {e}")
    
    print(f"\n{'='*50}")
    print("C전략 테스트 완료!")
    
except Exception as e:
    print(f"전체 테스트 실패: {e}")
    import traceback
    traceback.print_exc()