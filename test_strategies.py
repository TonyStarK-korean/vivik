# -*- coding: utf-8 -*-
"""
APR, BLUAI의 B전략, C전략 조건 확인용 테스트 스크립트
"""
import os
import sys
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime

# 스크립트 디렉토리 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from alpha_z_triple_strategy import FifteenMinuteMegaStrategy

class StrategyTester:
    def __init__(self):
        # 전략 클래스 인스턴스 생성 (간소화)
        self.exchange = ccxt.binance()
        try:
            # 전체 클래스를 생성하지 말고 필요한 함수만 가져와서 사용
            temp_strategy = FifteenMinuteMegaStrategy(sandbox=False)
            self.calculate_indicators = temp_strategy.calculate_indicators
            self._check_strategy_a_bottom_entry = temp_strategy._check_strategy_a_bottom_entry
            self._check_strategy_b_uptrend_entry = temp_strategy._check_strategy_b_uptrend_entry
            self._check_strategy_c_3min_precision = temp_strategy._check_strategy_c_3min_precision
            self.get_ohlcv_data = temp_strategy.get_ohlcv_data
        except Exception as e:
            print(f"전략 초기화 실패: {e}")
            sys.exit(1)
    
    def test_symbol_strategies(self, symbol):
        """심볼별 A,B,C 전략 테스트"""
        print(f"=== {symbol} 전략별 테스트 ===")
        
        try:
            # 15분봉 데이터 조회
            df_15m = self.get_ohlcv_data(symbol, '15m', limit=1200)
            if df_15m is None or len(df_15m) < 500:
                print("15분봉 데이터 부족")
                return
                
            # 지표 계산
            df_calc = self.calculate_indicators(df_15m)
            if df_calc is None:
                print("지표 계산 실패")
                return
            
            # A전략 테스트
            try:
                strategy_a_signal, strategy_a_conditions = self._check_strategy_a_bottom_entry(symbol, df_calc)
                print(f"A전략 결과: {strategy_a_signal}")
                if strategy_a_signal:
                    print("  A전략 충족 조건들:")
                    for condition in strategy_a_conditions:
                        if 'True' in condition:
                            print(f"    {condition}")
            except Exception as e:
                print(f"A전략 테스트 실패: {e}")
                
            # B전략 테스트
            try:
                strategy_b_signal, strategy_b_conditions = self._check_strategy_b_uptrend_entry(df_calc)
                print(f"B전략 결과: {strategy_b_signal}")
                if strategy_b_signal:
                    print("  B전략 충족 조건들:")
                    for condition in strategy_b_conditions:
                        if 'True' in condition:
                            print(f"    {condition}")
            except Exception as e:
                print(f"B전략 테스트 실패: {e}")
                
            # C전략 테스트
            try:
                strategy_c_signal, strategy_c_conditions = self._check_strategy_c_3min_precision(symbol)
                print(f"C전략 결과: {strategy_c_signal}")
                if strategy_c_signal:
                    print("  C전략 충족 조건들:")
                    for condition in strategy_c_conditions:
                        if 'True' in condition:
                            print(f"    {condition}")
            except Exception as e:
                print(f"C전략 테스트 실패: {e}")
            
            # 종합 결과
            overall_signal = strategy_a_signal or strategy_b_signal or strategy_c_signal
            print(f"종합 결과: {overall_signal} (A:{strategy_a_signal} OR B:{strategy_b_signal} OR C:{strategy_c_signal})")
            print()
            
        except Exception as e:
            print(f"{symbol} 테스트 실패: {e}")
            print()

    def test_multiple_symbols(self):
        """APR, BLUAI, METIS 테스트"""
        symbols = ["APR/USDT:USDT", "BLUAI/USDT:USDT", "METIS/USDT:USDT"]
        for symbol in symbols:
            self.test_symbol_strategies(symbol)

if __name__ == "__main__":
    try:
        tester = StrategyTester()
        tester.test_multiple_symbols()
    except Exception as e:
        print(f"테스트 실패: {e}")