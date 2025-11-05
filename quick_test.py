# Simple test
print("Quick test start")

try:
    import sys
    import os
    sys.path.append(os.getcwd())
    
    # Import without running strategy
    import pandas as pd
    import ccxt
    
    # Test basic components
    print("Basic imports OK")
    
    # Test if we can create exchange connection
    exchange = ccxt.binance({
        'apiKey': '',
        'secret': '',
        'sandbox': False,
        'options': {'defaultType': 'swap'}
    })
    
    markets = exchange.load_markets()
    usdt_symbols = [s for s, m in markets.items() if 'USDT' in s and m.get('type') == 'swap']
    print(f"USDT symbols found: {len(usdt_symbols)}")
    
    # Test completed
    print("Test completed successfully")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()