# Comprehensive Trading Strategy Conditions Guide

## Overview

This trading system implements multiple strategies with OR logic:
- **Strategy C**: 3-minute surge entry detection (Active ✅)
- **Strategy D**: 5-minute ultra-strong entry point (Active ✅)
- **2-Hour Strategy**: Triple entry surge strategy (Pine Script)

## Trading Configuration (Current 2% Entry State)
- **Leverage**: 10x
- **Position Size**: 2.0% of capital × 10x leverage (20% exposure)
- **Max Concurrent Positions**: 15 symbols
- **Re-entry**: Cyclic trading enabled (max 3 cycles)
- **Stage Stop Loss**: Initial -10%, After 1st DCA -7%, After 2nd DCA -5%
- **Max Position per Symbol**: 7.0% (initial 2.0% + DCA 2.5% + 2.5%)
- **Max Capital Usage**: 105% (15 symbols × 7.0%)
- **Max Loss Rate**: 0.20% (initial), 0.308% (1st DCA), 0.350% (2nd DCA)

## Strategy C: 3-Minute Surge Entry Detection (Active ✅)

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

## Strategy D: 5-Minute Ultra-Strong Entry Point (Active ✅)

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

## 2-Hour Triple Entry Surge Strategy (Pine Script)

### Entry Requirements (2-hour candles only)
1. **Historical Condition**: 3 candles ago: BB80 upper < BB200 upper
2. **Recent Activity**: Within 3 candles: BB80-BB200 golden cross OR gap within 2%
3. **Breakout Candle**: Current candle with 20%+ rise breaks both BB80 and BB200 upper bands

### Position Management
- **1st Entry**: All conditions met → 30% of equity × leverage
- **2nd Entry**: Upper/lower shadow detected → 25% of equity × leverage  
- **3rd Entry**: Next candle shows lower shadow → 20% of equity × leverage

### Exit Strategy
- **MA5 Dead Cross**: MA5 < BB80 upper after being above → Full exit (highest priority)
- **Profit Trailing**: 
  - Start at 5% profit
  - Tighten stop every 10% profit tier
  - Uses tightening factor of 0.8 per tier
- **Breakeven Stop**: Exit at average entry price after all entries complete

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