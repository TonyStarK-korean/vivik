import ccxt
import sys
import os

# Add parent directory to path
sys.path.append('C:\\Project\\Alpha_Z')

try:
    from binance_config import BinanceConfig
    
    print("=== Binance API Key Permission Test ===")
    print(f"Testing API Key: {BinanceConfig.API_KEY[:10]}...")
    
    # Create exchange instance
    exchange = ccxt.binance({
        'apiKey': BinanceConfig.API_KEY,
        'secret': BinanceConfig.SECRET_KEY,
        'sandbox': False,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
        }
    })
    
    print("\n1. Testing market data (no auth needed)...")
    try:
        ticker = exchange.fetch_ticker('BTC/USDT:USDT')
        print(f"   SUCCESS: BTC Price ${ticker['last']:,.2f}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    print("\n2. Testing account balance (needs permissions)...")
    try:
        balance = exchange.fetch_balance()
        usdt_balance = balance.get('USDT', {}).get('free', 0)
        print(f"   SUCCESS: Balance {usdt_balance:.2f} USDT")
    except Exception as e:
        if "2015" in str(e):
            print("   ERROR: API key lacks permissions")
            print("   SOLUTION: Enable 'Spot & Margin Trading' in Binance")
        else:
            print(f"   ERROR: {e}")
    
    print("\n3. Testing futures positions (needs futures permission)...")
    try:
        positions = exchange.fetch_positions()
        active_positions = [p for p in positions if float(p['contracts']) > 0]
        print(f"   SUCCESS: {len(active_positions)} active positions")
    except Exception as e:
        if "2015" in str(e):
            print("   ERROR: API key lacks futures permissions")
            print("   SOLUTION: Enable 'Futures' permission in Binance")
        else:
            print(f"   ERROR: {e}")
    
    print("\n=== API Key Permission Requirements ===")
    print("Required permissions in Binance:")
    print("1. Enable Reading ✓")
    print("2. Enable Spot & Margin Trading (for balance)")
    print("3. Enable Futures (for positions)")
    print("4. No IP restrictions OR add current IP")
    print("\nHow to fix:")
    print("1. Go to Binance.com → API Management")
    print("2. Find your API key → Edit")
    print("3. Enable required permissions")
    print("4. Save and wait 5 minutes")
    
except ImportError:
    print("ERROR: Could not import binance_config.py")
    print("Make sure the file exists and is accessible")
except Exception as e:
    print(f"ERROR: {e}")