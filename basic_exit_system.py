# -*- coding: utf-8 -*-
"""
🎯 기본 Exit 시스템 (Basic Exit System)
SuperClaude Expert Mode Implementation

핵심 Exit방식:
1. 15분/30minute candles BB600 상단선 돌파시 50% Exit (1times 한정)
2. 5minute candles SuperTrend(10-3) 하락전환시 전량Exit
3. 5%+ 상승 후 본절 근처 하락시 Approx수익Exit

통합 Exit 시스템:
- 우선순위: 본절보호 > BB돌파 > SuperTrend
- 텔레그램 Notification: 모든 Exit에 대한 실Time Notification
- 중복 방지: 각 Exit Type별 1times 제한
"""

import pandas as pd
import numpy as np
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import ccxt
import logging

class BasicExitType(Enum):
    """기본 Exit Type"""
    BB_BREAKTHROUGH = "bb_breakthrough"           # BB600 돌파 50% Exit
    SUPERTREND_DOWN = "supertrend_down"          # SuperTrend 하락 전량Exit  
    BREAKEVEN_PROTECTION = "breakeven_protection" # 본절 보호 Exit

@dataclass
class PositionState:
    """Position Status 추적"""
    symbol: str
    max_profit_pct: float = 0.0                  # 최대 Profit ratio 기록
    breakeven_protection_triggered: bool = False # 본절 보호 Active화 여부
    bb_partial_exit_done: bool = False           # BB 50% Exit Complete 여부
    supertrend_exit_done: bool = False           # SuperTrend Exit Complete 여부
    protection_notified: bool = False            # 본절보호 Active화 Notification Complete
    bb_exit_notified: bool = False              # BB Exit Notification Complete
    supertrend_exit_notified: bool = False      # SuperTrend Exit Notification Complete
    last_update: str = ""                       # 마지막 Update Time

