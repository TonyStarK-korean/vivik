# -*- coding: utf-8 -*-
"""
WebSocket 실시간 진단 도구
"""

import time
import json
from datetime import datetime

def analyze_websocket_system():
    """WebSocket 시스템 실시간 진단"""
    try:
        print("=== WebSocket 시스템 실시간 진단 ===")
        
        # 전략 임포트
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        
        # 전략 초기화 (최소한의 로그)
        print("전략 초기화 중...")
        strategy = OneMinuteSurgeEntryStrategy(
            api_key=None,
            secret_key=None,
            sandbox=False
        )
        
        # 5초 대기 후 분석
        print("WebSocket 데이터 수집 대기... (5초)")
        time.sleep(5)
        
        print("\n=== WebSocket 매니저 상태 ===")
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            print("✅ WebSocket 매니저: 활성화됨")
            
            # 연결 상태 확인
            status = strategy.ws_kline_manager.get_status()
            subscribed = strategy.ws_kline_manager.get_subscribed_symbols()
            
            print(f"📊 구독된 심볼: {len(subscribed)}개")
            connected_count = sum(1 for s in status.values() if s == 'connected')
            print(f"🔗 연결된 WebSocket: {connected_count}개")
            
            # 타임프레임별 구독 분석
            timeframe_stats = {}
            for symbol in subscribed:
                if '_' in symbol:
                    tf = symbol.split('_')[-1]
                    timeframe_stats[tf] = timeframe_stats.get(tf, 0) + 1
            
            print("📈 타임프레임별 구독:")
            for tf, count in timeframe_stats.items():
                print(f"   {tf}: {count}개")
        else:
            print("❌ WebSocket 매니저: 비활성화됨")
            return
        
        print("\n=== WebSocket 버퍼 분석 ===")
        if hasattr(strategy, '_websocket_kline_buffer') and strategy._websocket_kline_buffer:
            buffer = strategy._websocket_kline_buffer
            print(f"📦 버퍼 총 심볼: {len(buffer)}개")
            
            # 타임프레임별 데이터 통계
            tf_data = {}
            for key, data in buffer.items():
                if '_' in key:
                    tf = key.split('_')[-1]
                    if tf not in tf_data:
                        tf_data[tf] = {'symbols': 0, 'total_candles': 0, 'avg_candles': 0}
                    tf_data[tf]['symbols'] += 1
                    tf_data[tf]['total_candles'] += len(data)
            
            for tf, stats in tf_data.items():
                if stats['symbols'] > 0:
                    stats['avg_candles'] = stats['total_candles'] / stats['symbols']
                print(f"   {tf}: {stats['symbols']}개 심볼, 평균 {stats['avg_candles']:.1f}개 캔들")
            
            # 4시간봉 상세 분석
            print("\n=== 4시간봉 데이터 상세 ===")
            h4_symbols = [k for k in buffer.keys() if k.endswith('_4h')]
            if h4_symbols:
                print(f"📊 4시간봉 수집된 심볼: {len(h4_symbols)}개")
                
                # 샘플 5개 표시
                for i, symbol in enumerate(h4_symbols[:5]):
                    candle_count = len(buffer[symbol])
                    if candle_count > 0:
                        latest = buffer[symbol][-1]
                        if isinstance(latest, dict):
                            timestamp = latest.get('timestamp', 0)
                            dt = datetime.fromtimestamp(timestamp/1000) if timestamp else "시간정보없음"
                            print(f"   {symbol}: {candle_count}개 캔들, 최신: {dt}")
                        else:
                            print(f"   {symbol}: {candle_count}개 캔들")
            else:
                print("❌ 4시간봉 데이터 없음")
                
                # 4시간봉 구독 시도
                print("\n=== 4시간봉 구독 테스트 ===")
                test_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
                for symbol in test_symbols:
                    try:
                        strategy.ws_kline_manager.subscribe_kline(symbol, '4h')
                        print(f"✅ {symbol} 4시간봉 구독 요청")
                    except Exception as e:
                        print(f"❌ {symbol} 구독 실패: {e}")
                
                print("5초 후 재확인...")
                time.sleep(5)
                
                # 재확인
                if hasattr(strategy, '_websocket_kline_buffer'):
                    new_h4 = [k for k in strategy._websocket_kline_buffer.keys() if k.endswith('_4h')]
                    print(f"📊 구독 후 4시간봉 심볼: {len(new_h4)}개")
        else:
            print("❌ WebSocket 버퍼 없음")
        
        print("\n=== 필터링 테스트 ===")
        # 테스트 심볼로 필터링 테스트
        test_symbols = [
            ('BTC/USDT:USDT', 2.5, 1000000),
            ('ETH/USDT:USDT', 1.8, 800000),
            ('BNB/USDT:USDT', 3.2, 600000)
        ]
        
        print(f"입력 심볼: {len(test_symbols)}개")
        
        # 4시간봉 필터링
        filtered_4h = strategy._websocket_4h_filtering(test_symbols)
        print(f"4시간봉 필터링 결과: {len(filtered_4h)}개")
        
        # 1시간봉 폴백 필터링
        filtered_1h = strategy._fallback_1h_filtering(test_symbols)
        print(f"1시간봉 폴백 결과: {len(filtered_1h)}개")
        
        # 정리
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            strategy.ws_kline_manager.shutdown()
        
        print("\n=== 진단 완료 ===")
        
    except Exception as e:
        print(f"❌ 진단 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_websocket_system()