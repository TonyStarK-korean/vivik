# -*- coding: utf-8 -*-
"""
급등 감지 테스트 (조건 완화)
"""

import time
from datetime import datetime

def test_surge_detection_with_relaxed_conditions():
    """완화된 조건으로 급등 감지 테스트"""
    try:
        print("=== 급등 감지 테스트 (조건 완화) ===")
        
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
        print("WebSocket 데이터 대기... (5초)")
        time.sleep(5)
        
        print("\n=== 다양한 급등 임계값으로 테스트 ===")
        
        if hasattr(strategy, '_websocket_kline_buffer') and strategy._websocket_kline_buffer:
            buffer = strategy._websocket_kline_buffer
            h4_symbols = [k for k in buffer.keys() if k.endswith('_4h')]
            
            if h4_symbols:
                print(f"4시간봉 심볼: {len(h4_symbols)}개")
                
                # 다양한 임계값으로 테스트
                thresholds = [0.1, 0.2, 0.5, 1.0, 1.5, 2.0]
                
                for threshold in thresholds:
                    match_count = 0
                    matches = []
                    
                    for symbol_key in h4_symbols:
                        candles = buffer[symbol_key]
                        if len(candles) >= 2:
                            # 최근 2개 캔들 확인
                            for i, candle in enumerate(candles[-2:]):
                                if isinstance(candle, dict):
                                    open_price = candle.get('open', 0)
                                    high_price = candle.get('high', 0)
                                    if open_price > 0:
                                        surge_pct = ((high_price - open_price) / open_price) * 100
                                        if surge_pct >= threshold:
                                            match_count += 1
                                            symbol_name = symbol_key.replace('_4h', '')
                                            matches.append((symbol_name, surge_pct, i))
                                            break
                    
                    print(f"임계값 {threshold:>4.1f}%: {match_count:>2d}개 심볼 조건 만족")
                    
                    # 0.5% 이상에서 상세 정보 표시
                    if threshold == 0.5 and matches:
                        print("  상세:")
                        for symbol, surge, candle_idx in matches[:5]:
                            print(f"    {symbol}: {surge:.2f}% (캔들 {candle_idx})")
                
                # 현재 시장 상황 분석
                print(f"\n=== 현재 시장 상황 분석 ===")
                
                # 모든 심볼의 최근 급등률 통계
                all_surges = []
                for symbol_key in h4_symbols:
                    candles = buffer[symbol_key]
                    if len(candles) >= 1:
                        latest_candle = candles[-1]
                        if isinstance(latest_candle, dict):
                            open_price = latest_candle.get('open', 0)
                            high_price = latest_candle.get('high', 0)
                            if open_price > 0:
                                surge_pct = ((high_price - open_price) / open_price) * 100
                                all_surges.append(surge_pct)
                
                if all_surges:
                    avg_surge = sum(all_surges) / len(all_surges)
                    max_surge = max(all_surges)
                    min_surge = min(all_surges)
                    print(f"최근 캔들 급등률: 평균 {avg_surge:.2f}%, 최대 {max_surge:.2f}%, 최소 {min_surge:.2f}%")
                    
                    # 상위 5개 급등 심볼 표시
                    surge_with_symbols = []
                    for i, symbol_key in enumerate(h4_symbols):
                        if i < len(all_surges):
                            symbol_name = symbol_key.replace('_4h', '')
                            surge_with_symbols.append((symbol_name, all_surges[i]))
                    
                    surge_with_symbols.sort(key=lambda x: x[1], reverse=True)
                    print("상위 5개 급등 심볼:")
                    for symbol, surge in surge_with_symbols[:5]:
                        print(f"  {symbol}: {surge:.2f}%")
            else:
                print("4시간봉 데이터 없음")
        else:
            print("WebSocket 버퍼 없음")
        
        # 임시 조건 완화 테스트
        print(f"\n=== 임시 조건 완화 테스트 ===")
        test_symbols = [
            ('BTC/USDT:USDT', 1.0, 1000000),
            ('ETH/USDT:USDT', 0.8, 800000),
            ('BNB/USDT:USDT', 1.2, 600000)
        ]
        
        # 원본 메서드 백업 후 임시 수정
        original_method = strategy._websocket_4h_filtering
        
        def relaxed_4h_filtering(candidate_symbols):
            """완화된 4시간봉 필터링 (0.2% 이상)"""
            filtered_symbols = []
            
            for item in candidate_symbols:
                if len(item) >= 3:
                    symbol = item[0]
                    change_pct = item[1] 
                    volume_24h = item[2]
                else:
                    continue
                
                # WebSocket 4시간봉 데이터 확인
                buffer_key_4h = f"{symbol.replace('/USDT:USDT', 'USDT')}_4h"
                
                if (hasattr(strategy, '_websocket_kline_buffer') and 
                    buffer_key_4h in strategy._websocket_kline_buffer):
                    
                    kline_4h = strategy._websocket_kline_buffer[buffer_key_4h]
                    
                    if len(kline_4h) >= 2:
                        recent_2_candles = kline_4h[-2:]
                        has_valid_surge = False
                        
                        for candle in recent_2_candles:
                            if isinstance(candle, dict):
                                open_price = candle.get('open', 0)
                                high_price = candle.get('high', 0)
                            else:
                                open_price = candle[1] if len(candle) > 1 else 0
                                high_price = candle[2] if len(candle) > 2 else 0
                            
                            if open_price > 0:
                                surge_pct = ((high_price - open_price) / open_price) * 100
                                
                                # 임시 완화된 조건: 0.2% 이상
                                if surge_pct >= 0.2:
                                    has_valid_surge = True
                                    print(f"    완화 조건 통과: {symbol} ({surge_pct:.2f}%)")
                                    break
                        
                        if has_valid_surge:
                            filtered_symbols.append((symbol, change_pct, volume_24h))
            
            return filtered_symbols
        
        # 임시 메서드 교체
        strategy._websocket_4h_filtering = relaxed_4h_filtering
        
        # 완화된 조건으로 테스트
        relaxed_result = strategy._websocket_4h_filtering(test_symbols)
        print(f"완화된 조건 결과: {len(relaxed_result)}개/{len(test_symbols)}개")
        
        # 원본 메서드 복원
        strategy._websocket_4h_filtering = original_method
        
        # 정리
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            strategy.ws_kline_manager.shutdown()
        
        print("\n=== 테스트 완료 ===")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_surge_detection_with_relaxed_conditions()