# -*- coding: utf-8 -*-
"""
통합 필터링 (4시간봉 Surge OR 상위 100위권) 테스트
"""

import time

def test_integrated_filtering():
    """통합 필터링 테스트"""
    try:
        print("=== 통합 필터링 테스트 (4h Surge OR Top100) ===")
        
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
        
        print("\n=== 통합 필터링 테스트 ===")
        
        # 심볼 필터링 실행
        filtered_symbols = strategy.get_filtered_symbols(min_change_pct=8.0)
        print(f"\n통합 필터링 결과: {len(filtered_symbols)}개 심볼")
        
        if filtered_symbols:
            print("필터링된 심볼 TOP 15:")
            for i, symbol in enumerate(filtered_symbols[:15]):
                symbol_name = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                print(f"  {i+1:2d}. {symbol_name}")
        
        # 정리
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            strategy.ws_kline_manager.shutdown()
        
        print("\n=== 통합 필터링 테스트 완료 ===")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_integrated_filtering()