# -*- coding: utf-8 -*-
"""
새로운 15분봉 조건 테스트
"""
import os
import sys
import pandas as pd
import numpy as np

# 스크립트 디렉토리를 Python 경로에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

def test_new_15m_conditions():
    """새로운 15분봉 조건 테스트"""
    print("[INFO] 새로운 15분봉 조건 테스트 시작...")
    print("="*60)
    
    try:
        from fifteen_minute_mega_strategy import FifteenMinuteMegaStrategy
        
        # 전략 인스턴스 생성
        strategy = FifteenMinuteMegaStrategy(sandbox=False)
        print("\n[TEST 1] 전략 초기화 완료")
        
        # 가상 15분봉 데이터 생성 (조건 충족하도록)
        print("\n[TEST 2] 가상 15분봉 데이터 생성 중...")
        
        # 500개 15분봉 데이터 생성
        dates = pd.date_range('2023-01-01', periods=500, freq='15min')
        base_price = 100.0
        
        # 조건을 만족하는 패턴 생성
        data = []
        for i, date in enumerate(dates):
            # 기본적으로 상승 추세
            price_trend = base_price + (i * 0.1)
            
            # 노이즈 추가
            noise = np.random.uniform(-0.5, 0.5)
            
            open_price = price_trend + noise
            high_price = open_price + abs(noise) + 0.2
            low_price = open_price - abs(noise) - 0.1
            close_price = open_price + np.random.uniform(-0.3, 0.3)
            volume = np.random.uniform(100000, 1000000)
            
            data.append([
                int(date.timestamp() * 1000),
                open_price,
                high_price,
                low_price,
                close_price,
                volume
            ])
        
        # DataFrame 생성
        df_15m = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        print(f"   생성된 데이터: {len(df_15m)}개 15분봉")
        
        # 15분봉 조건 체크
        print("\n[TEST 3] 새로운 15분봉 조건 체크...")
        
        symbol = 'TEST/USDT:USDT'
        is_signal, conditions = strategy.check_fifteen_minute_mega_conditions(symbol, df_15m)
        
        print(f"\n[RESULT] 조건 체크 결과: {is_signal}")
        print("\n[CONDITIONS] 상세 조건:")
        for i, condition in enumerate(conditions, 1):
            print(f"   {i}. {condition}")
        
        if is_signal:
            print("\n✅ 새로운 15분봉 조건 충족!")
        else:
            print("\n❌ 새로운 15분봉 조건 미충족")
            
        return True
        
    except Exception as e:
        print(f"\n[ERROR] 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 함수"""
    print("="*60)
    print("새로운 15분봉 초필살기 조건 테스트")
    print("조건1: MA80-MA480 골든크로스")
    print("조건2: BB200상단-BB480상단 OR BB80상단-BB480상단 골든크로스") 
    print("조건3: MA5-MA20 골든크로스")
    print("조건4: BB200상단-MA480 상향돌파")
    print("="*60)
    
    success = test_new_15m_conditions()
    
    print("\n" + "="*60)
    if success:
        print("[SUCCESS] 새로운 15분봉 조건 테스트 완료")
    else:
        print("[FAILED] 테스트 실패")
    print("="*60)

if __name__ == "__main__":
    main()