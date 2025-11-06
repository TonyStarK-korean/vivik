# -*- coding: utf-8 -*-
"""
WebSocket Defense System
실전 필수 방어 로직 3종

1. Heartbeat 감시 (30초 무응답 → reconnect)
2. 데이터 동기화 체크 (2분 지연 → reconnect)
3. Stream Flush 감지 (close 이벤트 누락 → 강제 close)
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

        # 방어 설정
        self.heartbeat_check_interval = 10  # 10초마다 체크
        self.heartbeat_timeout = 30  # 30초 무응답 시 재연결

        self.sync_check_interval = 30  # 30초마다 체크
        self.sync_threshold = 120  # 2분 지연 시 재연결

        self.flush_check_interval = 5  # 5초마다 체크
        self.candle_timeout = 65  # 1분 + 5초 여유

        # 스레드 관리
        self.running = False
        self.threads = []

        self.logger.info("🛡️ WebSocket Defense System 초기화 완료")

    def start(self):
        """방어 시스템 시작 (백그라운드 스레드)"""
        if self.running:
            self.logger.warning("⚠️ 방어 시스템이 이미 실행 중입니다")
            return

        self.running = True

        # 3가지 방어 로직 스레드 시작
        threads_config = [
            ("Heartbeat Monitor", self._heartbeat_monitor_loop),
            ("Data Sync Check", self._data_sync_check_loop),
            ("Stream Flush Detection", self._stream_flush_detection_loop)
        ]

        for name, target in threads_config:
            thread = threading.Thread(target=target, name=name, daemon=True)
            thread.start()
            self.threads.append(thread)
            self.logger.info(f"✅ {name} 스레드 시작")

        self.logger.info("🚀 WebSocket Defense System 가동 완료 (3개 스레드)")

    def stop(self):
        """방어 시스템 중지"""
        self.running = False
        self.logger.info("🛑 WebSocket Defense System 중지됨")

    def _heartbeat_monitor_loop(self):
        """
        1. Heartbeat 감시 (30초 이상 수신 없음 → reconnect)
        """
        self.logger.info("💓 Heartbeat Monitor 시작")

        while self.running:
            try:
                time.sleep(self.heartbeat_check_interval)

                if not self.bulk_manager.connection_active:
                    continue  # 연결이 끊긴 상태면 스킵

                # 마지막 메시지 수신 시간 확인
                elapsed = time.time() - self.bulk_manager.last_message_time

                if elapsed > self.heartbeat_timeout:
                    self.logger.warning(
                        f"⚠️ Heartbeat 끊김: {elapsed:.1f}초 무응답 "
                        f"(임계값: {self.heartbeat_timeout}초)"
                    )

                    # 재연결 트리거
                    self.bulk_manager.handle_connection_loss()

                    # 마지막 메시지 시간 갱신 (재연결 시도 후)
                    self.bulk_manager.last_message_time = time.time()

            except Exception as e:
                self.logger.error(f"❌ Heartbeat Monitor 에러: {e}")
                time.sleep(5)  # 에러 시 5초 대기

    def _data_sync_check_loop(self):
        """
        2. 데이터 동기화 체크 (2분 이상 지연 → reconnect)
        """
        self.logger.info("🔄 Data Sync Check 시작")

        while self.running:
            try:
                time.sleep(self.sync_check_interval)

                if not self.bulk_manager.connection_active:
                    continue

                # 모든 구독 심볼의 최근 캔들 확인
                symbols_to_check = list(self.bulk_manager.subscribed_symbols)[:10]  # 샘플 10개만 체크

                max_delay = 0
                delayed_symbol = None

                for symbol in symbols_to_check:
                    try:
                        # 1분봉 최신 캔들 타임스탬프 확인
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
                                    f"⚠️ {symbol} 데이터 지연: {delay:.1f}초 "
                                    f"(임계값: {self.sync_threshold}초)"
                                )

                                # 재연결 트리거
                                self.bulk_manager.handle_connection_loss()
                                break

                    except Exception as e:
                        self.logger.debug(f"⚠️ {symbol} 동기화 체크 실패: {e}")
                        continue

                # 정상 상태 로그 (1분에 1회)
                if max_delay > 0 and max_delay < self.sync_threshold:
                    self.logger.debug(
                        f"✅ 동기화 정상: 최대 지연 {max_delay:.1f}초 ({delayed_symbol})"
                    )

            except Exception as e:
                self.logger.error(f"❌ Data Sync Check 에러: {e}")
                time.sleep(10)

    def _stream_flush_detection_loop(self):
        """
        3. Stream Flush 감지 (close 이벤트 누락 → 강제 close)
        """
        self.logger.info("🔍 Stream Flush Detection 시작")

        while self.running:
            try:
                time.sleep(self.flush_check_interval)

                if not self.bulk_manager.connection_active:
                    continue

                current_time = time.time() * 1000  # 밀리초

                # 모든 구독 심볼의 진행 중인 캔들 확인
                symbols_to_check = list(self.bulk_manager.subscribed_symbols)[:20]  # 샘플 20개만 체크

                for symbol in symbols_to_check:
                    try:
                        # 현재 진행 중인 1분봉 캔들 확인
                        pending_candle = self._get_pending_candle(symbol, '1m')

                        if pending_candle and not pending_candle.get('is_final'):
                            candle_start_time = pending_candle.get('timestamp', 0)
                            candle_age = (current_time - candle_start_time) / 1000  # 초

                            # 캔들이 1분 + 여유시간 초과하면 강제 close
                            if candle_age > self.candle_timeout:
                                self.logger.warning(
                                    f"⚠️ {symbol} close 이벤트 누락: {candle_age:.1f}초 "
                                    f"(임계값: {self.candle_timeout}초)"
                                )

                                # 강제 close 처리
                                self._force_close_candle(symbol, '1m', pending_candle)

                    except Exception as e:
                        self.logger.debug(f"⚠️ {symbol} Flush 감지 실패: {e}")
                        continue

            except Exception as e:
                self.logger.error(f"❌ Stream Flush Detection 에러: {e}")
                time.sleep(5)

    def _get_latest_candle(self, symbol: str, timeframe: str) -> dict:
        """최신 캔들 조회"""
        try:
            if not hasattr(self.bulk_manager.base_manager, 'kline_buffer'):
                return None

            buffer_key = f"{symbol}_{timeframe}"
            buffer = self.bulk_manager.base_manager.kline_buffer.get(buffer_key, [])

            if buffer:
                return buffer[-1]  # 마지막 캔들

        except Exception as e:
            self.logger.debug(f"최신 캔들 조회 실패 ({symbol}): {e}")

        return None

    def _get_pending_candle(self, symbol: str, timeframe: str) -> dict:
        """진행 중인 캔들 조회"""
        return self._get_latest_candle(symbol, timeframe)

    def _force_close_candle(self, symbol: str, timeframe: str, candle: dict):
        """강제로 캔들 종가 확정"""
        try:
            self.logger.info(f"🔒 {symbol} 캔들 강제 close 처리")

            # 캔들의 is_final 플래그 설정
            candle['is_final'] = True

            # 버퍼 업데이트
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
                    self.logger.error(f"스캔 트리거 실패: {e}")

        except Exception as e:
            self.logger.error(f"❌ 강제 close 실패 ({symbol}): {e}")

    def get_status(self) -> dict:
        """방어 시스템 상태 반환"""
        return {
            'running': self.running,
            'active_threads': sum(1 for t in self.threads if t.is_alive()),
            'heartbeat_timeout': self.heartbeat_timeout,
            'sync_threshold': self.sync_threshold,
            'candle_timeout': self.candle_timeout
        }


# 사용 예시
if __name__ == "__main__":
    import logging
    from bulk_websocket_kline_manager import BulkWebSocketKlineManager
    from binance_websocket_kline_manager import BinanceWebSocketKlineManager
    import ccxt

    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(threadName)s] %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    # Exchange 설정
    exchange = ccxt.binance({
        'options': {'defaultType': 'future'}
    })

    # WebSocket 매니저 생성
    base_ws_manager = BinanceWebSocketKlineManager(logger)
    bulk_manager = BulkWebSocketKlineManager(base_ws_manager, exchange, logger)

    # 방어 시스템 생성 및 시작
    defense_system = WebSocketDefenseSystem(bulk_manager, logger)
    defense_system.start()

    # 상태 확인
    print("\n방어 시스템 상태:")
    status = defense_system.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")

    # 10초 대기 후 종료
    time.sleep(10)
    defense_system.stop()
