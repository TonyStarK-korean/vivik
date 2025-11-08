# -*- coding: utf-8 -*-
"""
Simple WebSocket System Test
"""

import time

def test_strategy_websocket():
    """전략의 WebSocket 시스템 테스트"""
    try:
        print("=== WebSocket Initialization 테스트 ===")
        
        # 전략 import
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        print("전략 import Success")
        
        # 전략 초기화 (공개 API 모드)
        strategy = OneMinuteSurgeEntryStrategy(
            api_key=None,
            secret_key=None,
            sandbox=False
        )
        print("전략 Initialization Success")
        
        # WebSocket 매니저 확인
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            print("SUCCESS: WebSocket 매니저 Activated됨")
            
            # 4시간봉 구독 테스트
            test_symbols = ['BTCUSDT', 'ETHUSDT']
            for symbol in test_symbols:
                try:
                    strategy.ws_kline_manager.subscribe_kline(symbol, '4h')
                    print(f"SUCCESS: {symbol} 4시간봉 Subscribed Complete")
                except Exception as e:
                    print(f"ERROR: {symbol} 4시간봉 Subscribed Failed - {e}")
            
            # 2초 대기
            print("2초간 데이터 Received Waiting...")
            time.sleep(2)
            
            # 상태 확인
            status = strategy.ws_kline_manager.get_status()
            print(f"Connected 상태: {status}")
            
            subscribed = strategy.ws_kline_manager.get_subscribed_symbols()
            print(f"Subscribed된 심볼: {subscribed}")
            
            # WebSocket 버퍼 확인
            if hasattr(strategy, '_websocket_kline_buffer'):
                buffer_keys = list(strategy._websocket_kline_buffer.keys())
                print(f"WebSocket Buffer: {len(buffer_keys)} 키")
                for key in buffer_keys[:5]:  # 최대 5개만 표시
                    data_count = len(strategy._websocket_kline_buffer[key])
                    print(f"  {key}: {data_count} 데이터")
            else:
                print("ERROR: WebSocket Buffer 없음")
            
            # 종료
            strategy.ws_kline_manager.shutdown()
            print("WebSocket System 정상 종료")
            
        else:
            print("ERROR: WebSocket 매니저 비Activated됨")
            
        return True
        
    except Exception as e:
        print(f"ERROR: 테스트 Failed - {e}")
        return False

if __name__ == "__main__":
    print("Simple WebSocket System Test Starting")
    result = test_strategy_websocket()
    print(f"테스트 결과: {'Success' if result else 'Failed'}")