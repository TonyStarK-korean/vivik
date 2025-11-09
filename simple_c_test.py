#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C전략 간단 테스트
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
    
    print("C전략 직접 테스트")
    print("================")
    
    # WebSocket Provider 테스트
    print("\n1. WebSocket Provider 테스트")
    ws_provider = WebSocketOHLCVProvider()
    test_symbol = 'API3/USDT:USDT'
    
    data_3m = ws_provider.get_ohlcv(test_symbol, '3m', 600)
    print(f"   3분봉 데이터: {len(data_3m) if data_3m else 0}개")
    
    if data_3m and len(data_3m) >= 500:
        # DataFrame 변환
        df_calc = pd.DataFrame(data_3m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_calc['timestamp'] = pd.to_datetime(df_calc['timestamp'], unit='ms')
        print(f"   DataFrame 변환: {len(df_calc)}행")
        
        # 시가대비고가 계산 테스트
        print("\n2. 시가대비고가 3% 조건 테스트")
        high_move_count = 0
        for i in range(min(20, len(df_calc))):
            candle = df_calc.iloc[-(i+1)]
            if pd.notna(candle['open']) and pd.notna(candle['high']) and candle['open'] > 0:
                high_move_pct = ((candle['high'] - candle['open']) / candle['open']) * 100
                if high_move_pct >= 3.0:
                    high_move_count += 1
                    print(f"   봉 {i+1}: 시가대비고가 {high_move_pct:.2f}% (3% 이상!)")
        
        print(f"   20봉 내 3% 이상 급등: {high_move_count}회")
        print(f"   조건4 (3분봉만) 충족: {high_move_count >= 1}")
        
        # 15분봉 테스트도 추가
        print("\n   15분봉 시가대비고가 테스트:")
        df_15m = ws_provider.get_ohlcv(test_symbol, '15m', 100)
        if df_15m and len(df_15m) >= 20:
            high_move_count_15m = 0
            for i in range(min(20, len(df_15m))):
                candle_data = df_15m[-(i+1)]
                if len(candle_data) >= 5 and candle_data[1] > 0:
                    open_price = candle_data[1]
                    high_price = candle_data[2]
                    high_move_pct = ((high_price - open_price) / open_price) * 100
                    if high_move_pct >= 3.0:
                        high_move_count_15m += 1
                        print(f"      15분봉 {i+1}: 시가대비고가 {high_move_pct:.2f}% (3% 이상!)")
            print(f"   15분봉 20봉 내 3% 이상 급등: {high_move_count_15m}회")
            print(f"   조건4 (3분봉 OR 15분봉) 충족: {(high_move_count + high_move_count_15m) >= 1}")
        
        # 실제 C전략 호출 시도 (sandbox 모드)
        print("\n3. C전략 직접 호출 테스트")
        try:
            # 간단한 클래스만 생성
            class SimpleStrategy:
                def __init__(self):
                    self.ws_provider = ws_provider
                    
                def _calculate_technical_indicators(self, df):
                    # 간단한 지표만 계산
                    df = df.copy()
                    
                    # MA 계산
                    df['ma5'] = df['close'].rolling(5).mean()
                    df['ma20'] = df['close'].rolling(20).mean()
                    df['ma80'] = df['close'].rolling(80).mean()
                    df['ma480'] = df['close'].rolling(480).mean()
                    
                    # 간단한 BB 계산
                    rolling_mean = df['close'].rolling(80).mean()
                    rolling_std = df['close'].rolling(80).std()
                    df['bb80_upper'] = rolling_mean + (rolling_std * 2)
                    
                    rolling_mean_480 = df['close'].rolling(480).mean()
                    rolling_std_480 = df['close'].rolling(480).std()
                    df['bb480_upper'] = rolling_mean_480 + (rolling_std_480 * 1.5)
                    
                    return df
                    
            simple_strategy = SimpleStrategy()
            
            # 지표 계산
            df_with_indicators = simple_strategy._calculate_technical_indicators(df_calc)
            print(f"   지표 계산 완료: {len(df_with_indicators)}행")
            
            # 조건 1 체크: MA80 < MA480
            current_ma80 = df_with_indicators['ma80'].iloc[-1]
            current_ma480 = df_with_indicators['ma480'].iloc[-1]
            condition1 = current_ma80 < current_ma480 if pd.notna(current_ma80) and pd.notna(current_ma480) else False
            print(f"   조건1 (MA80<MA480): {condition1}")
            
        except Exception as e:
            print(f"   C전략 직접 호출 실패: {e}")
    else:
        print("   데이터 부족으로 테스트 불가")
        
except Exception as e:
    print(f"전체 테스트 실패: {e}")
    import traceback
    traceback.print_exc()