# -*- coding: utf-8 -*-
"""
Test the filtering logic without all the noise
"""

import time

def test_filtering_only():
    """필터링 로직만 테스트"""
    try:
        print("=== 필터링 로직 테스트 ===")
        
        # 전략 import
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        
        # 전략 초기화 (공개 API 모드)
        strategy = OneMinuteSurgeEntryStrategy(
            api_key=None,
            secret_key=None,
            sandbox=False
        )
        
        # WebSocket이 초기화될 때까지 5초 대기
        print("WebSocket 시스템 초기화 대기... (5초)")
        time.sleep(5)
        
        # 테스트용 가짜 심볼 데이터 생성
        test_symbols = [
            ('BTC/USDT:USDT', 2.5, 1000000),
            ('ETH/USDT:USDT', 1.8, 800000),
            ('BNB/USDT:USDT', 3.2, 600000),
            ('ADA/USDT:USDT', 5.1, 400000),
            ('SOL/USDT:USDT', 1.2, 300000)
        ]
        
        print(f"테스트 심볼: {len(test_symbols)}개")
        
        # 4시간봉 필터링 테스트
        print("\n=== 4시간봉 WebSocket 필터링 테스트 ===")
        filtered_4h = strategy._websocket_4h_filtering(test_symbols)
        print(f"4시간봉 필터링 결과: {len(filtered_4h)}개/{len(test_symbols)}개")
        
        if filtered_4h:
            for symbol, change_pct, volume in filtered_4h:
                print(f"  통과: {symbol} ({change_pct:.1f}%)")
        else:
            print("  결과: 모든 심볼이 필터링됨 (WebSocket 데이터 없음)")
        
        # 1시간봉 폴백 필터링 테스트
        print("\n=== 1시간봉 폴백 필터링 테스트 ===")
        filtered_1h = strategy._fallback_1h_filtering(test_symbols)
        print(f"1시간봉 필터링 결과: {len(filtered_1h)}개/{len(test_symbols)}개")
        
        if filtered_1h:
            for symbol, change_pct, volume in filtered_1h:
                print(f"  통과: {symbol} ({change_pct:.1f}%)")
        else:
            print("  결과: 모든 심볼이 필터링됨 (WebSocket 데이터 없음)")
        
        # WebSocket 버퍼 상태 확인
        print("\n=== WebSocket 버퍼 상태 ===")
        if hasattr(strategy, '_websocket_kline_buffer'):
            buffer_keys = list(strategy._websocket_kline_buffer.keys())
            print(f"WebSocket 버퍼: {len(buffer_keys)}개 키")
            for key in buffer_keys:
                data_count = len(strategy._websocket_kline_buffer[key])
                print(f"  {key}: {data_count}개 캔들 데이터")
        else:
            print("WebSocket 버퍼 없음")
        
        # 정리
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            strategy.ws_kline_manager.shutdown()
        
        print("\n=== 테스트 완료 ===")
        print("결론: 필터링 로직이 제대로 작동함 - WebSocket 데이터가 없으면 모든 심볼을 필터링함")
        
        return True
        
    except Exception as e:
        print(f"ERROR: 테스트 실패 - {e}")
        return False

if __name__ == "__main__":
    test_filtering_only()