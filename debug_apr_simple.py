#!/usr/bin/env python3
"""
APR 종목 15분봉 초필살기 조건 디버깅 스크립트 (간단 버전)
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
import time

def calculate_indicators(df):
    """지표 계산"""
    if df is None or len(df) == 0:
        return None
    
    df_calc = df.copy()
    
    # MA 계산
    df_calc['ma5'] = df_calc['close'].rolling(window=5).mean()
    df_calc['ma20'] = df_calc['close'].rolling(window=20).mean()
    df_calc['ma80'] = df_calc['close'].rolling(window=80).mean()
    df_calc['ma480'] = df_calc['close'].rolling(window=480).mean()
    
    # 볼린저 밴드 계산
    # BB200 (표준편차 2.0)
    if len(df_calc) >= 200:
        bb200_ma = df_calc['close'].rolling(window=200).mean()
        bb200_std = df_calc['close'].rolling(window=200).std()
        df_calc['bb200_upper'] = bb200_ma + (bb200_std * 2.0)
        df_calc['bb200_lower'] = bb200_ma - (bb200_std * 2.0)
        df_calc['bb200_middle'] = bb200_ma
    
    # BB480 (표준편차 1.5)
    if len(df_calc) >= 480:
        bb480_ma = df_calc['close'].rolling(window=480).mean()
        bb480_std = df_calc['close'].rolling(window=480).std()
        df_calc['bb480_upper'] = bb480_ma + (bb480_std * 1.5)
        df_calc['bb480_lower'] = bb480_ma - (bb480_std * 1.5)
        df_calc['bb480_middle'] = bb480_ma
    
    # BB80 (표준편차 2.0)
    if len(df_calc) >= 80:
        bb80_ma = df_calc['close'].rolling(window=80).mean()
        bb80_std = df_calc['close'].rolling(window=80).std()
        df_calc['bb80_upper'] = bb80_ma + (bb80_std * 2.0)
        df_calc['bb80_lower'] = bb80_ma - (bb80_std * 2.0)
        df_calc['bb80_middle'] = bb80_ma
    
    return df_calc

def check_conditions_debug(symbol, df_15m):
    """조건 체크 디버깅"""
    print(f"\n{symbol} 조건 분석")
    print("=" * 50)
    
    if df_15m is None or len(df_15m) < 500:
        print(f"데이터 부족: {len(df_15m) if df_15m is not None else 0}봉")
        return False
    
    print(f"데이터: {len(df_15m)}봉")
    
    # 지표 계산
    df_calc = calculate_indicators(df_15m)
    if df_calc is None:
        print("지표 계산 실패")
        return False
    
    # 최신 데이터
    latest = df_calc.iloc[-1]
    print(f"최신 가격: {latest['close']:.6f}")
    
    results = []
    
    # 조건 1: MA80-MA480 골든크로스 (200봉 이내)
    condition_1 = False
    if len(df_calc) >= 200:
        for i in range(len(df_calc) - 200, len(df_calc)):
            if i <= 0:
                continue
            prev = df_calc.iloc[i-1]
            curr = df_calc.iloc[i]
            
            if (pd.notna(prev['ma80']) and pd.notna(prev['ma480']) and
                pd.notna(curr['ma80']) and pd.notna(curr['ma480']) and
                prev['ma80'] < prev['ma480'] and
                curr['ma80'] >= curr['ma480']):
                condition_1 = True
                bars_ago = len(df_calc) - i - 1
                print(f"조건1 OK: MA80-MA480 골든크로스 {bars_ago}봉전")
                break
    
    if not condition_1:
        print("조건1 FAIL: MA80-MA480 골든크로스 없음")
        if pd.notna(latest['ma80']) and pd.notna(latest['ma480']):
            print(f"  현재: MA80({latest['ma80']:.6f}) vs MA480({latest['ma480']:.6f})")
    
    results.append(condition_1)
    
    # 조건 2: BB 골든크로스 (200봉 이내)
    condition_2 = False
    if len(df_calc) >= 200:
        # BB200-BB480 체크
        for i in range(len(df_calc) - 200, len(df_calc)):
            if i <= 0:
                continue
            prev = df_calc.iloc[i-1]
            curr = df_calc.iloc[i]
            
            if (pd.notna(prev['bb200_upper']) and pd.notna(prev['bb480_upper']) and
                pd.notna(curr['bb200_upper']) and pd.notna(curr['bb480_upper']) and
                prev['bb200_upper'] < prev['bb480_upper'] and
                curr['bb200_upper'] >= curr['bb480_upper']):
                condition_2 = True
                bars_ago = len(df_calc) - i - 1
                print(f"조건2 OK: BB200-BB480 골든크로스 {bars_ago}봉전")
                break
        
        # BB80-BB480 체크 (위에서 못찾은 경우)
        if not condition_2:
            for i in range(len(df_calc) - 200, len(df_calc)):
                if i <= 0:
                    continue
                prev = df_calc.iloc[i-1]
                curr = df_calc.iloc[i]
                
                if (pd.notna(prev.get('bb80_upper')) and pd.notna(prev['bb480_upper']) and
                    pd.notna(curr.get('bb80_upper')) and pd.notna(curr['bb480_upper']) and
                    prev['bb80_upper'] < prev['bb480_upper'] and
                    curr['bb80_upper'] >= curr['bb480_upper']):
                    condition_2 = True
                    bars_ago = len(df_calc) - i - 1
                    print(f"조건2 OK: BB80-BB480 골든크로스 {bars_ago}봉전")
                    break
    
    if not condition_2:
        print("조건2 FAIL: BB 골든크로스 없음")
        if pd.notna(latest['bb200_upper']) and pd.notna(latest['bb480_upper']):
            print(f"  현재: BB200상단({latest['bb200_upper']:.6f}) vs BB480상단({latest['bb480_upper']:.6f})")
    
    results.append(condition_2)
    
    # 조건 3: MA5-MA20 골든크로스 (10봉 이내)
    condition_3 = False
    if len(df_calc) >= 10:
        for i in range(len(df_calc) - 10, len(df_calc)):
            if i <= 0:
                continue
            prev = df_calc.iloc[i-1]
            curr = df_calc.iloc[i]
            
            if (pd.notna(prev['ma5']) and pd.notna(prev['ma20']) and
                pd.notna(curr['ma5']) and pd.notna(curr['ma20']) and
                prev['ma5'] < prev['ma20'] and
                curr['ma5'] >= curr['ma20']):
                condition_3 = True
                bars_ago = len(df_calc) - i - 1
                print(f"조건3 OK: MA5-MA20 골든크로스 {bars_ago}봉전")
                break
    
    if not condition_3:
        print("조건3 FAIL: MA5-MA20 골든크로스 없음")
        if pd.notna(latest['ma5']) and pd.notna(latest['ma20']):
            print(f"  현재: MA5({latest['ma5']:.6f}) vs MA20({latest['ma20']:.6f})")
    
    results.append(condition_3)
    
    # 조건 4: BB200상단-MA480 상향돌파 (250봉 이내)
    condition_4 = False
    if len(df_calc) >= 250:
        for i in range(len(df_calc) - 250, len(df_calc)):
            if i <= 0:
                continue
            prev = df_calc.iloc[i-1]
            curr = df_calc.iloc[i]
            
            if (pd.notna(prev['bb200_upper']) and pd.notna(prev['ma480']) and
                pd.notna(curr['bb200_upper']) and pd.notna(curr['ma480']) and
                prev['bb200_upper'] <= prev['ma480'] and
                curr['bb200_upper'] > curr['ma480']):
                condition_4 = True
                bars_ago = len(df_calc) - i - 1
                print(f"조건4 OK: BB200상단-MA480 상향돌파 {bars_ago}봉전")
                break
    
    if not condition_4:
        print("조건4 FAIL: BB200상단-MA480 상향돌파 없음")
        if pd.notna(latest['bb200_upper']) and pd.notna(latest['ma480']):
            print(f"  현재: BB200상단({latest['bb200_upper']:.6f}) vs MA480({latest['ma480']:.6f})")
    
    results.append(condition_4)
    
    # 최종 결과
    all_ok = all(results)
    failed_count = sum(not r for r in results)
    
    print(f"\n최종 결과:")
    print(f"  조건1: {results[0]} (MA80-MA480)")
    print(f"  조건2: {results[1]} (BB골든크로스)")
    print(f"  조건3: {results[2]} (MA5-MA20)")
    print(f"  조건4: {results[3]} (BB200상단-MA480)")
    print(f"  전체: {all_ok}")
    print(f"  미충족: {failed_count}개")
    
    return all_ok

def main():
    try:
        exchange = ccxt.binance({
            'sandbox': False,
            'enableRateLimit': True,
        })
        
        symbol = 'APR/USDT:USDT'
        print(f"{symbol} 분석 시작...")
        
        # 15분봉 데이터 (500봉)
        ohlcv = exchange.fetch_ohlcv(symbol, '15m', limit=500)
        
        if not ohlcv or len(ohlcv) < 500:
            print(f"데이터 부족: {len(ohlcv) if ohlcv else 0}봉")
            return
        
        # DataFrame 변환
        df_15m = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
        
        print(f"데이터 로드: {len(df_15m)}봉")
        
        # 조건 분석
        result = check_conditions_debug(symbol, df_15m)
        
    except Exception as e:
        print(f"오류: {str(e)}")

if __name__ == "__main__":
    main()