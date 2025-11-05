# -*- coding: utf-8 -*-
"""
멀티플렉싱 WebSocket 테스트 스크립트
기존 3,186개 스레드 -> 1-2개 스레드로 개선 검증
"""

from websocket_multiplexed_kline_manager import MultiplexedWebSocketManager
import time
import logging
from datetime import datetime
import sys
import io

# UTF-8 출력 설정 (Windows 콘솔 호환)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 통계 변수
update_count = {}
last_prices = {}


def price_callback(symbol: str, timeframe: str, kline_data: dict):
    """
    가격 업데이트 콜백

    Args:
        symbol: "BTCUSDT"
        timeframe: "1m", "5m", etc.
        kline_data: Binance kline 데이터
    """
    try:
        k = kline_data['k']
        close_price = float(k['c'])
        is_closed = k['x']  # 봉 종료 여부

        key = f"{symbol}_{timeframe}"
        update_count[key] = update_count.get(key, 0) + 1
        last_prices[key] = close_price

        # 봉 종료시에만 출력 (화면 정리)
        if is_closed:
            timestamp = datetime.fromtimestamp(k['t'] / 1000).strftime('%H:%M:%S')
            print(f"[{timestamp}] {symbol:12s} {timeframe:4s}: ${close_price:12,.2f} (업데이트 {update_count[key]:4d}회)")

    except Exception as e:
        logger.error(f"콜백 처리 실패 ({symbol} {timeframe}): {e}")


def run_test(test_type='small'):
    """
    테스트 실행

    Args:
        test_type: 'small' (10 심볼) / 'medium' (50 심볼) / 'large' (531 심볼)
    """
    print("\n" + "="*80)
    print(f"WebSocket 멀티플렉싱 테스트 - {test_type.upper()} 규모")
    print("="*80 + "\n")

    # 테스트 설정
    test_configs = {
        'small': {
            'symbols': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'DOGEUSDT',
                       'XRPUSDT', 'DOTUSDT', 'UNIUSDT', 'LINKUSDT', 'LTCUSDT'],
            'timeframes': ['1m', '5m'],
            'duration': 60
        },
        'medium': {
            'symbols': [f"SYMBOL{i}USDT" for i in range(1, 51)],  # 50개
            'timeframes': ['1m', '3m', '5m'],
            'duration': 120
        },
        'large': {
            'symbols': [f"SYMBOL{i}USDT" for i in range(1, 532)],  # 531개
            'timeframes': ['1m', '3m', '5m', '15m', '30m', '4h'],
            'duration': 180
        }
    }

    config = test_configs[test_type]

    # WebSocket 관리자 생성
    manager = MultiplexedWebSocketManager(
        callback=price_callback,
        logger=logger
    )

    print(f"[TEST CONFIG]")
    print(f"   Symbols: {len(config['symbols'])}")
    print(f"   Timeframes: {config['timeframes']}")
    print(f"   Total Streams: {len(config['symbols']) * len(config['timeframes'])}")
    print(f"   Duration: {config['duration']}s\n")

    # 배치 구독 시작
    start_time = time.time()
    print("[START] Batch subscription...")

    manager.subscribe_batch(
        symbols=config['symbols'],
        timeframes=config['timeframes']
    )

    subscribe_time = time.time() - start_time
    print(f"[OK] Subscription completed: {subscribe_time:.2f}s\n")

    # 통계 출력
    stats = manager.get_stats()
    print("[STATS] WebSocket Statistics:")
    print(f"   Total subscriptions: {stats['total_subscriptions']}")
    print(f"   Active connections: {stats['active_connections']}")
    print(f"   Thread count: {stats['thread_count']}")
    print(f"   Streams per connection: {stats['streams_per_connection']}")
    print()

    # 성능 비교
    old_thread_count = stats['total_subscriptions']  # 기존 방식: 1 스트림 = 1 스레드
    new_thread_count = stats['thread_count']
    reduction = ((old_thread_count - new_thread_count) / old_thread_count) * 100

    print("[PERFORMANCE] Improvement:")
    print(f"   Old thread count: {old_thread_count:,}")
    print(f"   New thread count: {new_thread_count}")
    print(f"   Thread reduction: {reduction:.1f}%")
    print(f"   Memory saved: ~{(old_thread_count - new_thread_count) * 0.2:.0f}MB")
    print()

    # 데이터 수신 대기
    print(f"[WAIT] Receiving data for {config['duration']}s...\n")
    print("-" * 80)

    try:
        time.sleep(config['duration'])
    except KeyboardInterrupt:
        print("\n\n⚠️  사용자 중단")

    # 결과 출력
    print("\n" + "-" * 80)
    print("\n[RESULTS] Test Results:")

    total_updates = sum(update_count.values())
    active_streams = len(update_count)
    avg_updates = total_updates / active_streams if active_streams > 0 else 0

    print(f"   Total updates: {total_updates:,}")
    print(f"   Active streams: {active_streams}/{stats['total_subscriptions']}")
    print(f"   Avg per stream: {avg_updates:.1f}")
    print(f"   Duration: {config['duration']}s")
    print(f"   Updates/sec: {total_updates / config['duration']:.1f}")

    # 지연 시간 추정
    if avg_updates > 0:
        expected_updates_1m = config['duration'] / 60  # 1분봉 예상 업데이트 (약 1회)
        latency_ok = avg_updates >= expected_updates_1m * 0.8
        latency_status = "[OK] Normal" if latency_ok else "[WARN] Delay detected"
        print(f"   Latency: {latency_status}")

    print()

    # 상위 10개 활성 스트림
    if update_count:
        print("[TOP10] Most Active Streams:")
        sorted_streams = sorted(update_count.items(), key=lambda x: x[1], reverse=True)[:10]
        for i, (stream, count) in enumerate(sorted_streams, 1):
            price = last_prices.get(stream, 0)
            print(f"   {i:2d}. {stream:20s}: {count:4d} updates (price ${price:12,.2f})")

    # 종료
    print("\n[SHUTDOWN] Closing WebSocket...")
    manager.shutdown()
    print("[OK] Test completed\n")

    return {
        'subscribe_time': subscribe_time,
        'total_updates': total_updates,
        'active_streams': active_streams,
        'thread_count': new_thread_count,
        'reduction_pct': reduction
    }


if __name__ == "__main__":
    import sys

    # 명령줄 인수로 테스트 타입 선택
    test_type = sys.argv[1] if len(sys.argv) > 1 else 'small'

    if test_type not in ['small', 'medium', 'large']:
        print("사용법: python test_multiplexed_websocket.py [small|medium|large]")
        print("  small:  10 심볼 × 2 타임프레임 = 20 스트림 (60초)")
        print("  medium: 50 심볼 × 3 타임프레임 = 150 스트림 (120초)")
        print("  large:  531 심볼 × 6 타임프레임 = 3,186 스트림 (180초)")
        sys.exit(1)

    # 테스트 실행
    results = run_test(test_type)

    # 최종 요약
    print("="*80)
    print("[SUMMARY] Final Summary")
    print("="*80)
    print(f"Subscribe time: {results['subscribe_time']:.2f}s")
    print(f"Total updates: {results['total_updates']:,}")
    print(f"Active streams: {results['active_streams']}")
    print(f"Thread count: {results['thread_count']}")
    print(f"Thread reduction: {results['reduction_pct']:.1f}%")
    print("="*80)
