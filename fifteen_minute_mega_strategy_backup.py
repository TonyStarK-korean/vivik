# -*- coding: utf-8 -*-
"""
15분봉 A전략(바닥타점) + B전략(급등초입) 시스템
레버리지 20배 적용

거래 설정:
- 레버리지: 20배
- 포지션 크기: 원금 1.0% x 20배 레버리지 (20% 노출)
- 최대 진입 종목: 10종목
- 재진입: 순환매 활성화 (최대 3회 순환매)
- 단계별 손절: 초기 -10% (시드 대비 6% 손실)
- 종목당 최대 비중: 3.0% (초기 1.0% + DCA 1.0% + 1.0%)
- 최대 원금 사용: 30% (10종목 × 3.0%)
- 손실 계산: 총 3% × 20배 × -10% = 시드의 6% 손실

DCA 시스템:
- 최초 진입: 1.0% x 20배 = 20% 노출 시장가 매수
- 1차 DCA: -3% 하락가에 1.0% x 20배 지정가 주문 (즉시 등록)
- 2차 DCA: -6% 하락가에 1.0% x 20배 지정가 주문 (즉시 등록)
- 전량 손절: -10% (시드 대비 6% 손실)

15분봉 A전략(바닥타점) + B전략(급등초입) 조건:
A전략: (ma80<ma480 and ma5<ma480) and BB복합조건 및 골든크로스
B전략: 기존 급등초입 조건 유지
"""

import os
import sys
import ccxt
import pandas as pd
import numpy as np
import time
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# 🔧 스크립트 디렉토리를 Python 경로에 추가 (import 문제 해결)
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# 기존 모듈들 import
try:
    from binance_config import BinanceConfig
    HAS_BINANCE_CONFIG = True
except ImportError:
    print("[INFO] binance_config.py 없음 - 공개 API만 사용")
    class BinanceConfig:
        API_KEY = ""
        SECRET_KEY = ""
    HAS_BINANCE_CONFIG = False

try:
    from telegram_bot import TelegramBot
    HAS_TELEGRAM = True
    print("[INFO] 텔레그램 봇 모듈 로드 완료")
except ImportError:
    print("[INFO] telegram_bot.py 없음 - 텔레그램 알림 비활성화")
    HAS_TELEGRAM = False
    class TelegramBot:
        def __init__(self):
            pass
        def send_message(self, message):
            pass

try:
    from improved_dca_position_manager import ImprovedDCAPositionManager
    HAS_DCA_MANAGER = True
    print("[INFO] 개선된 DCA 매니저 로드 완료")
except ImportError:
    print("[INFO] improved_dca_position_manager.py 없음 - DCA 기능 비활성화")
    HAS_DCA_MANAGER = False

# 가상매매 제거 - 실전매매로 변경
# try:
#     from virtual_trading_manager import VirtualTradingManager
#     HAS_VIRTUAL_TRADING = True
#     print("[INFO] 가상매매 매니저 로드 완료")
# except ImportError:
#     print("[INFO] virtual_trading_manager.py 없음 - 가상매매 기능 비활성화")
#     HAS_VIRTUAL_TRADING = False

HAS_VIRTUAL_TRADING = False  # 실전매매 모드

try:
    from websocket_ohlcv_provider import WebSocketOHLCVProvider
    HAS_WEBSOCKET_PROVIDER = True
    print("[INFO] WebSocket OHLCV 제공자 로드 완료")
except ImportError:
    print("[INFO] websocket_ohlcv_provider.py 없음 - WebSocket 최적화 비활성화")
    HAS_WEBSOCKET_PROVIDER = False

def get_korea_time():
    """한국 시간 반환"""
    return datetime.now(timezone(timedelta(hours=9)))

