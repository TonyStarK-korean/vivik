#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Daily Surge Debugging Tool (No Unicode)
1% daily surge condition analysis tool
"""

import ccxt
import pandas as pd
import numpy as np
import datetime
import json
from binance_config import BinanceConfig

class SimpleDailySurgeDebugger:
    def __init__(self):
        """Initialize debugger"""
        print("Daily Surge Condition Debugger starting...")
        
        try:
            self.exchange = ccxt.binance({
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
            print("SUCCESS: Binance connected")
        except Exception as e:
            print(f"ERROR: Binance connection failed: {e}")
            self.exchange = None
    
    def get_daily_data(self, symbol, days=65):
        """Fetch daily OHLCV data"""
        try:
            # Convert to futures symbol format
            if '/' not in symbol:
                formatted_symbol = f"{symbol[:-4]}/{symbol[-4:]}:USDT"
            else:
                formatted_symbol = symbol
            
            print(f"Fetching daily data for {formatted_symbol} ({days} days)...")
            
            # Fetch data from days ago
            since = int((datetime.datetime.now() - datetime.timedelta(days=days)).timestamp()) * 1000
            ohlcv = self.exchange.fetch_ohlcv(formatted_symbol, '1d', since=since, limit=days)
            
            if not ohlcv:
                print(f"ERROR: No data for {formatted_symbol}")
                return None
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            print(f"SUCCESS: Got {len(df)} daily candles for {formatted_symbol}")
            return df
            
        except Exception as e:
            print(f"ERROR: Data fetch failed for {formatted_symbol}: {e}")
            return None
    
    def analyze_surge_condition(self, symbol):
        """Analyze 1% daily surge condition"""
        print(f"\n{'='*60}")
        print(f"ANALYZING: {symbol} - 1% Daily Surge Analysis")
        print(f"{'='*60}")
        
        df = self.get_daily_data(symbol, 65)
        if df is None:
            return None
        
        # Analyze last 60 days
        recent_60 = df.tail(60)
        
        print(f"\nDATA QUALITY CHECK:")
        
        # Check for NaN values
        nan_count = recent_60[['open', 'high', 'low', 'close']].isnull().sum().sum()
        print(f"- NaN values: {nan_count}")
        
        # Check for zero/negative values
        zero_negative = (recent_60[['open', 'high', 'low', 'close']] <= 0).sum().sum()
        print(f"- Zero/negative values: {zero_negative}")
        
        # Price ranges
        print(f"- Open range: ${recent_60['open'].min():.4f} ~ ${recent_60['open'].max():.4f}")
        print(f"- High range: ${recent_60['high'].min():.4f} ~ ${recent_60['high'].max():.4f}")
        
        # Surge analysis
        print(f"\nSURGE ANALYSIS:")
        
        surge_days_1pct = 0
        surge_days_2pct = 0
        surge_days_3pct = 0
        surge_days_5pct = 0
        max_surge = 0
        all_surges = []
        
        for i, row in recent_60.iterrows():
            open_price = row['open']
            high_price = row['high']
            date_str = row['datetime'].strftime('%Y-%m-%d')
            
            if open_price > 0:
                surge_pct = ((high_price - open_price) / open_price) * 100
                max_surge = max(max_surge, surge_pct)
                all_surges.append(surge_pct)
                
                if surge_pct >= 1.0:
                    surge_days_1pct += 1
                    print(f"  SUCCESS: {date_str}: {surge_pct:.2f}% (O:{open_price:.4f}, H:{high_price:.4f})")
                
                if surge_pct >= 2.0:
                    surge_days_2pct += 1
                if surge_pct >= 3.0:
                    surge_days_3pct += 1
                if surge_pct >= 5.0:
                    surge_days_5pct += 1
        
        print(f"\nSURGE STATISTICS:")
        print(f"- Max surge: {max_surge:.2f}%")
        print(f"- 1%+ surge days: {surge_days_1pct}/{len(recent_60)} days")
        print(f"- 2%+ surge days: {surge_days_2pct}/{len(recent_60)} days")
        print(f"- 3%+ surge days: {surge_days_3pct}/{len(recent_60)} days")
        print(f"- 5%+ surge days: {surge_days_5pct}/{len(recent_60)} days")
        print(f"- Average surge: {np.mean(all_surges):.2f}%")
        print(f"- Median surge: {np.median(all_surges):.2f}%")
        
        # Reality check
        print(f"\nREALITY CHECK:")
        if surge_days_1pct == 0:
            if max_surge < 0.1:
                print(f"SEVERE DATA ISSUE: Max surge {max_surge:.3f}%")
                print("   -> OHLC data appears incorrect or extremely stable asset")
            else:
                print(f"UNUSUAL PATTERN: Max surge {max_surge:.2f}%")
                print("   -> Bear market or extremely stable period")
        else:
            print(f"NORMAL VOLATILITY: {surge_days_1pct} days with 1%+ surge")
        
        return {
            'symbol': symbol,
            'surge_days_1pct': surge_days_1pct,
            'max_surge': max_surge,
            'avg_surge': np.mean(all_surges),
            'data_issues': nan_count + zero_negative > 0
        }

if __name__ == "__main__":
    # Test symbols
    test_symbols = [
        'BTCUSDT',    # Major coin
        'ETHUSDT',    # Major coin
        'ADAUSDT',    # Alt coin
        'SOLUSDT',    # Popular coin
        'DOGEUSDT',   # Meme coin
    ]
    
    debugger = SimpleDailySurgeDebugger()
    
    if debugger.exchange is None:
        print("ERROR: Exchange connection failed - exiting")
        exit(1)
    
    # Analyze each symbol
    results = []
    problem_symbols = []
    
    for symbol in test_symbols:
        print(f"\n[{len(results)+1}/{len(test_symbols)}] Analyzing: {symbol}")
        
        try:
            analysis = debugger.analyze_surge_condition(symbol)
            if analysis:
                results.append(analysis)
                
                if analysis['surge_days_1pct'] == 0:
                    problem_symbols.append(analysis)
                    
        except Exception as e:
            print(f"ERROR: Analysis failed for {symbol}: {e}")
    
    # Summary report
    print(f"\n{'='*80}")
    print(f"SUMMARY REPORT")
    print(f"{'='*80}")
    
    total_analyzed = len(results)
    problem_count = len(problem_symbols)
    
    print(f"- Total symbols analyzed: {total_analyzed}")
    print(f"- Symbols with no 1% surge: {problem_count} ({problem_count/total_analyzed*100:.1f}%)")
    
    if problem_symbols:
        print(f"\nPROBLEM SYMBOLS:")
        for prob in problem_symbols:
            print(f"  - {prob['symbol']}: max {prob['max_surge']:.2f}%, avg {prob['avg_surge']:.2f}%")
    
    print(f"\nCONCLUSION:")
    if problem_count == total_analyzed:
        print("ALL SYMBOLS FAILED 1% SURGE TEST - This indicates:")
        print("1. Possible data quality issues")
        print("2. Extremely bearish market period")
        print("3. Need to check _get_historical_data() method")
    elif problem_count > total_analyzed * 0.5:
        print("MAJORITY FAILED - Suggests market or data issues")
    else:
        print("NORMAL RESULTS - Some symbols passing 1% surge test")