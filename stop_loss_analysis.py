#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stop Loss Analysis Tool
Checks if current positions should have triggered stop loss at -3%
"""

import json
import ccxt
import pandas as pd
from datetime import datetime, timezone
import time

def load_positions():
    """Load current DCA positions"""
    try:
        with open('dca_positions.json', 'r', encoding='utf-8') as f:
            positions = json.load(f)
        return positions
    except Exception as e:
        print(f"❌ Failed to load positions: {e}")
        return {}

def setup_exchange():
    """Setup Binance exchange for price fetching"""
    try:
        exchange = ccxt.binance({
            'apiKey': '',  # No API key needed for public data
            'secret': '',
            'sandbox': False,
            'enableRateLimit': True,
        })
        return exchange
    except Exception as e:
        print(f"❌ Failed to setup exchange: {e}")
        return None

def get_current_prices(exchange, symbols):
    """Fetch current prices for all symbols"""
    prices = {}
    if not exchange:
        print("❌ No exchange available for price fetching")
        return prices
    
    print(f"📊 Fetching current prices for {len(symbols)} symbols...")
    
    for symbol in symbols:
        try:
            ticker = exchange.fetch_ticker(symbol)
            prices[symbol] = float(ticker['last'])
            print(f"   {symbol}: ${prices[symbol]:.6f}")
            time.sleep(0.1)  # Rate limiting
        except Exception as e:
            print(f"   ❌ Failed to fetch {symbol}: {e}")
            prices[symbol] = None
    
    return prices

def analyze_stop_loss_conditions():
    """Main analysis function"""
    print("🔍 Stop Loss Analysis - Checking if -3% threshold should have triggered")
    print("=" * 80)
    
    # Load positions
    positions = load_positions()
    if not positions:
        print("❌ No positions found!")
        return
    
    # Setup exchange
    exchange = setup_exchange()
    
    # Extract active positions and their symbols
    active_positions = {}
    symbols = []
    
    for symbol, pos_data in positions.items():
        if pos_data.get('is_active', False):
            active_positions[symbol] = pos_data
            symbols.append(symbol)
    
    if not active_positions:
        print("ℹ️  No active positions found")
        return
    
    print(f"📈 Found {len(active_positions)} active positions:")
    for symbol in symbols:
        entry_price = active_positions[symbol]['initial_entry_price']
        print(f"   {symbol}: Entry @ ${entry_price:.6f}")
    
    print()
    
    # Get current prices
    current_prices = get_current_prices(exchange, symbols)
    
    print("\n" + "=" * 80)
    print("📊 STOP LOSS ANALYSIS RESULTS")
    print("=" * 80)
    
    # Analysis results
    should_be_liquidated = []
    analysis_results = []
    
    for symbol, pos_data in active_positions.items():
        entry_price = pos_data['initial_entry_price']
        current_price = current_prices.get(symbol)
        
        if current_price is None:
            print(f"❌ {symbol}: No current price available")
            continue
        
        # Calculate profit/loss percentage based on initial entry price
        profit_pct = (current_price - entry_price) / entry_price * 100
        
        # Check if should be liquidated (-3% threshold)
        should_liquidate = profit_pct <= -3.0
        
        status = "🚨 SHOULD BE LIQUIDATED" if should_liquidate else "✅ Safe"
        
        result = {
            'symbol': symbol,
            'entry_price': entry_price,
            'current_price': current_price,
            'profit_pct': profit_pct,
            'should_liquidate': should_liquidate,
            'status': status
        }
        
        analysis_results.append(result)
        
        if should_liquidate:
            should_be_liquidated.append(result)
        
        print(f"{status} {symbol}")
        print(f"   Entry Price:  ${entry_price:.6f}")
        print(f"   Current Price: ${current_price:.6f}")
        print(f"   Profit/Loss:  {profit_pct:+.2f}%")
        print(f"   Distance to -3%: {profit_pct - (-3.0):+.2f}%")
        print()
    
    # Summary
    print("=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)
    
    if should_be_liquidated:
        print(f"🚨 CRITICAL: {len(should_be_liquidated)} positions should have been liquidated!")
        print("\nPositions that should be liquidated:")
        for result in should_be_liquidated:
            print(f"   {result['symbol']}: {result['profit_pct']:+.2f}% (Entry: ${result['entry_price']:.6f}, Current: ${result['current_price']:.6f})")
        
        print(f"\n⚠️  STOP LOSS LOGIC MAY NOT BE WORKING PROPERLY!")
        print(f"   Expected trigger: -3.0% loss from initial entry price")
        print(f"   Current implementation should liquidate these positions immediately")
    else:
        print("✅ All positions are above -3% stop loss threshold")
        print("✅ Stop loss conditions are not triggered")
    
    total_positions = len(analysis_results)
    safe_positions = total_positions - len(should_be_liquidated)
    
    print(f"\nPosition Status:")
    print(f"   Total Active: {total_positions}")
    print(f"   Safe (>-3%):  {safe_positions}")
    print(f"   At Risk (≤-3%): {len(should_be_liquidated)}")
    
    # Focus on BANK position as requested
    print("\n" + "=" * 80)
    print("🏦 BANK POSITION ANALYSIS (As Requested)")
    print("=" * 80)
    
    bank_symbol = None
    for symbol in active_positions.keys():
        if 'BANK' in symbol.upper():
            bank_symbol = symbol
            break
    
    if bank_symbol:
        bank_data = active_positions[bank_symbol]
        bank_current = current_prices.get(bank_symbol)
        bank_entry = bank_data['initial_entry_price']
        
        if bank_current:
            bank_profit = (bank_current - bank_entry) / bank_entry * 100
            
            print(f"Symbol: {bank_symbol}")
            print(f"Entry Price: ${bank_entry:.6f}")
            print(f"Current Price: ${bank_current:.6f}")
            print(f"Profit/Loss: {bank_profit:+.2f}%")
            print(f"Stop Loss Threshold: -3.00%")
            print(f"Distance to Stop Loss: {bank_profit - (-3.0):+.2f}%")
            
            if bank_profit <= -3.0:
                print("🚨 BANK should be liquidated immediately!")
            else:
                print("✅ BANK is safe from stop loss")
        else:
            print("❌ Could not fetch BANK current price")
    else:
        print("❌ BANK position not found in active positions")
    
    return analysis_results, should_be_liquidated

if __name__ == "__main__":
    try:
        analysis_results, liquidation_list = analyze_stop_loss_conditions()
        
        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"stop_loss_analysis_{timestamp}.json"
        
        results_data = {
            'timestamp': datetime.now().isoformat(),
            'analysis_results': analysis_results,
            'positions_to_liquidate': liquidation_list,
            'summary': {
                'total_positions': len(analysis_results),
                'positions_to_liquidate': len(liquidation_list),
                'stop_loss_working': len(liquidation_list) == 0
            }
        }
        
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Analysis results saved to: {results_file}")
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()