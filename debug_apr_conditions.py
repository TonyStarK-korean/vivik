# -*- coding: utf-8 -*-
"""
APR 종목 B전략 조건 디버깅 테스트
"""

import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import sys
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

# 스크립트 디렉토리 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

def get_korea_time():
    """한국 시간 반환"""
    return datetime.now(timezone(timedelta(hours=9)))

def calculate_indicators_debug(df):
    """기술적 지표 계산 (디버깅용)"""
    try:
        if df is None or len(df) == 0:
            return None
        
        df = df.copy()
        
        # 기본 이동평균선
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['ma80'] = df['close'].rolling(window=80).mean()
        df['ma480'] = df['close'].rolling(window=480).mean()
        
        # 볼린저 밴드
        # BB200 (기간 200, 표준편차 2.0)
        if len(df) >= 200:
            bb200_ma = df['close'].rolling(window=200).mean()
            bb200_std = df['close'].rolling(window=200).std()
            df['bb200_upper'] = bb200_ma + (bb200_std * 2.0)
            df['bb200_lower'] = bb200_ma - (bb200_std * 2.0)
            df['bb200_middle'] = bb200_ma
        
        # BB480 (기간 480, 표준편차 1.5) - 중요!
        if len(df) >= 480:
            bb480_ma = df['close'].rolling(window=480).mean()
            bb480_std = df['close'].rolling(window=480).std()
            df['bb480_upper'] = bb480_ma + (bb480_std * 1.5)
            df['bb480_lower'] = bb480_ma - (bb480_std * 1.5)
            df['bb480_middle'] = bb480_ma
        
        # BB80 (기간 80, 표준편차 2.0) - 누락되었던 지표!
        if len(df) >= 80:
            bb80_ma = df['close'].rolling(window=80).mean()
            bb80_std = df['close'].rolling(window=80).std()
            df['bb80_upper'] = bb80_ma + (bb80_std * 2.0)
            df['bb80_lower'] = bb80_ma - (bb80_std * 2.0)
            df['bb80_middle'] = bb80_ma
        
        return df
        
    except Exception as e:
        print(f"지표 계산 실패: {e}")
        return df

