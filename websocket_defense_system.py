# -*- coding: utf-8 -*-
"""
WebSocket Defense System
실전 필수 방어 로직 3종

1. Heartbeat 감시 (30초 무Response → reconnect)
2. 데이터 Sync 체크 (2분 지연 → reconnect)
3. Stream Flush 감지 (close event missing → 강제 close)
"""

import time
import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bulk_websocket_kline_manager import BulkWebSocketKlineManager


class WebSocketDefenseSystem:
    """실전 필수 방어 로직"""

    def __init__(self, bulk_manager: 'BulkWebSocketKlineManager', logger=None):
        """
        Args:
            bulk_manager: BulkWebSocketKlineManager 인스턴스
            logger: 로거 인스턴스
        """
        self.bulk_manager = bulk_manager
        self.logger = logger or logging.getLogger(__name__)

        # 방어 Settings
        self.heartbeat_check_interval = 10  # 10초마다 체크
        self.heartbeat_timeout = 30  # 30초 무Response 시 재Connections

        self.sync_check_interval = 30  # 30초마다 체크
        self.sync_threshold = 120  # 2분 지연 시 재Connections

        self.flush_check_interval = 5  # 5초마다 체크
        self.candle_timeout = 65  # 1분 + 5초 여유

        # 스레드 관리
        self.running = False
        self.threads = []

        self.logger.info("🛡️ WebSocket Defense System Initialization complete")

    def start(self):
        """방어 시스템 Starting (백그라운드 스레드)"""
        if self.running:
            self.logger.warning("⚠️ Defense system already running")
            return

        self.running = True

        # 3가지 방어 로직 스레드 Starting
        threads_config = [
            ("Heartbeat Monitor", self._heartbeat_monitor_loop),
            ("Data Sync Check", self._data_sync_check_loop),
            ("Stream Flush Detection", self._stream_flush_detection_loop)
        ]

        for name, target in threads_config:
            thread = threading.Thread(target=target, name=name, daemon=True)
            thread.start()
            self.threads.append(thread)
            self.logger.info(f"✅ {name} 스레드 Starting")

        self.logger.info("🚀 WebSocket Defense System 가동 Complete (3count 스레드)")

    def stop(self):
        """방어 시스템 중지"""
        self.running = False
        self.logger.info("🛑 WebSocket Defense System stopped")

    def _heartbeat_monitor_loop(self):
        """
        1. Heartbeat 감시 (30초 이상 수신 Absent → reconnect)
        """
        self.logger.info("💓 Heartbeat Monitor Starting")

        while self.running:
            try:
                time.sleep(self.heartbeat_check_interval)

                if not self.bulk_manager.connection_active:
                    continue  # Connections이 끊긴 Status면 Skip

                # 마지막 Message 수신 Time Confirm
                elapsed = time.time() - self.bulk_manager.last_message_time

                if elapsed > self.heartbeat_timeout:
                    self.logger.warning(
                        f"⚠️ Heartbeat disconnected: {elapsed:.1f}초 무Response "
                        f"(Threshold: {self.heartbeat_timeout}초)"
                    )

                    # 재Connections 트리거
                    self.bulk_manager.handle_connection_loss()

                    # 마지막 Message Time 갱신 (Reconnection attempt 후)
                    self.bulk_manager.last_message_time = time.time()

            except Exception as e:
                self.logger.error(f"❌ Heartbeat Monitor error: {e}")
                time.sleep(5)  # 에러 시 5초 대기

    def _data_sync_check_loop(self):
        """
        2. 데이터 Sync 체크 (2분 이상 지연 → reconnect)
        """
        self.logger.info("🔄 Data Sync Check Starting")

        while self.running:
            try:
                time.sleep(self.sync_check_interval)

                if not self.bulk_manager.connection_active:
                    continue

                # 모든 Subscription Symbol의 최근 캔들 Confirm
                symbols_to_check = list(self.bulk_manager.subscribed_symbols)[:10]  # 샘플 10count만 체크

                max_delay = 0
                delayed_symbol = None

                for symbol in symbols_to_check:
                    try:
                        # 1minute candles 최신 캔들 타임스탬프 Confirm
                        latest_candle = self._get_latest_candle(symbol, '1m')

                        if latest_candle:
                            candle_time = latest_candle.get('timestamp', 0)
                            current_time = time.time() * 1000  # 밀리초로 변환
                            delay = (current_time - candle_time) / 1000  # 초로 변환

                            if delay > max_delay:
                                max_delay = delay
                                delayed_symbol = symbol

                            if delay > self.sync_threshold:
                                self.logger.warning(
                                    f"⚠️ {symbol} Data delay: {delay:.1f}초 "
                                    f"(Threshold: {self.sync_threshold}초)"
                                )

                                # 재Connections 트리거
                                self.bulk_manager.handle_connection_loss()
                                break

                    except Exception as e:
                        self.logger.debug(f"⚠️ {symbol} Sync 체크 Failed: {e}")
                        continue

                # 정상 Status Log (1분에 1times)
                if max_delay > 0 and max_delay < self.sync_threshold:
                    self.logger.debug(
                        f"✅ Sync 정상: 최대 지연 {max_delay:.1f}초 ({delayed_symbol})"
                    )

            except Exception as e:
                self.logger.error(f"❌ Data Sync Check error: {e}")
                time.sleep(10)

    def _stream_flush_detection_loop(self):
        """
        3. Stream Flush 감지 (close event missing → 강제 close)
        """
        self.logger.info("🔍 Stream Flush Detection Starting")

        while self.running:
            try:
                time.sleep(self.flush_check_interval)

                if not self.bulk_manager.connection_active:
                    continue

                current_time = time.time() * 1000  # 밀리초

                # 모든 Subscription Symbol의 Progress 중인 캔들 Confirm
                symbols_to_check = list(self.bulk_manager.subscribed_symbols)[:20]  # 샘플 20count만 체크

                for symbol in symbols_to_check:
                    try:
                        # Current Progress 중인 1minute candles 캔들 Confirm
                        pending_candle = self._get_pending_candle(symbol, '1m')

                        if pending_candle and not pending_candle.get('is_final'):
                            candle_start_time = pending_candle.get('timestamp', 0)
                            candle_age = (current_time - candle_start_time) / 1000  # 초

                            # 캔들이 1분 + 여유Time Exceeded하면 강제 close
                            if candle_age > self.candle_timeout:
                                self.logger.warning(
                                    f"⚠️ {symbol} close event missing: {candle_age:.1f}초 "
                                    f"(Threshold: {self.candle_timeout}초)"
                                )

                                # 강제 close Process
                                self._force_close_candle(symbol, '1m', pending_candle)

                    except Exception as e:
                        self.logger.debug(f"⚠️ {symbol} Flush Detected Failed: {e}")
                        continue

            except Exception as e:
                self.logger.error(f"❌ Stream Flush Detection error: {e}")
                time.sleep(5)

    def _get_latest_candle(self, symbol: str, timeframe: str) -> dict:
        """최신 캔들 조times"""
        try:
            if not hasattr(self.bulk_manager.base_manager, 'kline_buffer'):
                return None

            buffer_key = f"{symbol}_{timeframe}"
            buffer = self.bulk_manager.base_manager.kline_buffer.get(buffer_key, [])

            if buffer:
                return buffer[-1]  # 마지막 캔들

        except Exception as e:
            self.logger.debug(f"최신 캔들 조times Failed ({symbol}): {e}")

        return None

    def _get_pending_candle(self, symbol: str, timeframe: str) -> dict:
        """Progress 중인 캔들 조times"""
        return self._get_latest_candle(symbol, timeframe)

    def _force_close_candle(self, symbol: str, timeframe: str, candle: dict):
        """강제로 캔들 종가 확정"""
        try:
            self.logger.info(f"🔒 {symbol} Candle forced close processing")

            # 캔들의 is_final 플래그 Settings
            candle['is_final'] = True

            # 버퍼 Update
            buffer_key = f"{symbol}_{timeframe}"
            if hasattr(self.bulk_manager.base_manager, 'kline_buffer'):
                buffer = self.bulk_manager.base_manager.kline_buffer.get(buffer_key, [])
                if buffer and buffer[-1] == candle:
                    buffer[-1] = candle

            # 스캔 트리거 (옵션)
            if self.bulk_manager.scan_callback:
                try:
                    self.bulk_manager.scan_callback(symbol, timeframe)
                except Exception as e:
                    self.logger.error(f"스캔 트리거 Failed: {e}")

        except Exception as e:
            self.logger.error(f"❌ 강제 close Failed ({symbol}): {e}")

    def get_status(self) -> dict:
        """방어 시스템 Status 반환"""
        return {
            'running': self.running,
            'active_threads': sum(1 for t in self.threads if t.is_alive()),
            'heartbeat_timeout': self.heartbeat_timeout,
            'sync_threshold': self.sync_threshold,
            'candle_timeout': self.candle_timeout
        }


# Usage 예시
if __name__ == "__main__":
    import logging
    from bulk_websocket_kline_manager import BulkWebSocketKlineManager
    from binance_websocket_kline_manager import BinanceWebSocketKlineManager
    import ccxt

    # 로깅 Settings
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(threadName)s] %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    # Exchange Settings
    exchange = ccxt.binance({
        'options': {'defaultType': 'future'}
    })

    # WebSocket 매니저 Create
    base_ws_manager = BinanceWebSocketKlineManager(logger)
    bulk_manager = BulkWebSocketKlineManager(base_ws_manager, exchange, logger)

    # 방어 시스템 Create 및 Starting
    defense_system = WebSocketDefenseSystem(bulk_manager, logger)
    defense_system.start()

    # Status Confirm
    print("\n방어 System Status:")
    status = defense_system.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")

    # 10초 대기 후 Terminate
    time.sleep(10)
    defense_system.stop()
