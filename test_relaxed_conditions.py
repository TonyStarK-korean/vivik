# -*- coding: utf-8 -*-
"""
완화된 조건으로 전략 테스트
"""

import time

def test_relaxed_strategy():
    """완화된 조건으로 전략 테스트"""
    print("=== 완화된 조건으로 전략 테스트 ===")
    
    try:
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        
        # 전략 초기화
        print("전략 초기화 중...")
        strategy = OneMinuteSurgeEntryStrategy(
            api_key=None,
            secret_key=None,
            sandbox=False
        )
        
        # 데이터 수집 대기
        print("데이터 수집 대기... (5초)")
        time.sleep(5)
        
        # 완화된 조건으로 필터링
        print("완화된 조건으로 심볼 필터링...")
        print("- 변동률 기준: 8% → 3%")
        print("- 4시간봉 급등: 2% → 1%")
        
        filtered_symbols = strategy.get_filtered_symbols(min_change_pct=3.0)
        print(f"필터링 결과: {len(filtered_symbols)}개 심볼")
        
        if filtered_symbols:
            print("필터링된 심볼 TOP 10:")
            for i, symbol in enumerate(filtered_symbols[:10]):
                clean_name = symbol.replace('/USDT:USDT', '')
                print(f"  {i+1:2d}. {clean_name}")
            
            # 상위 3개 심볼로 분석 테스트
            print(f"\n상위 3개 심볼 분석 테스트...")
            test_symbols = filtered_symbols[:3]
            
            for symbol in test_symbols:
                try:
                    result = strategy.analyze_symbol(symbol)
                    clean_name = symbol.replace('/USDT:USDT', '')
                    
                    if result:
                        print(f"[{clean_name}] 신호 발견: {len(result)}개")
                        for r in result:
                            print(f"  → {r['strategy_type']}: {r['status']}")
                    else:
                        print(f"[{clean_name}] 신호 없음")
                        
                except Exception as e:
                    print(f"[{symbol}] 분석 오류: {e}")
        else:
            print("❌ 필터링된 심볼이 없습니다.")
            print("시장이 매우 조용한 상태입니다.")
        
        # 정리
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            strategy.ws_kline_manager.shutdown()
        
        print("\n=== 테스트 완료 ===")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_relaxed_strategy()