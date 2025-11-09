#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""사용자 언급 문제 심볼들 직접 테스트"""

import os
import sys
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 스크립트 디렉토리를 Python 경로에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from binance_config import BinanceConfig

def test_specific_symbols():
    """사용자가 언급한 문제 심볼들 직접 테스트"""
    print("문제 심볼들 직접 테스트 시작")
    
    # 바이낸스 거래소 연결
    try:
        exchange = ccxt.binance({
            'apiKey': BinanceConfig.API_KEY,
            'secret': BinanceConfig.SECRET_KEY,
            'timeout': 30000,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
                'recvWindow': 60000,
            },
            'sandbox': False,
        })
        print("SUCCESS: 바이낸스 연결 성공")
    except Exception as e:
        print(f"ERROR: 바이낸스 연결 실패: {e}")
        return
    
    # 사용자가 언급한 문제 심볼들
    problem_symbols = ['TURTLEUSDT', 'BLUAIUSDT', 'EVAALUSDT', 'RIVERUSDT', 'PUTHUSDT']
    
    for symbol in problem_symbols:
        print(f"\n{'='*60}")
        print(f"TESTING: {symbol} 심볼 테스트")
        print(f"{'='*60}")
        
        try:
            # 1. 심볼 존재 여부 확인
            try:
                ticker = exchange.fetch_ticker(f"{symbol[:-4]}/USDT:USDT")
                print(f"SUCCESS: 심볼 존재 확인: 현재가 ${ticker['last']:.6f}")
            except Exception as e:
                print(f"ERROR: 심볼 존재 확인 실패: {e}")
                continue
            
            # 2. 일봉 데이터 조회 (여러 방법 시도)
            print(f"\nDATA: 일봉 데이터 조회 시도...")
            
            # 방법 1: 일반 fetch_ohlcv
            try:
                formatted_symbol = f"{symbol[:-4]}/USDT:USDT"
                ohlcv = exchange.fetch_ohlcv(formatted_symbol, '1d', limit=35)
                
                if not ohlcv:
                    print(f"ERROR: 방법1: 데이터 없음")
                else:
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
                    
                    start_date = df['datetime'].min().strftime('%Y-%m-%d')
                    end_date = df['datetime'].max().strftime('%Y-%m-%d')
                    data_days = len(df)
                    
                    print(f"SUCCESS: 방법1 성공: {data_days}일 데이터 ({start_date} ~ {end_date})")
                    
                    # 급등률 계산
                    surge_rates = []
                    max_surge = 0
                    surge_days = 0
                    
                    for i, row in df.iterrows():
                        if row['open'] > 0:
                            surge_pct = ((row['high'] - row['open']) / row['open']) * 100
                            surge_rates.append(surge_pct)
                            max_surge = max(max_surge, surge_pct)
                            if surge_pct >= 30.0:  # 30% 기준
                                surge_days += 1
                                date_str = row['datetime'].strftime('%Y-%m-%d')
                                print(f"   SURGE: {date_str}: {surge_pct:.2f}% (O:{row['open']:.6f}, H:{row['high']:.6f})")
                    
                    print(f"\nRESULT: 급등 분석 결과:")
                    print(f"   - 최대 급등률: {max_surge:.2f}%")
                    print(f"   - 30%+ 급등일: {surge_days}/{data_days}일")
                    print(f"   - 평균 급등률: {np.mean(surge_rates):.2f}%")
                    
                    # 데이터 품질 진단
                    if data_days < 10:
                        print(f"WARNING: 데이터 부족 ({data_days}일) - 신규 상장 가능성")
                    elif max_surge < 1.0:
                        print(f"WARNING: 급등률 매우 낮음 ({max_surge:.2f}%) - 데이터 이상 가능성")
                    elif surge_days == 0 and max_surge < 30.0:
                        print(f"WARNING: 30% 급등 없음 - 조건 불통과")
                    else:
                        print(f"SUCCESS: 정상 범위 데이터")
                        
            except Exception as e:
                print(f"ERROR: 방법1 실패: {e}")
                
            # 방법 2: since 매개변수 사용
            try:
                print(f"\nDATA: 방법2: since 매개변수로 재시도...")
                since = int((datetime.now() - timedelta(days=40)).timestamp()) * 1000
                ohlcv2 = exchange.fetch_ohlcv(formatted_symbol, '1d', since=since, limit=40)
                
                if not ohlcv2:
                    print(f"ERROR: 방법2: 데이터 없음")
                else:
                    df2 = pd.DataFrame(ohlcv2, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df2['datetime'] = pd.to_datetime(df2['timestamp'], unit='ms')
                    
                    start_date2 = df2['datetime'].min().strftime('%Y-%m-%d')
                    end_date2 = df2['datetime'].max().strftime('%Y-%m-%d')
                    data_days2 = len(df2)
                    
                    print(f"SUCCESS: 방법2 성공: {data_days2}일 데이터 ({start_date2} ~ {end_date2})")
                    
                    if data_days2 != data_days:
                        print(f"WARNING: 방법1과 데이터 수 차이: {data_days} vs {data_days2}")
                        
            except Exception as e:
                print(f"ERROR: 방법2 실패: {e}")
                
        except Exception as e:
            print(f"ERROR: {symbol} 전체 테스트 실패: {e}")
            
    print(f"\n{'='*80}")
    print("CONCLUSION: 문제 심볼들의 데이터 상태를 확인했습니다.")
    print("신규 상장 코인의 경우 충분한 이력 데이터가 없어 조건 통과가 어려울 수 있습니다.")

if __name__ == "__main__":
    test_specific_symbols()