# -*- coding: utf-8 -*-
"""
빠른 WebSocket 진단
"""

import time

def quick_diagnosis():
    """빠른 WebSocket 상태 진단"""
    print("=== 빠른 WebSocket 진단 ===")
    
    try:
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        
        print("전략 초기화 중...")
        strategy = OneMinuteSurgeEntryStrategy(
            api_key=None,
            secret_key=None,
            sandbox=False
        )
        
        # 1초 대기 후 상태 확인
        time.sleep(2)
        
        # WebSocket 매니저 상태
        ws_status = "활성화" if (hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager) else "비활성화"
        print(f"WebSocket 매니저: {ws_status}")
        
        # 버퍼 상태 확인
        if hasattr(strategy, '_websocket_kline_buffer'):
            buffer_count = len(strategy._websocket_kline_buffer)
            print(f"WebSocket 버퍼: {buffer_count}개 키")
            
            # 타임프레임별 키 분포 확인
            timeframes = {}
            for key in strategy._websocket_kline_buffer.keys():
                if '_' in key:
                    tf = key.split('_')[-1]
                    timeframes[tf] = timeframes.get(tf, 0) + 1
            
            print("타임프레임별 분포:")
            for tf, count in timeframes.items():
                print(f"  {tf}: {count}개")
        else:
            print("WebSocket 버퍼: 없음")
        
        # 간단한 필터링 테스트 (타임아웃 없이)
        print("\n간단한 심볼 필터링...")
        try:
            # 필터링 없이 빠른 체크
            print("기본 거래소 연결 상태 확인...")
            symbols = strategy.exchange.load_markets()
            futures_count = sum(1 for symbol, market in symbols.items() 
                              if market.get('type') == 'swap' and 'USDT' in symbol)
            print(f"USDT 퓨처스 심볼: {futures_count}개")
            
        except Exception as e:
            print(f"거래소 연결 실패: {e}")
        
        # 빠른 종료
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            strategy.ws_kline_manager.shutdown()
        
        print("진단 완료")
        
    except Exception as e:
        print(f"진단 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    quick_diagnosis()