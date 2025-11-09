# -*- coding: utf-8 -*-
"""
METIS MA 값 디버그용 스크립트
"""
import os
import sys
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime

# 스크립트 디렉토리를 Python 경로에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

class MetisDebugger:
    def __init__(self):
        self.exchange = ccxt.binance()
        
    def get_ohlcv_data(self, symbol, timeframe='15m', limit=500):
        """OHLCV 데이터 조회"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol + '/USDT', timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"데이터 조회 실패 {symbol}: {e}")
            return None
            
    def calculate_indicators(self, df):
        """기술적 지표 계산"""
        if df is None or len(df) < 480:
            return None
            
        try:
            df_calc = df.copy()
            
            # Moving Averages
            df_calc['ma5'] = df_calc['close'].rolling(window=5).mean()
            df_calc['ma20'] = df_calc['close'].rolling(window=20).mean()
            df_calc['ma80'] = df_calc['close'].rolling(window=80).mean()
            df_calc['ma480'] = df_calc['close'].rolling(window=480).mean()
            
            # Bollinger Bands
            bb200_ma = df_calc['close'].rolling(window=200).mean()
            bb200_std = df_calc['close'].rolling(window=200).std()
            df_calc['bb200_upper'] = bb200_ma + (bb200_std * 2.0)
            df_calc['bb200_lower'] = bb200_ma - (bb200_std * 2.0)
            
            bb480_ma = df_calc['close'].rolling(window=480).mean()
            bb480_std = df_calc['close'].rolling(window=480).std()
            df_calc['bb480_upper'] = bb480_ma + (bb480_std * 1.5)
            df_calc['bb480_lower'] = bb480_ma - (bb480_std * 1.5)
            
            return df_calc
        except Exception as e:
            print(f"지표 계산 실패: {e}")
            return None
    
    def debug_metis(self):
        """METIS MA 값 분석"""
        symbol = "METIS"
        print(f"=== {symbol} MA 분석 ===")
        
        # 15분봉 데이터 조회
        df = self.get_ohlcv_data(symbol, '15m', 500)
        if df is None:
            print("데이터 조회 실패")
            return
            
        df_calc = self.calculate_indicators(df)
        if df_calc is None:
            print("지표 계산 실패")
            return
            
        # 현재 MA 값들
        ma5 = df_calc['ma5'].iloc[-1]
        ma20 = df_calc['ma20'].iloc[-1]
        ma80 = df_calc['ma80'].iloc[-1]
        ma480 = df_calc['ma480'].iloc[-1]
        current_price = df_calc['close'].iloc[-1]
        
        print(f"현재가: {current_price:.4f}")
        print(f"MA5: {ma5:.4f}")
        print(f"MA20: {ma20:.4f}")
        print(f"MA80: {ma80:.4f}")
        print(f"MA480: {ma480:.4f}")
        print()
        
        # 조건1 체크
        print("=== A전략 조건1 체크 ===")
        ma80_vs_ma480 = ma80 < ma480
        ma5_vs_ma480 = ma5 < ma480
        condition1 = ma80_vs_ma480 and ma5_vs_ma480
        
        print(f"MA80 < MA480: {ma80_vs_ma480} ({ma80:.4f} < {ma480:.4f})")
        print(f"MA5 < MA480: {ma5_vs_ma480} ({ma5:.4f} < {ma480:.4f})")
        print(f"조건1 최종: {condition1}")
        
        # 최근 10개 봉의 MA 추이 확인
        print("\n=== 최근 10개 봉 MA 추이 ===")
        for i in range(10):
            idx = -(i+1)
            ma80_val = df_calc['ma80'].iloc[idx]
            ma480_val = df_calc['ma480'].iloc[idx]
            timestamp = df_calc['timestamp'].iloc[idx]
            
            print(f"{timestamp.strftime('%m-%d %H:%M')} | MA80:{ma80_val:.4f}, MA480:{ma480_val:.4f}, MA80<MA480:{ma80_val < ma480_val}")

    def debug_multiple_symbols(self):
        """APR, BLUAI, METIS 모두 분석"""
        symbols = ["APR", "BLUAI", "METIS"]
        for symbol in symbols:
            print(f"=== {symbol} MA 분석 ===")
            try:
                # 15분봉 데이터 조회
                df = self.get_ohlcv_data(symbol, '15m', 500)
                if df is None:
                    print("데이터 조회 실패\n")
                    continue
                    
                df_calc = self.calculate_indicators(df)
                if df_calc is None:
                    print("지표 계산 실패\n")
                    continue
                    
                # 현재 MA 값들
                ma5 = df_calc['ma5'].iloc[-1]
                ma20 = df_calc['ma20'].iloc[-1]
                ma80 = df_calc['ma80'].iloc[-1]
                ma480 = df_calc['ma480'].iloc[-1]
                current_price = df_calc['close'].iloc[-1]
                
                print(f"현재가: {current_price:.4f}")
                print(f"MA5: {ma5:.4f}")
                print(f"MA20: {ma20:.4f}")
                print(f"MA80: {ma80:.4f}")
                print(f"MA480: {ma480:.4f}")
                
                # 조건1 체크
                ma80_vs_ma480 = ma80 < ma480
                ma5_vs_ma480 = ma5 < ma480
                condition1 = ma80_vs_ma480 and ma5_vs_ma480
                
                print(f"MA80 < MA480: {ma80_vs_ma480} ({ma80:.4f} < {ma480:.4f})")
                print(f"MA5 < MA480: {ma5_vs_ma480} ({ma5:.4f} < {ma480:.4f})")
                print(f"조건1 최종: {condition1}")
                print()
                
            except Exception as e:
                print(f"{symbol} 분석 실패: {e}\n")

if __name__ == "__main__":
    debugger = MetisDebugger()
    debugger.debug_multiple_symbols()