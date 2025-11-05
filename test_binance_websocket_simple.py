# -*- coding: utf-8 -*-
"""
Binance WebSocket Kline Manager Simple Test
"""

import time
from binance_websocket_kline_manager import BinanceWebSocketKlineManager


def on_kline_update(symbol: str, timeframe: str, kline_data: dict):
    """Kline update callback"""
    print(f"[{symbol}] {timeframe} - Close: ${kline_data['close']:.4f} | Vol: {kline_data['volume']:.2f}")


def main():
    print("=" * 80)
    print("Binance WebSocket Kline Manager Test")
    print("=" * 80)

    # Create WebSocket Manager
    ws_manager = BinanceWebSocketKlineManager(callback=on_kline_update)

    try:
        # Start WebSocket
        print("\nStarting WebSocket...")
        ws_manager.start()
        time.sleep(2)

        # Subscribe test symbols
        test_symbols = ['BTCUSDT', 'ETHUSDT']
        test_timeframes = ['1m']

        print(f"\nSubscribing to symbols: {test_symbols}")
        print(f"Timeframes: {test_timeframes}\n")

        ws_manager.subscribe_batch(test_symbols, test_timeframes)

        print("Waiting for data (15 seconds)...\n")

        # Wait 15 seconds
        for i in range(15):
            time.sleep(1)

            # Print stats every 5 seconds
            if (i + 1) % 5 == 0:
                print("\n" + "=" * 80)
                stats = ws_manager.get_stats()
                print(f"Stats:")
                print(f"  Running: {stats['running']}")
                print(f"  Subscriptions: {stats['total_subscriptions']}")
                print(f"  Buffer Size: {stats['total_buffer_size']}")

                for symbol in test_symbols:
                    for timeframe in test_timeframes:
                        buffer_size = ws_manager.get_buffer_size(symbol, timeframe)
                        latest = ws_manager.get_latest_kline(symbol, timeframe)
                        if latest:
                            print(f"  [{symbol}] {timeframe}: Buffer={buffer_size}, Price=${latest['close']:.4f}")
                print("=" * 80 + "\n")

        print("\nTest completed!")

    except KeyboardInterrupt:
        print("\nUser interrupted (Ctrl+C)")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\nStopping WebSocket...")
        ws_manager.stop()
        print("Stopped successfully")


if __name__ == "__main__":
    main()
