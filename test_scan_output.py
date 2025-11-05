# -*- coding: utf-8 -*-
"""
스캔 결과 출력 테스트
"""

import time

def test_scan_output():
    """스캔 결과 출력 메시지 테스트"""
    try:
        print("=== 스캔 결과 출력 테스트 ===")
        
        # 전략 임포트
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        
        # 전략 초기화
        print("전략 초기화 중...")
        strategy = OneMinuteSurgeEntryStrategy(
            api_key=None,
            secret_key=None,
            sandbox=False
        )
        
        # 5초 대기
        print("WebSocket 초기화 대기... (5초)")
        time.sleep(5)
        
        print("\n=== 심볼 필터링 테스트 ===")
        
        # 심볼 필터링 실행
        filtered_symbols = strategy.get_filtered_symbols(min_change_pct=8.0)
        print(f"\n필터링된 심볼 수: {len(filtered_symbols)}개")
        
        if filtered_symbols:
            print("필터링된 심볼들:")
            for i, symbol in enumerate(filtered_symbols[:10]):
                symbol_name = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                print(f"  {i+1}. {symbol_name}")
        
        # 정리
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            strategy.ws_kline_manager.shutdown()
        
        print("\n=== 테스트 완료 ===")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_scan_output()