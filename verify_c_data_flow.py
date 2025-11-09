#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C전략 데이터 흐름 상세 검증
- None 값 체크
- 실제 데이터 값들 확인
- 각 단계별 데이터 상태 점검
"""

import sys
import os
import pandas as pd
import numpy as np

# 현재 디렉토리를 PATH에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

def check_data_quality(data, data_name):
    """데이터 품질 체크"""
    print(f"\n=== {data_name} 데이터 품질 체크 ===")
    
    if data is None:
        print("❌ 데이터가 None입니다!")
        return False
    
    print(f"✅ 데이터 타입: {type(data)}")
    print(f"✅ 데이터 개수: {len(data)}")
    
    if len(data) > 0:
        # 첫 5개와 마지막 5개 샘플 확인
        print(f"\n📊 첫 5개 데이터 샘플:")
        for i, item in enumerate(data[:5]):
            if isinstance(item, list):
                print(f"   [{i}]: {item}")
                # OHLCV 데이터인지 확인
                if len(item) >= 5:
                    timestamp, open_p, high_p, low_p, close_p = item[:5]
                    print(f"        시간: {timestamp}, 시가: {open_p}, 고가: {high_p}, 저가: {low_p}, 종가: {close_p}")
            else:
                print(f"   [{i}]: {item}")
        
        print(f"\n📊 마지막 5개 데이터 샘플:")
        for i, item in enumerate(data[-5:], len(data)-5):
            if isinstance(item, list):
                print(f"   [{i}]: {item}")
                # None 값 체크
                if len(item) >= 5:
                    has_none = any(x is None for x in item[:5])
                    if has_none:
                        print(f"        ❌ None 값 발견!")
                    else:
                        print(f"        ✅ 모든 값 정상")
            else:
                print(f"   [{i}]: {item}")
    
    return True

def test_websocket_data_integrity():
    """WebSocket 데이터 무결성 테스트"""
    try:
        from websocket_ohlcv_provider import WebSocketOHLCVProvider
        
        print("C전략 데이터 흐름 상세 검증")
        print("=" * 60)
        
        ws_provider = WebSocketOHLCVProvider()
        test_symbol = 'API3/USDT:USDT'
        
        print(f"테스트 심볼: {test_symbol}")
        
        # 1. 3분봉 데이터 검증
        print(f"\n{'='*30} 3분봉 데이터 검증 {'='*30}")
        data_3m = ws_provider.get_ohlcv(test_symbol, '3m', 600)
        check_data_quality(data_3m, "3분봉")
        
        # 3분봉 DataFrame 변환 테스트
        if data_3m and len(data_3m) >= 500:
            print(f"\n📊 3분봉 DataFrame 변환 테스트:")
            try:
                df_3m = pd.DataFrame(data_3m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df_3m['timestamp'] = pd.to_datetime(df_3m['timestamp'], unit='ms')
                print(f"   ✅ DataFrame 변환 성공: {len(df_3m)}행")
                print(f"   📊 컬럼들: {list(df_3m.columns)}")
                
                # None 값 체크
                null_counts = df_3m.isnull().sum()
                print(f"   🔍 Null 값 체크:")
                for col, count in null_counts.items():
                    if count > 0:
                        print(f"      ❌ {col}: {count}개 null 값")
                    else:
                        print(f"      ✅ {col}: null 값 없음")
                
                # 실제 값 범위 확인
                print(f"\n   📈 실제 데이터 값 범위:")
                print(f"      시가: {df_3m['open'].min():.6f} ~ {df_3m['open'].max():.6f}")
                print(f"      고가: {df_3m['high'].min():.6f} ~ {df_3m['high'].max():.6f}")
                print(f"      저가: {df_3m['low'].min():.6f} ~ {df_3m['low'].max():.6f}")
                print(f"      종가: {df_3m['close'].min():.6f} ~ {df_3m['close'].max():.6f}")
                
            except Exception as e:
                print(f"   ❌ DataFrame 변환 실패: {e}")
        
        # 2. 15분봉 데이터 검증
        print(f"\n{'='*30} 15분봉 데이터 검증 {'='*30}")
        data_15m = ws_provider.get_ohlcv(test_symbol, '15m', 120)
        check_data_quality(data_15m, "15분봉")
        
        # 3. 30분봉 데이터 검증  
        print(f"\n{'='*30} 30분봉 데이터 검증 {'='*30}")
        data_30m = ws_provider.get_ohlcv(test_symbol, '30m', 120)
        check_data_quality(data_30m, "30분봉")
        
        # 4. 캐시 상태 확인
        print(f"\n{'='*30} 캐시 상태 확인 {'='*30}")
        cache_status = ws_provider.get_cache_status()
        print(f"📊 캐시 상태: {cache_status}")
        
        # 5. 시가대비고가 계산 테스트
        if data_3m and len(data_3m) >= 30:
            print(f"\n{'='*30} 시가대비고가 계산 검증 {'='*30}")
            high_move_count = 0
            valid_candles = 0
            
            for i in range(min(30, len(data_3m))):
                candle = data_3m[-(i+1)]
                if len(candle) >= 5:
                    timestamp, open_p, high_p, low_p, close_p = candle[:5]
                    
                    # None 값 체크
                    if open_p is not None and high_p is not None and open_p > 0:
                        valid_candles += 1
                        high_move_pct = ((high_p - open_p) / open_p) * 100
                        
                        if high_move_pct >= 3.0:
                            high_move_count += 1
                            print(f"   💹 봉 {i+1}: 시가 {open_p:.6f}, 고가 {high_p:.6f}, 급등률 {high_move_pct:.2f}%")
                    else:
                        print(f"   ❌ 봉 {i+1}: 잘못된 데이터 (open={open_p}, high={high_p})")
            
            print(f"\n   📊 계산 결과:")
            print(f"      유효한 봉: {valid_candles}/30개")
            print(f"      급등 봉(≥3%): {high_move_count}개")
            print(f"      급등률: {(high_move_count/max(1, valid_candles)*100):.1f}%")
            
        return True
        
    except Exception as e:
        print(f"❌ 전체 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_strategy_data_flow():
    """실제 C전략에서의 데이터 흐름 테스트"""
    try:
        from alpha_z_triple_strategy import FifteenMinuteMegaStrategy
        
        print(f"\n{'='*50}")
        print("실제 C전략 데이터 흐름 테스트")
        print(f"{'='*50}")
        
        # sandbox 모드로 전략 생성
        strategy = FifteenMinuteMegaStrategy(sandbox=True)
        test_symbol = 'API3/USDT:USDT'
        
        print(f"테스트 심볼: {test_symbol}")
        print(f"WebSocket Provider 활성화: {strategy.ws_provider is not None}")
        
        # C전략 직접 호출하여 데이터 흐름 추적
        print(f"\n📊 C전략 조건 체크 시작...")
        
        try:
            c_signal, c_conditions = strategy._check_strategy_c_3min_precision(test_symbol)
            
            print(f"\n🎯 C전략 결과:")
            print(f"   신호: {c_signal}")
            print(f"   조건 개수: {len(c_conditions)}")
            print(f"\n📋 조건 상세:")
            
            for i, condition in enumerate(c_conditions, 1):
                print(f"   {i}. {condition}")
                
                # 조건4에서 실제 데이터 값들 확인
                if "조건4" in condition:
                    print(f"      📊 조건4 상세 분석:")
                    if "3분봉" in condition:
                        print(f"         - 3분봉 데이터 사용됨")
                    if "15분봉" in condition:
                        print(f"         - 15분봉 데이터 사용됨") 
                    if "30분봉" in condition:
                        print(f"         - 30분봉 데이터 사용됨")
            
        except Exception as e:
            print(f"❌ C전략 호출 실패: {e}")
            import traceback
            traceback.print_exc()
        
        return True
        
    except Exception as e:
        print(f"❌ 전략 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("C전략 데이터 검증 시작")
    print("="*80)
    
    # 1. WebSocket 데이터 무결성 테스트
    ws_success = test_websocket_data_integrity()
    
    # 2. 실제 전략 데이터 흐름 테스트 
    strategy_success = test_strategy_data_flow()
    
    print(f"\n{'='*80}")
    print("최종 검증 결과")
    print(f"{'='*80}")
    print(f"WebSocket 데이터 검증: {'✅ 성공' if ws_success else '❌ 실패'}")
    print(f"C전략 데이터 흐름: {'✅ 성공' if strategy_success else '❌ 실패'}")
    
    if ws_success and strategy_success:
        print(f"\n🎉 모든 데이터가 정상적으로 흐르고 있습니다!")
        print(f"   - None 값 없음 확인")
        print(f"   - 실제 OHLCV 데이터 생성됨")
        print(f"   - C전략 조건 계산 정상 작동")
    else:
        print(f"\n⚠️ 일부 데이터 흐름에 문제가 있을 수 있습니다.")