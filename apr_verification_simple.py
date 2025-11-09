# -*- coding: utf-8 -*-
"""
APR/USDT B전략 조건2와 조건4 검증 스크립트 (간단 버전)
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import warnings
warnings.filterwarnings('ignore')

class APRVerification:
    def __init__(self):
        self.exchange = ccxt.binance({
            'apiKey': '',
            'secret': '',
            'sandbox': False,
            'enableRateLimit': True
        })
    
    def calculate_indicators(self, df):
        """지표 계산"""
        try:
            # 이동평균
            df['ma5'] = df['close'].rolling(window=5).mean()
            df['ma20'] = df['close'].rolling(window=20).mean()
            df['ma80'] = df['close'].rolling(window=80).mean()
            df['ma480'] = df['close'].rolling(window=480).mean()
            
            # BB200 (기간 200, 표준편차 2.0)
            if len(df) >= 200:
                bb200_ma = df['close'].rolling(window=200).mean()
                bb200_std = df['close'].rolling(window=200).std()
                df['bb200_upper'] = bb200_ma + (bb200_std * 2.0)
                df['bb200_lower'] = bb200_ma - (bb200_std * 2.0)
                df['bb200_middle'] = bb200_ma
            
            # BB480 (기간 480, 표준편차 1.5)
            if len(df) >= 480:
                bb480_ma = df['close'].rolling(window=480).mean()
                bb480_std = df['close'].rolling(window=480).std()
                df['bb480_upper'] = bb480_ma + (bb480_std * 1.5)
                df['bb480_lower'] = bb480_ma - (bb480_std * 1.5)
                df['bb480_middle'] = bb480_ma
            
            # BB80 (기간 80, 표준편차 2.0)
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
    
    def check_condition2_bb_golden_cross(self, df_calc):
        """조건2: BB 골든크로스 (BB200상단선-BB480상단선 OR BB80상단선-BB480상단선) 200봉 이내"""
        condition2 = False
        condition2_detail = "골든크로스 없음"
        
        print("\n=== Condition 2: BB Golden Cross ===")
        print("200봉 이내에서 BB200상단-BB480상단 또는 BB80상단-BB480상단 골든크로스 찾기")
        
        if len(df_calc) >= 200:
            # BB200상단선(표편2.0)-BB480상단선(표편1.5) 골든크로스 체크
            print("\n1) BB200상단-BB480상단 골든크로스 체크:")
            for i in range(len(df_calc) - 200, len(df_calc)):
                if i <= 0:
                    continue
                
                prev_candle = df_calc.iloc[i-1]
                curr_candle = df_calc.iloc[i]
                
                # 골든크로스: 이전봉에서 BB200상단 < BB480상단, 현재봉에서 BB200상단 >= BB480상단
                if (pd.notna(prev_candle['bb200_upper']) and pd.notna(prev_candle['bb480_upper']) and
                    pd.notna(curr_candle['bb200_upper']) and pd.notna(curr_candle['bb480_upper']) and
                    prev_candle['bb200_upper'] < prev_candle['bb480_upper'] and
                    curr_candle['bb200_upper'] >= curr_candle['bb480_upper']):
                    
                    condition2 = True
                    bars_ago = len(df_calc) - i - 1
                    condition2_detail = f"BB200-BB480 골든크로스 {bars_ago}봉전"
                    
                    print(f"   FOUND: {bars_ago}봉전 골든크로스!")
                    print(f"      시간: {df_calc.iloc[i]['timestamp']}")
                    print(f"      이전봉 BB200상단: {prev_candle['bb200_upper']:.6f}")
                    print(f"      이전봉 BB480상단: {prev_candle['bb480_upper']:.6f}")
                    print(f"      현재봉 BB200상단: {curr_candle['bb200_upper']:.6f}")
                    print(f"      현재봉 BB480상단: {curr_candle['bb480_upper']:.6f}")
                    break
            
            # BB80상단선(표편2.0)-BB480상단선(표편1.5) 골든크로스 체크 (위에서 못찾은 경우)
            if not condition2:
                print("\n2) BB80상단-BB480상단 골든크로스 체크:")
                for i in range(len(df_calc) - 200, len(df_calc)):
                    if i <= 0:
                        continue
                    
                    prev_candle = df_calc.iloc[i-1]
                    curr_candle = df_calc.iloc[i]
                    
                    # 골든크로스: 이전봉에서 BB80상단 < BB480상단, 현재봉에서 BB80상단 >= BB480상단
                    if (pd.notna(prev_candle.get('bb80_upper')) and pd.notna(prev_candle['bb480_upper']) and
                        pd.notna(curr_candle.get('bb80_upper')) and pd.notna(curr_candle['bb480_upper']) and
                        prev_candle['bb80_upper'] < prev_candle['bb480_upper'] and
                        curr_candle['bb80_upper'] >= curr_candle['bb480_upper']):
                        
                        condition2 = True
                        bars_ago = len(df_calc) - i - 1
                        condition2_detail = f"BB80-BB480 골든크로스 {bars_ago}봉전"
                        
                        print(f"   FOUND: {bars_ago}봉전 골든크로스!")
                        print(f"      시간: {df_calc.iloc[i]['timestamp']}")
                        print(f"      이전봉 BB80상단: {prev_candle['bb80_upper']:.6f}")
                        print(f"      이전봉 BB480상단: {prev_candle['bb480_upper']:.6f}")
                        print(f"      현재봉 BB80상단: {curr_candle['bb80_upper']:.6f}")
                        print(f"      현재봉 BB480상단: {curr_candle['bb480_upper']:.6f}")
                        break
            
            if not condition2:
                print("   NOT FOUND: 200봉 이내에 골든크로스 없음")
        
        return condition2, condition2_detail
    
    def check_condition4_bb_ma_breakout(self, df_calc):
        """조건4: 250봉이내 BB200상단선이 MA480 상향돌파"""
        condition4 = False
        condition4_detail = "상향돌파 없음"
        
        print("\n=== Condition 4: BB200 vs MA480 Breakout ===")
        print("250봉 이내에서 BB200상단선이 MA480을 상향돌파")
        
        if len(df_calc) >= 250:
            for i in range(len(df_calc) - 250, len(df_calc)):
                if i <= 0:
                    continue
                
                prev_candle = df_calc.iloc[i-1]
                curr_candle = df_calc.iloc[i]
                
                # 상향돌파: 이전봉에서 BB200상단 <= MA480, 현재봉에서 BB200상단 > MA480
                if (pd.notna(prev_candle['bb200_upper']) and pd.notna(prev_candle['ma480']) and
                    pd.notna(curr_candle['bb200_upper']) and pd.notna(curr_candle['ma480']) and
                    prev_candle['bb200_upper'] <= prev_candle['ma480'] and
                    curr_candle['bb200_upper'] > curr_candle['ma480']):
                    
                    condition4 = True
                    bars_ago = len(df_calc) - i - 1
                    condition4_detail = f"BB200상단-MA480 상향돌파 {bars_ago}봉전"
                    
                    print(f"   FOUND: {bars_ago}봉전 상향돌파!")
                    print(f"      시간: {df_calc.iloc[i]['timestamp']}")
                    print(f"      이전봉 BB200상단: {prev_candle['bb200_upper']:.6f}")
                    print(f"      이전봉 MA480: {prev_candle['ma480']:.6f}")
                    print(f"      현재봉 BB200상단: {curr_candle['bb200_upper']:.6f}")
                    print(f"      현재봉 MA480: {curr_candle['ma480']:.6f}")
                    break
            
            if not condition4:
                print("   NOT FOUND: 250봉 이내에 상향돌파 없음")
        
        return condition4, condition4_detail
    
    def analyze_recent_values(self, df_calc):
        """최근 값들 분석"""
        print("\n=== Recent Values Analysis ===")
        
        # 최근 5개 봉 데이터 확인
        for i in range(-5, 0):
            row = df_calc.iloc[i]
            print(f"\n{i}봉전 ({row['timestamp']}):")
            
            bb200_upper = row.get('bb200_upper')
            bb480_upper = row.get('bb480_upper') 
            bb80_upper = row.get('bb80_upper')
            ma480 = row.get('ma480')
            
            bb200_str = f"{bb200_upper:.6f}" if pd.notna(bb200_upper) else "N/A"
            bb480_str = f"{bb480_upper:.6f}" if pd.notna(bb480_upper) else "N/A"
            bb80_str = f"{bb80_upper:.6f}" if pd.notna(bb80_upper) else "N/A"
            ma480_str = f"{ma480:.6f}" if pd.notna(ma480) else "N/A"
            
            print(f"  BB200상단: {bb200_str}")
            print(f"  BB480상단: {bb480_str}")
            print(f"  BB80상단:  {bb80_str}")
            print(f"  MA480:    {ma480_str}")
            
            # BB80상단 vs BB480상단 관계
            if pd.notna(bb80_upper) and pd.notna(bb480_upper):
                if bb80_upper > bb480_upper:
                    print(f"  BB80상단 > BB480상단 (차이: {bb80_upper - bb480_upper:.6f})")
                else:
                    print(f"  BB80상단 < BB480상단 (차이: {bb480_upper - bb80_upper:.6f})")
            
            # BB200상단 vs MA480 관계
            if pd.notna(bb200_upper) and pd.notna(ma480):
                if bb200_upper > ma480:
                    print(f"  BB200상단 > MA480 (차이: {bb200_upper - ma480:.6f})")
                else:
                    print(f"  BB200상단 < MA480 (차이: {ma480 - bb200_upper:.6f})")
    
    def verify_apr_conditions(self):
        """APR/USDT B전략 조건 검증"""
        try:
            print("=== APR/USDT B전략 조건2, 조건4 검증 ===")
            print(f"검증 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 15분봉 데이터 가져오기 (충분한 데이터를 위해 800개)
            symbol = 'APR/USDT:USDT'
            print(f"\n{symbol} 15분봉 데이터 가져오는 중...")
            
            ohlcv = self.exchange.fetch_ohlcv(symbol, '15m', limit=800)
            
            # 데이터프레임 생성
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            print(f"   데이터 개수: {len(df)}개")
            print(f"   데이터 범위: {df['timestamp'].iloc[0]} ~ {df['timestamp'].iloc[-1]}")
            
            # 지표 계산
            print("\n지표 계산 중...")
            df_calc = self.calculate_indicators(df)
            
            # 최근 값들 분석
            self.analyze_recent_values(df_calc)
            
            # 조건2 검증
            condition2, condition2_detail = self.check_condition2_bb_golden_cross(df_calc)
            
            # 조건4 검증
            condition4, condition4_detail = self.check_condition4_bb_ma_breakout(df_calc)
            
            # 결과 출력
            print("\n" + "="*80)
            print("FINAL RESULT:")
            print("="*80)
            print(f"조건2 (BB 골든크로스): {condition2} - {condition2_detail}")
            print(f"조건4 (BB200상단-MA480 상향돌파): {condition4} - {condition4_detail}")
            
            if condition2 and condition4:
                print("\n[SUCCESS] 사용자 주장이 맞습니다! 두 조건 모두 충족되었습니다.")
                print("   코드 구현에 문제가 있을 가능성이 있습니다.")
            elif condition2 or condition4:
                print(f"\n[PARTIAL] 부분적으로 맞습니다. {'조건2' if condition2 else '조건4'}만 충족되었습니다.")
            else:
                print("\n[FAILED] 두 조건 모두 충족되지 않았습니다.")
            
            return condition2, condition4, condition2_detail, condition4_detail
            
        except Exception as e:
            print(f"검증 실패: {e}")
            return False, False, f"오류: {e}", f"오류: {e}"

if __name__ == "__main__":
    verifier = APRVerification()
    verifier.verify_apr_conditions()