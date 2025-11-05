# -*- coding: utf-8 -*-
"""
조용한 디버깅 테스트 - 핵심 스캔 결과만 출력
"""

import time

def test_quiet_debugging():
    """조용한 디버깅 테스트"""
    try:
        print("=== 조용한 디버깅 모드 테스트 ===")
        
        # 전략 임포트
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        
        # 전략 초기화 (스캔 모드로)
        print("전략 초기화 중... (공개 API 모드)")
        strategy = OneMinuteSurgeEntryStrategy(
            api_key=None,
            secret_key=None,
            sandbox=False
        )
        
        # 스캔 모드 활성화
        strategy._scan_mode = True
        
        # 5초 대기
        print("WebSocket 초기화 대기... (5초)")
        time.sleep(5)
        
        print("\n=== 필터링된 심볼 조회 (조용한 모드) ===")
        
        # 필터링된 심볼 조회 - 이제 verbose 메시지 없이 깔끔해야 함
        filtered_symbols = strategy.get_filtered_symbols(min_change_pct=8.0)
        
        print(f"\n필터링 결과: {len(filtered_symbols)}개 심볼")
        
        if filtered_symbols:
            print("상위 5개 심볼:")
            for i, symbol in enumerate(filtered_symbols[:5]):
                symbol_name = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                print(f"  {i+1}. {symbol_name}")
        
        print("\n=== 조용한 스캔 테스트 ===")
        
        # 소수 심볼로 스캔 테스트
        if filtered_symbols:
            test_symbols = filtered_symbols[:3]  # 상위 3개만
            print(f"테스트 심볼: {[s.replace('/USDT:USDT', '') for s in test_symbols]}")
            
            # 스캔 실행 - 이제 verbose 메시지 없이 깔끔해야 함
            results = strategy.scan_symbols(test_symbols)
            
            print(f"\n스캔 완료: {len(results) if results else 0}개 진입신호")
        
        # 정리
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            strategy.ws_kline_manager.shutdown()
        
        print("\n=== 테스트 완료 - 조용한 디버깅 확인됨 ===")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_quiet_debugging()