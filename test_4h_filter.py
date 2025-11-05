# -*- coding: utf-8 -*-
"""
4h 필터링 디버깅 테스트
WebSocket vs REST API 4h 데이터 비교
"""

import sys
import io
import pandas as pd
from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy

# UTF-8 인코딩 강제
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def test_4h_filtering():
    """4h 필터링 로직 검증"""

    print("=" * 80)
    print("4h 필터링 디버깅 테스트")
    print("=" * 80)

    # 전략 초기화
    print("\n1. 전략 초기화 중...")
    strategy = OneMinuteSurgeEntryStrategy()

    # 테스트 심볼 (다양하게)
    test_symbols = [
        "BTC/USDT:USDT",
        "ETH/USDT:USDT",
        "SOL/USDT:USDT",
        "BNB/USDT:USDT",
        "XRP/USDT:USDT"
    ]

    print(f"\n2. 테스트 심볼: {len(test_symbols)}개")
    for sym in test_symbols:
        print(f"   - {sym}")

    print("\n" + "=" * 80)
    print("4h 데이터 확인 및 필터링 조건 검증")
    print("=" * 80)

    for symbol in test_symbols:
        print(f"\n{'─'*80}")
        print(f"[{symbol}]")
        print(f"{'─'*80}")

        try:
            # REST API로 4h 데이터 로드
            print("  📊 REST API에서 4h 데이터 로드 중...")
            data = strategy.exchange.fetch_ohlcv(symbol, '4h', limit=10)

            if not data or len(data) < 4:
                print(f"  ❌ 데이터 부족: {len(data) if data else 0}개")
                continue

            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            print(f"  ✅ 데이터 수신: {len(df)}개 캔들")
            print(f"  📅 최신 시간: {df['timestamp'].iloc[-1]}")

            # 최근 4개 캔들의 급등 확인
            print("\n  🔍 최근 4개 캔들 급등 검사 (시가 → 고가):")
            print(f"     {'캔들':>6} | {'시간':>16} | {'시가':>12} | {'고가':>12} | {'상승률':>8} | {'통과'}")
            print("     " + "-" * 75)

            surge_found = False
            for i in range(-4, 0):
                row = df.iloc[i]
                surge_pct = ((row['high'] - row['open']) / row['open']) * 100 if row['open'] > 0 else 0
                passed = "✅" if surge_pct >= 2.0 else "❌"

                if surge_pct >= 2.0:
                    surge_found = True

                print(f"     {i+4:>6} | {str(row['timestamp'])[11:16]:>16} | ${row['open']:>11,.2f} | ${row['high']:>11,.2f} | {surge_pct:>7.2f}% | {passed}")

            # 필터링 결과
            print(f"\n  {'🎯 필터링 결과: ✅ 통과' if surge_found else '  ⚠️ 필터링 결과: ❌ 불통과'}")
            if not surge_found:
                print(f"     이유: 최근 4개 캔들 중 2% 이상 급등 봉 없음")

            # WebSocket 데이터 확인 (있다면)
            ws_symbol = symbol.replace('/USDT:USDT', 'USDT').replace('/', '')
            if not ws_symbol.endswith('USDT'):
                ws_symbol += 'USDT'

            stream_key = f"{ws_symbol}_4h"
            if hasattr(strategy.websocket_manager, 'latest_data'):
                ws_data = strategy.websocket_manager.latest_data.get(stream_key)
                if ws_data:
                    print(f"\n  📡 WebSocket 데이터 있음:")
                    print(f"     캔들 수: {len(ws_data)}개")
                else:
                    print(f"\n  ⚠️ WebSocket 데이터 없음 (stream_key: {stream_key})")

        except Exception as e:
            print(f"  ❌ 오류: {e}")
            import traceback
            traceback.print_exc()

    # 요약
    print("\n" + "=" * 80)
    print("요약")
    print("=" * 80)
    print("\n✅ 4h 필터링 로직:")
    print("   - 최근 4개 4h 캔들 중 하나라도")
    print("   - (고가 - 시가) / 시가 >= 2.0% 이면 통과")
    print("\n💡 0개 통과 원인 추정:")
    print("   1. 현재 시장이 급등 없이 횡보/하락 중")
    print("   2. WebSocket에서 4h 데이터를 받지 못함")
    print("   3. 4h 캔들이 비어있거나 오래됨")

    return True

if __name__ == "__main__":
    print("\n4h 필터링 디버깅 테스트 시작\n")
    test_4h_filtering()
