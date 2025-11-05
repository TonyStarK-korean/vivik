# -*- coding: utf-8 -*-
"""
Simple WebSocket System Test
"""

import time

def test_strategy_websocket():
    """전략의 WebSocket 시스템 테스트"""
    try:
        print("=== WebSocket 초기화 테스트 ===")
        
        # 전략 import
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        print("전략 import 성공")
        
        # 전략 초기화 (공개 API 모드)
        strategy = OneMinuteSurgeEntryStrategy(
            api_key=None,
            secret_key=None,
            sandbox=False
        )
        print("전략 초기화 성공")
        
        # WebSocket 매니저 확인
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            print("SUCCESS: WebSocket 매니저 활성화됨")
            
            # 4시간봉 구독 테스트
            test_symbols = ['BTCUSDT', 'ETHUSDT']
            for symbol in test_symbols:
                try:
                    strategy.ws_kline_manager.subscribe_kline(symbol, '4h')
                    print(f"SUCCESS: {symbol} 4시간봉 구독 완료")
                except Exception as e:
                    print(f"ERROR: {symbol} 4시간봉 구독 실패 - {e}")
            
            # 2초 대기
            print("2초간 데이터 수신 대기...")
            time.sleep(2)
            
            # 상태 확인
            status = strategy.ws_kline_manager.get_status()
            print(f"연결 상태: {status}")
            
            subscribed = strategy.ws_kline_manager.get_subscribed_symbols()
            print(f"구독된 심볼: {subscribed}")
            
            # WebSocket 버퍼 확인
            if hasattr(strategy, '_websocket_kline_buffer'):
                buffer_keys = list(strategy._websocket_kline_buffer.keys())
                print(f"WebSocket 버퍼: {len(buffer_keys)}개 키")
                for key in buffer_keys[:5]:  # 최대 5개만 표시
                    data_count = len(strategy._websocket_kline_buffer[key])
                    print(f"  {key}: {data_count}개 데이터")
            else:
                print("ERROR: WebSocket 버퍼 없음")
            
            # 종료
            strategy.ws_kline_manager.shutdown()
            print("WebSocket 시스템 정상 종료")
            
        else:
            print("ERROR: WebSocket 매니저 비활성화됨")
            
        return True
        
    except Exception as e:
        print(f"ERROR: 테스트 실패 - {e}")
        return False

if __name__ == "__main__":
    print("Simple WebSocket System Test 시작")
    result = test_strategy_websocket()
    print(f"테스트 결과: {'성공' if result else '실패'}")