def debug_b_strategy_conditions(df_calc):
    """B전략 조건 디버깅"""
    print("🔍 B전략 조건 디버깅 시작")
    print("="*60)
    
    if df_calc is None or len(df_calc) < 500:
        print("❌ 데이터 부족")
        return False
    
    # 현재 데이터 상태 출력
    last_row = df_calc.iloc[-1]
    print(f"📊 현재 지표 값:")
    print(f"   MA5: {last_row.get('ma5', 'N/A'):.6f}")
    print(f"   MA20: {last_row.get('ma20', 'N/A'):.6f}")
    print(f"   MA80: {last_row.get('ma80', 'N/A'):.6f}")
    print(f"   MA480: {last_row.get('ma480', 'N/A'):.6f}")
    print(f"   BB80상단: {last_row.get('bb80_upper', 'N/A'):.6f}")
    print(f"   BB200상단: {last_row.get('bb200_upper', 'N/A'):.6f}")
    print(f"   BB480상단: {last_row.get('bb480_upper', 'N/A'):.6f}")
    print()
    
    # 조건 1: MA80-MA480 골든크로스
    print("🔍 조건1: MA80-MA480 골든크로스 (200봉 이내)")
    condition1 = False
    condition1_detail = "골든크로스 없음"
    
    if len(df_calc) >= 200:
        for i in range(max(0, len(df_calc) - 200), len(df_calc)):
            if i <= 0:
                continue
            
            prev_candle = df_calc.iloc[i-1]
            curr_candle = df_calc.iloc[i]
            
            if (pd.notna(prev_candle['ma80']) and pd.notna(prev_candle['ma480']) and
                pd.notna(curr_candle['ma80']) and pd.notna(curr_candle['ma480']) and
                prev_candle['ma80'] < prev_candle['ma480'] and
                curr_candle['ma80'] >= curr_candle['ma480']):
                condition1 = True
                bars_ago = len(df_calc) - i - 1
                condition1_detail = f"{bars_ago}봉전 골든크로스"
                print(f"✅ {condition1_detail}")
                print(f"   이전봉: MA80({prev_candle['ma80']:.6f}) < MA480({prev_candle['ma480']:.6f})")
                print(f"   현재봉: MA80({curr_candle['ma80']:.6f}) >= MA480({curr_candle['ma480']:.6f})")
                break
    
    if not condition1:
        print("❌ MA80-MA480 골든크로스 없음")
    print()
    
    # 조건 2: BB 골든크로스
    print("🔍 조건2: BB 골든크로스 (200봉 이내)")
    condition2 = False
    condition2_detail = "골든크로스 없음"
    
    # BB80이 없는지 체크
    if 'bb80_upper' not in df_calc.columns:
        print("❌ CRITICAL: bb80_upper 컬럼이 없음!")
        return False
    
    if len(df_calc) >= 200:
        # BB200-BB480 골든크로스 체크
        for i in range(max(0, len(df_calc) - 200), len(df_calc)):
            if i <= 0:
                continue
            
            prev_candle = df_calc.iloc[i-1]
            curr_candle = df_calc.iloc[i]
            
            if (pd.notna(prev_candle['bb200_upper']) and pd.notna(prev_candle['bb480_upper']) and
                pd.notna(curr_candle['bb200_upper']) and pd.notna(curr_candle['bb480_upper']) and
                prev_candle['bb200_upper'] < prev_candle['bb480_upper'] and
                curr_candle['bb200_upper'] >= curr_candle['bb480_upper']):
                condition2 = True
                bars_ago = len(df_calc) - i - 1
                condition2_detail = f"BB200-BB480 골든크로스 {bars_ago}봉전"
                print(f"✅ {condition2_detail}")
                break
        
        # BB80-BB480 골든크로스 체크 (위에서 못찾은 경우)
        if not condition2:
            print("   BB200-BB480 골든크로스 없음, BB80-BB480 체크 중...")
            for i in range(max(0, len(df_calc) - 200), len(df_calc)):
                if i <= 0:
                    continue
                
                prev_candle = df_calc.iloc[i-1]
                curr_candle = df_calc.iloc[i]
                
                # 디버깅: 골든크로스 근처 데이터 출력
                bars_ago = len(df_calc) - i - 1
                if bars_ago <= 35 and bars_ago >= 25:  # 30봉 근처 체크
                    print(f"   {bars_ago}봉전: BB80({curr_candle.get('bb80_upper', 'N/A'):.6f}) vs BB480({curr_candle.get('bb480_upper', 'N/A'):.6f})")
                
                if (pd.notna(prev_candle.get('bb80_upper')) and pd.notna(prev_candle['bb480_upper']) and
                    pd.notna(curr_candle.get('bb80_upper')) and pd.notna(curr_candle['bb480_upper']) and
                    prev_candle['bb80_upper'] < prev_candle['bb480_upper'] and
                    curr_candle['bb80_upper'] >= curr_candle['bb480_upper']):
                    condition2 = True
                    condition2_detail = f"BB80-BB480 골든크로스 {bars_ago}봉전"
                    print(f"✅ {condition2_detail}")
                    print(f"   이전봉: BB80({prev_candle['bb80_upper']:.6f}) < BB480({prev_candle['bb480_upper']:.6f})")
                    print(f"   현재봉: BB80({curr_candle['bb80_upper']:.6f}) >= BB480({curr_candle['bb480_upper']:.6f})")
                    break
    
    if not condition2:
        print("❌ BB 골든크로스 없음")
    print()
    
    # 조건 3: MA5-MA20 골든크로스
    print("🔍 조건3: MA5-MA20 골든크로스 (10봉 이내)")
    condition3 = False
    condition3_detail = "골든크로스 없음"
    
    if len(df_calc) >= 10:
        for i in range(max(0, len(df_calc) - 10), len(df_calc)):
            if i <= 0:
                continue
            
            prev_candle = df_calc.iloc[i-1]
            curr_candle = df_calc.iloc[i]
            
            if (pd.notna(prev_candle['ma5']) and pd.notna(prev_candle['ma20']) and
                pd.notna(curr_candle['ma5']) and pd.notna(curr_candle['ma20']) and
                prev_candle['ma5'] < prev_candle['ma20'] and
                curr_candle['ma5'] >= curr_candle['ma20']):
                condition3 = True
                bars_ago = len(df_calc) - i - 1
                condition3_detail = f"MA5-MA20 골든크로스 {bars_ago}봉전"
                print(f"✅ {condition3_detail}")
                print(f"   이전봉: MA5({prev_candle['ma5']:.6f}) < MA20({prev_candle['ma20']:.6f})")
                print(f"   현재봉: MA5({curr_candle['ma5']:.6f}) >= MA20({curr_candle['ma20']:.6f})")
                break
    
    if not condition3:
        print("❌ MA5-MA20 골든크로스 없음")
    print()
    
    # 조건 4: BB200-MA480 상향돌파
    print("🔍 조건4: BB200-MA480 상향돌파 (250봉 이내)")
    condition4 = False
    condition4_detail = "상향돌파 없음"
    
    if len(df_calc) >= 250:
        print("   BB200-MA480 상향돌파 체크 중...")
        for i in range(max(0, len(df_calc) - 250), len(df_calc)):
            if i <= 0:
                continue
            
            prev_candle = df_calc.iloc[i-1]
            curr_candle = df_calc.iloc[i]
            
            # 디버깅: 상향돌파 근처 데이터 출력
            bars_ago = len(df_calc) - i - 1
            if bars_ago <= 55 and bars_ago >= 35:  # 47봉 근처 체크
                cross_status = "상향돌파!" if (prev_candle['bb200_upper'] <= prev_candle['ma480'] and curr_candle['bb200_upper'] > curr_candle['ma480']) else "미돌파"
                print(f"   {bars_ago}봉전: BB200({curr_candle['bb200_upper']:.6f}) vs MA480({curr_candle['ma480']:.6f}) - {cross_status}")
            
            if (pd.notna(prev_candle['bb200_upper']) and pd.notna(prev_candle['ma480']) and
                pd.notna(curr_candle['bb200_upper']) and pd.notna(curr_candle['ma480']) and
                prev_candle['bb200_upper'] <= prev_candle['ma480'] and
                curr_candle['bb200_upper'] > curr_candle['ma480']):
                condition4 = True
                bars_ago = len(df_calc) - i - 1
                condition4_detail = f"BB200-MA480 상향돌파 {bars_ago}봉전"
                print(f"✅ {condition4_detail}")
                print(f"   이전봉: BB200({prev_candle['bb200_upper']:.6f}) <= MA480({prev_candle['ma480']:.6f})")
                print(f"   현재봉: BB200({curr_candle['bb200_upper']:.6f}) > MA480({curr_candle['ma480']:.6f})")
                break
    
    if not condition4:
        print("❌ BB200-MA480 상향돌파 없음")
    print()
    
    # 최종 결과
    all_conditions = condition1 and condition2 and condition3 and condition4
    print("🎯 최종 결과:")
    print(f"   조건1 (MA80-MA480): {condition1}")
    print(f"   조건2 (BB 골든크로스): {condition2}")
    print(f"   조건3 (MA5-MA20): {condition3}")
    print(f"   조건4 (BB200-MA480): {condition4}")
    print(f"   최종 B전략 신호: {all_conditions}")
    
    return all_conditions

