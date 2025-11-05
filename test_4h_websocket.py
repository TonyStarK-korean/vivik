# -*- coding: utf-8 -*-
"""
4h WebSocket 구독 및 데이터 확인 테스트
"""

import sys
import io
import time
from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy

# UTF-8 인코딩 강제
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def test_4h_websocket():
    """4h WebSocket 구독 및 데이터 확인"""

    print("=" * 80)
    print("4h WebSocket 구독 테스트")
    print("=" * 80)

    # 전략 초기화
    print("\n1. 전략 초기화 중...")
    strategy = OneMinuteSurgeEntryStrategy()

    # WebSocket 매니저 확인
    if not strategy.ws_kline_manager:
        print("❌ WebSocket 매니저 없음!")
        return False

    print("✅ WebSocket 매니저 존재")

    # 테스트 심볼
    test_symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]

    print(f"\n2. 4h 구독 테스트: {len(test_symbols)}개 심볼")

    # 수동 구독 테스트
    for symbol in test_symbols:
        ws_symbol = symbol.replace('/USDT:USDT', 'USDT').replace('/', '')
        if not ws_symbol.endswith('USDT'):
            ws_symbol += 'USDT'

        print(f"\n📡 {symbol} ({ws_symbol}) 4h 구독 중...")

        try:
            # 배치 구독
            strategy.ws_kline_manager.subscribe_batch(
                symbols=[ws_symbol],
                timeframes=['4h'],
                load_history=True
            )
            print(f"   ✅ 구독 성공")
        except Exception as e:
            print(f"   ❌ 구독 실패: {e}")

    # 5초 대기 (데이터 수신 시간)
    print("\n3. 5초 대기 (데이터 수신 중)...")
    for i in range(5, 0, -1):
        print(f"   {i}초...")
        time.sleep(1)

    # 데이터 확인
    print("\n4. 4h 데이터 확인:")
    print("=" * 80)

    for symbol in test_symbols:
        print(f"\n[{symbol}]")

        # get_websocket_kline_data() 사용
        ohlcv_df = strategy.get_websocket_kline_data(symbol, '4h', limit=10)

        if ohlcv_df is not None and len(ohlcv_df) > 0:
            print(f"   ✅ WebSocket 데이터: {len(ohlcv_df)}개 캔들")
            print(f"   📅 최신 시간: {ohlcv_df['timestamp'].iloc[-1]}")
            print(f"   💰 최신 종가: ${ohlcv_df['close'].iloc[-1]:,.2f}")

            # 최근 4개 캔들의 급등 확인
            if len(ohlcv_df) >= 4:
                surge_found = False
                for i in range(-4, 0):
                    row = ohlcv_df.iloc[i]
                    surge_pct = ((row['high'] - row['open']) / row['open']) * 100 if row['open'] > 0 else 0
                    if surge_pct >= 2.0:
                        surge_found = True
                        print(f"   🎯 캔들 {i+4}: {surge_pct:.2f}% 급등 (✅ 통과)")
                        break

                if not surge_found:
                    max_surge = max(
                        ((ohlcv_df.iloc[i]['high'] - ohlcv_df.iloc[i]['open']) / ohlcv_df.iloc[i]['open']) * 100
                        if ohlcv_df.iloc[i]['open'] > 0 else 0
                        for i in range(-4, 0)
                    )
                    print(f"   ❌ 최대 급등: {max_surge:.2f}% (2% 미만)")
        else:
            print(f"   ❌ WebSocket 데이터 없음")

            # 버퍼 직접 확인
            ws_symbol = symbol.replace('/USDT:USDT', 'USDT').replace('/', '')
            if not ws_symbol.endswith('USDT'):
                ws_symbol += 'USDT'

            buffer_data = strategy.ws_kline_manager.get_kline_buffer(ws_symbol, '4h', 10)
            if buffer_data:
                print(f"   ℹ️ 버퍼에는 {len(buffer_data)}개 있음 (변환 문제?)")
            else:
                print(f"   ℹ️ 버퍼도 비어있음 (구독 안 됨?)")

    # 요약
    print("\n" + "=" * 80)
    print("요약")
    print("=" * 80)
    print("\n만약 WebSocket 데이터가 없다면:")
    print("  1. 구독이 제대로 안 되었을 수 있음")
    print("  2. 대기 시간이 부족할 수 있음 (더 기다려보기)")
    print("  3. Binance API가 4h를 지원하지 않을 수 있음 (확인 필요)")

    return True

if __name__ == "__main__":
    print("\n4h WebSocket 구독 테스트 시작\n")
    test_4h_websocket()