class FifteenMinuteMegaStrategy:
    """15분봉 A전략(바닥타점) + B전략(급등초입) 시스템"""
    
    def __init__(self, sandbox=False):
        """초기화"""
        self.sandbox = sandbox
        self.logger = self._setup_logger()
        
        # Exchange 설정 (공개 API + 프라이빗 API 분리)
        # 공개 API (스캔용)
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
        # 프라이빗 API (거래용)
        if HAS_BINANCE_CONFIG and BinanceConfig.API_KEY:
            self.private_exchange = ccxt.binance({
                'apiKey': BinanceConfig.API_KEY,
                'secret': BinanceConfig.SECRET_KEY,
                'sandbox': sandbox,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'warnOnFetchOpenOrdersWithoutSymbol': False  # 경고 메시지 억제
                }
            })
            print("[INFO] 프라이빗 API 초기화 완료")
        else:
            self.private_exchange = None
            print("[WARN] 프라이빗 API 없음 - 거래 기능 비활성화")
        
        # 텔레그램 봇 초기화
        self.telegram_bot = TelegramBot() if HAS_TELEGRAM else None
        
        # 실전매매 설정
        self.virtual_trader = None  # 가상매매 제거
        self.active_positions = {}  # 실제 포지션 추적 {symbol: position_info}
        print("[INFO] 실전매매 모드 - 실제 거래 활성화")
        
        # WebSocket OHLCV 제공자 초기화
        if HAS_WEBSOCKET_PROVIDER:
            self.ws_provider = WebSocketOHLCVProvider()
            print("[INFO] WebSocket OHLCV 제공자 초기화 완료")
        else:
            self.ws_provider = None
            print("[WARN] WebSocket OHLCV 제공자 없음")
        
        # DCA 매니저 초기화 (레버리지 20배)
        if HAS_DCA_MANAGER:
            self.dca_manager = ImprovedDCAPositionManager()
            # 레버리지 20배로 설정 업데이트
            self.dca_manager.leverage = 20.0
            print("[INFO] DCA 매니저 초기화 완료 - 레버리지 20배 적용")
        else:
            self.dca_manager = None
            print("[WARN] DCA 매니저 없음")
        
        # 캐시 시스템
        self._ohlcv_cache = {}
        self._ohlcv_cache_ttl = 1200  # 20분
        self._market_cache = None
        self._market_cache_time = 0
        self._market_cache_ttl = 3600  # 1시간
        
        # 실제 포지션을 조회해서 초기화
        self._load_active_positions()
        
        # 스캔 모드
        self._scan_mode = True
        
        # 디버그 로그 파일
        self.debug_log_file = "fifteen_minute_mega.log"
        
        print("🚀 15분봉 초필살기 전략 시스템 초기화 완료")
        print(f"   📊 레버리지: 20배")
        print(f"   💰 최초 진입: 1% (20% 노출)")
        print(f"   📉 최대 손실: 6% (시드 기준)")
    
    def _setup_logger(self):
        """로거 설정"""
        import logging
        logger = logging.getLogger('FifteenMinuteMega')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _write_debug_log(self, message):
        """디버그 로그 작성"""
        try:
            timestamp = get_korea_time().strftime('%H:%M:%S')
            with open(self.debug_log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception:
            pass
    
    def _load_active_positions(self):
        """실제 거래소에서 활성 포지션 로드"""
        try:
            if not self.private_exchange:
                print("⚠️ 프라이빗 API 없음 - 포지션 조회 건너뛰기")
                if not hasattr(self, 'active_positions'):
                    self.active_positions = {}
                return
                
            # 실제 포지션 조회
            positions = self.private_exchange.fetch_positions()
            
            # 실제 포지션이 있는 심볼들을 active_positions에 추가
            for position in positions:
                if position['contracts'] > 0:  # 포지션이 있는 경우
                    symbol = position['symbol']
                    self.active_positions[symbol] = {
                        'size': position['contracts'],
                        'side': position['side'],
                        'entry_price': position['entryPrice'],
                        'mark_price': position['markPrice'],
                        'unrealized_pnl': position['unrealizedPnl'],
                        'percentage': position['percentage']
                    }
            
            print(f"[INFO] 실제 포지션 로드 완료: {len(self.active_positions)}개")
            if self.active_positions:
                for symbol, pos in self.active_positions.items():
                    clean_symbol = symbol.replace('/USDT:USDT', '')
                    print(f"   • {clean_symbol}: {pos['percentage']:+.2f}% (${pos['size']:,.0f})")
                    
        except Exception as e:
            print(f"[WARN] 포지션 로드 실패: {e}")
            # 실패시 빈 딕셔너리로 초기화
            if not hasattr(self, 'active_positions'):
                self.active_positions = {}
    
    def get_portfolio_summary(self):
        """실제 포트폴리오 현황 조회"""
        try:
            if not self.private_exchange:
                return {
                    'free_balance': 0,
                    'total_balance': 0, 
                    'total_unrealized_pnl': 0,
                    'open_positions': 0,
                    'positions': {}
                }
                
            # 실제 잔고 조회
            balance = self.private_exchange.fetch_balance()
            
            # 포지션 재조회
            positions = self.private_exchange.fetch_positions()
            active_positions = [p for p in positions if p['contracts'] > 0]
            
            total_unrealized_pnl = sum(p.get('unrealizedPnl', 0) for p in active_positions)
            free_balance = balance['USDT']['free']
            total_balance = balance['USDT']['total']
            
            return {
                'free_balance': free_balance,
                'total_balance': total_balance,
                'total_unrealized_pnl': total_unrealized_pnl,
                'open_positions': len(active_positions),
                'positions': {p['symbol']: {
                    'symbol': p['symbol'],
                    'size': p['contracts'], 
                    'side': p['side'],
                    'entry_price': p['entryPrice'],
                    'mark_price': p['markPrice'],
                    'unrealized_pnl': p['unrealizedPnl'],
                    'percentage': p['percentage']
                } for p in active_positions}
            }
            
        except Exception as e:
            self.logger.error(f"포트폴리오 조회 실패: {e}")
            return {
                'free_balance': 0,
                'total_balance': 0, 
                'total_unrealized_pnl': 0,
                'open_positions': 0,
                'positions': {}
            }
    
    def get_ohlcv_data(self, symbol, timeframe, limit=500):
        """OHLCV 데이터 조회 (캐싱 시스템 적용)"""
        try:
            # 캐시 체크
            cache_key = f"{symbol}_{timeframe}"
            current_time = time.time()
            
            if cache_key in self._ohlcv_cache:
                cached_data, cached_time = self._ohlcv_cache[cache_key]
                if current_time - cached_time < self._ohlcv_cache_ttl:
                    if len(cached_data) >= limit:
                        return cached_data.tail(limit)
                    return cached_data
            
            # API 호출
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if ohlcv and len(ohlcv) >= 10:
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # 캐시 저장
                self._ohlcv_cache[cache_key] = (df, current_time)
                return df
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"{symbol} {timeframe} 데이터 조회 실패: {e}")
            return None
    
    def calculate_indicators(self, df):
        """기술적 지표 계산"""
        try:
            if df is None or len(df) == 0:
                return None
            
            df = df.copy()
            
            # 기본 이동평균선
            df['ma5'] = df['close'].rolling(window=5).mean()
            df['ma20'] = df['close'].rolling(window=20).mean()
            df['ma80'] = df['close'].rolling(window=80).mean()
            df['ma480'] = df['close'].rolling(window=480).mean()
            
            # 볼린저 밴드
            # BB200 (기간 200, 표준편차 2.0)
            if len(df) >= 200:
                bb200_ma = df['close'].rolling(window=200).mean()
                bb200_std = df['close'].rolling(window=200).std()
                df['bb200_upper'] = bb200_ma + (bb200_std * 2.0)
                df['bb200_lower'] = bb200_ma - (bb200_std * 2.0)
                df['bb200_middle'] = bb200_ma
            
            # BB480 (기간 480, 표준편차 1.5)
            if len(df) >= 480:
                bb480_ma = df['close'].rolling(window=480).mean()
                bb480_std = df['close'].rolling(window=480).std()
                df['bb480_upper'] = bb480_ma + (bb480_std * 1.5)
                df['bb480_lower'] = bb480_ma - (bb480_std * 1.5)
                df['bb480_middle'] = bb480_ma
            
            return df
            
        except Exception as e:
            self.logger.error(f"지표 계산 실패: {e}")
            return df
    
    def check_fifteen_minute_mega_conditions(self, symbol, df_15m):
        """
        15분봉 A전략(바닥타점) + B전략(급등초입) 조건 체크
        
        A전략: 15분봉 바닥타점
        - (ma80<ma480 and ma5<ma480) AND
        - ((15분봉상 60봉이내 (bb80상단선-bb200상단선 이격도 1%이내 or bb80상단선-bb200상단선 골든크로스) or 
           (5분봉상 30봉이내 bb80상단선-bb200상단선 골든크로스)) AND
        - ((5봉이내 1봉전 ma5-ma80 골든크로스) or (5봉이내 ma5-ma20 골든크로스 ma5>ma20 and ma5우상향 2회이상)) AND
        - (현재가 ma5이격도 0.5%이내 or 현재가<ma5)
        
        B전략: 15분봉 급등초입
        - 200봉 이내 MA80-MA480 골든크로스 AND
        - BB 골든크로스 AND
        - 10봉 이내 MA5-MA20 골든크로스 AND
        - 250봉이내 BB200상단-MA480 상향돌파
        
        Args:
            symbol: 심볼명
            df_15m: 15분봉 데이터프레임
        
        Returns:
            tuple: (조건충족여부, 조건상세리스트)
        """
        conditions = []
        clean_symbol = symbol.replace('/USDT:USDT', '')
        
        if df_15m is None or len(df_15m) < 500:
            conditions.append("[15분봉 전략] 데이터 부족 (500봉 필요)")
            return False, conditions
        
        # 지표 계산
        df_calc = self.calculate_indicators(df_15m)
        if df_calc is None:
            conditions.append("[15분봉 전략] 지표 계산 실패")
            return False, conditions
        
        # BB80 추가 계산 (기간 80, 표준편차 2.0)
        if len(df_calc) >= 80:
            bb80_ma = df_calc['close'].rolling(window=80).mean()
            bb80_std = df_calc['close'].rolling(window=80).std()
            df_calc['bb80_upper'] = bb80_ma + (bb80_std * 2.0)
            df_calc['bb80_lower'] = bb80_ma - (bb80_std * 2.0)
            df_calc['bb80_middle'] = bb80_ma
        
        try:
            # A전략: 15분봉 바닥 타점 체크
            strategy_a_signal, strategy_a_conditions = self._check_strategy_a_bottom_entry(symbol, df_calc)
            conditions.extend(strategy_a_conditions)
            
            # B전략: 15분봉 상승초입 타점 체크 (기존 조건)
            strategy_b_signal, strategy_b_conditions = self._check_strategy_b_uptrend_entry(df_calc)
            conditions.extend(strategy_b_conditions)
            
            # A전략 OR B전략 (둘 중 하나라도 충족하면 진입)
            is_signal = strategy_a_signal or strategy_b_signal
            
            # 전략별 결과 추가
            if strategy_a_signal:
                conditions.append("[전략결과] A전략(바닥타점) 조건 충족 ✅")
            if strategy_b_signal:
                conditions.append("[전략결과] B전략(급등초입) 조건 충족 ✅")
            if not is_signal:
                conditions.append("[전략결과] A전략, B전략 모두 미충족 ❌")
            
            # 디버그 로그
            if is_signal:
                strategy_name = "A전략(바닥타점)" if strategy_a_signal else "B전략(급등초입)"
                if strategy_a_signal and strategy_b_signal:
                    strategy_name = "A전략(바닥타점)+B전략(급등초입)"
                self._write_debug_log(f"🎯 [{clean_symbol}] 15분봉 {strategy_name} 조건 충족!")
                for condition in conditions:
                    self._write_debug_log(f"   {condition}")
            
            return is_signal, conditions
            
        except Exception as e:
            conditions.append(f"[15분봉 전략] 조건 체크 오류: {str(e)}")
            self.logger.error(f"[{clean_symbol}] 15분봉 전략 조건 체크 실패: {e}")
            return False, conditions
    
    def _check_strategy_a_bottom_entry(self, symbol, df_calc):
        """A전략: 15분봉 바닥 타점"""
        try:
            conditions = []
            
            # 조건 1: (ma80<ma480 and ma5<ma480)
            condition1 = False
            try:
                ma80_current = df_calc['ma80'].iloc[-1]
                ma480_current = df_calc['ma480'].iloc[-1]
                ma5_current = df_calc['ma5'].iloc[-1]
                
                if pd.notna(ma80_current) and pd.notna(ma480_current) and pd.notna(ma5_current):
                    if ma80_current < ma480_current and ma5_current < ma480_current:
                        condition1 = True
                
                conditions.append(f"[A전략 조건1] MA80<MA480 AND MA5<MA480: {condition1}")
            except Exception as e:
                conditions.append(f"[A전략 조건1] 기본 MA 조건 계산 실패: {e}")
            
            # 조건 2: BB 이격도 및 골든크로스 체크
            condition2 = False
            try:
                # 15분봉상 60봉이내 BB80상단선-BB200상단선 이격도 1%이내 or 골든크로스
                bb80_upper = df_calc.get('bb80_upper', pd.Series())
                bb200_upper = df_calc['bb200_upper']
                
                # 15분봉 BB 체크
                bb_15m_check = False
                if len(bb80_upper) >= 60 and len(bb200_upper) >= 60:
                    for i in range(min(60, len(bb80_upper))):
                        bb80_val = bb80_upper.iloc[-(i+1)]
                        bb200_val = bb200_upper.iloc[-(i+1)]
                        
                        if pd.notna(bb80_val) and pd.notna(bb200_val) and bb200_val > 0:
                            # 이격도 1%이내 체크
                            gap_pct = abs(bb80_val - bb200_val) / bb200_val
                            if gap_pct <= 0.01:
                                bb_15m_check = True
                                break
                            
                            # 골든크로스 체크 (i>0일때만)
                            if i > 0:
                                bb80_prev = bb80_upper.iloc[-(i+2)]
                                bb200_prev = bb200_upper.iloc[-(i+2)]
                                if (pd.notna(bb80_prev) and pd.notna(bb200_prev) and
                                    bb80_prev <= bb200_prev and bb80_val > bb200_val):
                                    bb_15m_check = True
                                    break
                
                # 5분봉상 30봉이내 BB80상단선-BB200상단선 골든크로스
                bb_5m_check = False
                try:
                    # 5분봉 데이터 조회
                    df_5m = self.get_ohlcv_data(symbol, '5m', limit=100)
                    if df_5m is not None and len(df_5m) >= 30:
                        df_5m_calc = self.calculate_indicators(df_5m)
                        if df_5m_calc is not None and len(df_5m_calc) >= 80:
                            # BB80 계산
                            bb80_ma_5m = df_5m_calc['close'].rolling(window=80).mean()
                            bb80_std_5m = df_5m_calc['close'].rolling(window=80).std()
                            bb80_5m = bb80_ma_5m + (bb80_std_5m * 2.0)
                            bb200_5m = df_5m_calc['bb200_upper']
                            
                            if len(bb80_5m) >= 30 and len(bb200_5m) >= 30:
                                for i in range(1, min(31, len(bb80_5m))):
                                    bb80_prev = bb80_5m.iloc[-i-1]
                                    bb80_curr = bb80_5m.iloc[-i]
                                    bb200_prev = bb200_5m.iloc[-i-1]
                                    bb200_curr = bb200_5m.iloc[-i]
                                    
                                    if (pd.notna(bb80_prev) and pd.notna(bb80_curr) and
                                        pd.notna(bb200_prev) and pd.notna(bb200_curr) and
                                        bb80_prev <= bb200_prev and bb80_curr > bb200_curr):
                                        bb_5m_check = True
                                        break
                except:
                    pass
                
                condition2 = bb_15m_check or bb_5m_check
                bb_status = "15분봉" if bb_15m_check else "5분봉" if bb_5m_check else "미충족"
                conditions.append(f"[A전략 조건2] BB 이격도/골든크로스 ({bb_status}): {condition2}")
            except Exception as e:
                conditions.append(f"[A전략 조건2] BB 조건 계산 실패: {e}")
            
            # 조건 3: MA 골든크로스 조건
            condition3 = False
            try:
                ma5 = df_calc['ma5']
                ma20 = df_calc['ma20']
                ma80 = df_calc['ma80']
                
                # 5봉이내 1봉전 MA5-MA80 골든크로스
                ma5_ma80_cross = False
                if len(ma5) >= 6 and len(ma80) >= 6:
                    for i in range(1, min(6, len(ma5)-1)):  # 1봉전부터 체크
                        prev_idx = -(i+2)  # 1봉전
                        curr_idx = -(i+1)  # 현재
                        ma5_prev = ma5.iloc[prev_idx]
                        ma5_curr = ma5.iloc[curr_idx]
                        ma80_prev = ma80.iloc[prev_idx]
                        ma80_curr = ma80.iloc[curr_idx]
                        
                        if (pd.notna(ma5_prev) and pd.notna(ma5_curr) and 
                            pd.notna(ma80_prev) and pd.notna(ma80_curr) and
                            ma5_prev <= ma80_prev and ma5_curr > ma80_curr):
                            ma5_ma80_cross = True
                            break
                
                # 5봉이내 MA5-MA20 골든크로스 with 조건
                ma5_ma20_cross = False
                if len(ma5) >= 5 and len(ma20) >= 5:
                    for i in range(1, min(6, len(ma5))):
                        ma5_prev = ma5.iloc[-i-1]
                        ma5_curr = ma5.iloc[-i]
                        ma20_prev = ma20.iloc[-i-1]
                        ma20_curr = ma20.iloc[-i]
                        
                        if (pd.notna(ma5_prev) and pd.notna(ma5_curr) and
                            pd.notna(ma20_prev) and pd.notna(ma20_curr) and
                            ma5_prev <= ma20_prev and ma5_curr > ma20_curr):
                            # MA5>MA20 and MA5 우상향 2회이상 체크
                            current_ma5 = ma5.iloc[-1]
                            current_ma20 = ma20.iloc[-1]
                            
                            if pd.notna(current_ma5) and pd.notna(current_ma20) and current_ma5 > current_ma20:
                                # MA5 우상향 2회이상 체크
                                uptrend_count = 0
                                for j in range(1, min(4, len(ma5))):
                                    if (pd.notna(ma5.iloc[-j]) and pd.notna(ma5.iloc[-j-1]) and
                                        ma5.iloc[-j] > ma5.iloc[-j-1]):
                                        uptrend_count += 1
                                
                                if uptrend_count >= 2:
                                    ma5_ma20_cross = True
                                    break
                
                condition3 = ma5_ma80_cross or ma5_ma20_cross
                cross_type = "MA5-MA80" if ma5_ma80_cross else "MA5-MA20" if ma5_ma20_cross else "미충족"
                conditions.append(f"[A전략 조건3] MA 골든크로스 ({cross_type}): {condition3}")
            except Exception as e:
                conditions.append(f"[A전략 조건3] MA 골든크로스 계산 실패: {e}")
            
            # 조건 4: 현재가 MA5 이격도 조건
            condition4 = False
            try:
                current_price = df_calc['close'].iloc[-1]
                ma5_current = df_calc['ma5'].iloc[-1]
                
                if pd.notna(current_price) and pd.notna(ma5_current) and ma5_current > 0:
                    # 현재가 MA5 이격도 0.5%이내 or 현재가<MA5
                    ma5_distance = abs(current_price - ma5_current) / ma5_current
                    
                    if ma5_distance <= 0.005 or current_price < ma5_current:
                        condition4 = True
                
                price_status = "이격도 0.5%이내" if condition4 and current_price >= ma5_current else "현재가<MA5" if condition4 else "미충족"
                conditions.append(f"[A전략 조건4] 현재가-MA5 조건 ({price_status}): {condition4}")
            except Exception as e:
                conditions.append(f"[A전략 조건4] 현재가-MA5 이격도 계산 실패: {e}")
            
            # A전략 최종 판정: 모든 조건 충족
            strategy_a_signal = condition1 and condition2 and condition3 and condition4
            
            return strategy_a_signal, conditions
            
        except Exception as e:
            return False, [f"A전략 체크 실패: {e}"]
    
    def _check_strategy_b_uptrend_entry(self, df_calc):
        """B전략: 15분봉 급등초입"""
        try:
            conditions = []
            
            # 조건 1: 200봉이내 MA80-MA480 골든크로스
            condition1 = False
            condition1_detail = "골든크로스 없음"
            
            if len(df_calc) >= 200:
                for i in range(len(df_calc) - 200, len(df_calc)):
                    if i <= 0:
                        continue
                    
                    prev_candle = df_calc.iloc[i-1]
                    curr_candle = df_calc.iloc[i]
                    
                    # 골든크로스: 이전봉에서 MA80 < MA480, 현재봉에서 MA80 >= MA480
                    if (pd.notna(prev_candle['ma80']) and pd.notna(prev_candle['ma480']) and
                        pd.notna(curr_candle['ma80']) and pd.notna(curr_candle['ma480']) and
                        prev_candle['ma80'] < prev_candle['ma480'] and
                        curr_candle['ma80'] >= curr_candle['ma480']):
                        condition1 = True
                        bars_ago = len(df_calc) - i - 1
                        condition1_detail = f"{bars_ago}봉전 골든크로스"
                        break
            
            conditions.append(f"[B전략 조건1] MA80-MA480 골든크로스 ({condition1_detail}): {condition1}")
            
            # 조건 2: BB 골든크로스 (BB200상단선-BB480상단선 OR BB80상단선-BB480상단선)
            condition2 = False
            condition2_detail = "골든크로스 없음"
            
            if len(df_calc) >= 200:
                # BB200상단선(표편2)-BB480상단선(표편1.5) 골든크로스 체크
                for i in range(len(df_calc) - 200, len(df_calc)):
                    if i <= 0:
                        continue
                    
                    prev_candle = df_calc.iloc[i-1]
                    curr_candle = df_calc.iloc[i]
                    
                    # 골든크로스: 이전봉에서 BB200상단 < BB480상단, 현재봉에서 BB200상단 >= BB480상단
                    if (pd.notna(prev_candle['bb200_upper']) and pd.notna(prev_candle['bb480_upper']) and
                        pd.notna(curr_candle['bb200_upper']) and pd.notna(curr_candle['bb480_upper']) and
                        prev_candle['bb200_upper'] < prev_candle['bb480_upper'] and
                        curr_candle['bb200_upper'] >= curr_candle['bb480_upper']):
                        condition2 = True
                        bars_ago = len(df_calc) - i - 1
                        condition2_detail = f"BB200-BB480 골든크로스 {bars_ago}봉전"
                        break
                
                # BB80상단선(표편2)-BB480상단선(표편1.5) 골든크로스 체크 (위에서 못찾은 경우)
                if not condition2:
                    for i in range(len(df_calc) - 200, len(df_calc)):
                        if i <= 0:
                            continue
                        
                        prev_candle = df_calc.iloc[i-1]
                        curr_candle = df_calc.iloc[i]
                        
                        # 골든크로스: 이전봉에서 BB80상단 < BB480상단, 현재봉에서 BB80상단 >= BB480상단
                        if (pd.notna(prev_candle.get('bb80_upper')) and pd.notna(prev_candle['bb480_upper']) and
                            pd.notna(curr_candle.get('bb80_upper')) and pd.notna(curr_candle['bb480_upper']) and
                            prev_candle['bb80_upper'] < prev_candle['bb480_upper'] and
                            curr_candle['bb80_upper'] >= curr_candle['bb480_upper']):
                            condition2 = True
                            bars_ago = len(df_calc) - i - 1
                            condition2_detail = f"BB80-BB480 골든크로스 {bars_ago}봉전"
                            break
            
            conditions.append(f"[B전략 조건2] BB 골든크로스 ({condition2_detail}): {condition2}")
            
            # 조건 3: 10봉이내 MA5-MA20 골든크로스
            condition3 = False
            condition3_detail = "골든크로스 없음"
            
            if len(df_calc) >= 10:
                for i in range(len(df_calc) - 10, len(df_calc)):
                    if i <= 0:
                        continue
                    
                    prev_candle = df_calc.iloc[i-1]
                    curr_candle = df_calc.iloc[i]
                    
                    # 골든크로스: 이전봉에서 MA5 < MA20, 현재봉에서 MA5 >= MA20
                    if (pd.notna(prev_candle['ma5']) and pd.notna(prev_candle['ma20']) and
                        pd.notna(curr_candle['ma5']) and pd.notna(curr_candle['ma20']) and
                        prev_candle['ma5'] < prev_candle['ma20'] and
                        curr_candle['ma5'] >= curr_candle['ma20']):
                        condition3 = True
                        bars_ago = len(df_calc) - i - 1
                        condition3_detail = f"MA5-MA20 골든크로스 {bars_ago}봉전"
                        break
            
            conditions.append(f"[B전략 조건3] MA5-MA20 골든크로스 ({condition3_detail}): {condition3}")
            
            # 조건 4: 250봉이내 BB200상단선이 MA480 상향돌파
            condition4 = False
            condition4_detail = "상향돌파 없음"
            
            if len(df_calc) >= 250:
                for i in range(len(df_calc) - 250, len(df_calc)):
                    if i <= 0:
                        continue
                    
                    prev_candle = df_calc.iloc[i-1]
                    curr_candle = df_calc.iloc[i]
                    
                    # 상향돌파: 이전봉에서 BB200상단 <= MA480, 현재봉에서 BB200상단 > MA480
                    if (pd.notna(prev_candle['bb200_upper']) and pd.notna(prev_candle['ma480']) and
                        pd.notna(curr_candle['bb200_upper']) and pd.notna(curr_candle['ma480']) and
                        prev_candle['bb200_upper'] <= prev_candle['ma480'] and
                        curr_candle['bb200_upper'] > curr_candle['ma480']):
                        condition4 = True
                        bars_ago = len(df_calc) - i - 1
                        condition4_detail = f"BB200상단-MA480 상향돌파 {bars_ago}봉전"
                        break
            
            conditions.append(f"[B전략 조건4] BB200상단-MA480 상향돌파 ({condition4_detail}): {condition4}")
            
            # B전략 최종 신호 판정: 모든 조건이 True여야 함
            strategy_b_signal = condition1 and condition2 and condition3 and condition4
            
            return strategy_b_signal, conditions
            
        except Exception as e:
            return False, [f"B전략 체크 실패: {e}"]
    
    def scan_symbols(self):
        """15분봉 초필살기 전략 스캔 (단계별 상세 출력)"""
        try:
            print(f"\n{'='*80}")
            print("🚀 15분봉 초필살기 전략 스캔 시작")
            print(f"{'='*80}")
            scan_start_time = time.time()
            
            # 공개 API를 사용한 실제 데이터 스캔 (API 키 불필요)
            try:
                print("🔍 공개 API 실시간 데이터 스캔 시작...")
                return self._detailed_scan_with_real_data()
            
            except Exception as scan_error:
                print(f"❌ 실시간 스캔 실패: {str(scan_error)[:100]}")
                print("⚠️ 스캔을 중단합니다. (가짜 신호 생성 방지)")
                return []
                
        except Exception as e:
            self.logger.error(f"스캔 실패: {e}")
            return []
    
    def _detailed_scan_with_real_data(self):
        """상세 실제 데이터 스캔 (단계별 출력)"""
        scan_start = time.time()
        
        try:
            # 1단계: 마켓 데이터 로드
            print("\n📋 1단계: 마켓 데이터 로드 중...")
            markets = self.exchange.load_markets()
            
            # USDT 선물 심볼 필터링
            usdt_futures = [symbol for symbol in markets.keys() 
                          if symbol.endswith('/USDT:USDT') and markets[symbol]['active']]
            
            print(f"   📊 전체 USDT 선물: {len(usdt_futures)}개")
            
            # 2단계: 24시간 상승률 상위 200개 → 4시간봉 필터링
            print("\n📈 2단계: 24시간 상승률 상위 200개 선별 중...")
            filter_start = time.time()
            
            try:
                tickers = self.exchange.fetch_tickers()
                
                # 24시간 상승률 + KST 상승률 상위 심볼 선별
                change_filtered = []
                kst_timezone = timezone(timedelta(hours=9))  # 한국 시간
                current_kst = datetime.now(kst_timezone)
                kst_start_today = current_kst.replace(hour=0, minute=0, second=0, microsecond=0)
                
                for symbol, ticker in tickers.items():
                    if symbol in usdt_futures:
                        volume = ticker.get('quoteVolume', 0)
                        change_24h = ticker.get('percentage', 0) or 0
                        current_price = ticker.get('last', 0)
                        
                        # 기본 필터링: 거래량 > 0, 24시간 변동률 > 0%
                        if volume > 0 and change_24h > 0 and current_price > 0:
                            try:
                                # KST 상승률 계산 (실제 데이터 사용)
                                try:
                                    ohlcv_1h = self.exchange.fetch_ohlcv(symbol, '1h', limit=24)
                                    
                                    if ohlcv_1h and len(ohlcv_1h) > 0:
                                        # 대략 KST 00:00 시간대의 가격을 찾기
                                        kst_open_price = None
                                        for candle in ohlcv_1h:
                                            candle_time = datetime.fromtimestamp(candle[0] / 1000, tz=kst_timezone)
                                            if candle_time.hour == 0:  # KST 00시대 봉
                                                kst_open_price = candle[1]  # 시가
                                                break
                                        
                                        # KST 00시 데이터가 없으면 가장 오래된 데이터 사용
                                        if not kst_open_price and ohlcv_1h:
                                            kst_open_price = ohlcv_1h[0][1]  # 첫 번째 봉의 시가
                                        
                                        # KST 상승률 계산
                                        if kst_open_price and kst_open_price > 0:
                                            kst_change_pct = ((current_price - kst_open_price) / kst_open_price) * 100
                                            
                                            # 현실적인 범위 체크 (-50% ~ +50%)
                                            if -50 <= kst_change_pct <= 50 and kst_change_pct > 0:
                                                change_filtered.append((symbol, ticker, change_24h, volume, kst_change_pct))
                                            elif change_24h > 0:
                                                # KST 데이터 비현실적이면 24h만 사용
                                                change_filtered.append((symbol, ticker, change_24h, volume, 0))
                                        elif change_24h > 0:
                                            # KST 계산 실패시 24h만 사용
                                            change_filtered.append((symbol, ticker, change_24h, volume, 0))
                                    elif change_24h > 0:
                                        # 1h 데이터 없으면 24h만 사용
                                        change_filtered.append((symbol, ticker, change_24h, volume, 0))
                                        
                                except:
                                    # API 오류시 24h만 사용
                                    if change_24h > 0:
                                        change_filtered.append((symbol, ticker, change_24h, volume, 0))
                                        
                            except Exception:
                                # 심볼별 처리 오류시 건너뛰기
                                continue
                
                # 24시간 상승률 순 정렬
                change_sorted = sorted(change_filtered, key=lambda x: x[2], reverse=True)
                
                # 실제 필터링된 개수 확인 후 상위 200개 선별
                total_filtered = len(change_filtered)
                top_200_symbols = change_sorted[:200]
                actual_selected = len(top_200_symbols)
                
                print(f"   ✅ 24h+KST 상승률 조건 통과: {total_filtered}개")
                print(f"   📊 상위 {actual_selected}개 선별 (최대 200개)")
                
                if actual_selected > 0:
                    avg_24h = sum(item[2] for item in top_200_symbols) / len(top_200_symbols)
                    print(f"   📊 평균 24h 상승률: {avg_24h:.2f}%")
                    
                    # KST 상승률이 있는 심볼들의 평균 표시
                    kst_positive_symbols = [item for item in top_200_symbols if len(item) > 4 and item[4] > 0]
                    if kst_positive_symbols:
                        avg_kst_change = sum(item[4] for item in kst_positive_symbols) / len(kst_positive_symbols)
                        print(f"   📊 평균 KST 상승률: {avg_kst_change:.2f}% ({len(kst_positive_symbols)}개 심볼)")
                    else:
                        print("   📊 KST 상승률 계산 성공한 심볼: 0개 (24h 데이터만 사용)")
                else:
                    print("   ⚠️ 조건을 만족하는 심볼이 없습니다")
                
                # 3단계: 4시간봉 시가대비고가 4%이상 필터링
                print("\n🔍 3단계: 4시간봉 급등 패턴 필터링 중...")
                pattern_filter_start = time.time()
                
                pattern_filtered = []
                for item in top_200_symbols:
                    symbol, ticker, change_24h, volume = item[:4]  # 처음 4개 값만 사용
                    try:
                        # 4시간봉 데이터 조회 (최근 4봉)
                        if self.ws_provider:
                            ohlcv_4h = self.ws_provider.get_ohlcv(symbol, '4h', 4)
                        else:
                            ohlcv_4h = self.exchange.fetch_ohlcv(symbol, '4h', limit=4)
                        
                        if not ohlcv_4h or len(ohlcv_4h) < 4:
                            continue
                            
                        # 조건1: 최근 4봉이내 시가대비고가 4%이상 1회이상 확인
                        surge_found = False
                        for candle in ohlcv_4h:
                            timestamp, open_price, high_price, low_price, close_price, volume = candle
                            
                            if open_price and open_price > 0:
                                surge_pct = ((high_price - open_price) / open_price) * 100
                                if surge_pct >= 4.0:
                                    surge_found = True
                                    break
                        
                        # 조건2: 4봉이전~0봉까지의 상승률 합계 > 0% 확인
                        total_gain = False
                        if len(ohlcv_4h) >= 4:
                            # 4봉 전 시가 (첫 번째 봉의 시가)
                            first_open = ohlcv_4h[0][1]
                            # 현재 봉 종가 (마지막 봉의 종가)
                            last_close = ohlcv_4h[-1][4]
                            
                            if first_open and first_open > 0 and last_close:
                                total_gain_pct = ((last_close - first_open) / first_open) * 100
                                if total_gain_pct > 0:
                                    total_gain = True
                        
                        # 두 조건 모두 만족해야 통과
                        if surge_found and total_gain:
                            pattern_filtered.append(symbol)
                            
                    except Exception:
                        # 개별 심볼 오류는 조용히 건너뛰기
                        continue
                
                filtered_symbols = pattern_filtered
                
                pattern_filter_elapsed = time.time() - pattern_filter_start
                filter_elapsed = time.time() - filter_start
                print(f"   ✅ 4시간봉 급등 패턴 필터링 완료: {len(filtered_symbols)}개 선별 ({pattern_filter_elapsed:.1f}초)")
                print(f"   📊 전체 필터링 소요시간: {filter_elapsed:.1f}초")
                
            except Exception as e:
                print(f"   ⚠️ 필터링 실패: {e}")
                filtered_symbols = usdt_futures[:100]
            
            # 3단계: 15분봉 초필살기 조건 스캔
            print(f"\n🔍 3단계: 15분봉 초필살기 조건 스캔 ({len(filtered_symbols)}개 심볼)")
            scan_stage_start = time.time()
            
            # 진행상황 추적 변수
            total_symbols = len(filtered_symbols)
            analyzed_count = 0
            entry_signals = []
            condition_stats = {
                'analyzed': 0,
                'data_insufficient': 0,
                'condition_1_fail': 0,
                'condition_2_fail': 0,
                'condition_3_fail': 0,
                'entry_fail': 0,
                'signals_found': 0
            }
            
            # 모든 분석 결과 수집용 리스트
            all_results = []
            entry_signals = []
            near_entry = []
            potential_entry = []
            watchlist = []
            
            # 병렬 분석 실행
            with ThreadPoolExecutor(max_workers=15) as executor:
                future_to_symbol = {
                    executor.submit(self.detailed_symbol_analysis, symbol): symbol 
                    for symbol in filtered_symbols
                }
                
                # 진행 상황 출력용 카운터
                progress_interval = max(1, total_symbols // 10)  # 10% 단위로 출력
                
                for i, future in enumerate(as_completed(future_to_symbol, timeout=90)):
                    symbol = future_to_symbol[future]
                    analyzed_count += 1
                    
                    try:
                        result = future.result(timeout=8)
                        
                        if result is None:
                            condition_stats['data_insufficient'] += 1
                            continue
                            
                        condition_stats['analyzed'] += 1
                        all_results.append(result)  # 모든 결과 저장
                        
                        # 결과 분류
                        status = result.get('status', 'watchlist')
                        if status == 'entry_signal':
                            entry_signals.append(result)
                            condition_stats['signals_found'] += 1
                            
                            clean_symbol = result['clean_symbol']
                            price = result['price']
                            print(f"   🚨 진입 신호 발견: {clean_symbol} @ ${price:,.4f}")
                            
                            # 텔레그램 알림
                            self.send_entry_signal_notification(result)
                        elif status == 'near_entry':
                            near_entry.append(result)
                        elif status == 'potential_entry':
                            potential_entry.append(result)
                        elif status == 'watchlist':
                            watchlist.append(result)
                        
                        # 조건별 통계 업데이트 (기존 유지)
                        if 'failure_reason' in result:
                            reason = result['failure_reason']
                            if 'condition_1' in reason:
                                condition_stats['condition_1_fail'] += 1
                            elif 'condition_2' in reason:
                                condition_stats['condition_2_fail'] += 1
                            elif 'condition_3' in reason:
                                condition_stats['condition_3_fail'] += 1
                            elif 'condition_4' in reason:
                                condition_stats['condition_4_fail'] = condition_stats.get('condition_4_fail', 0) + 1
                            elif 'entry' in reason:
                                condition_stats['entry_fail'] += 1
                        
                        # 진행률 출력 (10% 단위)
                        if analyzed_count % progress_interval == 0:
                            progress_pct = (analyzed_count / total_symbols) * 100
                            signals_so_far = len(entry_signals)
                            print(f"   📊 진행률: {progress_pct:.0f}% ({analyzed_count}/{total_symbols}) - 신호: {signals_so_far}개")
                            
                    except Exception as e:
                        # 개별 심볼 분석 실패는 조용히 처리
                        condition_stats['data_insufficient'] += 1
            
            # 4단계: 스캔 결과 요약
            scan_elapsed = time.time() - scan_stage_start
            total_elapsed = time.time() - scan_start
            
            print(f"\n📊 4단계: 15분봉 초필살기 스캔 결과 요약")
            print(f"{'─'*60}")
            print(f"   📈 분석 대상: {total_symbols}개 심볼")
            print(f"   ✅ 분석 완료: {condition_stats['analyzed']}개")
            print(f"   ❌ 데이터 부족: {condition_stats['data_insufficient']}개")
            print(f"   🚨 진입 신호: {len(entry_signals)}개")
            print(f"   ⏱️ 스캔 소요시간: {scan_elapsed:.1f}초")
            print(f"   ⚡ 전체 소요시간: {total_elapsed:.1f}초")
            print(f"   🔥 분석 속도: {total_symbols/total_elapsed:.1f} 심볼/초")
            
            
            # 새로운 출력 형식 (one_minute_surge_entry_strategy.py 스타일)
            print(f"\n🚀 15분봉 A전략(바닥타점) + B전략(급등초입) 스캔 결과")
            print(f"{'='*60}")
            
            # 1. 진입신호 (모든 조건 충족)
            if entry_signals:
                print(f"\n🔥 진입신호 [15분봉 바닥타점+급등초입] (모든 조건 충족)")
                for result in entry_signals:
                    clean_symbol = result['symbol'].replace('/USDT:USDT', '')
                    price = result['price']
                    print(f"   🎯 \033[93m{clean_symbol}\033[0m @ ${price:,.4f}")
            else:
                print(f"\n🔥 진입신호 [15분봉 바닥타점+급등초입] (모든 조건 충족)")
                print("   없음")
            
            # 2. 진입임박 (1개 조건 미충족)
            if near_entry:
                print(f"\n⚡ 진입임박 [15분봉 바닥타점+급등초입] (1개 조건 미충족)")
                for result in near_entry:
                    clean_symbol = result['symbol'].replace('/USDT:USDT', '')
                    price = result['price']
                    failed_conds = result.get('failed_conditions', [])
                    print(f"   ⏰ \033[93m{clean_symbol}\033[0m @ ${price:,.4f}")
                    for failed_cond in failed_conds:
                        print(f"      \033[91m❌ {failed_cond}\033[0m")
            else:
                print(f"\n⚡ 진입임박 [15분봉 바닥타점+급등초입] (1개 조건 미충족)")
                print("   없음")
            
            # 3. 진입확률 (2개 조건 미충족) - 가로 정렬
            print(f"\n📈 진입확률 [15분봉 바닥타점+급등초입] (2개 조건 미충족)")
            if potential_entry:
                # 심볼명만 가로 정렬 (노란색 적용)
                symbols = []
                for result in potential_entry:
                    clean_symbol = result['symbol'].replace('/USDT:USDT', '')
                    symbols.append(f"\033[93m{clean_symbol}\033[0m")
                
                # 5개씩 가로 정렬
                batch_size = 5
                for i in range(0, len(symbols), batch_size):
                    batch = symbols[i:i+batch_size]
                    print(f"   {' | '.join(batch)}")
            else:
                print("   없음")
            
            # 4. 관심종목 (3개 이상 조건 미충족) - 가로 정렬
            print(f"\n👀 관심종목 [15분봉 바닥타점+급등초입] (3개 이상 조건 미충족)")
            if watchlist:
                # 심볼명만 가로 정렬
                symbols = []
                for result in watchlist:
                    clean_symbol = result['symbol'].replace('/USDT:USDT', '')
                    symbols.append(clean_symbol)
                
                # 6개씩 가로 정렬
                batch_size = 6
                for i in range(0, len(symbols), batch_size):
                    batch = symbols[i:i+batch_size]
                    print(f"   {' | '.join(batch)}")
            else:
                print("   없음")
            
            # 5. 통계 정보
            total_analyzed = len(all_results)
            if total_analyzed > 0:
                print(f"\n📊 스캔 통계")
                print(f"{'─'*40}")
                print(f"   📈 분석 완료: {total_analyzed}개")
                print(f"   🔥 진입신호: {len(entry_signals)}개")
                print(f"   ⚡ 진입임박: {len(near_entry)}개")
                print(f"   📈 진입확률: {len(potential_entry)}개")
                print(f"   👀 관심종목: {len(watchlist)}개")
                print(f"   📊 신호발견율: {(len(entry_signals)/total_analyzed*100):.1f}%")
            
            print(f"{'='*60}")
            return entry_signals
            
        except Exception as e:
            self.logger.error(f"상세 스캔 실패: {e}")
            return []
    
    def scan_symbols_optimized(self, api_call_tracker):
        """🚀 최고속도 최적화된 심볼 스캔 (IP 밴 방지)"""
        try:
            scan_start = time.time()
            print(f"\n🚀 최적화 15분봉 초필살기 스캔 시작")
            print(f"{'='*60}")
            
            # 1단계: 캐시된 마켓 데이터 사용 (API 호출 최소화)
            print("📋 1단계: 고속 마켓 데이터 로드...")
            if not hasattr(self, '_cached_futures_symbols') or \
               not hasattr(self, '_cache_time') or \
               time.time() - self._cache_time > 300:  # 5분마다 캐시 갱신
                
                # 마켓 데이터 캐시 갱신
                try:
                    markets = self.exchange.load_markets()
                    self._cached_futures_symbols = [
                        symbol for symbol, market in markets.items()
                        if symbol.endswith('/USDT:USDT') and market.get('active', False)
                    ]
                    self._cache_time = time.time()
                    api_call_tracker['calls_in_minute'] += 1
                    print(f"   🔄 마켓 데이터 캐시 갱신: {len(self._cached_futures_symbols)}개 심볼")
                except Exception as e:
                    print(f"   ⚠️ 마켓 데이터 로드 실패: {e}")
                    return []
            else:
                print(f"   ⚡ 캐시된 마켓 데이터 사용: {len(self._cached_futures_symbols)}개 심볼")
            
            # 2단계: 스마트 티커 배치 조회 (최적화)
            print("\n📈 2단계: 고속 티커 배치 조회...")
            batch_start = time.time()
            
            try:
                # 단일 배치 호출로 모든 티커 정보 가져오기
                tickers = self.exchange.fetch_tickers()
                api_call_tracker['calls_in_minute'] += 1
                batch_elapsed = time.time() - batch_start
                print(f"   ⚡ 배치 티커 조회 완료: {len(tickers)}개 ({batch_elapsed:.1f}초)")
            except Exception as e:
                print(f"   ❌ 배치 티커 조회 실패: {e}")
                return []
            
            # 3단계: 스마트 필터링 (메모리 기반)
            print("\n🔍 3단계: 고속 필터링 및 선별...")
            
            # 거래량 상위 심볼 선별 (API 호출 없이 메모리 처리)
            volume_threshold = 1000000  # 100만 달러
            filtered_symbols = []
            
            for symbol in self._cached_futures_symbols:
                if symbol in tickers:
                    ticker = tickers[symbol]
                    volume_24h = ticker.get('quoteVolume', 0) or 0
                    change_24h = ticker.get('percentage', 0) or 0
                    
                    # 기본 필터링: 거래량 + 상승률
                    if volume_24h >= volume_threshold and change_24h > 0:
                        filtered_symbols.append((symbol, ticker, change_24h, volume_24h))
            
            # 상승률 기준 정렬 및 상위 100개 선별
            filtered_symbols.sort(key=lambda x: x[2], reverse=True)
            top_symbols = filtered_symbols[:100]
            
            print(f"   ✅ 거래량+상승률 필터링: {len(filtered_symbols)}개 → {len(top_symbols)}개 선별")
            
            # 4단계: 병렬 조건 분석 (스마트 배치)
            print(f"\n🔥 4단계: 최고속도 병렬 조건 분석 (상위 {len(top_symbols)}개)...")
            analysis_start = time.time()
            
            entry_signals = []
            near_entry = []
            potential_entry = []
            watchlist = []
            all_results = []
            
            # 스마트 병렬 처리 (API 호출 최적화)
            max_workers = min(8, len(top_symbols))
            if max_workers > 0:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # 분석 태스크 생성
                    analysis_tasks = {}
                    
                    for symbol, ticker, change_24h, volume in top_symbols:
                        if api_call_tracker['calls_in_minute'] >= api_call_tracker['max_calls_per_minute'] - 50:
                            print(f"   ⚠️ API 호출 제한 임박 ({api_call_tracker['calls_in_minute']}/{api_call_tracker['max_calls_per_minute']}) - 분석 중단")
                            break
                            
                        future = executor.submit(self._optimized_symbol_analysis, symbol, ticker, api_call_tracker)
                        analysis_tasks[future] = symbol
                    
                    # 결과 수집
                    completed_count = 0
                    total_tasks = len(analysis_tasks)
                    
                    for future in as_completed(analysis_tasks):
                        try:
                            result = future.result(timeout=10)  # 10초 타임아웃
                            if result and result.get('analyzed'):
                                all_results.append(result)
                                
                                # 상태별 분류
                                status = result.get('status')
                                if status == 'entry_signal':
                                    entry_signals.append(result)
                                elif status == 'near_entry':
                                    near_entry.append(result)
                                elif status == 'potential_entry':
                                    potential_entry.append(result)
                                elif status == 'watchlist':
                                    watchlist.append(result)
                                
                                completed_count += 1
                                
                                # 진행률 출력 (25% 단위)
                                if total_tasks > 0 and completed_count % max(1, total_tasks // 4) == 0:
                                    progress_pct = (completed_count / total_tasks) * 100
                                    print(f"   📊 분석 진행: {progress_pct:.0f}% ({completed_count}/{total_tasks}) - 신호: {len(entry_signals)}개")
                        
                        except Exception as e:
                            # 개별 분석 실패는 조용히 처리
                            continue
            
            # 5단계: 결과 출력
            analysis_elapsed = time.time() - analysis_start
            total_elapsed = time.time() - scan_start
            
            print(f"\n⚡ 최고속도 스캔 완료!")
            print(f"{'─'*60}")
            print(f"   📈 대상 심볼: {len(top_symbols)}개")
            print(f"   ✅ 분석 완료: {len(all_results)}개")
            print(f"   🚨 진입 신호: {len(entry_signals)}개")
            print(f"   ⚡ 분석 시간: {analysis_elapsed:.1f}초")
            print(f"   🔥 전체 시간: {total_elapsed:.1f}초")
            print(f"   📊 분석 속도: {len(all_results)/total_elapsed:.1f} 심볼/초")
            print(f"   🛡️ API 호출: {api_call_tracker['calls_in_minute']}/{api_call_tracker['max_calls_per_minute']}")
            
            # 새로운 출력 형식 (one_minute_surge_entry_strategy.py 스타일)
            print(f"\n🚀 15분봉 A전략(바닥타점) + B전략(급등초입) 스캔 결과")
            print(f"{'='*60}")
            
            # 1. 진입신호 (모든 조건 충족)
            if entry_signals:
                print(f"\n🔥 진입신호 [15분봉 바닥타점+급등초입] (모든 조건 충족)")
                for result in entry_signals:
                    clean_symbol = result['symbol'].replace('/USDT:USDT', '')
                    price = result['price']
                    print(f"   🎯 \033[93m{clean_symbol}\033[0m @ ${price:,.4f}")
            else:
                print(f"\n🔥 진입신호 [15분봉 바닥타점+급등초입] (모든 조건 충족)")
                print("   없음")
            
            # 2. 진입임박 (1개 조건 미충족)
            if near_entry:
                print(f"\n⚡ 진입임박 [15분봉 바닥타점+급등초입] (1개 조건 미충족)")
                for result in near_entry:
                    clean_symbol = result['symbol'].replace('/USDT:USDT', '')
                    price = result['price']
                    failed_conds = result.get('failed_conditions', [])
                    print(f"   ⏰ \033[93m{clean_symbol}\033[0m @ ${price:,.4f}")
                    for failed_cond in failed_conds:
                        print(f"      \033[91m❌ {failed_cond}\033[0m")
            else:
                print(f"\n⚡ 진입임박 [15분봉 바닥타점+급등초입] (1개 조건 미충족)")
                print("   없음")
            
            # 3. 진입확률 (2개 조건 미충족) - 가로 정렬
            print(f"\n📈 진입확률 [15분봉 바닥타점+급등초입] (2개 조건 미충족)")
            if potential_entry:
                # 심볼명만 가로 정렬 (노란색 적용)
                symbols = []
                for result in potential_entry:
                    clean_symbol = result['symbol'].replace('/USDT:USDT', '')
                    symbols.append(f"\033[93m{clean_symbol}\033[0m")
                
                batch_size = 5
                for i in range(0, len(symbols), batch_size):
                    batch = symbols[i:i+batch_size]
                    print(f"   {' | '.join(batch)}")
            else:
                print("   없음")
            
            # 4. 관심종목 (3개 이상 조건 미충족) - 가로 정렬
            print(f"\n👀 관심종목 [15분봉 바닥타점+급등초입] (3개 이상 조건 미충족)")
            if watchlist:
                symbols = [result['symbol'].replace('/USDT:USDT', '') for result in watchlist]
                batch_size = 6
                for i in range(0, len(symbols), batch_size):
                    batch = symbols[i:i+batch_size]
                    print(f"   {' | '.join(batch)}")
            else:
                print("   없음")
            
            # 5. 통계 정보
            total_analyzed = len(all_results)
            if total_analyzed > 0:
                print(f"\n📊 최고속도 스캔 통계")
                print(f"{'─'*40}")
                print(f"   📈 분석 완료: {total_analyzed}개")
                print(f"   🔥 진입신호: {len(entry_signals)}개")
                print(f"   ⚡ 진입임박: {len(near_entry)}개")
                print(f"   📈 진입확률: {len(potential_entry)}개")
                print(f"   👀 관심종목: {len(watchlist)}개")
                print(f"   📊 신호발견율: {(len(entry_signals)/total_analyzed*100):.1f}%")
                print(f"   🚀 처리속도: {total_analyzed/total_elapsed:.1f} 심볼/초")
            
            print(f"{'='*60}")
            return entry_signals
            
        except Exception as e:
            self.logger.error(f"최적화 스캔 실패: {e}")
            print(f"❌ 최적화 스캔 실패: {e}")
            return []
    
    def _optimized_symbol_analysis(self, symbol, ticker, api_call_tracker):
        """최적화된 개별 심볼 분석 (API 호출 최소화)"""
        try:
            clean_symbol = symbol.replace('/USDT:USDT', '')
            
            # API 호출 제한 체크
            if api_call_tracker['calls_in_minute'] >= api_call_tracker['max_calls_per_minute'] - 10:
                return None
            
            # 기존 포지션 확인
            if symbol in self.active_positions:
                return None
            
            # 현재가 정보 (티커에서 직접 사용)
            current_price = ticker.get('last') or ticker.get('close')
            if not current_price or current_price <= 0:
                return None
            
            # 15분봉 데이터 조회 (WebSocket 우선, 단일 API 호출)
            df_15m = None
            
            # WebSocket 데이터 시도 (API 호출 없음)
            if self.ws_provider:
                try:
                    df_15m = self.ws_provider.get_ohlcv_dataframe(symbol, '15m', limit=500)
                except:
                    pass
            
            # 폴백: REST API (필요시에만)
            if df_15m is None or len(df_15m) < 100:
                try:
                    df_15m = self.get_ohlcv_data(symbol, '15m', limit=500)
                    api_call_tracker['calls_in_minute'] += 1
                    if df_15m is None or len(df_15m) < 100:
                        return None
                except:
                    return None
            
            # 15분봉 초필살기 조건 체크
            is_signal, conditions = self.check_fifteen_minute_mega_conditions(symbol, df_15m)
            
            # 결과 객체 생성
            result = {
                'symbol': symbol,
                'clean_symbol': clean_symbol,
                'price': current_price,
                'timestamp': get_korea_time().strftime('%Y-%m-%d %H:%M:%S'),
                'conditions': conditions,
                'analyzed': True
            }
            
            if is_signal:
                result['status'] = 'entry_signal'
                return result
            else:
                # 조건별 통과 여부 확인 및 분류
                passed_conditions = 0
                failed_conditions = []
                
                for condition in conditions:
                    if '[15분봉 조건1]' in condition:
                        if 'True' in condition:
                            passed_conditions += 1
                        else:
                            failed_conditions.append("조건1(MA80-MA480 골든크로스)")
                    elif '[15분봉 조건2]' in condition:
                        if 'True' in condition:
                            passed_conditions += 1
                        else:
                            failed_conditions.append("조건2(BB 골든크로스)")
                    elif '[15분봉 조건3]' in condition:
                        if 'True' in condition:
                            passed_conditions += 1
                        else:
                            failed_conditions.append("조건3(MA5-MA20 골든크로스)")
                    elif '[15분봉 조건4]' in condition:
                        if 'True' in condition:
                            passed_conditions += 1
                        else:
                            failed_conditions.append("조건4(BB200상단-MA480 돌파)")
                
                # 미충족 조건 개수 계산
                failed_count = 4 - passed_conditions
                
                # 상태 분류
                if failed_count == 0:
                    result['status'] = 'entry_signal'  # 모든 조건 통과 (진입신호)
                elif failed_count == 1:
                    result['status'] = 'near_entry'    # 1개 미충족 (진입임박)
                elif failed_count == 2:
                    result['status'] = 'potential_entry'  # 2개 미충족 (진입확률)
                else:
                    result['status'] = 'watchlist'     # 3개 이상 미충족 (관심종목)
                
                # 추가 정보
                result['passed_conditions'] = passed_conditions
                result['failed_count'] = failed_count
                result['failed_conditions'] = failed_conditions
                
                return result
                
        except Exception as e:
            # 개별 심볼 분석 실패는 조용히 처리
            return None
    
    def _detailed_fallback_scan(self):
        """상세 폴백 스캔 (API 키 문제시)"""
        print("\n🧪 가상 데이터 스캔 모드 (API 키 문제)")
        print(f"{'─'*60}")
        
        # 가상 스캔 시뮬레이션
        import random
        signals = []
        
        print("📋 1단계: 가상 마켓 데이터 로드...")
        print("   📊 가상 USDT 선물: 150개")
        
        print("\n📈 2단계: 가상 거래량 필터링...")
        print("   ✅ 거래량 필터링 완료: 150개 선별 (0.1초)")
        
        print("\n🔍 3단계: 가상 15분봉 초필살기 스캔...")
        
        # 20% 확률로 더미 진입 신호 생성
        if random.random() < 0.20:
            # 동적 심볼 로드
            try:
                # 실제 거래소에서 심볼 목록 가져오기 (퍼블릭 API)
                import ccxt
                public_exchange = ccxt.binance({'enableRateLimit': True})
                markets = public_exchange.load_markets()
                
                # USDT 선물 심볼 필터링 (상위 거래량 기준)
                usdt_futures = [symbol for symbol, market in markets.items() 
                              if symbol.endswith('/USDT:USDT') and market.get('active', False)]
                
                # 상위 거래량 심볼 선별 (최대 50개)
                dummy_symbols = usdt_futures[:50] if usdt_futures else []
                
                print(f"   📊 동적 로드된 심볼: {len(dummy_symbols)}개")
                
            except Exception as e:
                print(f"   ⚠️ 동적 심볼 로드 실패: {e}")
                # 폴백: 최소한의 주요 심볼
                dummy_symbols = [
                    'BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', 'BNB/USDT:USDT',
                    'XRP/USDT:USDT', 'ADA/USDT:USDT', 'DOGE/USDT:USDT', 'MATIC/USDT:USDT'
                ]
            
            # 1-2개 신호 생성
            num_signals = random.randint(1, 2)
            selected_symbols = random.sample(dummy_symbols, min(num_signals, len(dummy_symbols)))
            
            for dummy_symbol in selected_symbols:
                # 동적 현재가 조회 시도
                dummy_price = None
                try:
                    # 실제 현재가 조회
                    ticker = public_exchange.fetch_ticker(dummy_symbol)
                    dummy_price = ticker.get('last') or ticker.get('close')
                    print(f"   📊 실시간 가격 조회: {dummy_symbol.replace('/USDT:USDT', '')} @ ${dummy_price:,.4f}")
                except:
                    # 폴백: 심볼별 현실적 가격 범위
                    if 'BTC' in dummy_symbol:
                        dummy_price = random.uniform(60000, 100000)
                    elif 'ETH' in dummy_symbol:
                        dummy_price = random.uniform(2000, 4000)
                    elif 'SOL' in dummy_symbol:
                        dummy_price = random.uniform(100, 300)
                    elif 'BNB' in dummy_symbol:
                        dummy_price = random.uniform(200, 600)
                    elif 'XRP' in dummy_symbol:
                        dummy_price = random.uniform(0.5, 2.0)
                    else:
                        dummy_price = random.uniform(0.1, 100)
                
                if dummy_price is None or dummy_price <= 0:
                    dummy_price = random.uniform(1, 100)
                
                clean_symbol = dummy_symbol.replace(':USDT', '').replace('/USDT', '')
                
                signal_data = {
                    'symbol': dummy_symbol,
                    'clean_symbol': clean_symbol,
                    'price': dummy_price,
                    'timestamp': get_korea_time().strftime('%Y-%m-%d %H:%M:%S'),
                    'status': 'entry_signal',
                    'conditions': ['[가상] 15분봉 초필살기 테스트 신호']
                }
                
                signals.append(signal_data)
                print(f"   🧪 가상 진입 신호: {clean_symbol} @ ${dummy_price:,.4f}")
                
                # 텔레그램 알림
                self.send_entry_signal_notification(signal_data)
        
        # 동적 가상 통계 출력
        total_analyzed = len(dummy_symbols) if 'dummy_symbols' in locals() else 150
        print(f"\n📊 4단계: 가상 스캔 결과 요약")
        print(f"{'─'*60}")
        print(f"   📈 분석 대상: {total_analyzed}개 심볼 (동적 로드)")
        print(f"   ✅ 분석 완료: {total_analyzed}개")
        print(f"   ❌ 데이터 부족: 0개")
        print(f"   🚨 진입 신호: {len(signals)}개")
        print(f"   ⏱️ 스캔 소요시간: 0.5초 (가상)")
        print(f"   ⚡ 전체 소요시간: 0.5초 (가상)")
        print(f"   🔥 분석 속도: {total_analyzed * 2} 심볼/초 (가상)")
        print(f"   ⚠️ 주의: 가상 데이터로 생성된 신호입니다")
        print(f"{'─'*60}")
        
        return signals
    
    def detailed_symbol_analysis(self, symbol):
        """상세 개별 심볼 분석 (통계 포함)"""
        try:
            clean_symbol = symbol.replace('/USDT:USDT', '')
            
            # 포지션 중복 체크
            if symbol in self.active_positions:
                return None
            
            # 15분봉 데이터 조회 (WebSocket 우선, REST 폴백)
            df_15m = None
            current_price = None
            
            # WebSocket 데이터 시도
            if self.ws_provider:
                try:
                    df_15m = self.ws_provider.get_ohlcv_dataframe(symbol, '15m', limit=500)
                    if df_15m is not None and len(df_15m) > 0:
                        current_price = df_15m['close'].iloc[-1]
                except:
                    pass
            
            # 폴백: REST API
            if df_15m is None:
                df_15m = self.get_ohlcv_data(symbol, '15m', limit=500)
                if df_15m is None or len(df_15m) < 100:
                    return None
            
            # 현재가 확보
            if current_price is None:
                try:
                    ticker = self.exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
                except:
                    if df_15m is not None and len(df_15m) > 0:
                        current_price = df_15m['close'].iloc[-1]
                    else:
                        return None
            
            # 15분봉 초필살기 조건 체크
            is_signal, conditions = self.check_fifteen_minute_mega_conditions(symbol, df_15m)
            
            # 결과 객체 생성
            result = {
                'symbol': symbol,
                'clean_symbol': clean_symbol,
                'price': current_price,
                'timestamp': get_korea_time().strftime('%Y-%m-%d %H:%M:%S'),
                'conditions': conditions,
                'analyzed': True
            }
            
            if is_signal:
                result['status'] = 'entry_signal'
                return result
            else:
                # 조건별 통과 여부 확인 및 분류
                passed_conditions = 0
                failed_conditions = []
                
                for condition in conditions:
                    if '[15분봉 조건1]' in condition:
                        if 'True' in condition:
                            passed_conditions += 1
                        else:
                            failed_conditions.append("조건1(MA80-MA480 골든크로스)")
                    elif '[15분봉 조건2]' in condition:
                        if 'True' in condition:
                            passed_conditions += 1
                        else:
                            failed_conditions.append("조건2(BB 골든크로스)")
                    elif '[15분봉 조건3]' in condition:
                        if 'True' in condition:
                            passed_conditions += 1
                        else:
                            failed_conditions.append("조건3(MA5-MA20 골든크로스)")
                    elif '[15분봉 조건4]' in condition:
                        if 'True' in condition:
                            passed_conditions += 1
                        else:
                            failed_conditions.append("조건4(BB200상단-MA480 돌파)")
                
                # 미충족 조건 개수 계산
                failed_count = 4 - passed_conditions
                
                # 상태 분류
                if failed_count == 0:
                    result['status'] = 'entry_signal'  # 모든 조건 통과 (진입신호)
                elif failed_count == 1:
                    result['status'] = 'near_entry'    # 1개 미충족 (진입임박)
                elif failed_count == 2:
                    result['status'] = 'potential_entry'  # 2개 미충족 (진입확률)
                else:
                    result['status'] = 'watchlist'     # 3개 이상 미충족 (관심종목)
                
                # 추가 정보
                result['passed_conditions'] = passed_conditions
                result['failed_count'] = failed_count
                result['failed_conditions'] = failed_conditions
                
                # 기존 실패 이유 분석도 유지
                failure_reason = 'unknown'
                for condition in conditions:
                    if '[15분봉 조건1]' in condition and 'False' in condition:
                        failure_reason = 'condition_1_fail'
                        break
                    elif '[15분봉 조건2]' in condition and 'False' in condition:
                        failure_reason = 'condition_2_fail'
                        break
                    elif '[15분봉 조건3]' in condition and 'False' in condition:
                        failure_reason = 'condition_3_fail'
                        break
                    elif '[15분봉 조건4]' in condition and 'False' in condition:
                        failure_reason = 'condition_4_fail'
                        break
                    elif '[15분봉 최종]' in condition and 'False' in condition:
                        failure_reason = 'entry_fail'
                        break
                
                result['failure_reason'] = failure_reason
                return result
            
        except Exception as e:
            self.logger.debug(f"[{symbol}] 상세 분석 실패: {e}")
            return None
    
    def analyze_symbol_fast(self, symbol):
        """최적화된 개별 심볼 분석"""
        try:
            clean_symbol = symbol.replace('/USDT:USDT', '')
            
            # 포지션 중복 체크
            if symbol in self.active_positions:
                return None
            
            # WebSocket 우선 시도, 실패시 REST API 폴백
            df_15m = None
            current_price = None
            
            # WebSocket 데이터 시도
            if self.ws_provider:
                try:
                    df_15m = self.ws_provider.get_ohlcv_dataframe(symbol, '15m', limit=500)
                    # WebSocket에서 현재가 가져오기 시도
                    if df_15m is not None and len(df_15m) > 0:
                        current_price = df_15m['close'].iloc[-1]
                except:
                    pass
            
            # 폴백: REST API
            if df_15m is None:
                df_15m = self.get_ohlcv_data(symbol, '15m', limit=500)
                if df_15m is None or len(df_15m) < 100:
                    return None
            
            if current_price is None:
                try:
                    ticker = self.exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
                except:
                    if df_15m is not None and len(df_15m) > 0:
                        current_price = df_15m['close'].iloc[-1]
                    else:
                        return None
            
            # 15분봉 초필살기 조건 체크
            is_signal, conditions = self.check_fifteen_minute_mega_conditions(symbol, df_15m)
            
            if is_signal:
                return {
                    'symbol': symbol,
                    'clean_symbol': clean_symbol,
                    'price': current_price,
                    'timestamp': get_korea_time().strftime('%Y-%m-%d %H:%M:%S'),
                    'conditions': conditions,
                    'status': 'entry_signal'
                }
            
            return None
            
        except Exception as e:
            self.logger.debug(f"[{symbol}] 고속 분석 실패: {e}")
            return None
    
    def analyze_symbol(self, symbol):
        """개별 심볼 분석"""
        try:
            clean_symbol = symbol.replace('/USDT:USDT', '')
            
            # 포지션 중복 체크
            if symbol in self.active_positions:
                return None
            
            # 15분봉 데이터 조회
            df_15m = self.get_ohlcv_data(symbol, '15m', limit=500)
            if df_15m is None or len(df_15m) < 100:
                return None
            
            # 15분봉 초필살기 조건 체크
            is_signal, conditions = self.check_fifteen_minute_mega_conditions(symbol, df_15m)
            
            if is_signal:
                # 현재가 조회
                current_price = df_15m.iloc[-1]['close']
                current_time = get_korea_time().strftime('%H:%M:%S')
                
                return {
                    'symbol': symbol,
                    'clean_symbol': clean_symbol,
                    'status': 'entry_signal',
                    'strategy_type': '15분봉 초필살기 전략',
                    'price': current_price,
                    'timestamp': current_time,
                    'conditions': conditions
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"{symbol} 분석 실패: {e}")
            return None
    
    def send_entry_signal_notification(self, signal_data):
        """진입 신호 텔레그램 알림"""
        if not self.telegram_bot:
            return
        
        try:
            symbol = signal_data['clean_symbol']
            price = signal_data['price']
            timestamp = signal_data['timestamp']
            
            message = f"""🚨 15분봉 바닥타점+급등초입 진입 신호 🚨
━━━━━━━━━━━━━━━━━━━━━━
📈 심볼: {symbol}
💰 현재가: ${price:,.4f}
⏰ 신호발생: {timestamp}
━━━━━━━━━━━━━━━━━━━━━━
🎯 전략: 15분봉 A전략(바닥타점) + B전략(급등초입)
🔥 레버리지: 20배
💡 진입설정:
   • 포지션: 1% 상당 (20% 노출)
   • 1차 DCA: -3% (20% 노출)
   • 2차 DCA: -6% (20% 노출)
   • 손절: -10% (시드 6% 손실)
"""
            
            self.telegram_bot.send_message(message)
            
        except Exception as e:
            self.logger.error(f"텔레그램 알림 실패: {e}")
    
    def execute_trade(self, signal_data):
        """실전매매 거래 실행"""
        try:
            if not self.private_exchange:
                print(f"⚠️ 프라이빗 API 없음 - {signal_data['clean_symbol']} 거래 건너뛰기")
                return False
                
            symbol = signal_data['symbol']
            price = signal_data['price']
            clean_symbol = signal_data['clean_symbol']
            
            # 포지션 개수 제한 체크 (최대 10개)
            portfolio = self.get_portfolio_summary()
            if portfolio['open_positions'] >= 10:
                print(f"⚠️ 최대 포지션 개수 도달 (10개) - {clean_symbol} 진입 건너뛰기")
                return False
            
            # 중복 포지션 체크
            if symbol in self.active_positions:
                print(f"⚠️ 이미 포지션 보유 중 - {clean_symbol} 진입 건너뛰기")
                return False
            
            # 잔고 조회
            balance = self.private_exchange.fetch_balance()
            free_usdt = balance['USDT']['free']
            
            # 포지션 크기 계산 (1% x 20배 레버리지)
            position_value = free_usdt * 0.01  # 1%
            leverage = 20
            quantity = (position_value * leverage) / price  # 실제 구매할 수량
            
            if free_usdt < position_value:
                print(f"⚠️ 잔고 부족 - 필요: ${position_value:.0f}, 보유: ${free_usdt:.0f}")
                return False
            
            # 레버리지 설정
            try:
                self.private_exchange.set_leverage(leverage, symbol)
                print(f"✅ 레버리지 {leverage}배 설정 완료: {clean_symbol}")
            except Exception as e:
                print(f"⚠️ 레버리지 설정 실패: {e}")
            
            # 시장가 매수 주문
            order = self.private_exchange.create_market_buy_order(
                symbol=symbol,
                amount=quantity,
                params={'leverage': leverage}
            )
            
            if order['status'] == 'closed' or order['filled'] > 0:
                filled_qty = order['filled']
                filled_price = order['average'] or price
                
                # active_positions에 추가
                self.active_positions[symbol] = {
                    'size': filled_qty,
                    'side': 'long',
                    'entry_price': filled_price,
                    'leverage': leverage,
                    'order_id': order['id']
                }
                
                print(f"✅ 실전 진입 완료: {clean_symbol}")
                print(f"   💰 진입가: ${filled_price:,.4f}")
                print(f"   📊 수량: {filled_qty:.6f}")
                print(f"   🔥 레버리지: {leverage}배")
                print(f"   💵 투입금액: ${position_value:.0f} USDT")
                print(f"   📋 주문ID: {order['id']}")
                
                # DCA 주문 등록
                self._place_dca_orders(symbol, filled_price, quantity)
                
                # 텔레그램 알림
                if self.telegram_bot:
                    portfolio = self.get_portfolio_summary()
                    message = f"""🔥 실전 진입 완료 🔥
━━━━━━━━━━━━━━━━━━━━━━
📈 심볼: {clean_symbol}
💰 진입가: ${filled_price:,.4f}
📊 수량: {filled_qty:.6f}
🔥 레버리지: {leverage}배
💵 투입금액: ${position_value:.0f} USDT
📋 주문ID: {order['id']}
━━━━━━━━━━━━━━━━━━━━━━
📊 포트폴리오 현황:
   • 잔고: ${portfolio['free_balance']:.0f} USDT
   • 포지션수: {portfolio['open_positions']}개
   • 총 PnL: ${portfolio['total_unrealized_pnl']:+.0f} USDT
━━━━━━━━━━━━━━━━━━━━━━
🎯 자동 DCA 설정:
   • 1차: ${filled_price * 0.97:,.4f} (-3%)
   • 2차: ${filled_price * 0.94:,.4f} (-6%)
   • 손절: ${filled_price * 0.90:,.4f} (-10%)
⚠️ 실제 거래 - 리스크 관리 필수!"""
                    self.telegram_bot.send_message(message)
                
                return True
            else:
                print(f"❌ 주문 실패: {clean_symbol} - {order.get('info', '')}")
                return False
            
        except Exception as e:
            self.logger.error(f"실전 거래 실행 실패: {e}")
            print(f"❌ 거래 실행 실패: {clean_symbol} - {e}")
            return False
    
    def _place_dca_orders(self, symbol, entry_price, base_quantity):
        """DCA 주문 등록 (-3%, -6%)"""
        try:
            clean_symbol = symbol.replace('/USDT:USDT', '')
            dca_orders = []
            
            # 1차 DCA: -3% 가격에 1% 추가 매수
            dca1_price = entry_price * 0.97
            balance = self.private_exchange.fetch_balance()
            free_usdt = balance['USDT']['free']
            dca1_value = free_usdt * 0.01  # 1%
            dca1_quantity = (dca1_value * 20) / dca1_price  # 20배 레버리지
            
            if free_usdt >= dca1_value:
                try:
                    dca1_order = self.exchange.create_limit_buy_order(
                        symbol=symbol,
                        amount=dca1_quantity,
                        price=dca1_price,
                        params={'leverage': 20}
                    )
                    dca_orders.append({
                        'stage': '1차_DCA',
                        'price': dca1_price,
                        'quantity': dca1_quantity,
                        'order_id': dca1_order['id']
                    })
                    print(f"   📋 1차 DCA 주문 등록: ${dca1_price:,.4f} ({dca1_quantity:.6f})")
                except Exception as e:
                    print(f"   ⚠️ 1차 DCA 주문 실패: {e}")
            
            # 2차 DCA: -6% 가격에 1% 추가 매수
            dca2_price = entry_price * 0.94
            dca2_value = free_usdt * 0.01  # 1%
            dca2_quantity = (dca2_value * 20) / dca2_price  # 20배 레버리지
            
            if free_usdt >= dca2_value:
                try:
                    dca2_order = self.exchange.create_limit_buy_order(
                        symbol=symbol,
                        amount=dca2_quantity,
                        price=dca2_price,
                        params={'leverage': 20}
                    )
                    dca_orders.append({
                        'stage': '2차_DCA',
                        'price': dca2_price,
                        'quantity': dca2_quantity,
                        'order_id': dca2_order['id']
                    })
                    print(f"   📋 2차 DCA 주문 등록: ${dca2_price:,.4f} ({dca2_quantity:.6f})")
                except Exception as e:
                    print(f"   ⚠️ 2차 DCA 주문 실패: {e}")
            
            # 손절 주문: -10%
            stop_price = entry_price * 0.90
            try:
                stop_order = self.exchange.create_order(
                    symbol=symbol,
                    type='stop_market',
                    side='sell',
                    amount=base_quantity,  # 기본 포지션만 손절
                    price=None,
                    params={
                        'stopPrice': stop_price,
                        'leverage': 20
                    }
                )
                dca_orders.append({
                    'stage': '손절',
                    'price': stop_price,
                    'quantity': base_quantity,
                    'order_id': stop_order['id']
                })
                print(f"   🛑 손절 주문 등록: ${stop_price:,.4f}")
            except Exception as e:
                print(f"   ⚠️ 손절 주문 실패: {e}")
            
            # DCA 주문 정보를 active_positions에 저장
            if symbol in self.active_positions:
                self.active_positions[symbol]['dca_orders'] = dca_orders
            
            return dca_orders
            
        except Exception as e:
            self.logger.error(f"DCA 주문 등록 실패: {e}")
            print(f"❌ DCA 주문 등록 실패: {e}")
            return []
    
    def get_total_balance(self):
        """총 잔고 조회"""
        try:
            if not self.private_exchange:
                return None
            balance = self.private_exchange.fetch_balance()
            return balance.get('USDT', {}).get('total', 0)
        except Exception as e:
            self.logger.error(f"잔고 조회 실패: {e}")
            return None
    
    def check_real_position_status(self):
        """실제 포지션 상태 체크 (주문 체결 여부 확인)"""
        try:
            if not self.private_exchange:
                return
                
            # 실제 포지션 재조회
            positions = self.private_exchange.fetch_positions()
            # open_orders 전체 조회는 제거 (Rate Limit 문제 회피)
            
            # 현재 실제 포지션 업데이트
            current_positions = {}
            for position in positions:
                if position['contracts'] > 0:
                    symbol = position['symbol']
                    current_positions[symbol] = {
                        'size': position['contracts'],
                        'side': position['side'],
                        'entry_price': position['entryPrice'],
                        'mark_price': position['markPrice'],
                        'unrealized_pnl': position['unrealizedPnl'],
                        'percentage': position['percentage']
                    }
            
            # DCA 주문 체결 확인
            for symbol, pos_info in self.active_positions.items():
                if 'dca_orders' not in pos_info:
                    continue
                
                clean_symbol = symbol.replace('/USDT:USDT', '')
                
                # 각 DCA 주문 상태 체크
                for dca_order in pos_info['dca_orders']:
                    order_id = dca_order['order_id']
                    stage = dca_order['stage']
                    
                    try:
                        # 주문 상태 조회
                        order_status = self.private_exchange.fetch_order(order_id, symbol)
                        
                        if order_status['status'] == 'closed' and order_status['filled'] > 0:
                            # DCA 주문이 체결됨
                            filled_price = order_status['average']
                            filled_qty = order_status['filled']
                            
                            print(f"🔥 실전 {stage} 체결: {clean_symbol}")
                            print(f"   💰 체결가: ${filled_price:,.4f}")
                            print(f"   📊 수량: {filled_qty:.6f}")
                            
                            # 텔레그램 DCA 체결 알림
                            if self.telegram_bot:
                                portfolio = self.get_portfolio_summary()
                                message = f"""🔥 실전 {stage} 체결 🔥
━━━━━━━━━━━━━━━━━━━━━━
📈 심볼: {clean_symbol}
💰 체결가: ${filled_price:,.4f}
📊 수량: {filled_qty:.6f}
📋 주문ID: {order_id}
━━━━━━━━━━━━━━━━━━━━━━
📊 포트폴리오 현황:
   • 잔고: ${portfolio['free_balance']:.0f} USDT
   • 포지션수: {portfolio['open_positions']}개
   • 총 PnL: ${portfolio['total_unrealized_pnl']:+.0f} USDT
⚠️ 실제 거래 체결"""
                                self.telegram_bot.send_message(message)
                            
                            # 체결된 주문 제거
                            dca_order['status'] = 'filled'
                            
                    except Exception as e:
                        # 주문이 취소되었거나 조회 실패
                        pass
            
            # active_positions 업데이트
            self.active_positions = current_positions
            
        except Exception as e:
            self.logger.error(f"실제 포지션 상태 체크 실패: {e}")
    
    def run_continuous_scan(self, interval=30):
        """🚀 IP 밴 방지 최고속도 연속 스캔 실행"""
        print("🚀 15분봉 초필살기 전략 연속 스캔 시작 (🔥 실전매매 모드 🔥)")
        print(f"   ⚡ 최적화 스캔 주기: {interval}초 (바이낸스 레이트 리밋 준수)")
        print(f"   📊 레버리지: 20배")
        print(f"   🛡️ IP 밴 방지: 스마트 API 호출 제한 및 재사용 최적화")
        
        # 실제 잔고 조회
        try:
            portfolio = self.get_portfolio_summary()
            print(f"   💰 현재 잔고: ${portfolio['free_balance']:.0f} USDT")
            print(f"   📊 총 자산: ${portfolio['total_balance']:.0f} USDT")
            print(f"   🎯 활성 포지션: {portfolio['open_positions']}개")
        except:
            print(f"   ⚠️ 잔고 조회 실패")
        
        print(f"   💀 최대 손실: 6% (시드 기준)")
        print(f"   🔥 실제 거래 활성화 - 리스크 관리 필수!")
        print(f"\n🔥 바이낸스 API 레이트 리밋 최적화:")
        print(f"   • Futures: 1200 requests/min (20/sec)")
        print(f"   • 스마트 배치: 병렬 + 순차 하이브리드") 
        print(f"   • 캐시 활용: 티커 데이터 재사용")
        print(f"   • 에러 복구: 자동 백오프 및 재시도")
        
        # API 호출 제한 관리
        api_call_tracker = {
            'calls_in_minute': 0,
            'last_minute_reset': time.time(),
            'max_calls_per_minute': 800,  # 안전 마진 (1200의 66%)
            'retry_delays': [1, 2, 5, 10, 30]  # 백오프 딜레이 (초)
        }
        
        while True:
            try:
                # API 호출 수 리셋 (매분)
                current_time = time.time()
                if current_time - api_call_tracker['last_minute_reset'] >= 60:
                    api_call_tracker['calls_in_minute'] = 0
                    api_call_tracker['last_minute_reset'] = current_time
                
                print(f"\n{'='*60}")
                print(f"🔍 최적화 스캔 시작: {get_korea_time().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"📊 API 호출 현황: {api_call_tracker['calls_in_minute']}/{api_call_tracker['max_calls_per_minute']}/분")
                
                # API 호출 제한 체크
                if api_call_tracker['calls_in_minute'] >= api_call_tracker['max_calls_per_minute']:
                    wait_time = 60 - (current_time - api_call_tracker['last_minute_reset'])
                    if wait_time > 0:
                        print(f"⚠️ API 호출 제한 도달 - {wait_time:.0f}초 대기 (IP 밴 방지)")
                        time.sleep(wait_time)
                        api_call_tracker['calls_in_minute'] = 0
                        api_call_tracker['last_minute_reset'] = time.time()
                
                # 심볼 스캔 (최적화된 API 호출)
                scan_start = time.time()
                signals = self.scan_symbols_optimized(api_call_tracker)
                scan_duration = time.time() - scan_start
                
                print(f"⚡ 스캔 완료: {scan_duration:.1f}초, API 호출: {api_call_tracker['calls_in_minute']}/{api_call_tracker['max_calls_per_minute']}")
                
                # 진입 신호 처리
                for signal in signals:
                    if self.execute_trade(signal):
                        print(f"✅ {signal['clean_symbol']} 진입 완료")
                
                # 실제 포지션 상태 체크 (DCA 주문 체결 확인)
                self.check_real_position_status()
                
                # 실제 포트폴리오 현황 출력
                portfolio = self.get_portfolio_summary()
                print(f"\n📊 실제 포트폴리오 현황:")
                print(f"   💰 현재잔고: ${portfolio['free_balance']:.0f} USDT")
                print(f"   📈 총 자산: ${portfolio['total_balance']:.0f} USDT")
                print(f"   📊 미실현 PnL: ${portfolio['total_unrealized_pnl']:+.0f} USDT")
                print(f"   🎯 포지션수: {portfolio['open_positions']}개")
                if portfolio['open_positions'] > 0:
                    print(f"   🔍 활성 포지션:")
                    for symbol, pos in portfolio['positions'].items():
                        clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                        print(f"      • {clean_symbol}: {pos['percentage']:+.2f}% (${pos['unrealized_pnl']:+.0f})")
                
                # 동적 대기 시간 계산
                effective_interval = max(interval, 30)  # 최소 30초 대기
                if api_call_tracker['calls_in_minute'] > 600:  # 75% 도달시 더 긴 대기
                    effective_interval = interval * 1.5
                
                print(f"⏳ {effective_interval:.0f}초 대기 중 (다음 스캔까지)...")
                time.sleep(effective_interval)
                
            except KeyboardInterrupt:
                print("\n👋 사용자에 의해 중단됨")
                break
            except Exception as e:
                self.logger.error(f"스캔 중 오류: {e}")
                print(f"❌ 스캔 오류: {e}")
                
                # 백오프 전략으로 재시도
                for delay in api_call_tracker['retry_delays']:
                    print(f"🔄 {delay}초 후 재시도...")
                    time.sleep(delay)
                    try:
                        # 간단한 연결 테스트
                        self.exchange.fetch_ticker('BTC/USDT')
                        print("✅ 연결 복구됨")
                        break
                    except:
                        continue
                else:
                    print("❌ 연결 복구 실패 - 60초 대기")
                    time.sleep(60)

def main():
    """🚀 IP 밴 방지 최고속도 메인 함수"""
    import sys
    
    try:
        print("🚀 15분봉 A전략(바닥타점) + B전략(급등초입) 시작")
        print("="*60)
        
        # 명령행 인수 처리
        mode = 'single'  # 기본값: 단일 스캔
        interval = 30    # 기본값: 30초 간격 (최적화)
        
        if len(sys.argv) > 1:
            if sys.argv[1] in ['continuous', 'cont', 'c']:
                mode = 'continuous'
            if len(sys.argv) > 2:
                try:
                    interval = int(sys.argv[2])
                    interval = max(30, min(600, interval))  # 30초~10분 제한
                except:
                    interval = 30
        
        # 15분봉 A전략(바닥타점) + B전략(급등초입) 초기화 (실전매매 모드)
        strategy = FifteenMinuteMegaStrategy(sandbox=False)
        
        # 실제 포트폴리오 상태 출력
        portfolio = strategy.get_portfolio_summary()
        print(f"\n📊 실전매매 포트폴리오 초기 상태:")
        print(f"   💰 현재 잔고: ${portfolio['free_balance']:.0f} USDT")
        print(f"   📈 총 자산: ${portfolio['total_balance']:.0f} USDT")
        print(f"   📊 미실현 PnL: ${portfolio['total_unrealized_pnl']:+.0f} USDT")
        print(f"   🎯 활성 포지션: {portfolio['open_positions']}개")
        if portfolio['open_positions'] > 0:
            print(f"   🔍 기존 포지션:")
            for symbol, pos in portfolio['positions'].items():
                clean_symbol = symbol.replace('/USDT:USDT', '')
                print(f"      • {clean_symbol}: {pos['percentage']:+.2f}% (${pos['unrealized_pnl']:+.0f})")
        
        if mode == 'continuous':
            # 연속 스캔 모드 (IP 밴 방지 최적화)
            print(f"\n🚀 연속 스캔 모드 시작 (IP 밴 방지 최적화)")
            print(f"   ⚡ 스캔 간격: {interval}초")
            print(f"   🛡️ 바이낸스 레이트 리밋 준수")
            print(f"   📊 사용법: python fifteen_minute_mega_strategy.py continuous [간격초]")
            print(f"   ⚠️ 중단: Ctrl+C")
            strategy.run_continuous_scan(interval)
        else:
            # 단일 스캔 모드 (기본값)
            print(f"\n🔍 단일 스캔 모드 (최고속도 최적화)")
            print(f"   ⚡ IP 밴 방지 최적화 적용")
            print(f"   📊 연속 모드: python fifteen_minute_mega_strategy.py continuous")
            
            # API 호출 추적기 초기화
            api_call_tracker = {
                'calls_in_minute': 0,
                'last_minute_reset': time.time(),
                'max_calls_per_minute': 800,
                'retry_delays': [1, 2, 5, 10, 30]
            }
            
            # 최적화된 단일 스캔 실행
            signals = strategy.scan_symbols_optimized(api_call_tracker)
            
            # 진입 신호 처리
            if signals:
                print(f"\n🔥 진입 신호 처리 중...")
                for signal in signals:
                    if strategy.execute_trade(signal):
                        print(f"✅ {signal['clean_symbol']} 진입 완료")
            
            # 최종 포지션 상태 체크
            strategy.check_real_position_status()
            
            # 최종 포트폴리오 현황 출력
            final_portfolio = strategy.get_portfolio_summary()
            print(f"\n📊 최종 포트폴리오 현황:")
            print(f"   💰 잔고: ${final_portfolio['free_balance']:.0f} USDT")
            print(f"   📈 총 자산: ${final_portfolio['total_balance']:.0f} USDT") 
            print(f"   📊 미실현 PnL: ${final_portfolio['total_unrealized_pnl']:+.0f} USDT")
            print(f"   🎯 포지션수: {final_portfolio['open_positions']}개")
            
            print(f"\n⚡ 최고속도 스캔 완료!")
            print(f"   🛡️ API 호출: {api_call_tracker['calls_in_minute']}/{api_call_tracker['max_calls_per_minute']}")
            print(f"   📊 IP 밴 방지: 성공적으로 레이트 리밋 준수")
        
    except KeyboardInterrupt:
        print("\n👋 사용자에 의해 중단됨")
    except Exception as e:
        print(f"❌ 시스템 오류: {e}")
        import traceback
        traceback.print_exc()

def emergency_close_all_positions():
    """긴급 전체 포지션 청산 (비상용)"""
    try:
        strategy = FifteenMinuteMegaStrategy(sandbox=False)
        
        if not strategy.private_exchange:
            print("❌ 프라이빗 API 없음 - 청산 불가")
            return
        
        print("🚨 긴급 전체 포지션 청산 시작...")
        
        # 실제 포지션 조회
        positions = strategy.private_exchange.fetch_positions()
        open_positions = [p for p in positions if p['contracts'] > 0]
        
        if not open_positions:
            print("✅ 청산할 포지션이 없습니다.")
            return
        
        print(f"📊 청산할 포지션: {len(open_positions)}개")
        
        for position in open_positions:
            try:
                symbol = position['symbol']
                size = position['contracts']
                clean_symbol = symbol.replace('/USDT:USDT', '')
                
                # 시장가 매도 (전량 청산)
                order = strategy.private_exchange.create_market_sell_order(symbol, size)
                print(f"✅ {clean_symbol} 청산 완료: {size:.6f}")
                
            except Exception as e:
                print(f"❌ {symbol} 청산 실패: {e}")
        
        print("✅ 긴급 청산 완료")
        
    except Exception as e:
        print(f"❌ 긴급 청산 실패: {e}")

if __name__ == "__main__":
    main()