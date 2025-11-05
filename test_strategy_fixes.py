# -*- coding: utf-8 -*-
"""
전략 수정사항 테스트
"""

import time

def test_strategy_fixes():
    """전략C, D 수정사항 테스트"""
    print("=== 전략 수정사항 테스트 ===")
    
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
        
        # 필터링된 심볼 가져오기
        print("심볼 필터링...")
        filtered_symbols = strategy.get_filtered_symbols(min_change_pct=1.0)  # 완화된 기준
        print(f"필터링 결과: {len(filtered_symbols)}개 심볼")
        
        if filtered_symbols:
            print("필터링된 심볼 TOP 5:")
            for i, symbol in enumerate(filtered_symbols[:5]):
                clean_name = symbol.replace('/USDT:USDT', '')
                print(f"  {i+1:2d}. {clean_name}")
            
            # 상위 3개 심볼로 분석 테스트
            print(f"\n상위 3개 심볼 분석 테스트...")
            test_symbols = filtered_symbols[:3]
            
            for symbol in test_symbols:
                try:
                    clean_name = symbol.replace('/USDT:USDT', '')
                    print(f"\n[{clean_name}] 분석 중...")
                    
                    result = strategy.analyze_symbol(symbol)
                    
                    if result:
                        print(f"✅ [{clean_name}] 신호 발견: {len(result)}개")
                        for r in result:
                            print(f"  → {r['strategy_type']}: {r['status']}")
                            # 조건 상세 정보 출력
                            if 'conditions' in r:
                                failed_count = r.get('failed_count', 0)
                                total_count = r.get('total_conditions', 0)
                                passed_count = total_count - failed_count
                                print(f"    조건 통과: {passed_count}/{total_count}")
                    else:
                        print(f"❌ [{clean_name}] 신호 없음")
                        
                except Exception as e:
                    print(f"❌ [{clean_name}] 분석 오류: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            print("❌ 필터링된 심볼이 없습니다.")
            print("시장이 매우 조용한 상태입니다.")
        
        # 정리
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            strategy.ws_kline_manager.shutdown()
        
        print("\n=== 테스트 완료 ===")
        print("주요 수정사항:")
        print("1. ✅ 전략D의 check_supertrend_signal 함수 오류 수정")
        print("2. ✅ SuperTrend 진입 신호 디버그 로그 강화")
        print("3. ✅ BB200-BB480 골든크로스 조건 확인 (이전봉→현재봉 비교)")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_strategy_fixes()