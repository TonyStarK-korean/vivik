#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C전략 데이터 None 체크 (간단 버전)
"""

import sys
import os
import pandas as pd

# 현재 디렉토리를 PATH에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from websocket_ohlcv_provider import WebSocketOHLCVProvider
    from alpha_z_triple_strategy import FifteenMinuteMegaStrategy
    
    print("C전략 데이터 None 체크")
    print("=" * 40)
    
    # 1. WebSocket Provider 데이터 체크
    ws_provider = WebSocketOHLCVProvider()
    test_symbol = 'API3/USDT:USDT'
    
    print(f"\n테스트 심볼: {test_symbol}")
    
    # 3분봉 데이터 체크
    print("\n1. 3분봉 데이터 체크:")
    data_3m = ws_provider.get_ohlcv(test_symbol, '3m', 600)
    
    if data_3m is None:
        print("   ERROR: 3분봉 데이터가 None입니다!")
    else:
        print(f"   OK: 3분봉 데이터 {len(data_3m)}개 생성됨")
        
        # 처음 3개와 마지막 3개 체크
        print("   처음 3개 데이터:")
        for i, candle in enumerate(data_3m[:3]):
            if candle is None:
                print(f"      [{i}] None!")
            elif len(candle) < 5:
                print(f"      [{i}] 부족한 데이터: {candle}")
            else:
                timestamp, open_p, high_p, low_p, close_p = candle[:5]
                none_count = sum(1 for x in [open_p, high_p, low_p, close_p] if x is None)
                if none_count > 0:
                    print(f"      [{i}] {none_count}개 None 값 발견!")
                else:
                    print(f"      [{i}] 정상: O={open_p:.6f}, H={high_p:.6f}, L={low_p:.6f}, C={close_p:.6f}")
        
        print("   마지막 3개 데이터:")
        for i, candle in enumerate(data_3m[-3:], len(data_3m)-3):
            if candle is None:
                print(f"      [{i}] None!")
            elif len(candle) < 5:
                print(f"      [{i}] 부족한 데이터: {candle}")
            else:
                timestamp, open_p, high_p, low_p, close_p = candle[:5]
                none_count = sum(1 for x in [open_p, high_p, low_p, close_p] if x is None)
                if none_count > 0:
                    print(f"      [{i}] {none_count}개 None 값 발견!")
                else:
                    print(f"      [{i}] 정상: O={open_p:.6f}, H={high_p:.6f}, L={low_p:.6f}, C={close_p:.6f}")
    
    # DataFrame 변환 체크
    if data_3m and len(data_3m) >= 500:
        print("\n2. DataFrame 변환 체크:")
        try:
            df_3m = pd.DataFrame(data_3m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_3m['timestamp'] = pd.to_datetime(df_3m['timestamp'], unit='ms')
            
            print(f"   OK: DataFrame 변환 성공 ({len(df_3m)}행)")
            
            # None/NaN 체크
            null_counts = df_3m.isnull().sum()
            has_nulls = any(count > 0 for count in null_counts.values())
            
            if has_nulls:
                print("   WARNING: Null 값 발견:")
                for col, count in null_counts.items():
                    if count > 0:
                        print(f"      {col}: {count}개")
            else:
                print("   OK: Null 값 없음")
                
            # 실제 값 범위 확인
            print(f"   데이터 범위:")
            print(f"      시가: {df_3m['open'].min():.6f} ~ {df_3m['open'].max():.6f}")
            print(f"      고가: {df_3m['high'].min():.6f} ~ {df_3m['high'].max():.6f}")
            print(f"      저가: {df_3m['low'].min():.6f} ~ {df_3m['low'].max():.6f}")
            print(f"      종가: {df_3m['close'].min():.6f} ~ {df_3m['close'].max():.6f}")
            
        except Exception as e:
            print(f"   ERROR: DataFrame 변환 실패: {e}")
    
    # 3. 실제 C전략 데이터 흐름 체크
    print("\n3. C전략 실제 데이터 흐름 체크:")
    try:
        strategy = FifteenMinuteMegaStrategy(sandbox=True)
        print(f"   OK: 전략 초기화 완료")
        print(f"   WebSocket Provider: {strategy.ws_provider is not None}")
        
        # C전략 호출하여 데이터가 None인지 확인
        c_signal, c_conditions = strategy._check_strategy_c_3min_precision(test_symbol)
        
        print(f"   C전략 신호: {c_signal}")
        print(f"   조건 개수: {len(c_conditions)}")
        
        # 조건4 세부 내용에서 실제 카운트 확인
        for condition in c_conditions:
            if "조건4" in condition:
                print(f"   조건4 결과: {condition}")
                # "3분봉 N회" 패턴 찾아서 실제 값 확인
                if "3분봉 0회" in condition and "15분봉 0회" in condition and "30분봉 0회" in condition:
                    print("   WARNING: 모든 타임프레임에서 급등 0회 - 데이터 문제 의심")
                else:
                    print("   OK: 실제 급등 데이터 감지됨")
                break
    
    except Exception as e:
        print(f"   ERROR: C전략 테스트 실패: {e}")
    
    print("\n" + "="*40)
    print("데이터 검증 완료")
    
except Exception as e:
    print(f"전체 테스트 실패: {e}")
    import traceback
    traceback.print_exc()