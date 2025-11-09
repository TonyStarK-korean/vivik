#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API 데이터 조회 방식 문제 디버깅"""

import ccxt
import pandas as pd
from datetime import datetime, timedelta
from binance_config import BinanceConfig

def debug_api_calls():
    """API 호출 방식별 차이 확인"""
    
    # 바이낸스 거래소 연결
    exchange = ccxt.binance({
        'apiKey': BinanceConfig.API_KEY,
        'secret': BinanceConfig.SECRET_KEY,
        'timeout': 30000,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',  # futures 모드
            'recvWindow': 60000,
        },
        'sandbox': False,
    })
    
    print("=== BTCUSDT 데이터 조회 방식별 비교 ===")
    
    # 방법 1: 직접 BTCUSDT로 조회
    try:
        print("\n1. 직접 BTCUSDT로 조회:")
        data1 = exchange.fetch_ohlcv('BTCUSDT', '1d', limit=10)
        if data1:
            df1 = pd.DataFrame(data1, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df1['datetime'] = pd.to_datetime(df1['timestamp'], unit='ms')
            print(f"   데이터 수: {len(df1)}개")
            print(f"   날짜 범위: {df1['datetime'].min()} ~ {df1['datetime'].max()}")
            print(f"   가격 범위: ${df1['low'].min():.2f} ~ ${df1['high'].max():.2f}")
            print(f"   첫번째 캔들: {df1.iloc[0]['datetime']} - O:{df1.iloc[0]['open']:.2f}, C:{df1.iloc[0]['close']:.2f}")
    except Exception as e:
        print(f"   오류: {e}")
    
    # 방법 2: BTC/USDT:USDT 형식으로 조회
    try:
        print("\n2. BTC/USDT:USDT 형식으로 조회:")
        data2 = exchange.fetch_ohlcv('BTC/USDT:USDT', '1d', limit=10)
        if data2:
            df2 = pd.DataFrame(data2, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df2['datetime'] = pd.to_datetime(df2['timestamp'], unit='ms')
            print(f"   데이터 수: {len(df2)}개")
            print(f"   날짜 범위: {df2['datetime'].min()} ~ {df2['datetime'].max()}")
            print(f"   가격 범위: ${df2['low'].min():.2f} ~ ${df2['high'].max():.2f}")
            print(f"   첫번째 캔들: {df2.iloc[0]['datetime']} - O:{df2.iloc[0]['open']:.2f}, C:{df2.iloc[0]['close']:.2f}")
    except Exception as e:
        print(f"   오류: {e}")
    
    # 방법 3: since 매개변수 사용
    try:
        print("\n3. since 매개변수로 조회:")
        since = int((datetime.now() - timedelta(days=15)).timestamp()) * 1000
        data3 = exchange.fetch_ohlcv('BTCUSDT', '1d', since=since, limit=15)
        if data3:
            df3 = pd.DataFrame(data3, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df3['datetime'] = pd.to_datetime(df3['timestamp'], unit='ms')
            print(f"   데이터 수: {len(df3)}개")
            print(f"   날짜 범위: {df3['datetime'].min()} ~ {df3['datetime'].max()}")
            print(f"   가격 범위: ${df3['low'].min():.2f} ~ ${df3['high'].max():.2f}")
            print(f"   첫번째 캔들: {df3.iloc[0]['datetime']} - O:{df3.iloc[0]['open']:.2f}, C:{df3.iloc[0]['close']:.2f}")
    except Exception as e:
        print(f"   오류: {e}")
    
    # 방법 4: 마켓 확인
    try:
        print("\n4. 지원되는 마켓 확인:")
        markets = exchange.load_markets()
        
        if 'BTCUSDT' in markets:
            market = markets['BTCUSDT']
            print(f"   BTCUSDT 마켓: {market['type']}, {market['spot']}, {market['future']}")
        
        if 'BTC/USDT:USDT' in markets:
            market = markets['BTC/USDT:USDT']
            print(f"   BTC/USDT:USDT 마켓: {market['type']}, {market['spot']}, {market['future']}")
            
    except Exception as e:
        print(f"   마켓 로드 오류: {e}")
    
    # 방법 5: defaultType 변경 테스트
    try:
        print("\n5. spot 모드로 조회:")
        exchange_spot = ccxt.binance({
            'apiKey': BinanceConfig.API_KEY,
            'secret': BinanceConfig.SECRET_KEY,
            'timeout': 30000,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',  # spot 모드로 변경
            },
            'sandbox': False,
        })
        
        data5 = exchange_spot.fetch_ohlcv('BTC/USDT', '1d', limit=10)
        if data5:
            df5 = pd.DataFrame(data5, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df5['datetime'] = pd.to_datetime(df5['timestamp'], unit='ms')
            print(f"   데이터 수: {len(df5)}개")
            print(f"   날짜 범위: {df5['datetime'].min()} ~ {df5['datetime'].max()}")
            print(f"   가격 범위: ${df5['low'].min():.2f} ~ ${df5['high'].max():.2f}")
            print(f"   첫번째 캔들: {df5.iloc[0]['datetime']} - O:{df5.iloc[0]['open']:.2f}, C:{df5.iloc[0]['close']:.2f}")
    except Exception as e:
        print(f"   오류: {e}")

if __name__ == "__main__":
    debug_api_calls()