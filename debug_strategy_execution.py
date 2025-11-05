# -*- coding: utf-8 -*-
"""
전략 실행 상태 진단 스크립트
"""

import time
from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy

def diagnose_strategy():
    """전략 실행 상태 진단"""
    print("=== 전략 실행 상태 진단 ===")
    
    try:
        # 전략 초기화
        print("1. 전략 초기화 중...")
        strategy = OneMinuteSurgeEntryStrategy(
            api_key=None,
            secret_key=None,
            sandbox=False
        )
        
        # WebSocket 상태 확인
        print("\n2. WebSocket 상태 확인...")
        print(f"   - WebSocket 관리자: {'있음' if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager else '없음'}")
        
        if hasattr(strategy, '_websocket_kline_buffer'):
            buffer_count = len(strategy._websocket_kline_buffer)
            print(f"   - WebSocket 버퍼: {buffer_count}개 키")
            
            # 4시간봉과 1시간봉 키 개수 확인
            h4_keys = [k for k in strategy._websocket_kline_buffer.keys() if k.endswith('_4h')]
            h1_keys = [k for k in strategy._websocket_kline_buffer.keys() if k.endswith('_1h')]
            print(f"   - 4시간봉 데이터: {len(h4_keys)}개 심볼")
            print(f"   - 1시간봉 데이터: {len(h1_keys)}개 심볼")
        else:
            print("   - WebSocket 버퍼: 없음")
        
        # 심볼 필터링 테스트
        print("\n3. 심볼 필터링 테스트...")
        time.sleep(2)  # 데이터 수집 대기
        
        filtered_symbols = strategy.get_filtered_symbols(min_change_pct=5.0)  # 낮은 기준으로 테스트
        print(f"   - 필터링된 심볼: {len(filtered_symbols)}개")
        
        if filtered_symbols:
            print(f"   - TOP 5: {filtered_symbols[:5]}")
        
        # 개별 심볼 분석 테스트
        print("\n4. 개별 심볼 분석 테스트...")
        test_symbols = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'BNB/USDT:USDT']
        
        for symbol in test_symbols:
            try:
                result = strategy.analyze_symbol(symbol)
                status = "신호 있음" if result else "신호 없음"
                print(f"   - {symbol}: {status}")
                
                if result:
                    for r in result:
                        print(f"     → {r['strategy_type']}: {r['status']}")
                        
            except Exception as e:
                print(f"   - {symbol}: 오류 - {e}")
        
        # API 상태 확인
        print("\n5. API 상태 확인...")
        try:
            # 간단한 API 호출 테스트
            markets = strategy.exchange.load_markets()
            print(f"   - 거래소 연결: 정상 ({len(markets)}개 마켓)")
            
            # Rate Limit 상태
            rate_limited = getattr(strategy, '_api_rate_limited', False)
            print(f"   - Rate Limit 상태: {'제한됨' if rate_limited else '정상'}")
            
        except Exception as e:
            print(f"   - 거래소 연결: 오류 - {e}")
        
        # WebSocket 실시간 데이터 확인
        print("\n6. 실시간 데이터 수신 확인...")
        print("   (3초간 데이터 수신 대기...)")
        
        if hasattr(strategy, '_websocket_kline_buffer'):
            initial_count = len(strategy._websocket_kline_buffer)
            time.sleep(3)
            final_count = len(strategy._websocket_kline_buffer)
            
            if final_count > initial_count:
                print(f"   - 실시간 데이터: 수신 중 ({final_count - initial_count}개 추가)")
            else:
                print(f"   - 실시간 데이터: 수신 없음 (버퍼 변화 없음)")
                print("     → WebSocket 연결 문제 가능성")
        
        print("\n=== 진단 완료 ===")
        
        # 정리
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            strategy.ws_kline_manager.shutdown()
            
    except Exception as e:
        print(f"❌ 진단 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnose_strategy()