class BasicExitSystem:
    """기본 Exit 시스템"""
    
    def __init__(self, exchange=None, telegram_bot=None, logger=None):
        self.exchange = exchange
        self.telegram_bot = telegram_bot
        self.logger = logger or self._setup_logger()
        
        # Settings
        self.config = {
            # BB 돌파 Exit Settings
            'bb_breakthrough': {
                'bb_period': 600,                    # BB600 기간
                'bb_std': 2.0,                      # 표준편차
                'exit_ratio': 0.5,                  # 50% Exit
                'timeframes': ['15m', '30m']        # 15분/30minute candles
            },
            
            # SuperTrend Exit Settings
            'supertrend': {
                'period': 10,                       # SuperTrend 기간
                'multiplier': 3.0,                  # SuperTrend 배수
                'timeframe': '5m',                  # 5minute candles
                'exit_ratio': 1.0                   # 전량 Exit
            },
            
            # 본절 보호 Exit Settings
            'breakeven_protection': {
                'trigger_threshold': 0.05,          # 5% 수익시 보호 Active화
                'exit_threshold': 0.01,             # 1% 수익으로 하락시 Exit
                'min_protection_profit': 0.005,    # 최소 0.5% 수익 확보
                'exit_ratio': 1.0                   # 전량 Exit
            }
        }
        
        # Status 관리
        self.position_states = {}               # {symbol: PositionState}
        self.lock = threading.Lock()
        
        self.logger.info("기본 Exit System Initialization complete")
    
    def _setup_logger(self):
        """로거 Settings"""
        logger = logging.getLogger('BasicExitSystem')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def get_position_state(self, symbol: str) -> PositionState:
        """Position Status 가져오기 (없으면 Create)"""
        with self.lock:
            if symbol not in self.position_states:
                self.position_states[symbol] = PositionState(symbol=symbol)
            return self.position_states[symbol]
    
    def calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 600, std: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """볼린저 밴드 계산"""
        try:
            if len(df) < period:
                # 데이터가 부족한 경우 Current price 기준으로 임시 계산
                current_price = df['close'].iloc[-1]
                bb_middle = pd.Series([current_price] * len(df), index=df.index)
                bb_upper = bb_middle * 1.02  # 2% 위
                bb_lower = bb_middle * 0.98  # 2% 아래
                return bb_upper, bb_middle, bb_lower
            
            # 정상 BB 계산
            bb_middle = df['close'].rolling(window=period).mean()
            bb_std = df['close'].rolling(window=period).std()
            bb_upper = bb_middle + (bb_std * std)
            bb_lower = bb_middle - (bb_std * std)
            
            return bb_upper, bb_middle, bb_lower
            
        except Exception as e:
            self.logger.error(f"볼린저 밴드 계산 Failed: {e}")
            # 에러시 Current price 기준 반환
            current_price = df['close'].iloc[-1]
            bb_middle = pd.Series([current_price] * len(df), index=df.index)
            bb_upper = bb_middle * 1.02
            bb_lower = bb_middle * 0.98
            return bb_upper, bb_middle, bb_lower
    
    def calculate_supertrend(self, df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
        """SuperTrend 계산"""
        try:
            if len(df) < period + 1:
                # 데이터가 부족한 경우 Current price 기준으로 임시 계산
                current_price = df['close'].iloc[-1]
                supertrend = pd.Series([current_price * 0.98] * len(df), index=df.index)  # Current price보다 2% 낮게
                trend = pd.Series([1] * len(df), index=df.index)  # 상승 트렌드로 가정
                return supertrend, trend
            
            # ATR 계산
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())
            true_range = np.maximum(high_low, np.maximum(high_close, low_close))
            atr = true_range.rolling(window=period).mean()
            
            # 기본 상한선과 하한선
            hl2 = (df['high'] + df['low']) / 2
            upper_band = hl2 + (multiplier * atr)
            lower_band = hl2 - (multiplier * atr)
            
            # SuperTrend 계산
            supertrend = pd.Series(index=df.index, dtype=float)
            trend = pd.Series(index=df.index, dtype=int)
            
            # 초기값 Settings
            supertrend.iloc[0] = lower_band.iloc[0]
            trend.iloc[0] = 1
            
            for i in range(1, len(df)):
                # Current 상한선/하한선 조정
                if lower_band.iloc[i] > lower_band.iloc[i-1] or df['close'].iloc[i-1] < lower_band.iloc[i-1]:
                    lower_band.iloc[i] = lower_band.iloc[i]
                else:
                    lower_band.iloc[i] = lower_band.iloc[i-1]
                
                if upper_band.iloc[i] < upper_band.iloc[i-1] or df['close'].iloc[i-1] > upper_band.iloc[i-1]:
                    upper_band.iloc[i] = upper_band.iloc[i]
                else:
                    upper_band.iloc[i] = upper_band.iloc[i-1]
                
                # 트렌드 결정
                if trend.iloc[i-1] == 1:  # 상승 트렌드
                    if df['close'].iloc[i] <= lower_band.iloc[i]:
                        trend.iloc[i] = -1
                        supertrend.iloc[i] = upper_band.iloc[i]
                    else:
                        trend.iloc[i] = 1
                        supertrend.iloc[i] = lower_band.iloc[i]
                else:  # 하락 트렌드
                    if df['close'].iloc[i] >= upper_band.iloc[i]:
                        trend.iloc[i] = 1
                        supertrend.iloc[i] = lower_band.iloc[i]
                    else:
                        trend.iloc[i] = -1
                        supertrend.iloc[i] = upper_band.iloc[i]
            
            return supertrend, trend
            
        except Exception as e:
            self.logger.error(f"SuperTrend 계산 Failed: {e}")
            # 에러시 Current price 기준 반환
            current_price = df['close'].iloc[-1]
            supertrend = pd.Series([current_price * 0.98] * len(df), index=df.index)
            trend = pd.Series([1] * len(df), index=df.index)
            return supertrend, trend
    
    def check_bb_breakthrough_exit(self, symbol: str, current_price: float, average_price: float) -> Optional[Dict[str, Any]]:
        """BB600 상단선 돌파 50% Exit Confirm"""
        try:
            position_state = self.get_position_state(symbol)
            
            # 이미 BB Exit Complete된 경우 Skip
            if position_state.bb_partial_exit_done:
                return None
            
            bb_config = self.config['bb_breakthrough']
            
            # 15분/30minute candles 데이터 조times 및 BB 계산
            for timeframe in bb_config['timeframes']:
                try:
                    # 데이터 조times
                    ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=bb_config['bb_period'] + 50)
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    
                    if len(df) < 10:  # 최소 데이터 Confirm
                        continue
                    
                    # BB600 계산
                    bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(
                        df, bb_config['bb_period'], bb_config['bb_std']
                    )
                    
                    # Current price가 BB600 상단선 돌파했는지 Confirm
                    current_bb_upper = bb_upper.iloc[-1]
                    
                    if pd.notna(current_bb_upper) and current_price > current_bb_upper:
                        self.logger.info(f"🚀 BB600 돌파 Detected: {symbol} ({timeframe})")
                        self.logger.info(f"   Current price: ${current_price:.6f}")
                        self.logger.info(f"   BB600 상단: ${current_bb_upper:.6f}")
                        
                        return {
                            'exit_type': BasicExitType.BB_BREAKTHROUGH.value,
                            'exit_ratio': bb_config['exit_ratio'],
                            'timeframe': timeframe,
                            'current_price': current_price,
                            'bb_upper': current_bb_upper,
                            'trigger_info': f"{timeframe}봉 BB600 상단선 돌파"
                        }
                        
                except Exception as e:
                    self.logger.debug(f"BB Confirmation failed {symbol} {timeframe}: {e}")
                    continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"BB 돌파 Confirmation failed {symbol}: {e}")
            return None
    
    def check_supertrend_exit(self, symbol: str, current_price: float, average_price: float) -> Optional[Dict[str, Any]]:
        """SuperTrend 하락전환 전량Exit Confirm - 실Time 감지"""
        try:
            position_state = self.get_position_state(symbol)
            
            # 이미 SuperTrend Exit Complete된 경우 Skip
            if position_state.supertrend_exit_done:
                return None
            
            st_config = self.config['supertrend']
            
            # 5minute candles 데이터 조times (완성된 캔들)
            ohlcv = self.exchange.fetch_ohlcv(symbol, st_config['timeframe'], limit=st_config['period'] + 50)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            if len(df) < st_config['period'] + 5:
                return None
            
            # 🚀 실Time 감지: Current Progress중인 캔들을 Current price로 Update
            df_realtime = df.copy()
            current_time = int(time.time() * 1000)
            last_candle_time = df_realtime.iloc[-1]['timestamp']
            
            # Current 캔들이 Progress 중인지 Confirm (5분 = 300초)
            time_diff = (current_time - last_candle_time) / 1000
            if time_diff < 300:  # Current 캔들 Progress 중
                # 마지막 캔들을 Current price로 Update (실Time 감지)
                df_realtime.iloc[-1, df_realtime.columns.get_loc('close')] = current_price
                df_realtime.iloc[-1, df_realtime.columns.get_loc('high')] = max(df_realtime.iloc[-1]['high'], current_price)
                df_realtime.iloc[-1, df_realtime.columns.get_loc('low')] = min(df_realtime.iloc[-1]['low'], current_price)
                
                self.logger.debug(f"🔄 실Time SuperTrend: {symbol} - Current price {current_price:.6f}로 Progress중 캔들 Update")
            
            # SuperTrend 계산 (실Time Update된 데이터 Usage)
            supertrend, trend = self.calculate_supertrend(
                df_realtime, st_config['period'], st_config['multiplier']
            )
            
            # Current 및 이전 트렌드 Confirm
            current_trend = trend.iloc[-1]
            prev_trend = trend.iloc[-2] if len(trend) > 1 else current_trend
            current_supertrend = supertrend.iloc[-1]
            
            # 하락 전환 Confirm (상승 → 하락) - 실Time 감지
            if prev_trend == 1 and current_trend == -1:
                self.logger.warning(f"🚀 실Time SuperTrend 하락전환 Detected: {symbol}")
                self.logger.warning(f"   Current price: ${current_price:.6f}")
                self.logger.warning(f"   SuperTrend: ${current_supertrend:.6f}")
                self.logger.warning(f"   트렌드: {prev_trend} → {current_trend}")
                self.logger.warning(f"   ⚡ 즉시 Exit (캔들 완성 Waiting Absent)")
                
                return {
                    'exit_type': BasicExitType.SUPERTREND_DOWN.value,
                    'exit_ratio': st_config['exit_ratio'],
                    'timeframe': st_config['timeframe'],
                    'current_price': current_price,
                    'supertrend_line': current_supertrend,
                    'trend_change': f"{prev_trend} → {current_trend}",
                    'trigger_info': f"5minute candles 실Time SuperTrend({st_config['period']}-{st_config['multiplier']}) 하락전환 (즉시Exit)"
                }
            
            # Current price가 SuperTrend 라인 아래 있는지도 Confirm - 실Time 감지
            elif current_trend == -1 and current_price < current_supertrend:
                self.logger.warning(f"🚀 실Time SuperTrend 하락신호: {symbol}")
                self.logger.warning(f"   Current price: ${current_price:.6f} < SuperTrend: ${current_supertrend:.6f}")
                self.logger.warning(f"   ⚡ 즉시 Exit (캔들 완성 Waiting Absent)")
                
                return {
                    'exit_type': BasicExitType.SUPERTREND_DOWN.value,
                    'exit_ratio': st_config['exit_ratio'],
                    'timeframe': st_config['timeframe'],
                    'current_price': current_price,
                    'supertrend_line': current_supertrend,
                    'trend_change': "하락 지속",
                    'trigger_info': f"5minute candles 실Time SuperTrend 하락신호 (Current price < SuperTrend 라인, 즉시Exit)"
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"SuperTrend Confirmation failed {symbol}: {e}")
            return None
    
    def check_breakeven_protection_exit(self, symbol: str, current_price: float, average_price: float) -> Optional[Dict[str, Any]]:
        """본절 보호 Exit Confirm"""
        try:
            position_state = self.get_position_state(symbol)
            protection_config = self.config['breakeven_protection']
            
            # Current Profit ratio 계산
            current_profit_pct = (current_price - average_price) / average_price
            
            # 최대 Profit ratio Update
            if current_profit_pct > position_state.max_profit_pct:
                position_state.max_profit_pct = current_profit_pct
                position_state.last_update = datetime.now(timezone.utc).isoformat()
            
            # 5% 이상 수익 Reached시 본절 보호 Active화
            if current_profit_pct >= protection_config['trigger_threshold']:
                if not position_state.breakeven_protection_triggered:
                    position_state.breakeven_protection_triggered = True
                    position_state.last_update = datetime.now(timezone.utc).isoformat()
                    
                    # 텔레그램 Notification (1times만)
                    if not position_state.protection_notified and self.telegram_bot:
                        clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                        message = (f"🛡️ [본절보호 Active화] {clean_symbol}\n"
                                 f"최대수익: {position_state.max_profit_pct*100:.1f}%\n"
                                 f"Current price: ${current_price:.6f}")
                        self.telegram_bot.send_message(message)
                        position_state.protection_notified = True
                        self.logger.info(f"🛡️ 본절보호 Active화: {symbol} (최대수익: {position_state.max_profit_pct*100:.1f}%)")
            
            # 본절 보호가 Active화된 Status에서 본절 근처로 하락시 Exit
            if position_state.breakeven_protection_triggered:
                if current_profit_pct <= protection_config['exit_threshold']:
                    self.logger.critical(f"💙 본절보호 Exit 트리거: {symbol}")
                    self.logger.critical(f"   최대수익: {position_state.max_profit_pct*100:.1f}%")
                    self.logger.critical(f"   Current수익: {current_profit_pct*100:.1f}%")
                    self.logger.critical(f"   확보수익: {protection_config['exit_threshold']*100:.1f}%")
                    
                    return {
                        'exit_type': BasicExitType.BREAKEVEN_PROTECTION.value,
                        'exit_ratio': protection_config['exit_ratio'],
                        'current_price': current_price,
                        'current_profit_pct': current_profit_pct * 100,
                        'max_profit_pct': position_state.max_profit_pct * 100,
                        'secured_profit_pct': protection_config['exit_threshold'] * 100,
                        'trigger_info': f"5%+ 상승 후 본절 보호 Exit (최대{position_state.max_profit_pct*100:.1f}% → {current_profit_pct*100:.1f}%)"
                    }
            
            return None
            
        except Exception as e:
            self.logger.error(f"본절 보호 Confirmation failed {symbol}: {e}")
            return None
    
    def check_all_basic_exits(self, symbol: str, current_price: float, average_price: float) -> Optional[Dict[str, Any]]:
        """모든 기본 Exit 조건 Confirm (우선순위 적용)"""
        try:
            # 1순위: 본절 보호 Exit (최우선)
            breakeven_exit = self.check_breakeven_protection_exit(symbol, current_price, average_price)
            if breakeven_exit:
                return breakeven_exit
            
            # 2순위: BB 돌파 50% Exit
            bb_exit = self.check_bb_breakthrough_exit(symbol, current_price, average_price)
            if bb_exit:
                return bb_exit
            
            # 3순위: SuperTrend 전량 Exit
            supertrend_exit = self.check_supertrend_exit(symbol, current_price, average_price)
            if supertrend_exit:
                return supertrend_exit
            
            return None
            
        except Exception as e:
            self.logger.error(f"기본 Exit Confirmation failed {symbol}: {e}")
            return None
    
    def mark_exit_completed(self, symbol: str, exit_type: str):
        """Exit Complete 마킹"""
        try:
            position_state = self.get_position_state(symbol)
            
            if exit_type == BasicExitType.BB_BREAKTHROUGH.value:
                position_state.bb_partial_exit_done = True
                position_state.bb_exit_notified = True
            elif exit_type == BasicExitType.SUPERTREND_DOWN.value:
                position_state.supertrend_exit_done = True
                position_state.supertrend_exit_notified = True
            elif exit_type == BasicExitType.BREAKEVEN_PROTECTION.value:
                # 본절 보호는 전량 Exit이므로 모든 Status Complete Process
                position_state.bb_partial_exit_done = True
                position_state.supertrend_exit_done = True
            
            position_state.last_update = datetime.now(timezone.utc).isoformat()
            
        except Exception as e:
            self.logger.error(f"Exit Complete 마킹 Failed {symbol}: {e}")
    
    def send_exit_notification(self, symbol: str, exit_signal: Dict[str, Any], profit_pct: float):
        """Exit Notification 전송"""
        try:
            if not self.telegram_bot:
                return
            
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            exit_type = exit_signal['exit_type']
            
            # Exit Type별 Message Create
            if exit_type == BasicExitType.BB_BREAKTHROUGH.value:
                emoji = "💰"
                title = "BB돌파 50% Exit"
                details = f"돌파유형: {exit_signal['timeframe']}봉 BB600 상단선\nExit량: 50%\n잔여Position: 50%"
                
            elif exit_type == BasicExitType.SUPERTREND_DOWN.value:
                emoji = "🔴"
                title = "SuperTrend 하락Exit"
                details = f"{exit_signal['timeframe']}봉 SuperTrend 하락전환\nExit량: 100% (전량)"
                
            elif exit_type == BasicExitType.BREAKEVEN_PROTECTION.value:
                emoji = "💙"
                title = "본절보호 Exit"
                details = f"최대수익: {exit_signal['max_profit_pct']:.1f}%\n확보수익: {exit_signal['secured_profit_pct']:.1f}%"
            
            else:
                emoji = "📤"
                title = "Exit Complete"
                details = "기본 Exit"
            
            message = (f"{emoji} [{title}] {clean_symbol}\n"
                      f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                      f"💵 Exit가: ${exit_signal['current_price']:.6f}\n"
                      f"📊 Profit ratio: {profit_pct:+.1f}%\n"
                      f"{details}\n"
                      f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                      f"⚡️ {exit_signal['trigger_info']}\n"
                      f"🕐 ExitTime: {datetime.now().strftime('%H:%M:%S')}")
            
            self.telegram_bot.send_message(message)
            self.logger.info(f"{emoji} Exit Notification 전송: {clean_symbol} - {title}")
            
        except Exception as e:
            self.logger.error(f"Exit Notification 전송 Failed {symbol}: {e}")
    
    def reset_position_state(self, symbol: str):
        """Position Status Initialize (Position 완전 Terminate시)"""
        try:
            with self.lock:
                if symbol in self.position_states:
                    del self.position_states[symbol]
                    self.logger.info(f"Position Status Initialize: {symbol}")
                    
        except Exception as e:
            self.logger.error(f"Position Status Initialization failed {symbol}: {e}")