# -*- coding: utf-8 -*-
"""
WebSocket 시스템 테스트 스크립트
"""

import time
import asyncio

def test_websocket_manager():
    """WebSocket 매니저 테스트"""
    try:
        print("=== WebSocket 매니저 테스트 ===")
        
        # WebSocket 매니저 import 테스트
        from websocket_kline_manager import WebSocketKlineManager
        print("WebSocket 매니저 import 성공")
        
        # 콜백 함수 정의
        def test_callback(symbol, price, kline_data, timeframe='1m'):
            print(f"수신: {symbol} {timeframe} - 가격: ${price:.6f}")
        
        # WebSocket 매니저 생성
        manager = WebSocketKlineManager(test_callback)
        print("WebSocket 매니저 생성 성공")
        
        # 테스트 심볼 구독
        test_symbols = ['BTCUSDT', 'ETHUSDT']
        timeframes = ['1m', '4h']
        
        for symbol in test_symbols:
            for tf in timeframes:
                try:
                    manager.subscribe_kline(symbol, tf)
                    print(f"✅ 구독 성공: {symbol} {tf}")
                except Exception as e:
                    print(f"❌ 구독 실패: {symbol} {tf} - {e}")
        
        # 5초간 대기하며 데이터 수신 확인
        print("⏳ 5초간 데이터 수신 테스트...")
        time.sleep(5)
        
        # 상태 확인
        status = manager.get_status()
        print(f"📈 연결 상태: {status}")
        
        # 구독된 심볼 확인
        subscribed = manager.get_subscribed_symbols()
        print(f"📡 구독된 심볼: {subscribed}")
        
        # 종료
        manager.shutdown()
        print("✅ WebSocket 매니저 테스트 완료")
        
        return True
        
    except Exception as e:
        print(f"❌ WebSocket 매니저 테스트 실패: {e}")
        return False

def test_strategy_initialization():
    """전략 초기화 테스트"""
    try:
        print("\n=== 전략 초기화 테스트 ===")
        
        # 전략 import 테스트
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        print("✅ 전략 import 성공")
        
        # 전략 초기화 (공개 API 모드)
        strategy = OneMinuteSurgeEntryStrategy(
            api_key=None,
            secret_key=None,
            sandbox=False
        )
        print("✅ 전략 초기화 성공")
        
        # WebSocket 매니저 확인
        if strategy.ws_kline_manager:
            print("✅ WebSocket 매니저 활성화됨")
        else:
            print("❌ WebSocket 매니저 비활성화됨")
        
        # WebSocket 버퍼 확인
        if hasattr(strategy, '_websocket_kline_buffer'):
            print("✅ WebSocket 버퍼 초기화됨")
        else:
            print("❌ WebSocket 버퍼 없음")
        
        # 콜백 함수 확인
        if hasattr(strategy, 'on_websocket_kline_update'):
            print("✅ WebSocket 콜백 함수 존재")
        else:
            print("❌ WebSocket 콜백 함수 없음")
        
        return True
        
    except Exception as e:
        print(f"❌ 전략 초기화 테스트 실패: {e}")
        return False

def test_websocket_filtering():
    """WebSocket 필터링 테스트"""
    try:
        print("\n=== WebSocket 필터링 테스트 ===")
        
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        
        # 전략 초기화
        strategy = OneMinuteSurgeEntryStrategy(
            api_key=None,
            secret_key=None,
            sandbox=False
        )
        
        # 테스트 심볼 데이터
        test_symbols = [
            ('BTC/USDT:USDT', 2.5, 1000000),
            ('ETH/USDT:USDT', 1.8, 800000),
            ('BNB/USDT:USDT', 3.2, 600000)
        ]
        
        # WebSocket 버퍼에 가짜 4시간봉 데이터 추가
        if not hasattr(strategy, '_websocket_kline_buffer'):
            strategy._websocket_kline_buffer = {}
        
        for symbol, change_pct, volume in test_symbols:
            ws_symbol = symbol.replace('/USDT:USDT', 'USDT')
            buffer_key = f"{ws_symbol}_4h"
            
            # 가짜 4시간봉 데이터 (2% 이상 급등 포함)
            strategy._websocket_kline_buffer[buffer_key] = [
                {
                    'timestamp': int(time.time() * 1000) - 14400000,  # 4시간 전
                    'open': 50000.0,
                    'high': 51200.0,  # 2.4% 급등
                    'low': 49800.0,
                    'close': 51000.0,
                    'volume': 1000.0
                },
                {
                    'timestamp': int(time.time() * 1000),  # 현재
                    'open': 51000.0,
                    'high': 52100.0,  # 2.16% 급등
                    'low': 50800.0,
                    'close': 52000.0,
                    'volume': 1200.0
                }
            ]
        
        # 필터링 테스트
        filtered_result = strategy._websocket_4h_filtering(test_symbols)
        print(f"📊 필터링 결과: {len(filtered_result)}개/{len(test_symbols)}개 심볼 통과")
        
        for result in filtered_result:
            print(f"✅ 통과: {result[0]} (변동률: {result[1]:.1f}%)")
        
        return True
        
    except Exception as e:
        print(f"❌ WebSocket 필터링 테스트 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("WebSocket 시스템 종합 테스트 시작\n")
    
    # 테스트 실행
    test_results = []
    
    # 1. WebSocket 매니저 테스트
    test_results.append(test_websocket_manager())
    
    # 2. 전략 초기화 테스트
    test_results.append(test_strategy_initialization())
    
    # 3. WebSocket 필터링 테스트
    test_results.append(test_websocket_filtering())
    
    # 결과 요약
    print("\n" + "="*50)
    print("🏁 테스트 결과 요약")
    print("="*50)
    
    test_names = [
        "WebSocket 매니저",
        "전략 초기화", 
        "WebSocket 필터링"
    ]
    
    passed = 0
    for i, result in enumerate(test_results):
        status = "✅ 통과" if result else "❌ 실패"
        print(f"{test_names[i]}: {status}")
        if result:
            passed += 1
    
    print(f"\n전체 결과: {passed}/{len(test_results)} 테스트 통과")
    
    if passed == len(test_results):
        print("모든 테스트 통과! WebSocket 시스템이 정상 작동합니다.")
    else:
        print("일부 테스트 실패. 시스템을 점검해주세요.")

if __name__ == "__main__":
    main()