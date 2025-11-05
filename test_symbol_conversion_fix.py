#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
심볼 형식 변환 수정 테스트
"""

def test_symbol_conversion():
    """심볼 변환 테스트"""
    test_cases = [
        'BTC/USDT:USDT',
        'ETH/USDT:USDT', 
        'BCH/USDT:USDT',
        'XRP/USDT:USDT',
        'BNB/USDT:USDT'
    ]
    
    print("=== 심볼 변환 테스트 ===")
    for futures_symbol in test_cases:
        # 기존 변환 방식 
        ws_symbol = futures_symbol.replace('/USDT:USDT', 'USDT').replace('/', '')
        buffer_key_4h = f"{ws_symbol}_4h"
        buffer_key_1h = f"{ws_symbol}_1h"
        
        print(f"{futures_symbol} -> {ws_symbol}")
        print(f"  4h 버퍼키: {buffer_key_4h}")
        print(f"  1h 버퍼키: {buffer_key_1h}")
        print()

if __name__ == "__main__":
    test_symbol_conversion()