#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
필터링 수정 테스트
"""
import time

def test_filtering_fix():
    """필터링 수정 테스트"""
    try:
        print("=== 필터링 수정 테스트 ===")
        
        # 전략 임포트
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        
        # 전략 초기화
        print("전략 초기화 중...")
        strategy = OneMinuteSurgeEntryStrategy(
            api_key=None,
            secret_key=None,
            sandbox=False
        )
        
        # WebSocket 데이터 수집 대기
        print("WebSocket 데이터 수집 대기... (3초)")
        time.sleep(3)
        
        # 테스트 심볼 (futures 형식)
        test_symbols = [
            ('BTC/USDT:USDT', 2.5, 1000000),
            ('ETH/USDT:USDT', 1.8, 800000),
            ('BNB/USDT:USDT', 3.2, 600000)
        ]
        
        print(f"\n테스트 심볼: {len(test_symbols)}개")
        for symbol, change, volume in test_symbols:
            print(f"  {symbol} (변화율: {change}%, 거래량: {volume})")
        
        # 현재 버퍼 상태 확인
        print(f"\n=== WebSocket 버퍼 상태 ===")
        if hasattr(strategy, '_websocket_kline_buffer'):
            buffer = strategy._websocket_kline_buffer
            print(f"총 버퍼 키: {len(buffer)}개")
            
            # 4시간봉과 1시간봉 키 확인
            h4_keys = [k for k in buffer.keys() if k.endswith('_4h')]
            h1_keys = [k for k in buffer.keys() if k.endswith('_1h')]
            
            print(f"4시간봉 키: {len(h4_keys)}개")
            print(f"1시간봉 키: {len(h1_keys)}개")
            
            # 테스트 심볼에 대응하는 키가 있는지 확인
            print(f"\n=== 변환된 키 존재 확인 ===")
            for symbol, _, _ in test_symbols:
                ws_symbol = symbol.replace('/USDT:USDT', 'USDT').replace('/', '')
                key_4h = f"{ws_symbol}_4h"
                key_1h = f"{ws_symbol}_1h"
                
                exists_4h = key_4h in buffer
                exists_1h = key_1h in buffer
                
                print(f"{symbol} -> {ws_symbol}")
                print(f"  4h 키 ({key_4h}): {'존재' if exists_4h else '없음'}")
                print(f"  1h 키 ({key_1h}): {'존재' if exists_1h else '없음'}")
                
                if exists_4h:
                    data_count = len(buffer[key_4h])
                    print(f"  4h 데이터: {data_count}개")
                if exists_1h:
                    data_count = len(buffer[key_1h])
                    print(f"  1h 데이터: {data_count}개")
        else:
            print("❌ WebSocket 버퍼 없음")
            return
        
        print(f"\n=== 4시간봉 필터링 테스트 ===")
        try:
            filtered_4h = strategy._websocket_4h_filtering(test_symbols)
            print(f"4시간봉 필터링 결과: {len(filtered_4h)}개")
            for result in filtered_4h:
                print(f"  통과: {result[0]} (변화율: {result[1]}%)")
        except Exception as e:
            print(f"❌ 4시간봉 필터링 오류: {e}")
        
        print(f"\n=== 1시간봉 폴백 필터링 테스트 ===")
        try:
            filtered_1h = strategy._fallback_1h_filtering(test_symbols)
            print(f"1시간봉 폴백 결과: {len(filtered_1h)}개")
            for result in filtered_1h:
                print(f"  통과: {result[0]} (변화율: {result[1]}%)")
        except Exception as e:
            print(f"❌ 1시간봉 필터링 오류: {e}")
        
        # 정리
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            strategy.ws_kline_manager.shutdown()
        
        print("\n=== 테스트 완료 ===")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_filtering_fix()