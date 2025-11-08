# -*- coding: utf-8 -*-
"""
최적화된 WebSocket 스캔 시스템
- 100% WebSocket 기반 스캔
- IP 차단 없는 실시간 스캔
- 최대 속도 + 최소 지연
"""

import time
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import threading

@dataclass
class SymbolData:
    """심볼별 실시간 데이터"""
    symbol: str
    current_price: float
    change_24h: float
    volume_24h: float
    kline_1m: List[Dict]
    kline_3m: List[Dict] 
    kline_5m: List[Dict]
    kline_15m: List[Dict]
    kline_1d: List[Dict]
    last_update: float
    
class OptimizedWebSocketScanner:
    """100% WebSocket 기반 최적화 스캐너"""
    
    def __init__(self, strategy_instance):
        self.strategy = strategy_instance
        self.ws_manager = strategy_instance.ws_kline_manager
        
        # 실시간 데이터 저장소
        self.symbol_data: Dict[str, SymbolData] = {}
        
        # 스캔 설정
        self.scan_interval = 2.0  # 2초마다 스캔
        self.min_data_requirement = 200  # 최소 필요 데이터 수
        self.max_scan_symbols = 50  # 동시 스캔 최대 심볼 수
        
        # 성능 모니터링
        self.scan_stats = {
            'total_scans': 0,
            'successful_scans': 0,
            'avg_scan_time': 0,
            'signals_found': 0
        }
        
        # 동기화 락
        self.data_lock = threading.Lock()
        
        print("🚀 최적화된 WebSocket 스캐너 Initialization Complete")
    
    def start_optimized_scan(self):
        """최적화된 스캔 시작"""
        print("⚡ 100% WebSocket 기반 스캔 Starting")
        
        while True:
            try:
                scan_start = time.time()
                
                # 1단계: WebSocket 데이터 동기화
                self._sync_websocket_data()
                
                # 2단계: 충분한 데이터가 있는 심볼만 스캔
                ready_symbols = self._get_scan_ready_symbols()
                
                if ready_symbols:
                    # 3단계: 병렬 전략 분석 (API 호출 없음)
                    signals = self._parallel_strategy_analysis(ready_symbols)
                    
                    # 4단계: 신호 처리
                    if signals:
                        self._process_signals(signals)
                        self.scan_stats['signals_found'] += len(signals)
                
                # 성능 통계 업데이트
                scan_time = time.time() - scan_start
                self._update_scan_stats(scan_time, len(ready_symbols) > 0)
                
                # 다음 스캔까지 대기
                time.sleep(max(0, self.scan_interval - scan_time))
                
            except Exception as e:
                print(f"❌ 스캔 Error: {e}")
                time.sleep(1)
    
    def _sync_websocket_data(self):
        """WebSocket 데이터 동기화"""
        if not self.ws_manager:
            return
        
        try:
            with self.data_lock:
                # WebSocket 버퍼에서 최신 데이터 가져오기
                buffer = getattr(self.strategy, '_websocket_kline_buffer', {})
                
                for buffer_key, kline_data in buffer.items():
                    if '_' not in buffer_key:
                        continue
                        
                    symbol, timeframe = buffer_key.rsplit('_', 1)
                    
                    # 충분한 데이터가 있는 경우만 처리
                    if len(kline_data) >= self.min_data_requirement:
                        if symbol not in self.symbol_data:
                            self.symbol_data[symbol] = SymbolData(
                                symbol=symbol,
                                current_price=0,
                                change_24h=0,
                                volume_24h=0,
                                kline_1m=[],
                                kline_3m=[],
                                kline_5m=[],
                                kline_15m=[],
                                kline_1d=[],
                                last_update=time.time()
                            )
                        
                        # 타임프레임별 데이터 업데이트
                        symbol_obj = self.symbol_data[symbol]
                        latest_candle = kline_data[-1]
                        
                        if timeframe == '1m':
                            symbol_obj.kline_1m = kline_data[-500:]  # 최근 500개
                            symbol_obj.current_price = latest_candle['close']
                            
                            # 24시간 변동률 계산 (1440분 = 24시간)
                            if len(kline_data) >= 1440:
                                old_price = kline_data[-1440]['open']
                                symbol_obj.change_24h = ((latest_candle['close'] - old_price) / old_price) * 100
                            
                        elif timeframe == '3m':
                            symbol_obj.kline_3m = kline_data[-500:]
                        elif timeframe == '5m':
                            symbol_obj.kline_5m = kline_data[-200:]
                        elif timeframe == '15m':
                            symbol_obj.kline_15m = kline_data[-500:]
                        elif timeframe == '1d':
                            symbol_obj.kline_1d = kline_data[-100:]
                        
                        symbol_obj.last_update = time.time()
                        
        except Exception as e:
            print(f"⚠️ WebSocket 데이터 동기화 Error: {e}")
    
    def _get_scan_ready_symbols(self) -> List[str]:
        """스캔 준비된 심볼 목록 반환"""
        ready_symbols = []
        current_time = time.time()
        
        with self.data_lock:
            for symbol, data in self.symbol_data.items():
                # 데이터 신선도 체크 (5분 이내)
                if current_time - data.last_update > 300:
                    continue
                
                # 필수 타임프레임 데이터 확인
                if (len(data.kline_1m) >= self.min_data_requirement and
                    len(data.kline_3m) >= 100 and
                    len(data.kline_5m) >= 50 and
                    len(data.kline_15m) >= 100):
                    
                    # 변동률 필터 (너무 낮은 변동률 제외)
                    if abs(data.change_24h) >= 1.0:
                        ready_symbols.append(symbol)
        
        # 변동률 순으로 정렬하여 상위 심볼만 스캔
        ready_symbols.sort(key=lambda s: abs(self.symbol_data[s].change_24h), reverse=True)
        
        return ready_symbols[:self.max_scan_symbols]
    
    def _parallel_strategy_analysis(self, symbols: List[str]) -> List[Dict]:
        """병렬 전략 분석 (API 호출 없음)"""
        signals = []
        
        # CPU 코어 수에 맞춰 병렬 처리
        with ThreadPoolExecutor(max_workers=min(8, len(symbols))) as executor:
            futures = []
            
            for symbol in symbols:
                future = executor.submit(self._analyze_symbol_pure_websocket, symbol)
                futures.append((symbol, future))
            
            # 결과 수집
            for symbol, future in futures:
                try:
                    result = future.result(timeout=1.0)  # 1초 타임아웃
                    if result and result.get('signal'):
                        signals.append(result)
                except Exception as e:
                    # 개별 심볼 분석 실패는 무시하고 계속
                    pass
        
        return signals
    
    def _analyze_symbol_pure_websocket(self, symbol: str) -> Optional[Dict]:
        """순수 WebSocket 데이터로 심볼 분석"""
        try:
            with self.data_lock:
                if symbol not in self.symbol_data:
                    return None
                
                data = self.symbol_data[symbol]
                
                # DataFrame 생성 (캐시 없이 즉석 계산)
                df_1m = self._kline_to_dataframe(data.kline_1m)
                df_3m = self._kline_to_dataframe(data.kline_3m)
                df_5m = self._kline_to_dataframe(data.kline_5m)
                df_15m = self._kline_to_dataframe(data.kline_15m)
                df_1d = self._kline_to_dataframe(data.kline_1d)
                
                if df_1m is None or len(df_1m) < 200:
                    return None
                
                # 지표 계산 (최소한만)
                df_1m = self._calculate_minimal_indicators(df_1m)
                df_3m = self._calculate_minimal_indicators(df_3m) if df_3m is not None else None
                df_5m = self._calculate_minimal_indicators(df_5m) if df_5m is not None else None
                df_15m = self._calculate_minimal_indicators(df_15m) if df_15m is not None else None
                
                # 전략 조건 체크 (기존 로직 재사용)
                result = self.strategy.check_surge_entry_conditions(
                    symbol, df_1m, df_3m, df_1d, df_15m, df_5m, data.change_24h
                )
                
                if isinstance(result, tuple) and len(result) == 2:
                    is_signal, conditions = result
                    
                    if is_signal is True:  # 정확한 True 체크
                        return {
                            'symbol': symbol,
                            'signal': True,
                            'current_price': data.current_price,
                            'change_24h': data.change_24h,
                            'conditions': conditions,
                            'timestamp': time.time(),
                            'data_source': 'websocket_only'
                        }
                
                return None
                
        except Exception as e:
            return None
    
    def _kline_to_dataframe(self, kline_data: List[Dict]) -> Optional[pd.DataFrame]:
        """Kline 데이터를 DataFrame으로 변환"""
        if not kline_data or len(kline_data) < 10:
            return None
        
        try:
            # 표준 OHLCV 형식으로 변환
            df_data = []
            for candle in kline_data:
                df_data.append([
                    candle['timestamp'],
                    candle['open'],
                    candle['high'], 
                    candle['low'],
                    candle['close'],
                    candle['volume']
                ])
            
            df = pd.DataFrame(df_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            return df
            
        except Exception as e:
            return None
    
    def _calculate_minimal_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """최소한의 지표만 계산 (속도 우선)"""
        try:
            # 기본 이동평균 (빠른 계산)
            df['ma5'] = df['close'].rolling(window=5, min_periods=1).mean()
            df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()
            df['ma80'] = df['close'].rolling(window=80, min_periods=1).mean()
            
            if len(df) >= 480:
                df['ma480'] = df['close'].rolling(window=480, min_periods=1).mean()
            
            # 볼린저 밴드 (최소한만)
            if len(df) >= 200:
                bb200_period = 200
                bb200_std = df['close'].rolling(window=bb200_period).std()
                bb200_ma = df['close'].rolling(window=bb200_period).mean()
                df['bb200_upper'] = bb200_ma + (bb200_std * 1.5)
                df['bb200_lower'] = bb200_ma - (bb200_std * 1.5)
            
            # SuperTrend (5분봉용)
            if 'high' in df.columns and 'low' in df.columns:
                try:
                    period = 10
                    multiplier = 3
                    
                    hl2 = (df['high'] + df['low']) / 2
                    atr = self._calculate_atr(df, period)
                    
                    upper_band = hl2 + (multiplier * atr)
                    lower_band = hl2 - (multiplier * atr)
                    
                    # 간단한 SuperTrend 계산
                    supertrend = pd.Series(index=df.index, dtype=float)
                    direction = pd.Series(index=df.index, dtype=int)
                    
                    for i in range(len(df)):
                        if i == 0:
                            supertrend.iloc[i] = upper_band.iloc[i]
                            direction.iloc[i] = -1
                        else:
                            if df['close'].iloc[i] > supertrend.iloc[i-1]:
                                direction.iloc[i] = 1
                                supertrend.iloc[i] = lower_band.iloc[i]
                            else:
                                direction.iloc[i] = -1
                                supertrend.iloc[i] = upper_band.iloc[i]
                    
                    df['supertrend'] = supertrend
                    df['supertrend_direction'] = direction
                    
                except:
                    pass
            
            return df
            
        except Exception as e:
            return df
    
    def _calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """ATR 계산"""
        try:
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            
            return true_range.rolling(window=period, min_periods=1).mean()
            
        except Exception as e:
            return pd.Series(index=df.index, dtype=float)
    
    def _process_signals(self, signals: List[Dict]):
        """신호 처리"""
        for signal in signals:
            try:
                symbol = signal['symbol']
                print(f"🎯 WebSocket 신호 발견: {symbol.replace('/USDT:USDT', '')} "
                     f"(변동률: {signal['change_24h']:+.1f}%)")
                
                # 기존 전략의 진입 로직 호출
                self.strategy._execute_entry_signal(signal)
                
            except Exception as e:
                print(f"❌ 신호 Processing Failed: {e}")
    
    def _update_scan_stats(self, scan_time: float, success: bool):
        """스캔 통계 업데이트"""
        self.scan_stats['total_scans'] += 1
        if success:
            self.scan_stats['successful_scans'] += 1
        
        # 이동평균으로 평균 스캔 시간 계산
        alpha = 0.1
        self.scan_stats['avg_scan_time'] = (
            alpha * scan_time + 
            (1 - alpha) * self.scan_stats['avg_scan_time']
        )
        
        # 10번마다 통계 출력
        if self.scan_stats['total_scans'] % 10 == 0:
            success_rate = (self.scan_stats['successful_scans'] / 
                          self.scan_stats['total_scans'] * 100)
            
            print(f"📊 스캔 통계: Success률 {success_rate:.1f}%, "
                 f"평균 {self.scan_stats['avg_scan_time']:.2f}초, "
                 f"신호 {self.scan_stats['signals_found']}개")
    
    def get_data_status(self) -> Dict:
        """현재 데이터 상태 반환"""
        with self.data_lock:
            total_symbols = len(self.symbol_data)
            ready_symbols = len(self._get_scan_ready_symbols())
            
            return {
                'total_symbols': total_symbols,
                'ready_symbols': ready_symbols,
                'data_coverage': ready_symbols / max(1, total_symbols) * 100,
                'scan_stats': self.scan_stats.copy()
            }