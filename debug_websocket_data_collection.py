# -*- coding: utf-8 -*-
"""
WebSocket 데이터 수집 문제 완전 분석
"""

import time
import pandas as pd

def debug_websocket_data_collection():
    """WebSocket 데이터 수집 문제 완전 분석"""
    print("=== WebSocket 데이터 수집 디버깅 ===")
    
    try:
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        
        # 전략 초기화
        print("전략 초기화 중...")
        strategy = OneMinuteSurgeEntryStrategy(
            api_key=None,
            secret_key=None,
            sandbox=False
        )
        
        # WebSocket 매니저 확인
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            print("✅ WebSocket 매니저 활성화됨")
        else:
            print("❌ WebSocket 매니저 없음")
            return
        
        # 초기 데이터 수집 대기
        print("초기 데이터 수집 대기... (10초)")
        time.sleep(10)
        
        # 현재 구독 상태 확인
        print("\n=== 현재 WebSocket 구독 상태 ===")
        if hasattr(strategy, '_subscribed_symbols'):
            subscribed = strategy._subscribed_symbols
            print(f"구독 중인 심볼: {len(subscribed)}개")
            for sub in list(subscribed)[:5]:  # 처음 5개만 출력
                print(f"  - {sub}")
        
        # WebSocket 버퍼 상태 확인
        print("\n=== WebSocket 버퍼 상태 ===")
        if hasattr(strategy, '_websocket_kline_buffer'):
            buffer = strategy._websocket_kline_buffer
            print(f"버퍼 키 개수: {len(buffer)}개")
            
            # 4h 데이터 확인
            h4_keys = [k for k in buffer.keys() if k.endswith('_4h')]
            print(f"4h 데이터 키: {len(h4_keys)}개")
            if h4_keys:
                for key in h4_keys[:3]:  # 처음 3개만 확인
                    data_count = len(buffer[key])
                    print(f"  {key}: {data_count}개 캔들")
            
            # 5m 데이터 확인 (문제가 되는 부분)
            m5_keys = [k for k in buffer.keys() if k.endswith('_5m')]
            print(f"5m 데이터 키: {len(m5_keys)}개")
            if m5_keys:
                for key in m5_keys[:3]:
                    data_count = len(buffer[key])
                    print(f"  {key}: {data_count}개 캔들")
            else:
                print("  ❌ 5분봉 데이터 키가 없음!")
        else:
            print("❌ WebSocket 버퍼 없음")
        
        # 필터링된 심볼 확인
        print("\n=== 심볼 필터링 및 동적 구독 테스트 ===")
        filtered_symbols = strategy.get_filtered_symbols(min_change_pct=1.0)
        print(f"필터링 결과: {len(filtered_symbols)}개 심볼")
        
        if filtered_symbols:
            test_symbol = filtered_symbols[0]
            clean_name = test_symbol.replace('/USDT:USDT', '')
            print(f"테스트 심볼: {clean_name}")
            
            # 동적 구독 프로세스 확인
            print(f"\n=== [{clean_name}] 동적 구독 프로세스 ===")
            
            # 1. 5분봉 구독 시도
            print("5분봉 구독 시도...")
            ws_symbol = test_symbol.replace('/USDT:USDT', 'USDT')
            
            try:
                # 현재 구독 상태 확인
                sub_key = f"{ws_symbol}_5m"
                if sub_key not in strategy._subscribed_symbols:
                    print(f"  {sub_key} 구독 시작...")
                    strategy.ws_kline_manager.subscribe_kline(ws_symbol, '5m')
                    strategy._subscribed_symbols.add(sub_key)
                    print(f"  ✅ {sub_key} 구독 완료")
                else:
                    print(f"  ✅ {sub_key} 이미 구독됨")
                
                # 구독 후 데이터 수집 대기
                print("구독 후 데이터 수집 대기... (15초)")
                time.sleep(15)
                
                # 2. 5분봉 데이터 조회 테스트
                print(f"\n=== [{clean_name}] 5분봉 데이터 조회 테스트 ===")
                df_5m = strategy.get_websocket_kline_data(test_symbol, '5m', 100)
                
                if df_5m is not None and len(df_5m) > 0:
                    print(f"✅ 5분봉 데이터 수집 성공: {len(df_5m)}행")
                    print(f"   컬럼: {list(df_5m.columns)}")
                    print(f"   최신 데이터:")
                    print(df_5m.tail(3))
                    
                    # SuperTrend 계산 테스트
                    print(f"\n=== SuperTrend 계산 테스트 ===")
                    df_5m_calc = strategy.calculate_supertrend(df_5m, period=10, multiplier=3.0)
                    
                    if df_5m_calc is not None:
                        print(f"✅ SuperTrend 계산 성공: {len(df_5m_calc)}행")
                        st_cols = [col for col in df_5m_calc.columns if 'supertrend' in col.lower()]
                        print(f"   SuperTrend 컬럼: {st_cols}")
                        
                        if st_cols:
                            recent_values = df_5m_calc[st_cols].tail(3)
                            print(f"   최근 3개 값:")
                            print(recent_values)
                            
                            # 진입 신호 테스트
                            signal = strategy.check_5m_supertrend_entry_signal(test_symbol, df_5m_calc)
                            print(f"   SuperTrend 진입신호: {signal}")
                        else:
                            print("   ❌ SuperTrend 컬럼 없음")
                    else:
                        print("   ❌ SuperTrend 계산 실패")
                else:
                    print(f"❌ 5분봉 데이터 수집 실패")
                    
                    # 버퍼 상태 재확인
                    buffer_key = f"{ws_symbol}_5m"
                    if hasattr(strategy, '_websocket_kline_buffer'):
                        buffer_data = strategy._websocket_kline_buffer.get(buffer_key, [])
                        print(f"   버퍼 상태 ({buffer_key}): {len(buffer_data)}개")
                    
            except Exception as e:
                print(f"❌ 구독/조회 실패: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("❌ 필터링된 심볼이 없음")
        
        # 정리
        print("\n=== 정리 중... ===")
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            strategy.ws_kline_manager.shutdown()
        
        print("=== 디버깅 완료 ===")
        
    except Exception as e:
        print(f"❌ 디버깅 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_websocket_data_collection()