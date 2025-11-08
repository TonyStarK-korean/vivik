"""
python-binance 라이브러리를 Usage한 Binance WebSocket Kline Manager
공식 라이브러리 기반으로 안정적이고 신뢰성 있는 구현

주요 기능:
- python-binance BinanceSocketManager Usage
- 여러 Symbol의 1minute candles 실Time 데이터 수신
- 자동 재Connections 및 Error Process
- 동적 Symbol Subscription/Release
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
    python-binance 라이브러리 기반 WebSocket Kline 스트림 Admin
    
    ThreadedWebsocketManager를 Usage하여 안정적인 실Time 가격 데이터를 제공합니다.
    """
    
    def __init__(self, callback: Callable, logger: Optional[logging.Logger] = None):
        """
        WebSocket 매니저 Initialize
        
        Args:
            callback: 가격 Update Callback 함수 (symbol, price, kline_data)
            logger: 로깅 객체
        """
        self.callback = callback
        self.logger = logger or logging.getLogger(__name__)
        
        # python-binance WebSocket 매니저
        self.twm = None
        self.is_running = False
        self.is_connected = False
        
        # Subscription management
        self.subscribed_symbols: Set[str] = set()
        self.stream_keys: Dict[str, str] = {}  # symbol -> stream_key 매핑
        
        # 통계
        self.message_count = 0
        self.error_count = 0
        self.last_message_time = 0
        
        # 데이터 버퍼 (Symbol-Timeframe별 kline 데이터 Save)
        self.kline_buffer: Dict[str, List] = {}
        
        # 스레드 안전성
        self.lock = threading.Lock()
        
    def start(self, max_retries: int = 3, retry_delay: int = 2) -> bool:
        """
        WebSocket Connections Starting
        
        Args:
            max_retries: 최대 재Attempt 횟수
            retry_delay: 재Attempt 간격 (초)
            
        Returns:
            bool: Connections Success 여부
        """
        if self.is_running:
            return True
            
        for attempt in range(max_retries + 1):
            try:
                self.logger.info(f"WebSocket connection attempt {attempt + 1}/{max_retries + 1}")
                
                # ThreadedWebsocketManager Create (API Key 없이 public 스트림 Usage)
                self.twm = ThreadedWebsocketManager()
                self.twm.start()
                
                self.is_running = True
                self.is_connected = True
                self.last_message_time = time.time()
                
                self.logger.info("✅ python-binance WebSocket Starting Success")
                return True
                
            except Exception as e:
                self.logger.error(f"WebSocket Starting Failed (Attempt {attempt + 1}): {e}")
                self.stop()
                if attempt < max_retries:
                    time.sleep(retry_delay)
                    
        self.logger.error("WebSocket Connections Final Failed")
        return False
        
    def stop(self):
        """WebSocket Connections Terminate"""
        self.is_running = False
        self.is_connected = False
        
        if self.twm:
            try:
                # 모든 스트림 중지
                for symbol, stream_key in list(self.stream_keys.items()):
                    try:
                        self.twm.stop_socket(stream_key)
                    except Exception as e:
                        self.logger.debug(f"Stream stop error ({symbol}): {e}")
                
                # ThreadedWebsocketManager Terminate
                self.twm.stop()
            except Exception as e:
                self.logger.debug(f"WebSocket shutdown error: {e}")
            finally:
                self.twm = None
                
        self.subscribed_symbols.clear()
        self.stream_keys.clear()
        
    def _kline_callback_wrapper(self, symbol: str):
        """
        Symbol별 kline Callback 래퍼 Create
        
        Args:
            symbol: Subscription할 Symbol
            
        Returns:
            function: python-binance Callback 함수
        """
        def kline_callback(msg):
            try:
                self.message_count += 1
                self.last_message_time = time.time()
                
                # python-binance Message 형식 Process
                if msg.get('e') == 'kline':
                    kline_data = msg
                    k = msg['k']
                    price = float(k['c'])  # Current price
                    
                    # 데이터 버퍼에 Save (1minute candles 기준)
                    self._store_kline_data(symbol, '1m', kline_data)
                    
                    # 다른 Timeframe 집계 Create
                    self._generate_higher_timeframes(symbol, kline_data)
                    
                    # Usage자 Callback 호출
                    if self.callback:
                        try:
                            self.callback(symbol, price, kline_data)
                        except Exception as e:
                            self.logger.error(f"Callback processing error ({symbol}): {e}")
                            
            except Exception as e:
                self.logger.error(f"kline Callback Error ({symbol}): {e}")
                self.error_count += 1
                
        return kline_callback
        
    def subscribe_symbol(self, symbol: str) -> bool:
        """
        Symbol Subscription
        
        Args:
            symbol: Subscription할 Symbol (예: "BTCUSDT")
            
        Returns:
            bool: Subscription success 여부
        """
        if not self.is_running or not self.twm:
            self.logger.error(f"WebSocket not started - {symbol} subscription impossible (running: {self.is_running}, twm: {self.twm is not None})")
            return False
            
        with self.lock:
            # Symbol 정규화
            clean_symbol = symbol.upper().replace('/', '').replace(':USDT', '')
            
            if clean_symbol in self.subscribed_symbols:
                self.logger.debug(f"{clean_symbol} Already subscribed")
                return True
                
            try:
                self.logger.debug(f"Subscription attempt: {clean_symbol}")
                
                # python-binance kline 스트림 Starting
                callback = self._kline_callback_wrapper(clean_symbol)
                stream_key = self.twm.start_kline_socket(
                    callback=callback,
                    symbol=clean_symbol,
                    interval='1m'
                )
                
                if stream_key:
                    # Subscription Info Save
                    self.subscribed_symbols.add(clean_symbol)
                    self.stream_keys[clean_symbol] = stream_key
                    
                    self.logger.info(f"✅ {clean_symbol} Subscription success (Key: {stream_key})")
                    return True
                else:
                    self.logger.error(f"❌ {clean_symbol} Subscription failed - stream_key None")
                    return False
                
            except Exception as e:
                self.logger.error(f"❌ {clean_symbol} Subscription exception: {e}")
                import traceback
                self.logger.error(f"Detailed error: {traceback.format_exc()}")
                return False
                
    def unsubscribe_symbol(self, symbol: str) -> bool:
        """
        Symbol Unsubscribe
        
        Args:
            symbol: Unsubscribe할 Symbol
            
        Returns:
            bool: Unsubscribe Success 여부
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
                    
                # Subscription Info Remove
                self.subscribed_symbols.discard(clean_symbol)
                self.stream_keys.pop(clean_symbol, None)
                
                self.logger.debug(f"❌ {clean_symbol} Unsubscribe")
                return True
                
            except Exception as e:
                self.logger.error(f"Unsubscribe Failed ({clean_symbol}): {e}")
                return False
                
    def subscribe_batch(self, symbols: List[str], timeframes: List[str] = None, 
                       load_history: bool = False, batch_size: int = None, 
                       delay: float = 0.01, max_workers: int = None) -> int:
        """
        여러 Symbol 일괄 Subscription (전략 호환성을 위한 확장 파라미터 지원)
        
        Args:
            symbols: Subscription할 Symbol 리스트
            timeframes: Timeframe 리스트 (Current는 1m만 지원하므로 무시)
            load_history: 히스토리 Load 여부 (Current 미지원, 무시)
            batch_size: Batch Size (Current 미Usage)
            delay: Subscription 간 지연 Time
            max_workers: 최대 워커 수 (Current 미Usage)
            
        Returns:
            int: Success한 Subscription 수
        """
        if timeframes:
            self.logger.info(f"Batch subscription start: {len(symbols)} Symbol, Timeframe: {timeframes}")
        else:
            self.logger.info(f"Batch subscription start: {len(symbols)} Symbol")
            
        success_count = 0
        
        for symbol in symbols:
            try:
                if self.subscribe_symbol(symbol):
                    success_count += 1
                else:
                    self.logger.warning(f"Subscription failed: {symbol}")
            except Exception as e:
                self.logger.error(f"Subscription Error ({symbol}): {e}")
                
            # Subscription 간 지연 (python-binance 안정성을 위해)
            if delay > 0:
                time.sleep(delay)
            
        self.logger.info(f"Batch subscription complete: {success_count}/{len(symbols)} Success")
        return success_count
        
    def unsubscribe_batch(self, symbols: List[str]) -> int:
        """
        여러 Symbol Batch unsubscribe complete
        
        Args:
            symbols: Unsubscribe할 Symbol 리스트
            
        Returns:
            int: Success한 Unsubscribe 수
        """
        success_count = 0
        
        for symbol in symbols:
            if self.unsubscribe_symbol(symbol):
                success_count += 1
                
        self.logger.info(f"Batch unsubscribe complete: {success_count}/{len(symbols)} Success")
        return success_count
        
    def get_subscribed_symbols(self) -> Set[str]:
        """Current Subscription 중인 Symbol 목록 반환"""
        with self.lock:
            return self.subscribed_symbols.copy()
            
    def get_stats(self) -> dict:
        """WebSocket 통계 Info 반환"""
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
        """WebSocket Status 건강성 체크"""
        if not self.is_connected or not self.is_running:
            return False
            
        # ThreadedWebsocketManager Status 체크
        if not self.twm:
            return False
            
        # 30초 이상 Message가 없으면 비정상 (Subscription이 있는 경우)
        if len(self.subscribed_symbols) > 0 and self.last_message_time > 0:
            age = time.time() - self.last_message_time
            if age > 30:
                return False
                
        return True
    
    def _store_kline_data(self, symbol: str, timeframe: str, kline_data: dict):
        """Kline 데이터를 버퍼에 Save"""
        try:
            with self.lock:
                # 버퍼 Key Create
                buffer_key = f"{symbol}_{timeframe}"
                
                if buffer_key not in self.kline_buffer:
                    self.kline_buffer[buffer_key] = []
                
                # Kline 데이터에서 Required한 Info 추출
                k = kline_data.get('k', {})
                candle = {
                    'timestamp': k.get('t', 0),
                    'open': float(k.get('o', 0)),
                    'high': float(k.get('h', 0)),
                    'low': float(k.get('l', 0)),
                    'close': float(k.get('c', 0)),
                    'volume': float(k.get('v', 0)),
                    'close_time': k.get('T', 0),
                    'is_final': k.get('x', False)  # 캔들 Complete 여부
                }
                
                # Legacy 데이터가 있으면 마지막 캔들 Update, 없으면 Add
                buffer = self.kline_buffer[buffer_key]
                if buffer and buffer[-1]['timestamp'] == candle['timestamp']:
                    # 같은 타임스탬프의 캔들 Update
                    buffer[-1] = candle
                else:
                    # New 캔들 Add
                    buffer.append(candle)
                
                # 버퍼 Size 제한 (최대 1500count)
                if len(buffer) > 1500:
                    self.kline_buffer[buffer_key] = buffer[-1500:]
        
        except Exception as e:
            self.logger.error(f"Kline data save failed ({symbol}, {timeframe}): {e}")
    
    def get_kline_buffer(self, symbol: str, timeframe: str, limit: int = 1000, as_dataframe: bool = True):
        """버퍼에서 Kline 데이터 조times"""
        try:
            with self.lock:
                buffer_key = f"{symbol}_{timeframe}"
                
                if buffer_key not in self.kline_buffer:
                    return pd.DataFrame() if as_dataframe else []
                
                buffer = self.kline_buffer[buffer_key]
                
                # 최신 limitcount 선택
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
            self.logger.error(f"Kline Buffer 조times Failed ({symbol}, {timeframe}): {e}")
            return pd.DataFrame() if as_dataframe else []
    
    def _generate_higher_timeframes(self, symbol: str, kline_data: dict):
        """1minute candles 데이터로부터 다른 Timeframe 집계 Create"""
        try:
            # Timeframe별 분 단위
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
            
            # 각 Timeframe별로 집계
            for tf, minutes in timeframe_minutes.items():
                # 타임스탬프를 해당 Timeframe의 Starting Time으로 맞춤
                aligned_timestamp = self._align_timestamp(timestamp, minutes)
                
                with self.lock:
                    buffer_key = f"{symbol}_{tf}"
                    
                    if buffer_key not in self.kline_buffer:
                        self.kline_buffer[buffer_key] = []
                    
                    buffer = self.kline_buffer[buffer_key]
                    
                    # Legacy 캔들이 있고 같은 타임스탬프면 Update
                    if buffer and buffer[-1]['timestamp'] == aligned_timestamp:
                        # Legacy 캔들 Update
                        existing = buffer[-1]
                        existing['high'] = max(existing['high'], float(k.get('h', 0)))
                        existing['low'] = min(existing['low'], float(k.get('l', 0)))
                        existing['close'] = float(k.get('c', 0))
                        existing['volume'] += float(k.get('v', 0))
                        existing['close_time'] = k.get('T', 0)
                        existing['is_final'] = k.get('x', False)
                    else:
                        # New 캔들 Create
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
                    
                    # 버퍼 Size 제한
                    if len(buffer) > 1500:
                        self.kline_buffer[buffer_key] = buffer[-1500:]
        
        except Exception as e:
            self.logger.error(f"상위 Timeframe Create Failed ({symbol}): {e}")
    
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
            self.logger.error(f"Timestamp alignment failed ({timestamp}, {minutes}): {e}")
            return timestamp


# Usage 예시
if __name__ == "__main__":
    import logging
    
    # 로깅 Settings
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Message 카운터
    message_count = 0
    received_symbols = set()
    
    def price_callback(symbol: str, price: float, kline_data: dict):
        global message_count, received_symbols
        message_count += 1
        received_symbols.add(symbol)
        
        if message_count <= 5:
            print(f"[CALLBACK] {symbol}: ${price:.2f}")
    
    # WebSocket 매니저 Create 및 Test
    manager = BinanceWebSocketKlineManager(price_callback, logger)
    
    try:
        print("=== python-binance WebSocket Test Starting ===")
        
        # Starting
        if manager.start():
            print("✅ WebSocket Starting Success")
            
            # Test Symbol Subscription
            test_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
            success_count = manager.subscribe_batch(test_symbols)
            print(f"Subscription success: {success_count}/{len(test_symbols)}")
            
            # 15초 동안 데이터 수신 Test
            print("15초 동안 데이터 Received Test...")
            time.sleep(15)
            
            # 통계 출력
            stats = manager.get_stats()
            print(f"\n📊 Test 결과:")
            print(f"  - 총 Message Received: {message_count}")
            print(f"  - Received된 Symbol: {len(received_symbols)} ({', '.join(received_symbols)})")
            print(f"  - Connections Status: {'✅ 정상' if stats['is_connected'] else '❌ 끊김'}")
            print(f"  - Subscription 중인 Symbol: {stats['subscribed_count']}count")
            print(f"  - 스트림 수: {stats['stream_count']}")
            print(f"  - 마지막 Message: {stats['last_message_age']:.1f}초 전")
            print(f"  - 강성: {'✅ 정상' if manager.is_healthy() else '❌ 비정상'}")
            
            if message_count > 0:
                print("🎉 python-binance WebSocket 매니저 정상 작동!")
            else:
                print("⚠️ Message Received Absent")
                
        else:
            print("❌ WebSocket Starting Failed")
            
    except KeyboardInterrupt:
        print("\n🛑 Usage자에 의한 중단")
        
    except Exception as e:
        print(f"❌ Test 중 Error: {e}")
        
    finally:
        print("🔌 Closing WebSocket connection...")
        manager.stop()
        print("✅ Test Complete")