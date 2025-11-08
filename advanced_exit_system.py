# -*- coding: utf-8 -*-
"""🎯 고급 exit 시스템 (Advanced Exit System) SuperClaude Expert Mode Implementation 핵심 기능: 1. 적응형 stop loss 시스템 (ATR 기반 변동성별 stop loss 조정) 2. 다단계 take profit 시스템 (5%, 10%, 20%, 30% 단계별 min할 exit) 3. smart 트레일링 스톱 (수익률별 차등 트레일링) 4. 복합 기술적 exit (다중 지표 융합, 2개 이상 condition 충족시 exit)"""

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

class ExitSignalType(Enum):
    """exit 신호 타입"""
    ADAPTIVE_STOP_LOSS = "adaptive_stop_loss"# 적응형 stop loss MULTI_LEVEL_PROFIT ="multi_level_profit"# 다단계 take profit TRAILING_STOP ="trailing_stop"# 트레일링 스톱 TECHNICAL_EXIT ="technical_exit"# 복합 기술적 exit EMERGENCY_EXIT ="emergency_exit"# 긴급 exit class VolatilityLevel(Enum):"""변동성 수준"""
    LOW = "low"# 저변동성 (ATR < 2%) MEDIUM ="medium"# 중변동성 (ATR 2-5%) HIGH ="high"# 고변동성 (ATR > 5%) EXTREME ="extreme"# 극고변동성 (ATR > 10%) @dataclass class ExitLevel:"""exit 레벨 정의"""profit_threshold: float # 수익률 임계값 exit_ratio: float # exit 비율 name: str # 레벨 이름 is_executed: bool = False # 실행 여부 @dataclass class TrailingStopState:"""트레일링 스톱 상태"""symbol: str highest_price: float # 최고가 trailing_price: float # 트레일링 가격 trailing_pct: float # 트레일링 비율 is_active: bool = False # 활성 상태 activation_price: float = 0.0 # enabled 가격 last_update: str =""# 마지막 업데이트 @dataclass class TechnicalSignal:"""기술적 신호"""signal_type: str # 신호 타입 strength: float # 신호 강도 (0-1) timestamp: str # 신호 hour description: str # 신호 설명 class AdvancedExitSystem:"""고급 exit 시스템"""
    
    def __init__(self, exchange=None, logger=None):
        self.exchange = exchange
        self.logger = logger or self._setup_logger()
        
        # 설정
        self.config = {
            # 적응형 손절 설정
            'adaptive_stop_loss': {
                'low_volatility': {'initial': -0.12, 'first_dca': -0.09, 'second_dca': -0.06}, # 저변동성'medium_volatility': {'initial': -0.10, 'first_dca': -0.07, 'second_dca': -0.05}, # 중변동성 (기본)'high_volatility': {'initial': -0.08, 'first_dca': -0.06, 'second_dca': -0.04}, # 고변동성'extreme_volatility': {'initial': -0.06, 'first_dca': -0.04, 'second_dca': -0.03} # 극고변동성 }, # 다단계 take profit 설정'multi_level_exits': [
                ExitLevel(profit_threshold=0.05, exit_ratio=0.20, name="Level1_5%"), # 5% → 20% exit ExitLevel(profit_threshold=0.10, exit_ratio=0.30, name="Level2_10%"), # 10% → 30% exit (50% 유지) ExitLevel(profit_threshold=0.20, exit_ratio=0.40, name="Level3_20%"), # 20% → 40% exit (10% 유지) ExitLevel(profit_threshold=0.30, exit_ratio=1.00, name="Level4_30%")   # 30% → 나머지 전량
            ],
            
            # 트레일링 스톱 설정
            'trailing_stop': {
                'activation_threshold': 0.05, # 5% 수익시 enabled'trailing_levels': {
                    '5_to_10': 0.03, # 5-10% 구간: 3% 트레일링'10_to_20': 0.03, # 10-20% 구간: 3% 트레일링'20_plus': 0.05 # 20%+ 구간: 5% 트레일링 } }, # 기술적 exit 설정'technical_exit': {
                'signal_threshold': 2, # 최소 신호 개수'min_signal_strength': 0.6, # 최소 신호 강도'exit_ratio': 1.0 # exit 비율 (전량) }, # ATR 설정'atr_period': 14, # ATR 계산 기간'volatility_thresholds': {
                'low': 0.02, # 2% 미만'medium': 0.05,   # 2-5%
                'high': 0.10      # 5-10%
            }
        }
        
        # 상태 관리
        self.trailing_stops = {}        # {symbol: TrailingStopState}
        self.exit_levels = {}          # {symbol: List[ExitLevel]}
        self.last_volatility = {}      # {symbol: VolatilityLevel}
        self.technical_signals = {}    # {symbol: List[TechnicalSignal]}
        
        # 스레드 안전성
        self.lock = threading.Lock()
        
        self.logger.info("고급 Close system initialize completed")
    
    def _setup_logger(self):
        """로거 설정"""
        logger = logging.getLogger('AdvancedExitSystem')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def calculate_atr_volatility(self, symbol: str, timeframe: str = '1h', periods: int = 14) -> Tuple[float, VolatilityLevel]:
        """ATR 기반 변동성 계산"""
        try:
            if not self.exchange:
                return 0.05, VolatilityLevel.MEDIUM  # 기본값
            
            # OHLCV 데이터 조회
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=periods + 5)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']) # ATR 계산 df['tr1'] = df['high'] - df['low']
            df['tr2'] = abs(df['high'] - df['close'].shift(1))
            df['tr3'] = abs(df['low'] - df['close'].shift(1))
            df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1) # ATR 비율 계산 (가격 대비) atr = df['tr'].rolling(window=periods).mean().iloc[-1]
            current_price = df['close'].iloc[-1] atr_pct = atr / current_price # 변동성 수준 min류 thresholds = self.config['volatility_thresholds']
            if atr_pct < thresholds['low']:
                volatility_level = VolatilityLevel.LOW
            elif atr_pct < thresholds['medium']:
                volatility_level = VolatilityLevel.MEDIUM
            elif atr_pct < thresholds['high']:
                volatility_level = VolatilityLevel.HIGH
            else:
                volatility_level = VolatilityLevel.EXTREME
            
            self.logger.debug(f"{symbol} ATR: {atr_pct:.4f} ({volatility_level.value})")
            return atr_pct, volatility_level
            
        except Exception as e:
            self.logger.error(f"ATR 변동성 계산 failed {symbol}: {e}")
            return 0.05, VolatilityLevel.MEDIUM
    
    def get_adaptive_stop_loss(self, symbol: str, current_stage: str) -> float:
        """적응형 stop loss가 계산"""try: # 변동성 계산 atr_pct, volatility_level = self.calculate_atr_volatility(symbol) # 변동성별 stop loss 비율 조회 volatility_key = f"{volatility_level.value}_volatility"
            stop_loss_config = self.config['adaptive_stop_loss'].get(
                volatility_key, 
                self.config['adaptive_stop_loss']['medium_volatility']
            )
            
            # 단계별 손절 비율
            stop_loss_pct = stop_loss_config.get(current_stage, -0.10)
            
            # 변동성 정보 저장
            with self.lock:
                self.last_volatility[symbol] = volatility_level
            
            self.logger.info(f"🎯 {symbol} 적응형 Stop loss: {stop_loss_pct*100:.1f}% ({volatility_level.value}, {current_stage})")
            return stop_loss_pct
            
        except Exception as e:
            self.logger.error(f"적응형 Stop loss 계산 failed {symbol}: {e}")
            return -0.10  # 기본값
    
    def initialize_exit_levels(self, symbol: str):
        """exit 레벨 initialize"""
        with self.lock:
            # 다단계 익절 레벨 복사
            self.exit_levels[symbol] = [
                ExitLevel(
                    profit_threshold=level.profit_threshold,
                    exit_ratio=level.exit_ratio,
                    name=level.name,
                    is_executed=False
                ) for level in self.config['multi_level_exits']
            ]
        
        self.logger.info(f"🎯 {symbol} 다단계 Take profit 레벨 initialize: {len(self.exit_levels[symbol])}")
    
    def check_multi_level_exits(self, symbol: str, current_price: float, average_price: float) -> Optional[Dict[str, Any]]:
        """다단계 take profit 확인"""try: if symbol not in self.exit_levels: self.initialize_exit_levels(symbol) profit_pct = (current_price - average_price) / average_price with self.lock: levels = self.exit_levels[symbol] # 실행 가능한 레벨 찾기 for level in levels: if not level.is_executed and profit_pct >= level.profit_threshold: # 레벨 실행 마킹 level.is_executed = True self.logger.info(f"💰 {symbol} {level.name} Take profit 트리거: {profit_pct*100:.2f}% → {level.exit_ratio*100:.0f}% Close")
                        
                        return {
                            'signal_type': ExitSignalType.MULTI_LEVEL_PROFIT.value,
                            'exit_ratio': level.exit_ratio,
                            'level_name': level.name,
                            'profit_pct': profit_pct * 100,
                            'current_price': current_price,
                            'trigger_price': average_price * (1 + level.profit_threshold)
                        }
            
            return None
            
        except Exception as e:
            self.logger.error(f"다단계 Take profit verify failed {symbol}: {e}")
            return None
    
    def update_trailing_stop(self, symbol: str, current_price: float, average_price: float) -> Optional[Dict[str, Any]]:
        """트레일링 스톱 업데이트 및 확인"""
        try:
            profit_pct = (current_price - average_price) / average_price
            activation_threshold = self.config['trailing_stop']['activation_threshold']
            
            with self.lock:
                # 트레일링 스톱 상태 초기화
                if symbol not in self.trailing_stops:
                    self.trailing_stops[symbol] = TrailingStopState(
                        symbol=symbol,
                        highest_price=current_price,
                        trailing_price=current_price,
                        trailing_pct=0.03,  # 기본 3%
                        is_active=False
                    )
                
                trailing_state = self.trailing_stops[symbol]
                
                # 활성화 확인
                if not trailing_state.is_active and profit_pct >= activation_threshold:
                    trailing_state.is_active = True
                    trailing_state.activation_price = current_price
                    trailing_state.highest_price = current_price
                    self.logger.info(f"🔄 {symbol} 트레일링 스톱 enabled: {profit_pct*100:.2f}%")
                
                # 활성화된 경우 업데이트
                if trailing_state.is_active:
                    # 최고가 업데이트
                    if current_price > trailing_state.highest_price:
                        trailing_state.highest_price = current_price
                        
                        # 수익 구간별 트레일링 비율 설정
                        if profit_pct >= 0.20:
                            trailing_state.trailing_pct = self.config['trailing_stop']['trailing_levels']['20_plus']
                        elif profit_pct >= 0.10:
                            trailing_state.trailing_pct = self.config['trailing_stop']['trailing_levels']['10_to_20']
                        else:
                            trailing_state.trailing_pct = self.config['trailing_stop']['trailing_levels']['5_to_10']
                    
                    # 트레일링 가격 계산
                    trailing_state.trailing_price = trailing_state.highest_price * (1 - trailing_state.trailing_pct)
                    trailing_state.last_update = datetime.now().isoformat()
                    
                    # 트레일링 스톱 트리거 확인
                    if current_price <= trailing_state.trailing_price:
                        self.logger.info(f"🛑 {symbol} 트레일링 스톱 트리거!")
                        self.logger.info(f"Current price: ${current_price:.6f}")
                        self.logger.info(f"트레일링가: ${trailing_state.trailing_price:.6f}")
                        self.logger.info(f"최고가: ${trailing_state.highest_price:.6f}")
                        
                        # 트레일링 스톱 비활성화 (1회용)
                        trailing_state.is_active = False
                        
                        return {
                            'signal_type': ExitSignalType.TRAILING_STOP.value,
                            'exit_ratio': 1.0, # 전량 exit'highest_price': trailing_state.highest_price,
                            'trailing_price': trailing_state.trailing_price,
                            'trailing_pct': trailing_state.trailing_pct * 100,
                            'current_price': current_price
                        }
            
            return None
            
        except Exception as e:
            self.logger.error(f"트레일링 스톱 update failed {symbol}: {e}")
            return None
    
    def calculate_technical_signals(self, symbol: str) -> List[TechnicalSignal]:
        """복합 기술적 신호 계산"""
        signals = []
        
        try:
            if not self.exchange:
                return signals
            
            # 5분봉 데이터 조회 (기술적 청산용)
            ohlcv_5m = self.exchange.fetch_ohlcv(symbol, '5m', limit=100)
            df_5m = pd.DataFrame(ohlcv_5m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # 1. MA5-BB600 데드크로스 + RSI<30
            signal1 = self._check_ma_bb_rsi_signal(df_5m)
            if signal1:
                signals.append(signal1)
            
            # 2. 거래량 급감 (20봉 평균 대비 50% 이하)
            signal2 = self._check_volume_decline_signal(df_5m)
            if signal2:
                signals.append(signal2)
            
            # 3. 3연속 음봉 + MA5 하향 돌파
            signal3 = self._check_consecutive_red_signal(df_5m)
            if signal3:
                signals.append(signal3)
            
            # 4. BB 수축률 50% 이상 (변동성 소멸)
            signal4 = self._check_bb_squeeze_signal(df_5m)
            if signal4:
                signals.append(signal4)
            
            # 5. SuperTrend(10-3) 청산 시그널 (수익률 >10% 조건 하에서)
            signal5 = self._check_supertrend_signal(df_5m)
            if signal5:
                signals.append(signal5)
            
            # 신호 저장
            with self.lock:
                self.technical_signals[symbol] = signals
            
            return signals
            
        except Exception as e:
            self.logger.error(f"기술적 신호 계산 failed {symbol}: {e}")
            return signals
    
    def _check_ma_bb_rsi_signal(self, df: pd.DataFrame) -> Optional[TechnicalSignal]:
        """MA5-BB600 데드크로스 + RSI<30 신호"""
        try:
            # MA5 계산
            df['ma5'] = df['close'].rolling(window=5).mean() # BB600 계산 (600봉이므로 대신 20봉 사용) bb_period = min(20, len(df) - 1) df['bb_middle'] = df['close'].rolling(window=bb_period).mean()
            df['bb_std'] = df['close'].rolling(window=bb_period).std()
            df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * 2) # RSI 계산 delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs)) # 현재 및 이전 값 current_ma5 = df['ma5'].iloc[-1]
            current_bb_upper = df['bb_upper'].iloc[-1]
            current_rsi = df['rsi'].iloc[-1] # 데드크로스 확인 (5봉 내) ma5_cross_down = False for i in range(max(1, len(df) - 5), len(df)): if (df['ma5'].iloc[i-1] > df['bb_upper'].iloc[i-1] and 
                    df['ma5'].iloc[i] <= df['bb_upper'].iloc[i]):
                    ma5_cross_down = True
                    break
            
            # 조건 확인
            if ma5_cross_down and current_rsi < 30:
                strength = min(1.0, (30 - current_rsi) / 30 + 0.5)  # RSI가 낮을수록 강한 신호
                
                return TechnicalSignal(
                    signal_type="MA5_BB_RSI",
                    strength=strength,
                    timestamp=datetime.now().isoformat(),
                    description=f"MA5-BB600 데드크로스 + RSI({current_rsi:.1f})<30"
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"MA-BB-RSI 신호 계산 failed: {e}")
            return None
    
    def _check_volume_decline_signal(self, df: pd.DataFrame) -> Optional[TechnicalSignal]:
        """trade량 급감 신호"""
        try:
            # 20봉 평균 거래량
            df['volume_avg'] = df['volume'].rolling(window=20).mean()
            
            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume_avg'].iloc[-1]
            
            # 50% 이하로 급감
            if current_volume < avg_volume * 0.5:
                decline_ratio = current_volume / avg_volume
                strength = min(1.0, (0.5 - decline_ratio) / 0.5 + 0.3)
                
                return TechnicalSignal(
                    signal_type="VOLUME_DECLINE",
                    strength=strength,
                    timestamp=datetime.now().isoformat(),
                    description=f"trade량 급감 ({decline_ratio*100:.1f}% of 20MA)"
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"trade량 급감 신호 계산 failed: {e}")
            return None
    
    def _check_consecutive_red_signal(self, df: pd.DataFrame) -> Optional[TechnicalSignal]:
        """3연속 음봉 + MA5 하향 돌파 신호"""
        try:
            # MA5 계산
            df['ma5'] = df['close'].rolling(window=5).mean() # 3연속 음봉 확인 recent_3 = df.tail(3) is_3_red = all(row['close'] < row['open'] for _, row in recent_3.iterrows()) # MA5 하향 돌파 확인 current_close = df['close'].iloc[-1]
            current_ma5 = df['ma5'].iloc[-1]
            prev_close = df['close'].iloc[-2]
            prev_ma5 = df['ma5'].iloc[-2] ma5_break_down = (prev_close >= prev_ma5 and current_close < current_ma5) if is_3_red and ma5_break_down: # 음봉 크기 기반 강도 계산 red_ratios = [(row['open'] - row['close']) / row['open'] for _, row in recent_3.iterrows()]
                avg_red_ratio = sum(red_ratios) / len(red_ratios)
                strength = min(1.0, avg_red_ratio * 10 + 0.4)
                
                return TechnicalSignal(
                    signal_type="CONSECUTIVE_RED_MA5",
                    strength=strength,
                    timestamp=datetime.now().isoformat(),
                    description=f"3연속 음봉 + MA5 하향돌파 (평균하락률: {avg_red_ratio*100:.1f}%)"
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"연속 음봉 신호 계산 failed: {e}")
            return None
    
    def _check_bb_squeeze_signal(self, df: pd.DataFrame) -> Optional[TechnicalSignal]:
        """볼린저밴드 수축 신호"""
        try:
            # BB 계산
            bb_period = min(20, len(df) - 1)
            df['bb_middle'] = df['close'].rolling(window=bb_period).mean()
            df['bb_std'] = df['close'].rolling(window=bb_period).std()
            df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * 2)
            df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * 2)
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle'] # 수축률 계산 (현재 vs 평균) current_width = df['bb_width'].iloc[-1]
            avg_width = df['bb_width'].rolling(window=10).mean().iloc[-1]
            
            if current_width < avg_width * 0.5:  # 50% 이상 수축
                squeeze_ratio = current_width / avg_width
                strength = min(1.0, (0.5 - squeeze_ratio) / 0.5 + 0.3)
                
                return TechnicalSignal(
                    signal_type="BB_SQUEEZE",
                    strength=strength,
                    timestamp=datetime.now().isoformat(),
                    description=f"BB 수축 ({squeeze_ratio*100:.1f}% of 10MA width)"
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"BB 수축 신호 계산 failed: {e}")
            return None
    
    def _check_supertrend_signal(self, df: pd.DataFrame) -> Optional[TechnicalSignal]:
        """SuperTrend(10-3) exit 신호 (수익률 >10% condition 하에서만)"""
        try:
            # SuperTrend 계산 (period=10, multiplier=3)
            period = 10
            multiplier = 3
            
            # ATR 계산
            df['tr1'] = df['high'] - df['low']
            df['tr2'] = abs(df['high'] - df['close'].shift(1))
            df['tr3'] = abs(df['low'] - df['close'].shift(1))
            df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
            df['atr'] = df['tr'].rolling(window=period).mean()
            
            # HL2 (High + Low) / 2
            df['hl2'] = (df['high'] + df['low']) / 2
            
            # Basic Upper and Lower Bands
            df['basic_upper'] = df['hl2'] + (multiplier * df['atr'])
            df['basic_lower'] = df['hl2'] - (multiplier * df['atr'])
            
            # Final Upper and Lower Bands
            df['final_upper'] = df['basic_upper']
            df['final_lower'] = df['basic_lower']
            
            for i in range(1, len(df)):
                # Final Upper Band
                if df['basic_upper'].iloc[i] < df['final_upper'].iloc[i-1] or df['close'].iloc[i-1] > df['final_upper'].iloc[i-1]:
                    df.loc[df.index[i], 'final_upper'] = df['basic_upper'].iloc[i]
                else:
                    df.loc[df.index[i], 'final_upper'] = df['final_upper'].iloc[i-1]
                
                # Final Lower Band
                if df['basic_lower'].iloc[i] > df['final_lower'].iloc[i-1] or df['close'].iloc[i-1] < df['final_lower'].iloc[i-1]:
                    df.loc[df.index[i], 'final_lower'] = df['basic_lower'].iloc[i]
                else:
                    df.loc[df.index[i], 'final_lower'] = df['final_lower'].iloc[i-1] # SuperTrend 계산 df['supertrend'] = np.nan
            df['supertrend_direction'] = np.nan  # 1: up trend, -1: down trend
            
            for i in range(1, len(df)):
                if pd.isna(df['supertrend'].iloc[i-1]):
                    df.loc[df.index[i], 'supertrend'] = df['final_upper'].iloc[i]
                    df.loc[df.index[i], 'supertrend_direction'] = -1
                else:
                    if df['supertrend_direction'].iloc[i-1] == -1 and df['close'].iloc[i] <= df['final_lower'].iloc[i]:
                        df.loc[df.index[i], 'supertrend'] = df['final_lower'].iloc[i]
                        df.loc[df.index[i], 'supertrend_direction'] = -1
                    elif df['supertrend_direction'].iloc[i-1] == -1 and df['close'].iloc[i] > df['final_lower'].iloc[i]:
                        df.loc[df.index[i], 'supertrend'] = df['final_lower'].iloc[i]
                        df.loc[df.index[i], 'supertrend_direction'] = 1
                    elif df['supertrend_direction'].iloc[i-1] == 1 and df['close'].iloc[i] >= df['final_upper'].iloc[i]:
                        df.loc[df.index[i], 'supertrend'] = df['final_upper'].iloc[i]
                        df.loc[df.index[i], 'supertrend_direction'] = 1
                    elif df['supertrend_direction'].iloc[i-1] == 1 and df['close'].iloc[i] < df['final_upper'].iloc[i]:
                        df.loc[df.index[i], 'supertrend'] = df['final_upper'].iloc[i]
                        df.loc[df.index[i], 'supertrend_direction'] = -1 # exit 시그널 감지: 상승 트렌드에서 하락 트렌드로 전환 if len(df) >= 2: prev_direction = df['supertrend_direction'].iloc[-2]
                current_direction = df['supertrend_direction'].iloc[-1] # 상승(1)에서 하락(-1)으로 전환시 exit 시그널 if pd.notna(prev_direction) and pd.notna(current_direction): if prev_direction == 1 and current_direction == -1: # 신호 강도 계산 (ATR 기반) current_atr = df['atr'].iloc[-1]
                        current_price = df['close'].iloc[-1]
                        atr_ratio = current_atr / current_price if current_price > 0 else 0
                        
                        # ATR이 클수록 강한 신호
                        strength = min(1.0, atr_ratio * 20 + 0.6)  # 0.6-1.0 범위
                        
                        return TechnicalSignal(
                            signal_type="SUPERTREND_EXIT",
                            strength=strength,
                            timestamp=datetime.now().isoformat(),
                            description=f"SuperTrend(10-3) exit 시그널 (상승→하락 전환, ATR: {atr_ratio*100:.2f}%)"
                        )
            
            return None
            
        except Exception as e:
            self.logger.error(f"SuperTrend 신호 계산 failed: {e}")
            return None
    
    def check_technical_exit(self, symbol: str, current_price: float = None, average_price: float = None) -> Optional[Dict[str, Any]]:
        """복합 기술적 exit 확인"""try: # 기술적 신호 계산 signals = self.calculate_technical_signals(symbol) # SuperTrend 신호에 대한 수익률 condition 체크 if current_price and average_price: profit_pct = (current_price - average_price) / average_price # SuperTrend 신호가 있지만 수익률이 10% 미만인 경우 filter링 filtered_signals = [] for signal in signals: if signal.signal_type =="SUPERTREND_EXIT": if profit_pct >= 0.10: # 수익률 >10% condition filtered_signals.append(signal) self.logger.info(f"🎯 {symbol} SuperTrend Close 시그널 적용 (Profit/Loss: {profit_pct*100:.2f}%)")
                        else:
                            self.logger.debug(f"⏸️ {symbol} SuperTrend 시그널 무시 (Profit/Loss {profit_pct*100:.2f}% < 10%)")
                    else:
                        filtered_signals.append(signal)
                
                signals = filtered_signals
            
            if len(signals) < self.config['technical_exit']['signal_threshold']: return None # 강한 신호만 filter링 strong_signals = [ s for s in signals if s.strength >= self.config['technical_exit']['min_signal_strength']
            ]
            
            if len(strong_signals) >= self.config['technical_exit']['signal_threshold']:
                avg_strength = sum(s.strength for s in strong_signals) / len(strong_signals)
                signal_descriptions = [s.description for s in strong_signals]
                
                # SuperTrend 신호가 포함된 경우 특별 처리
                has_supertrend = any(s.signal_type == "SUPERTREND_EXIT" for s in strong_signals)
                
                self.logger.info(f"🔥 {symbol} 복합 기술적 Close 트리거!")
                for desc in signal_descriptions:
                    self.logger.info(f"   • {desc}")
                
                return {
                    'signal_type': ExitSignalType.TECHNICAL_EXIT.value,
                    'exit_ratio': self.config['technical_exit']['exit_ratio'],
                    'signal_count': len(strong_signals),
                    'avg_strength': avg_strength,
                    'signals': signal_descriptions,
                    'has_supertrend': has_supertrend
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"복합 기술적 Close verify failed {symbol}: {e}")
            return None
    
    def check_all_exit_conditions(self, symbol: str, current_price: float, average_price: float, 
                                 current_stage: str) -> Optional[Dict[str, Any]]:
        """모든 exit condition 종합 확인"""
        try:
            # 1. 적응형 손절 확인 (최우선)
            adaptive_stop_loss_pct = self.get_adaptive_stop_loss(symbol, current_stage)
            profit_pct = (current_price - average_price) / average_price
            
            if profit_pct <= adaptive_stop_loss_pct:
                volatility_level = self.last_volatility.get(symbol, VolatilityLevel.MEDIUM)
                
                return {
                    'signal_type': ExitSignalType.ADAPTIVE_STOP_LOSS.value,
                    'exit_ratio': 1.0,
                    'stop_loss_pct': adaptive_stop_loss_pct * 100,
                    'profit_pct': profit_pct * 100,
                    'volatility_level': volatility_level.value,
                    'current_stage': current_stage,
                    'current_price': current_price
                }
            
            # 2. 복합 기술적 청산 확인 (손절 다음 우선순위)
            technical_exit = self.check_technical_exit(symbol, current_price, average_price)
            if technical_exit:
                return technical_exit
            
            # 3. 트레일링 스톱 확인
            trailing_exit = self.update_trailing_stop(symbol, current_price, average_price)
            if trailing_exit:
                return trailing_exit
            
            # 4. 다단계 익절 확인
            multi_level_exit = self.check_multi_level_exits(symbol, current_price, average_price)
            if multi_level_exit:
                return multi_level_exit
            
            return None
            
        except Exception as e:
            self.logger.error(f"종합 Close Condition verify failed {symbol}: {e}")
            return None
    
    def reset_exit_state(self, symbol: str):
        """exit 상태 initialize"""with self.lock: # 트레일링 스톱 initialize if symbol in self.trailing_stops: del self.trailing_stops[symbol] # take profit 레벨 initialize if symbol in self.exit_levels: del self.exit_levels[symbol] # 기술적 신호 initialize if symbol in self.technical_signals: del self.technical_signals[symbol] # 변동성 정보 initialize if symbol in self.last_volatility: del self.last_volatility[symbol] self.logger.info(f"🔄 {symbol} Close 상태 initialize completed")
    
    def get_exit_status(self, symbol: str) -> Dict[str, Any]:
        """exit 시스템 상태 조회"""
        with self.lock:
            return {
                'trailing_stop': self.trailing_stops.get(symbol),
                'exit_levels': self.exit_levels.get(symbol, []),
                'last_volatility': self.last_volatility.get(symbol),
                'technical_signals': self.technical_signals.get(symbol, [])
            }