def main():
    """APR 디버깅 실행"""
    try:
        print("🚀 APR B전략 조건 디버깅 시작")
        print("="*60)
        
        # 바이낸스 공개 API 초기화
        exchange = ccxt.binance({
            'sandbox': False,
            'enableRateLimit': True,
            'timeout': 30000,
        })
        
        symbol = 'APR/USDT:USDT'
        
        print(f"📊 {symbol} 15분봉 데이터 조회 중...")
        
        # 15분봉 데이터 조회 (1000개 - 480기간 지표 계산을 위해)
        ohlcv = exchange.fetch_ohlcv(symbol, '15m', limit=1000)
        
        if not ohlcv or len(ohlcv) < 500:
            print("❌ 데이터 조회 실패 또는 부족")
            return
        
        # DataFrame 생성
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        print(f"✅ 데이터 조회 완료: {len(df)}개 봉")
        print(f"   기간: {df['timestamp'].iloc[0]} ~ {df['timestamp'].iloc[-1]}")
        print(f"   현재가: {df['close'].iloc[-1]:.6f}")
        print()
        
        # 지표 계산 (BB80 포함)
        df_calc = calculate_indicators_debug(df)
        
        if df_calc is None:
            print("❌ 지표 계산 실패")
            return
        
        # B전략 조건 디버깅
        result = debug_b_strategy_conditions(df_calc)
        
        print("\n🎯 결론:")
        if result:
            print("✅ APR은 B전략 조건을 모두 충족합니다!")
        else:
            print("❌ APR은 B전략 조건을 충족하지 않습니다.")
        
    except Exception as e:
        print(f"❌ 디버깅 실행 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()