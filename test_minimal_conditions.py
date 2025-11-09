# -*- coding: utf-8 -*-
"""
최소한의 조건 테스트 (유니코드 에러 회피)
"""
import os
import sys
import pandas as pd
import numpy as np

# 스크립트 디렉토리를 Python 경로에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

def test_conditions_directly():
    """조건 함수만 직접 테스트"""
    print("[INFO] 4개 조건 직접 테스트...")
    
    try:
        # 가상 데이터 생성
        dates = pd.date_range('2023-01-01', periods=500, freq='15min')
        data = []
        for i, date in enumerate(dates):
            price = 100 + i * 0.1
            data.append([
                int(date.timestamp() * 1000),
                price, price + 1, price - 1, price + 0.5, 100000
            ])
        
        df_15m = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        print(f"[DATA] 생성된 데이터: {len(df_15m)}개 15분봉")
        
        # 직접 조건 체크 함수만 import
        from fifteen_minute_mega_strategy import FifteenMinuteMegaStrategy
        
        # 최소한의 객체 생성 (실제 API 호출 없이)
        class MockStrategy:
            def __init__(self):
                self.logger = self
                
            def error(self, msg):
                print(f"[ERROR] {msg}")
                
            def debug(self, msg): 
                print(f"[DEBUG] {msg}")
                
            def _write_debug_log(self, msg):
                print(f"[DEBUG] {msg}")
                
            def calculate_indicators(self, df):
                """가상 지표 계산"""
                df_calc = df.copy()
                
                # 이동평균 계산
                df_calc['ma5'] = df_calc['close'].rolling(window=5).mean()
                df_calc['ma20'] = df_calc['close'].rolling(window=20).mean()
                df_calc['ma80'] = df_calc['close'].rolling(window=80).mean()
                df_calc['ma480'] = df_calc['close'].rolling(window=480).mean()
                
                # BB 계산
                for period, std in [(200, 2.0), (480, 1.5)]:
                    bb_ma = df_calc['close'].rolling(window=period).mean()
                    bb_std = df_calc['close'].rolling(window=period).std()
                    df_calc[f'bb{period}_upper'] = bb_ma + (bb_std * std)
                    df_calc[f'bb{period}_lower'] = bb_ma - (bb_std * std)
                    df_calc[f'bb{period}_middle'] = bb_ma
                
                return df_calc
        
        # Mock 객체로 조건 체크
        mock_strategy = MockStrategy()
        
        # FifteenMinuteMegaStrategy의 조건 체크 메소드를 Mock에 바인딩
        mock_strategy.check_fifteen_minute_mega_conditions = FifteenMinuteMegaStrategy.check_fifteen_minute_mega_conditions.__get__(mock_strategy)
        
        # 조건 체크 실행
        is_signal, conditions = mock_strategy.check_fifteen_minute_mega_conditions('TEST/USDT:USDT', df_15m)
        
        print()
        print("="*60)
        print(f"[RESULT] 신호 감지: {is_signal}")
        print("="*60)
        print("[CONDITIONS] 4개 조건별 결과:")
        for i, condition in enumerate(conditions, 1):
            print(f"  {i}. {condition}")
        
        print()
        print("[SUMMARY] 새로운 4개 조건 시스템:")
        print("  1. MA80-MA480 골든크로스 (200봉 이내)")
        print("  2. BB 골든크로스 (BB200/BB80 vs BB480, 200봉 이내)")
        print("  3. MA5-MA20 골든크로스 (10봉 이내)")
        print("  4. BB200상단선이 MA480 상향돌파 (250봉 이내)")
        print()
        print("[SUCCESS] 4개 조건 테스트 완료!")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("="*60)
    print("15분봉 새로운 4개 조건 직접 테스트")
    print("="*60)
    
    success = test_conditions_directly()
    
    print()
    print("="*60)
    if success:
        print("[SUCCESS] 모든 테스트 통과!")
    else:
        print("[FAILED] 테스트 실패")
    print("="*60)