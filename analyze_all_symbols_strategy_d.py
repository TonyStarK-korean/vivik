#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
전체 심볼 전략D 조건 분석 - 실전 모드
"""

import os
import sys
import time

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
    print("OK: Strategy class imported")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

def main():
    print("=== Full Symbol Strategy D Analysis ===")
    
    try:
        strategy = OneMinuteSurgeEntryStrategy()
        print("OK: Strategy instance created")
        
        # Rate limit 리셋
        if hasattr(strategy, '_api_rate_limited'):
            strategy._api_rate_limited = False
        
        # 실제 스캔 실행
        print("\nRunning full symbol scan...")
        start_time = time.time()
        
        # get_filtered_symbols 실행 (실제 스캔)
        symbols = strategy.get_filtered_symbols()
        
        scan_time = time.time() - start_time
        print(f"Scan completed in {scan_time:.1f} seconds")
        
        if symbols:
            print(f"SUCCESS: Found {len(symbols)} symbols")
            for i, symbol in enumerate(symbols[:10]):  # 처음 10개만 표시
                clean_name = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                print(f"  {i+1}. {clean_name}")
            if len(symbols) > 10:
                print(f"  ... and {len(symbols) - 10} more")
        else:
            print("ISSUE: No symbols found from scan")
        
        # 스캔 통계 확인
        print(f"\nChecking strategy internal states...")
        
        # 캐시 상태 확인
        if hasattr(strategy, '_4h_filter_cache'):
            cache = strategy._4h_filter_cache
            print(f"4H Filter Cache:")
            print(f"  Passed: {len(cache.get('passed_symbols', set()))} symbols")
            print(f"  Failed: {len(cache.get('failed_symbols', set()))} symbols")
            print(f"  Scan count: {cache.get('scan_count', 0)}")
        
        # Rate limit 상태 확인
        if hasattr(strategy, '_api_rate_limited'):
            print(f"Rate limit status: {strategy._api_rate_limited}")
        
        # WebSocket 상태 확인
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            stats = strategy.ws_kline_manager.get_stats()
            print(f"WebSocket stats:")
            print(f"  Connected: {stats.get('is_connected', False)}")
            print(f"  Subscribed: {stats.get('subscribed_count', 0)} symbols")
            print(f"  Messages: {stats.get('message_count', 0)}")
        
    except Exception as e:
        print(f"MAIN ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()