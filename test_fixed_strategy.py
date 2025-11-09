# -*- coding: utf-8 -*-
"""
수정된 전략 테스트
"""

import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from fifteen_minute_mega_strategy import FifteenMinuteMegaStrategy

def main():
    """수정된 전략 테스트"""
    try:
        print("🚀 수정된 15분봉 초필살기 전략 테스트")
        print("="*60)
        
        # 전략 초기화
        strategy = FifteenMinuteMegaStrategy(sandbox=False)
        
        print("📊 APR/USDT:USDT 조건 체크 중...")
        
        # APR 데이터 조회
        symbol = 'APR/USDT:USDT'
        df_15m = strategy.get_ohlcv_data(symbol, '15m', limit=500)
        
        if df_15m is None or len(df_15m) < 500:
            print("❌ 데이터 조회 실패")
            return
        
        print(f"✅ 데이터 조회 완료: {len(df_15m)}개 봉")
        
        # 조건 체크
        is_signal, conditions = strategy.check_fifteen_minute_mega_conditions(symbol, df_15m)
        
        print("\n🔍 조건 체크 결과:")
        for condition in conditions:
            if "True" in str(condition):
                print(f"✅ {condition}")
            elif "False" in str(condition):
                print(f"❌ {condition}")
            else:
                print(f"ℹ️ {condition}")
        
        print(f"\n🎯 최종 결과: {is_signal}")
        if is_signal:
            print("✅ APR은 15분봉 초필살기 조건을 충족합니다!")
        else:
            print("❌ APR은 15분봉 초필살기 조건을 충족하지 않습니다.")
        
    except Exception as e:
        print(f"❌ 테스트 실행 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()