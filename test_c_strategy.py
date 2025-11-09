#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C전략 테스트 스크립트
"""

import sys
import os
import traceback

# 현재 디렉토리를 PATH에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

def test_websocket_provider():
    """WebSocket Provider 테스트"""
    try:
        from websocket_ohlcv_provider import WebSocketOHLCVProvider
        
        print("=== WebSocket Provider 테스트 ===")
        ws_provider = WebSocketOHLCVProvider()
        
        # 3분봉 데이터 요청 테스트
        test_symbol = 'API3/USDT:USDT'
        
        # 1. get_ohlcv 테스트
        print(f"\n1. get_ohlcv 테스트 - {test_symbol}")
        data = ws_provider.get_ohlcv(test_symbol, '3m', 600)
        print(f"   결과: {len(data) if data else 0}개 데이터")
        
        # 2. get_cached_ohlcv 테스트 (메서드 존재 확인)
        if hasattr(ws_provider, 'get_cached_ohlcv'):
            print(f"\n2. get_cached_ohlcv 테스트 - {test_symbol}")
            cached_data = ws_provider.get_cached_ohlcv(test_symbol, '3m', 600)
            print(f"   결과: {len(cached_data) if cached_data else 0}개 데이터")
        else:
            print("\n2. get_cached_ohlcv 메서드 없음!")
            
        # 3. 첫 5개 데이터 샘플 확인
        if data and len(data) > 5:
            print(f"\n3. 데이터 샘플 (첫 5개):")
            for i, d in enumerate(data[:5]):
                print(f"   {i+1}: {d}")
                
        return True
        
    except Exception as e:
        print(f"WebSocket Provider 테스트 실패: {e}")
        traceback.print_exc()
        return False

def test_c_strategy():
    """C전략 테스트"""
    try:
        from alpha_z_triple_strategy import FifteenMinuteMegaStrategy
        
        print("\n=== C전략 테스트 ===")
        strategy = FifteenMinuteMegaStrategy(sandbox=True)
        
        # 테스트 심볼
        test_symbol = 'API3/USDT:USDT'
        
        print(f"\nC전략 체크 - {test_symbol}")
        c_signal, c_conditions = strategy._check_strategy_c_3min_precision(test_symbol)
        
        print(f"신호: {c_signal}")
        print("조건들:")
        for condition in c_conditions:
            print(f"  - {condition}")
            
        return True
        
    except Exception as e:
        print(f"C전략 테스트 실패: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("C전략 디버깅 테스트 시작\n")
    
    # WebSocket Provider 테스트
    ws_ok = test_websocket_provider()
    
    # C전략 테스트
    c_ok = test_c_strategy()
    
    print("\n=== 테스트 결과 ===")
    print(f"WebSocket Provider: {'성공' if ws_ok else '실패'}")
    print(f"C전략: {'성공' if c_ok else '실패'}")
    
    if ws_ok and c_ok:
        print("\n✅ 모든 테스트 통과!")
    else:
        print("\n❌ 일부 테스트 실패")