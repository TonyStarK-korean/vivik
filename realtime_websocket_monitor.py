# -*- coding: utf-8 -*-
"""
실시간 WebSocket 데이터 수신 모니터링
"""

import time
import json
from datetime import datetime

def monitor_websocket_data():
    """실시간 WebSocket 데이터 수신 모니터링"""
    try:
        print("=== 실시간 WebSocket 데이터 수신 모니터링 ===")
        
        # 전략 임포트
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        
        # 전략 초기화
        print("전략 초기화 중...")
        strategy = OneMinuteSurgeEntryStrategy(
            api_key=None,
            secret_key=None,
            sandbox=False
        )
        
        # 10초 대기하여 WebSocket 연결 안정화
        print("WebSocket 연결 안정화 대기... (10초)")
        time.sleep(10)
        
        # 15초간 실시간 모니터링
        print("\n=== 15초간 실시간 데이터 수신 모니터링 ===")
        start_time = time.time()
        last_buffer_size = 0
        
        while time.time() - start_time < 15:
            try:
                # WebSocket 매니저 상태
                if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
                    status = strategy.ws_kline_manager.get_status()
                    subscribed = strategy.ws_kline_manager.get_subscribed_symbols()
                    connected_count = sum(1 for s in status.values() if s == 'connected')
                    
                    # WebSocket 버퍼 상태
                    buffer_size = 0
                    new_data_count = 0
                    if hasattr(strategy, '_websocket_kline_buffer'):
                        buffer = strategy._websocket_kline_buffer
                        buffer_size = len(buffer)
                        
                        # 새로운 데이터 감지
                        if buffer_size > last_buffer_size:
                            new_data_count = buffer_size - last_buffer_size
                            last_buffer_size = buffer_size
                        
                        # 4시간봉 데이터 상세 확인
                        h4_symbols = [k for k in buffer.keys() if k.endswith('_4h')]
                        if h4_symbols:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                                  f"연결: {connected_count}/{len(subscribed)}, "
                                  f"버퍼: {buffer_size}개, "
                                  f"4h: {len(h4_symbols)}개, "
                                  f"신규: +{new_data_count}")
                            
                            # 첫 번째 4시간봉 심볼의 최신 데이터 표시
                            if h4_symbols:
                                first_symbol = h4_symbols[0]
                                candles = buffer[first_symbol]
                                if candles:
                                    latest = candles[-1]
                                    if isinstance(latest, dict):
                                        timestamp = latest.get('timestamp', 0)
                                        open_price = latest.get('open', 0)
                                        high_price = latest.get('high', 0) 
                                        close_price = latest.get('close', 0)
                                        surge_pct = ((high_price - open_price) / open_price * 100) if open_price > 0 else 0
                                        dt = datetime.fromtimestamp(timestamp/1000) if timestamp else "N/A"
                                        print(f"    {first_symbol}: {len(candles)}개 캔들, 최신({dt}): "
                                              f"O:{open_price:.6f} H:{high_price:.6f} C:{close_price:.6f} 급등:{surge_pct:.2f}%")
                        else:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                                  f"연결: {connected_count}/{len(subscribed)}, "
                                  f"버퍼: {buffer_size}개, 4h: 0개")
                    else:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] WebSocket 버퍼 없음")
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] WebSocket 매니저 비활성화")
                
                time.sleep(2)  # 2초마다 체크
                
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 모니터링 오류: {e}")
                time.sleep(2)
        
        print("\n=== 최종 상태 분석 ===")
        
        # 최종 WebSocket 버퍼 분석
        if hasattr(strategy, '_websocket_kline_buffer') and strategy._websocket_kline_buffer:
            buffer = strategy._websocket_kline_buffer
            print(f"총 버퍼 크기: {len(buffer)}개")
            
            # 타임프레임별 분석
            tf_stats = {}
            for key, data in buffer.items():
                if '_' in key:
                    symbol, tf = key.rsplit('_', 1)
                    if tf not in tf_stats:
                        tf_stats[tf] = []
                    tf_stats[tf].append((symbol, len(data)))
            
            for tf, symbols in tf_stats.items():
                avg_candles = sum(count for _, count in symbols) / len(symbols)
                print(f"{tf}: {len(symbols)}개 심볼, 평균 {avg_candles:.1f}개 캔들")
            
            # 4시간봉 급등 조건 테스트
            print("\n=== 4시간봉 급등 조건 테스트 ===")
            h4_symbols = [k for k in buffer.keys() if k.endswith('_4h')]
            surge_count = 0
            
            for symbol_key in h4_symbols[:5]:  # 첫 5개만 테스트
                candles = buffer[symbol_key]
                if len(candles) >= 2:
                    for candle in candles[-2:]:  # 최근 2개 캔들
                        if isinstance(candle, dict):
                            open_price = candle.get('open', 0)
                            high_price = candle.get('high', 0)
                            if open_price > 0:
                                surge_pct = ((high_price - open_price) / open_price) * 100
                                if surge_pct >= 2.0:
                                    surge_count += 1
                                    symbol_name = symbol_key.replace('_4h', '')
                                    print(f"  ✅ {symbol_name}: {surge_pct:.2f}% 급등 (조건 만족)")
                                    break
            
            print(f"급등 조건 만족: {surge_count}개/{min(len(h4_symbols), 5)}개 테스트")
        else:
            print("WebSocket 버퍼 없음")
        
        # 정리
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            strategy.ws_kline_manager.shutdown()
        
        print("\n=== 모니터링 완료 ===")
        
    except Exception as e:
        print(f"❌ 모니터링 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    monitor_websocket_data()