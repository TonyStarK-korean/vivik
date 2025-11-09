"""
python-binance 라이브러리를 사용한 Binance WebSocket Kline Manager
공식 라이브러리 기반으로 안정적이고 신뢰성 있는 구현

주요 기능:
- python-binance BinanceSocketManager 사용
- 여러 심볼의 1분봉 실시간 데이터 수신
- 자동 재연결 및 오류 처리
- 동적 심볼 구독/해제
- 스레드 안전성 보장
"""

import asyncio
import threading
import time
import logging
import pandas as pd
from typing import Callable, Optional, Set, Dict, List
from binance import ThreadedWebsocketManager
from binance.client import Client


class BinanceWebSocketKlineManager:
    """
    python-binance 라이브러리 기반 WebSocket Kline 스트림 관리자
    
    ThreadedWebsocketManager를 사용하여 안정적인 실시간 가격 데이터를 제공합니다.
    """
    
    def __init__(self, callback: Callable, logger: Optional[logging.Logger] = None):
        """
        WebSocket 매니저 초기화
        
        Args:
            callback: 가격 업데이트 콜백 함수 (symbol, price, kline_data)
            logger: 로깅 객체
        """
        self.callback = callback
        self.logger = logger or logging.getLogger(__name__)
        
        # python-binance WebSocket 매니저
        self.twm = None
        self.is_running = False
        self.is_connected = False
        
        # 구독 관리
        self.subscribed_symbols: Set[str] = set()
        self.stream_keys: Dict[str, str] = {}  # symbol -> stream_key 매핑
        
        # 통계
        self.message_count = 0
        self.error_count = 0
        self.last_message_time = 0
        
        # 데이터 버퍼 (심볼-타임프레임별 kline 데이터 저장)
        self.kline_buffer: Dict[str, List] = {}
        
        # 스레드 안전성
        self.lock = threading.Lock()
        
    def start(self, max_retries: int = 3, retry_delay: int = 2) -> bool:
        """
        WebSocket 연결 시작
        
        Args:
            max_retries: 최대 재시도 횟수
            retry_delay: 재시도 간격 (초)
            
        Returns:
            bool: 연결 성공 여부
        """
        if self.is_running:
            return True
            
        for attempt in range(max_retries + 1):
            try:
                self.logger.info(f"WebSocket 연결 시도 {attempt + 1}/{max_retries + 1}")
                
                # ThreadedWebsocketManager 생성 (API 키 없이 public 스트림 사용)
                self.twm = ThreadedWebsocketManager()
                self.twm.start()
                
                self.is_running = True
                self.is_connected = True
                self.last_message_time = time.time()
                
                self.logger.info("✅ python-binance WebSocket 시작 성공")
                return True
                
            except Exception as e:
                self.logger.error(f"WebSocket 시작 실패 (시도 {attempt + 1}): {e}")
                self.stop()
                if attempt < max_retries:
                    time.sleep(retry_delay)
                    
        self.logger.error("WebSocket 연결 최종 실패")
        return False
        
    def stop(self):
        """WebSocket 연결 종료"""
        self.is_running = False
        self.is_connected = False
        
        if self.twm:
            try:
                # 모든 스트림 중지
                for symbol, stream_key in list(self.stream_keys.items()):
                    try:
                        self.twm.stop_socket(stream_key)
                    except Exception as e:
                        self.logger.debug(f"스트림 중지 오류 ({symbol}): {e}")
                
                # ThreadedWebsocketManager 종료
                self.twm.stop()
            except Exception as e:
                self.logger.debug(f"WebSocket 종료 오류: {e}")
            finally:
                self.twm = None
                
        self.subscribed_symbols.clear()
        self.stream_keys.clear()
        
    def _kline_callback_wrapper(self, symbol: str):
        """
        심볼별 kline 콜백 래퍼 생성
        
        Args:
            symbol: 구독할 심볼
            
        Returns:
            function: python-binance 콜백 함수
        """
        def kline_callback(msg):
            try:
                self.message_count += 1
                self.last_message_time = time.time()
                
                # python-binance 메시지 형식 처리
                if msg.get('e') == 'kline':
                    kline_data = msg
                    k = msg['k']
                    price = float(k['c'])  # 현재가
                    
                    # 데이터 버퍼에 저장 (1분봉 기준)
                    self._store_kline_data(symbol, '1m', kline_data)
                    
                    # 다른 타임프레임 집계 생성
                    self._generate_higher_timeframes(symbol, kline_data)
                    
                    # 사용자 콜백 호출
                    if self.callback:
                        try:
                            self.callback(symbol, price, kline_data)
                        except Exception as e:
                            self.logger.error(f"콜백 처리 오류 ({symbol}): {e}")
                            
            except Exception as e:
                self.logger.error(f"kline 콜백 오류 ({symbol}): {e}")
                self.error_count += 1
                
        return kline_callback
        
    def subscribe_symbol(self, symbol: str) -> bool:
        """
        심볼 구독
        
        Args:
            symbol: 구독할 심볼 (예: "BTCUSDT")
            
        Returns:
            bool: 구독 성공 여부
        """
        if not self.is_running or not self.twm:
            self.logger.error(f"WebSocket 미시작 - {symbol} 구독 불가 (running: {self.is_running}, twm: {self.twm is not None})")
            return False
            
        with self.lock:
            # 심볼 정규화
            clean_symbol = symbol.upper().replace('/', '').replace(':USDT', '')
            
            if clean_symbol in self.subscribed_symbols:
                self.logger.debug(f"{clean_symbol} 이미 구독됨")
                return True
                
            try:
                self.logger.debug(f"구독 시도: {clean_symbol}")
                
                # python-binance kline 스트림 시작
                callback = self._kline_callback_wrapper(clean_symbol)
                stream_key = self.twm.start_kline_socket(
                    callback=callback,
                    symbol=clean_symbol,
                    interval='1m'
                )
                
                if stream_key:
                    # 구독 정보 저장
                    self.subscribed_symbols.add(clean_symbol)
                    self.stream_keys[clean_symbol] = stream_key
                    
                    self.logger.info(f"✅ {clean_symbol} 구독 성공 (키: {stream_key})")
                    return True
                else:
                    self.logger.error(f"❌ {clean_symbol} 구독 실패 - stream_key None")
                    return False
                
            except Exception as e:
                self.logger.error(f"❌ {clean_symbol} 구독 예외: {e}")
                import traceback
                self.logger.error(f"상세 오류: {traceback.format_exc()}")
                return False
                
    def unsubscribe_symbol(self, symbol: str) -> bool:
        """
        심볼 구독 해제
        
        Args:
            symbol: 구독 해제할 심볼
            
        Returns:
            bool: 구독 해제 성공 여부
        """
        if not self.is_running or not self.twm:
            return True
            
        with self.lock:
            clean_symbol = symbol.upper().replace('/', '').replace(':USDT', '')
            
            if clean_symbol not in self.subscribed_symbols:
                return True
                
            try:
                # 스트림 중지
                stream_key = self.stream_keys.get(clean_symbol)
                if stream_key:
                    self.twm.stop_socket(stream_key)
                    
                # 구독 정보 제거
                self.subscribed_symbols.discard(clean_symbol)
                self.stream_keys.pop(clean_symbol, None)
                
                self.logger.debug(f"❌ {clean_symbol} 구독 해제")
                return True
                
            except Exception as e:
                self.logger.error(f"구독 해제 실패 ({clean_symbol}): {e}")
                return False
                
    def subscribe_batch(self, symbols: List[str], timeframes: List[str] = None, 
                       load_history: bool = False, batch_size: int = None, 
                       delay: float = 0.01, max_workers: int = None) -> int:
        """
        여러 심볼 일괄 구독 (전략 호환성을 위한 확장 파라미터 지원)
        
        Args:
            symbols: 구독할 심볼 리스트
            timeframes: 타임프레임 리스트 (현재는 1m만 지원하므로 무시)
            load_history: 히스토리 로드 여부 (현재 미지원, 무시)
            batch_size: 배치 크기 (현재 미사용)
            delay: 구독 간 지연 시간
            max_workers: 최대 워커 수 (현재 미사용)
            
        Returns:
            int: 성공한 구독 수
        """
        if timeframes:
            self.logger.info(f"배치 구독 시작: {len(symbols)} 심볼, 타임프레임: {timeframes}")
        else:
            self.logger.info(f"배치 구독 시작: {len(symbols)} 심볼")
            
        success_count = 0
        
        for symbol in symbols:
            try:
                if self.subscribe_symbol(symbol):
                    success_count += 1
                else:
                    self.logger.warning(f"구독 실패: {symbol}")
            except Exception as e:
                self.logger.error(f"구독 오류 ({symbol}): {e}")
                
            # 구독 간 지연 (python-binance 안정성을 위해)
            if delay > 0:
                time.sleep(delay)
            
        self.logger.info(f"일괄 구독 완료: {success_count}/{len(symbols)} 성공")
        return success_count
        
    def unsubscribe_batch(self, symbols: List[str]) -> int:
        """
        여러 심볼 일괄 구독 해제
        
        Args:
            symbols: 구독 해제할 심볼 리스트
            
        Returns:
            int: 성공한 구독 해제 수
        """
        success_count = 0
        
        for symbol in symbols:
            if self.unsubscribe_symbol(symbol):
                success_count += 1
                
        self.logger.info(f"일괄 구독 해제: {success_count}/{len(symbols)} 성공")
        return success_count
        
    def get_subscribed_symbols(self) -> Set[str]:
        """현재 구독 중인 심볼 목록 반환"""
        with self.lock:
            return self.subscribed_symbols.copy()
            
    def get_stats(self) -> dict:
        """WebSocket 통계 정보 반환"""
        return {
            'is_connected': self.is_connected,
            'is_running': self.is_running,
            'subscribed_count': len(self.subscribed_symbols),
            'message_count': self.message_count,
            'error_count': self.error_count,
            'stream_count': len(self.stream_keys),
            'last_message_age': time.time() - self.last_message_time if self.last_message_time > 0 else -1
        }
        
    def is_healthy(self) -> bool:
        """WebSocket 상태 건강성 체크"""
        if not self.is_connected or not self.is_running:
            return False
            
        # ThreadedWebsocketManager 상태 체크
        if not self.twm:
            return False
            
        # 30초 이상 메시지가 없으면 비정상 (구독이 있는 경우)
        if len(self.subscribed_symbols) > 0 and self.last_message_time > 0:
            age = time.time() - self.last_message_time
            if age > 30:
                return False
                
        return True
    
    def _store_kline_data(self, symbol: str, timeframe: str, kline_data: dict):
        """Kline 데이터를 버퍼에 저장"""
        try:
            with self.lock:
                # 버퍼 키 생성
                buffer_key = f"{symbol}_{timeframe}"
                
                if buffer_key not in self.kline_buffer:
                    self.kline_buffer[buffer_key] = []
                
                # Kline 데이터에서 필요한 정보 추출
                k = kline_data.get('k', {})
                candle = {
                    'timestamp': k.get('t', 0),
                    'open': float(k.get('o', 0)),
                    'high': float(k.get('h', 0)),
                    'low': float(k.get('l', 0)),
                    'close': float(k.get('c', 0)),
                    'volume': float(k.get('v', 0)),
                    'close_time': k.get('T', 0),
                    'is_final': k.get('x', False)  # 캔들 완료 여부
                }
                
                # 기존 데이터가 있으면 마지막 캔들 업데이트, 없으면 추가
                buffer = self.kline_buffer[buffer_key]
                if buffer and buffer[-1]['timestamp'] == candle['timestamp']:
                    # 같은 타임스탬프의 캔들 업데이트
                    buffer[-1] = candle
                else:
                    # 새로운 캔들 추가
                    buffer.append(candle)
                
                # 버퍼 크기 제한 (최대 1500개)
                if len(buffer) > 1500:
                    self.kline_buffer[buffer_key] = buffer[-1500:]
        
        except Exception as e:
            self.logger.error(f"Kline 데이터 저장 실패 ({symbol}, {timeframe}): {e}")
    
    def get_kline_buffer(self, symbol: str, timeframe: str, limit: int = 1000, as_dataframe: bool = True):
        """버퍼에서 Kline 데이터 조회"""
        try:
            with self.lock:
                buffer_key = f"{symbol}_{timeframe}"
                
                if buffer_key not in self.kline_buffer:
                    return pd.DataFrame() if as_dataframe else []
                
                buffer = self.kline_buffer[buffer_key]
                
                # 최신 limit개 선택
                if limit > 0:
                    selected_data = buffer[-limit:] if len(buffer) > limit else buffer
                else:
                    selected_data = buffer
                
                if not selected_data:
                    return pd.DataFrame() if as_dataframe else []
                
                if as_dataframe:
                    # DataFrame으로 변환
                    df_data = []
                    for candle in selected_data:
                        df_data.append([
                            candle['timestamp'],
                            candle['open'],
                            candle['high'],
                            candle['low'],
                            candle['close'],
                            candle['volume']
                        ])
                    
                    df = pd.DataFrame(df_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    # 타임스탬프를 datetime으로 변환
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    return df
                else:
                    return selected_data
        
        except Exception as e:
            self.logger.error(f"Kline 버퍼 조회 실패 ({symbol}, {timeframe}): {e}")
            return pd.DataFrame() if as_dataframe else []
    
    def _generate_higher_timeframes(self, symbol: str, kline_data: dict):
        """1분봉 데이터로부터 다른 타임프레임 집계 생성"""
        try:
            # 타임프레임별 분 단위
            timeframe_minutes = {
                '3m': 3,
                '5m': 5,
                '15m': 15,
                '1d': 1440  # 1일 = 1440분
            }
            
            k = kline_data.get('k', {})
            timestamp = k.get('t', 0)
            if not timestamp:
                return
            
            # 각 타임프레임별로 집계
            for tf, minutes in timeframe_minutes.items():
                # 타임스탬프를 해당 타임프레임의 시작 시간으로 맞춤
                aligned_timestamp = self._align_timestamp(timestamp, minutes)
                
                with self.lock:
                    buffer_key = f"{symbol}_{tf}"
                    
                    if buffer_key not in self.kline_buffer:
                        self.kline_buffer[buffer_key] = []
                    
                    buffer = self.kline_buffer[buffer_key]
                    
                    # 기존 캔들이 있고 같은 타임스탬프면 업데이트
                    if buffer and buffer[-1]['timestamp'] == aligned_timestamp:
                        # 기존 캔들 업데이트
                        existing = buffer[-1]
                        existing['high'] = max(existing['high'], float(k.get('h', 0)))
                        existing['low'] = min(existing['low'], float(k.get('l', 0)))
                        existing['close'] = float(k.get('c', 0))
                        existing['volume'] += float(k.get('v', 0))
                        existing['close_time'] = k.get('T', 0)
                        existing['is_final'] = k.get('x', False)
                    else:
                        # 새로운 캔들 생성
                        new_candle = {
                            'timestamp': aligned_timestamp,
                            'open': float(k.get('o', 0)),
                            'high': float(k.get('h', 0)),
                            'low': float(k.get('l', 0)),
                            'close': float(k.get('c', 0)),
                            'volume': float(k.get('v', 0)),
                            'close_time': k.get('T', 0),
                            'is_final': k.get('x', False)
                        }
                        buffer.append(new_candle)
                    
                    # 버퍼 크기 제한
                    if len(buffer) > 1500:
                        self.kline_buffer[buffer_key] = buffer[-1500:]
        
        except Exception as e:
            self.logger.error(f"상위 타임프레임 생성 실패 ({symbol}): {e}")
    
    def _align_timestamp(self, timestamp: int, minutes: int) -> int:
        """타임스탬프를 지정된 분 단위로 정렬"""
        try:
            # 밀리초를 초로 변환
            seconds = timestamp // 1000
            
            # 분 단위로 변환
            minutes_since_epoch = seconds // 60
            
            # 지정된 분 단위로 정렬
            aligned_minutes = (minutes_since_epoch // minutes) * minutes
            
            # 밀리초로 다시 변환
            return aligned_minutes * 60 * 1000
        
        except Exception as e:
            self.logger.error(f"타임스탬프 정렬 실패 ({timestamp}, {minutes}): {e}")
            return timestamp


# 사용 예시
if __name__ == "__main__":
    import logging
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # 메시지 카운터
    message_count = 0
    received_symbols = set()
    
    def price_callback(symbol: str, price: float, kline_data: dict):
        global message_count, received_symbols
        message_count += 1
        received_symbols.add(symbol)
        
        if message_count <= 5:
            print(f"[CALLBACK] {symbol}: ${price:.2f}")
    
    # WebSocket 매니저 생성 및 테스트
    manager = BinanceWebSocketKlineManager(price_callback, logger)
    
    try:
        print("=== python-binance WebSocket 테스트 시작 ===")
        
        # 시작
        if manager.start():
            print("✅ WebSocket 시작 성공")
            
            # 테스트 심볼 구독 제거 - 하드코딩된 샘플 완전 삭제
            print("WebSocket 매니저 테스트 준비 완료 (샘플 심볼 제거됨)")
            
            # 15초 동안 데이터 수신 테스트
            print("15초 동안 데이터 수신 테스트...")
            time.sleep(15)
            
            # 통계 출력
            stats = manager.get_stats()
            print(f"\n📊 테스트 결과:")
            print(f"  - 총 메시지 수신: {message_count}")
            print(f"  - 수신된 심볼: {len(received_symbols)} ({', '.join(received_symbols)})")
            print(f"  - 연결 상태: {'✅ 정상' if stats['is_connected'] else '❌ 끊김'}")
            print(f"  - 구독 중인 심볼: {stats['subscribed_count']}개")
            print(f"  - 스트림 수: {stats['stream_count']}")
            print(f"  - 마지막 메시지: {stats['last_message_age']:.1f}초 전")
            print(f"  - 건강성: {'✅ 정상' if manager.is_healthy() else '❌ 비정상'}")
            
            if message_count > 0:
                print("🎉 python-binance WebSocket 매니저 정상 작동!")
            else:
                print("⚠️ 메시지 수신 없음")
                
        else:
            print("❌ WebSocket 시작 실패")
            
    except KeyboardInterrupt:
        print("\n🛑 사용자에 의한 중단")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류: {e}")
        
    finally:
        print("🔌 WebSocket 연결 종료 중...")
        manager.stop()
        print("✅ 테스트 완료")