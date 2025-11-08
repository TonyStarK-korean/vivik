# Comprehensive Trading Strategy Conditions Guide

## Overview

This trading system implements multiple strategies with OR logic:
- **Strategy A**: 3-minute surge entry detection (Active ✅)
- **Strategy B**: 5-minute ultra-strong entry point (Active ✅)
- **Strategy C**: 15-minute mega wave entry point (Active ✅)

## Trading Configuration (Current 2% Entry State)
- **Leverage**: 10x
- **Position Size**: 2.0% of capital × 10x leverage (20% exposure)
- **Max Concurrent Positions**: 15 symbols
- **Re-entry**: Cyclic trading enabled (max 3 cycles)
- **Stage Stop Loss**: Initial -10%, After 1st DCA -7%, After 2nd DCA -5%
- **Max Position per Symbol**: 7.0% (initial 2.0% + DCA 2.5% + 2.5%)
- **Max Capital Usage**: 105% (15 symbols × 7.0%)
- **Max Loss Rate**: 0.20% (initial), 0.308% (1st DCA), 0.350% (2nd DCA)

## Strategy A: 3-Minute Surge Entry Detection (Active ✅)

### Entry Conditions (All must be met)
1. **Bollinger Band Golden Cross**
   - Within 200 candles: BB200 upper (2.0 std) crosses above BB480 upper (1.5 std)

2. **MA Pattern (All sub-conditions must be met)**
   - 2A: MA5-MA20 dead cross within 60 candles
   - 2B: MA5-MA20 golden cross within 10 candles
   - 2C: MA5 < MA20 OR gap within 2%

3. **5-Minute SuperTrend Signal**
   - SuperTrend(10,3) switches from downtrend (-1) to uptrend (1) within recent 5 candles

**Final Logic**: Condition 1 AND Condition 2 AND SuperTrend Signal

## Strategy B: 5-Minute Ultra-Strong Entry Point (Active ✅)

### Entry Conditions (All 5 must be met)
1. **15-Minute MA Condition**
   - 15-minute MA80 < MA480

2. **5-Minute SuperTrend Signal**
   - SuperTrend(10,3) entry signal (downtrend to uptrend switch)

3. **MA Golden Cross or Gap**
   - Within 60 candles: MA80-MA480 golden cross
   - OR: MA80 < MA480 AND gap within 5%

4. **Complex Pattern (Both must be true)**
   - Within 700 candles: MA480 shows 5+ consecutive downward candles at least once
   - AND: BB200 upper crosses above MA480 (golden cross)

5. **Short-term MA Cross**
   - Within 20 candles: MA5-MA20 golden cross

## DCA (Dollar Cost Averaging) System

### Entry Structure
- **Initial Entry**: 2.0% × 10x = 20% exposure (market order)
- **1st DCA**: -3% drop → 2.5% limit order (placed immediately)
- **2nd DCA**: -6% drop → 2.5% limit order (placed immediately)
- **Order Management**: Check limit order fills every scan, auto-update average price
- **Cleanup**: Cancel unfilled limit orders → Market close filled positions only

## Exit Conditions (5 Exit Methods)

1. **SuperTrend Full Exit**
   - 5-minute SuperTrend(10,3) exit signal → Full position exit

2. **Breakeven Exit**
   - Profit-based protection levels:
     - 3%~5% profit: Exit before loss
     - 5%~10% profit: Exit on 50% drawdown
     - 10%+ profit: Exit on 50% drawdown

3. **Weak Rise + Sharp Drop Risk Avoidance**
   - Max profit ≥3% → Current near 0.5% loss + 5-minute SuperTrend(10,2) exit signal within 5 candles → Full exit

4. **BB600 Trailing Stop**
   - When 3min/5min/15min/30min candle high breaks BB600 upper:
     - Take 50% profit immediately
     - Apply 5% trailing stop on remaining 50%

5. **DCA Cyclic Partial Exit**
   - Maintains existing DCA system logic

## Strategy C: 15-Minute Mega Wave Entry Point (Active ✅)

### Entry Conditions (All 3 must be met)
1. **Complex MA/BB Pattern**
   - (MA80 < MA480 OR BB Complex Condition) AND 5-candle BB80-BB200 golden cross AND 100-candle BB200-MA480 cross pattern
   - BB Complex Condition: (BB80 < BB200 AND gap ≤ 5%) OR 100-candle BB480(1.5σ)-BB200(2σ) golden cross

2. **Short-term Entry Signal**
   - Within 5 candles: MA5 < MA20 AND open < MA5 AND close > MA5

3. **MA Position Confirmation**
   - MA5 < MA20 OR 3-candle MA5-MA20 golden cross within recent candles

## Exclusion Conditions

### 3-Minute 30% Surge Filter
- Exclude symbols showing 30%+ surge (open to high) within last 20 3-minute candles
- Protects against entering overextended moves

## Key Technical Indicators Used

### Moving Averages
- MA1, MA5, MA20, MA80, MA480

### Bollinger Bands  
- BB80 (period 80, 2.0 std dev)
- BB200 (period 200, 2.0 std dev)
- BB480 (period 480, 1.5 std dev)
- BB600 (period 600, 2.0 std dev)

### SuperTrend
- 5-minute SuperTrend(10,3) for entry/exit signals
- 5-minute SuperTrend(10,2) for risk avoidance

## Performance Optimization Notes

1. **WebSocket Priority**: Uses WebSocket data when available for real-time updates
2. **Caching System**: Implements OHLCV data caching to reduce API calls
3. **Batch Processing**: Subscribes to multiple symbols/timeframes simultaneously
4. **Early Exit Logic**: Checks critical conditions first to skip unnecessary calculations

## Risk Management

- **Maximum Drawdown Control**: Stage-based stop losses
- **Position Sizing**: Dynamic based on DCA stage
- **Correlation Management**: Max 15 concurrent positions
- **Leverage Control**: Fixed 10x with position size adjustments