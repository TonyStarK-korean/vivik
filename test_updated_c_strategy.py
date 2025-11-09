#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
업데이트된 C전략 조건4 테스트
(3분봉 or 15분봉 or 30분봉) 30봉이내 시가대비고가 3%이상 1회이상
"""

import sys
import os

# 현재 디렉토리를 PATH에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from websocket_ohlcv_provider import WebSocketOHLCVProvider
    
    print("업데이트된 C전략 조건4 테스트")
    print("=" * 40)
    
    # WebSocket Provider 테스트
    ws_provider = WebSocketOHLCVProvider()
    test_symbol = 'API3/USDT:USDT'
    
    print(f"\n테스트 심볼: {test_symbol}")
    print(f"조건: (3분봉 or 15분봉 or 30분봉) 30봉이내 시가대비고가 3%이상 1회이상")
    
    # 3분봉 테스트
    print("\n1. 3분봉 데이터 테스트:")
    data_3m = ws_provider.get_ohlcv(test_symbol, '3m', 120)  # 30봉 + 여유분
    high_move_count_3m = 0
    
    if data_3m and len(data_3m) >= 30:
        print(f"   데이터: {len(data_3m)}개")
        for i in range(min(30, len(data_3m))):
            candle = data_3m[-(i+1)]
            if len(candle) >= 5 and candle[1] > 0:  # open > 0
                open_price = candle[1]
                high_price = candle[2]
                high_move_pct = ((high_price - open_price) / open_price) * 100
                if high_move_pct >= 3.0:
                    high_move_count_3m += 1
                    print(f"      봉 {i+1}: 시가대비고가 {high_move_pct:.2f}% (3% 이상!)")
        print(f"   3분봉 30봉 내 3% 이상 급등: {high_move_count_3m}회")
    else:
        print(f"   데이터 부족: {len(data_3m) if data_3m else 0}개")
    
    # 15분봉 테스트
    print("\n2. 15분봉 데이터 테스트:")
    data_15m = ws_provider.get_ohlcv(test_symbol, '15m', 120)  # 30봉 + 여유분
    high_move_count_15m = 0
    
    if data_15m and len(data_15m) >= 30:
        print(f"   데이터: {len(data_15m)}개")
        for i in range(min(30, len(data_15m))):
            candle = data_15m[-(i+1)]
            if len(candle) >= 5 and candle[1] > 0:  # open > 0
                open_price = candle[1]
                high_price = candle[2]
                high_move_pct = ((high_price - open_price) / open_price) * 100
                if high_move_pct >= 3.0:
                    high_move_count_15m += 1
                    print(f"      봉 {i+1}: 시가대비고가 {high_move_pct:.2f}% (3% 이상!)")
        print(f"   15분봉 30봉 내 3% 이상 급등: {high_move_count_15m}회")
    else:
        print(f"   데이터 부족: {len(data_15m) if data_15m else 0}개")
    
    # 30분봉 테스트
    print("\n3. 30분봉 데이터 테스트:")
    data_30m = ws_provider.get_ohlcv(test_symbol, '30m', 120)  # 30봉 + 여유분
    high_move_count_30m = 0
    
    if data_30m and len(data_30m) >= 30:
        print(f"   데이터: {len(data_30m)}개")
        for i in range(min(30, len(data_30m))):
            candle = data_30m[-(i+1)]
            if len(candle) >= 5 and candle[1] > 0:  # open > 0
                open_price = candle[1]
                high_price = candle[2]
                high_move_pct = ((high_price - open_price) / open_price) * 100
                if high_move_pct >= 3.0:
                    high_move_count_30m += 1
                    print(f"      봉 {i+1}: 시가대비고가 {high_move_pct:.2f}% (3% 이상!)")
        print(f"   30분봉 30봉 내 3% 이상 급등: {high_move_count_30m}회")
    else:
        print(f"   데이터 부족: {len(data_30m) if data_30m else 0}개")
    
    # 최종 조건4 판정
    total_count = high_move_count_3m + high_move_count_15m + high_move_count_30m
    condition4_pass = total_count >= 1
    
    print(f"\n🎯 최종 조건4 결과:")
    print(f"   총 급등 횟수: {total_count}회")
    print(f"   조건4 통과: {condition4_pass}")
    
    if condition4_pass:
        timeframe_details = []
        if high_move_count_3m > 0:
            timeframe_details.append(f"3분봉 {high_move_count_3m}회")
        if high_move_count_15m > 0:
            timeframe_details.append(f"15분봉 {high_move_count_15m}회")
        if high_move_count_30m > 0:
            timeframe_details.append(f"30분봉 {high_move_count_30m}회")
        detail = " + ".join(timeframe_details)
        print(f"   통과 상세: {detail}")
    else:
        print(f"   통과 실패: 3분봉 {high_move_count_3m}회, 15분봉 {high_move_count_15m}회, 30분봉 {high_move_count_30m}회 (모두 0회)")
    
    print(f"\n✅ 업데이트된 C전략 조건4 테스트 완료!")
    
except Exception as e:
    print(f"테스트 실패: {e}")
    import traceback
    traceback.print_exc()