# -*- coding: utf-8 -*-
"""
SuperTrend 및 데이터프레임 크기 디버깅
"""

import time
import pandas as pd

def debug_supertrend_and_data():
    """SuperTrend와 데이터 문제 디버깅"""
    print("=== SuperTrend 및 데이터 디버깅 ===")
    
    try:
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        
        # 전략 초기화
        print("전략 초기화 중...")
        strategy = OneMinuteSurgeEntryStrategy(
            api_key=None,
            secret_key=None,
            sandbox=False
        )
        
        # 데이터 수집 대기
        print("데이터 수집 대기... (10초)")
        time.sleep(10)
        
        # 필터링된 심볼 가져오기
        print("심볼 필터링...")
        filtered_symbols = strategy.get_filtered_symbols(min_change_pct=1.0)
        print(f"필터링 결과: {len(filtered_symbols)}개 심볼")
        
        if filtered_symbols:
            # 상위 2개 심볼로 데이터 분석
            test_symbols = filtered_symbols[:2]
            
            for symbol in test_symbols:
                clean_name = symbol.replace('/USDT:USDT', '')
                print(f"\n=== [{clean_name}] 데이터 분석 ===")
                
                try:
                    # 1. 5분봉 데이터 크기 확인 (전략과 동일한 방법 사용)
                    df_5m = strategy.get_websocket_kline_data(symbol, '5m', 100)
                    if df_5m is not None:
                        print(f"5분봉 데이터: {len(df_5m)}행")
                        print(f"5분봉 컬럼: {list(df_5m.columns)}")
                        
                        # SuperTrend 계산 테스트
                        print("SuperTrend 계산 중...")
                        df_5m_calc = strategy.calculate_supertrend(df_5m, period=10, multiplier=3.0)
                        
                        if df_5m_calc is not None:
                            print(f"SuperTrend 계산 완료: {len(df_5m_calc)}행")
                            st_cols = [col for col in df_5m_calc.columns if 'supertrend' in col.lower()]
                            print(f"SuperTrend 컬럼들: {st_cols}")
                            
                            if st_cols:
                                recent_5 = df_5m_calc.tail(5)
                                for col in st_cols:
                                    values = recent_5[col].tolist()
                                    print(f"  {col} 최근 5개값: {values}")
                                
                                # SuperTrend 진입 신호 테스트
                                signal = strategy.check_5m_supertrend_entry_signal(symbol, df_5m_calc)
                                print(f"SuperTrend 진입신호: {signal}")
                        else:
                            print("❌ SuperTrend 계산 실패")
                    else:
                        print("❌ 5분봉 데이터 없음")
                    
                    # 2. BB200, MA480 데이터 확인 (700봉 필요)
                    print(f"\n[{clean_name}] BB200-MA480 골든크로스 데이터 확인")
                    
                    if df_5m is not None and len(df_5m) >= 700:
                        print(f"✅ 700봉 데이터 충분: {len(df_5m)}행")
                        
                        # BB200, MA480 컬럼 확인
                        bb_cols = [col for col in df_5m.columns if 'bb200' in col.lower()]
                        ma_cols = [col for col in df_5m.columns if 'ma480' in col.lower()]
                        
                        print(f"BB200 컬럼들: {bb_cols}")
                        print(f"MA480 컬럼들: {ma_cols}")
                        
                        if 'bb200_upper' in df_5m.columns and 'ma480' in df_5m.columns:
                            recent_10 = df_5m.tail(10)
                            bb200_values = recent_10['bb200_upper'].tolist()
                            ma480_values = recent_10['ma480'].tolist()
                            
                            print(f"BB200상단 최근 10개: {[f'{v:.6f}' if pd.notna(v) else 'NaN' for v in bb200_values]}")
                            print(f"MA480 최근 10개: {[f'{v:.6f}' if pd.notna(v) else 'NaN' for v in ma480_values]}")
                            
                            # 골든크로스 패턴 찾기
                            golden_found = False
                            recent_100 = df_5m.tail(100)
                            for i in range(1, min(len(recent_100), 50)):
                                prev_bb = recent_100.iloc[i-1]['bb200_upper']
                                prev_ma = recent_100.iloc[i-1]['ma480'] 
                                curr_bb = recent_100.iloc[i]['bb200_upper']
                                curr_ma = recent_100.iloc[i]['ma480']
                                
                                if (pd.notna(prev_bb) and pd.notna(prev_ma) and 
                                    pd.notna(curr_bb) and pd.notna(curr_ma) and
                                    prev_bb <= prev_ma and curr_bb > curr_ma):
                                    golden_found = True
                                    break
                            
                            print(f"BB200-MA480 골든크로스 발견: {golden_found}")
                        else:
                            print("❌ BB200_upper 또는 MA480 컬럼 없음")
                    else:
                        print(f"❌ 700봉 데이터 부족: {len(df_5m) if df_5m is not None else 0}행")
                    
                except Exception as e:
                    print(f"❌ [{clean_name}] 분석 오류: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            print("❌ 필터링된 심볼이 없습니다.")
        
        # 정리
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            strategy.ws_kline_manager.shutdown()
        
        print("\n=== 디버깅 완료 ===")
        
    except Exception as e:
        print(f"❌ 디버깅 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_supertrend_and_data()