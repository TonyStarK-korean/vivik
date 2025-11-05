# -*- coding: utf-8 -*-
"""
신호 없음 문제 진단 스크립트
"""

import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import ccxt
import pandas as pd
from datetime import datetime, timedelta
import time

print("="*80)
print("신호 없음 문제 진단")
print("="*80)
print()

# Binance Futures 초기화
exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

print("1. 거래소 연결 테스트...")
try:
    exchange.load_markets()
    print(f"   ✅ 연결 성공: {len(exchange.markets)} 마켓")
except Exception as e:
    print(f"   ❌ 연결 실패: {e}")
    sys.exit(1)

print()
print("2. USDT 선물 심볼 필터링...")
symbols = [s for s in exchange.symbols if s.endswith('/USDT:USDT')]
print(f"   ✅ 총 {len(symbols)}개 USDT 선물 발견")

print()
print("3. 4시간봉 급등 심볼 검사 (최근 4봉 이내 2% 이상)...")
print(f"   검사 대상: 처음 50개 심볼 (전체는 시간이 오래 걸림)")
print()

surge_symbols = []
checked_count = 0
max_check = 50  # 빠른 테스트를 위해 50개만

for symbol in symbols[:max_check]:
    try:
        # 4시간봉 10개 가져오기
        ohlcv = exchange.fetch_ohlcv(symbol, '4h', limit=10)

        if len(ohlcv) >= 4:
            # 최근 4봉 검사
            for i in range(-4, 0):
                candle = ohlcv[i]
                open_price = candle[1]
                high_price = candle[2]

                if open_price > 0:
                    surge_pct = ((high_price - open_price) / open_price) * 100

                    if surge_pct >= 2.0:
                        surge_symbols.append({
                            'symbol': symbol,
                            'surge': surge_pct,
                            'candle_idx': i
                        })
                        print(f"   🚀 {symbol}: {surge_pct:.2f}% 급등 (4h 봉 {i})")
                        break

        checked_count += 1

        # 진행 상황 출력
        if checked_count % 10 == 0:
            print(f"   ... {checked_count}/{max_check} 검사 완료")

        time.sleep(0.1)  # Rate limit 방지

    except Exception as e:
        continue

print()
print(f"4. 결과 요약:")
print(f"   검사한 심볼: {checked_count}개")
print(f"   급등 발견: {len(surge_symbols)}개")
print(f"   비율: {len(surge_symbols)/checked_count*100:.1f}%")
print()

if len(surge_symbols) > 0:
    print("✅ 급등 심볼 발견됨:")
    for s in surge_symbols[:10]:  # 최대 10개만 출력
        print(f"   - {s['symbol']}: {s['surge']:.2f}%")
else:
    print("⚠️  급등 심볼 없음!")
    print()
    print("가능한 원인:")
    print("1. 현재 시장이 횡보 중 (변동성 낮음)")
    print("2. 4h 필터링 조건이 너무 엄격 (2% → 1%로 완화 고려)")
    print("3. 검사 범위가 부족 (50개 → 전체로 확대 필요)")

print()
print("5. 실시간 가격 변동 테스트 (5개 주요 심볼, 30초)...")
test_symbols = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'BNB/USDT:USDT',
                'SOL/USDT:USDT', 'XRP/USDT:USDT']

prices_start = {}
for sym in test_symbols:
    try:
        ticker = exchange.fetch_ticker(sym)
        prices_start[sym] = ticker['last']
        print(f"   {sym}: ${ticker['last']:,.2f}")
    except:
        pass

print(f"\n   ⏳ 30초 대기 중...")
time.sleep(30)

print(f"\n   30초 후 가격:")
price_changes = []
for sym in test_symbols:
    try:
        ticker = exchange.fetch_ticker(sym)
        price_now = ticker['last']
        price_old = prices_start.get(sym, 0)

        if price_old > 0:
            change_pct = ((price_now - price_old) / price_old) * 100
            price_changes.append(abs(change_pct))

            change_str = f"+{change_pct:.3f}%" if change_pct > 0 else f"{change_pct:.3f}%"
            print(f"   {sym}: ${price_now:,.2f} ({change_str})")
    except:
        pass

if price_changes:
    avg_change = sum(price_changes) / len(price_changes)
    print(f"\n   평균 변동: {avg_change:.3f}%")

    if avg_change < 0.01:
        print("   ⚠️  변동성이 매우 낮음 - 신호 발생 어려움")
    elif avg_change < 0.05:
        print("   ⚠️  변동성이 낮음 - 신호 발생 가능성 낮음")
    else:
        print("   ✅ 변동성 정상 - 신호 발생 가능")

print()
print("="*80)
print("진단 완료")
print("="*80)
print()
print("권장 조치:")
print("1. 4h 급등 조건 완화: 2% → 1.5% 또는 1%")
print("2. 전체 531개 심볼 검사 (현재는 50개만 테스트)")
print("3. 전략 조건 완화 고려")
print("4. 시장 변동성이 높은 시간대에 재시도 (미국 장 시간)")
