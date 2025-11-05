# -*- coding: utf-8 -*-
"""
전략C 조건 체크 디버깅
"""

import time

def test_strategy_c_conditions():
    """전략C 조건들이 0/3으로 나오는 문제 디버깅"""
    print("=== 전략C 조건 체크 디버깅 ===")
    
    try:
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        
        strategy = OneMinuteSurgeEntryStrategy(None, None, False)
        
        # 관심종목에 포함된 심볼들 테스트
        test_symbols = [
            'AVAAI/USDT:USDT', 'SQD/USDT:USDT', 'JELLYJELLY/USDT:USDT', 
            'XPIN/USDT:USDT', 'YALA/USDT:USDT'
        ]
        
        print("대기 중... (10초)")
        time.sleep(10)
        
        for symbol in test_symbols[:2]:  # 처음 2개만 테스트
            clean_name = symbol.replace('/USDT:USDT', '')
            print(f"\n--- {clean_name} 분석 ---")
            
            try:
                results = strategy.analyze_symbol(symbol)
                
                if results:
                    for result in results:
                        print(f"전략: {result['strategy_type']}")
                        print(f"상태: {result['status']}")
                        if 'conditions' in result:
                            print("조건들:")
                            for condition in result['conditions']:
                                print(f"  {condition}")
                else:
                    print("분석 결과 없음")
                    
            except Exception as e:
                print(f"분석 실패: {e}")
        
        # 정리
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            strategy.ws_kline_manager.shutdown()
        
        print("\n디버깅 완료")
        
    except Exception as e:
        print(f"테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_strategy_c_conditions()