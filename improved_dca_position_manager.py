# -*- coding: utf-8 -*-
"""
🔄 count선된 Cyclic trading수 시스템 (DCA Position Manager)
SuperClaude Expert Mode Implementation

핵심 count선사항:
1. Sync 문제 해결 - Trade소와 DCA File 간 실Time Sync 강화
2. Exit 로직 통합 - 단일 책임 원칙 적용
3. Error Process 강화 - 네트워크/API Error 대응
4. 중복 Remove - 불Required한 복잡성 Remove
5. Test 가능한 구조로 count선
6. 고급 Exit 시스템 통합 - 적응형 손절, 다Stage 익절, Trailing 스톱, 복합 기술적 Exit
"""

import json
import time
import os
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import ccxt
import logging
import traceback
import pandas as pd
import numpy as np

# Legacy 고급/기본 Exit 시스템 Remove - New 4가지 Exit 방식만 Usage

# 콘솔 색상 정의
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def get_korea_time():
    """한국 표준시(KST) Current Time을 반환 (UTC +9Time)"""
    return datetime.now(timezone(timedelta(hours=9)))

class PositionStage(Enum):
    """Position Stage"""
    INITIAL = "initial"           # 최초 Entry
    FIRST_DCA = "first_dca"      # 1차 Add매수
    SECOND_DCA = "second_dca"    # 2차 Add매수
    CLOSING = "closing"          # Exit 중

class ExitType(Enum):
    """Exit Type - New 5가지 Exit 방식"""
    SUPERTREND_EXIT = "supertrend_exit"       # SuperTrend 전량Exit
    BB600_PARTIAL_EXIT = "bb600_partial_exit" # BB600 50% 익절Exit
    BREAKEVEN_PROTECTION = "breakeven_protection" # 절반 하락 Exit
    WEAK_RISE_DUMP_PROTECTION = "weak_rise_dump_protection" # Approx상승후 급락 리스크 times피
    DCA_CYCLIC_EXIT = "dca_cyclic_exit"       # DCA Cyclic trading 일부Exit

class CyclicState(Enum):
    """Cyclic trading Status"""
    NORMAL_DCA = "normal_dca"           # 일반 DCA (Cyclic trading 아님)
    CYCLIC_ACTIVE = "cyclic_active"     # Cyclic trading Active Status
    CYCLIC_PAUSED = "cyclic_paused"     # Cyclic trading 일시 중단
    CYCLIC_COMPLETE = "cyclic_complete" # Cyclic trading Complete (3times 달성)

@dataclass
class DCAEntry:
    """DCA Entry 기록"""
    stage: str              # Entry Stage
    entry_price: float      # Entry가
    quantity: float         # Quantity
    notional: float         # 명목가치 (USDT)
    leverage: float         # 레버리지
    timestamp: str          # Entry Time
    is_active: bool = True  # Active Status
    order_type: str = "market"    # 주문 Type (market/limit)
    order_id: str = ""            # 주문 ID (지정가 주문용)
    is_filled: bool = True        # 체결 Status (시장가는 즉시 True, 지정가는 체결시 True)

@dataclass
class DCAPosition:
    """DCA Position 데이터"""
    symbol: str
    entries: List[DCAEntry]
    current_stage: str
    initial_entry_price: float
    average_price: float
    total_quantity: float
    total_notional: float
    is_active: bool
    created_at: str
    last_update: str
    cyclic_count: int = 0
    max_cyclic_count: int = 3
    cyclic_state: str = CyclicState.NORMAL_DCA.value
    last_cyclic_entry: str = ""  # 마지막 Cyclic trading Entry Time
    total_cyclic_profit: float = 0.0  # Cumulative Cyclic trading 수익
    
    # New 5가지 Exit 방식 추적
    max_profit_pct: float = 0.0  # 최대 Profit ratio 추적
    bb600_exit_done: bool = False  # BB600 50% Exit Complete 여부
    breakeven_protection_active: bool = False  # Approx수익 보호 Active화 여부
    breakeven_exit_done: bool = False  # 본절보호Exit Complete 여부 (중복 방지용)
    supertrend_exit_done: bool = False  # SuperTrend Exit Complete 여부
    weak_rise_dump_exit_done: bool = False  # Approx상승후 급락 리스크 times피 Exit Complete 여부
    
    # Trailing 스탑 관련 필드
    trailing_stop_active: bool = False  # Trailing 스탑 Active화 여부
    trailing_stop_high: float = 0.0  # Trailing 스탑 Highest price 추적
    trailing_stop_percentage: float = 0.05  # Trailing 스탑 비율 (5%)

class ImprovedDCAPositionManager:
    """count선된 Cyclic trading수 Position Admin"""
    
    def __init__(self, exchange=None, telegram_bot=None, stats_callback=None, strategy=None):
        self.exchange = exchange
        self.telegram_bot = telegram_bot
        self.stats_callback = stats_callback
        self.strategy = strategy
        
        # Logger Settings
        self.logger = logging.getLogger(__name__)
        
        # File 경로
        self.positions_file = "dca_positions.json"
        self.data_file = "dca_positions.json"  # _load_sent_notifications에서 Usage
        self.limits_file = "dca_limits.json"
        self.backup_file = "dca_positions_backup.json"
        
        # Position 데이터
        self.positions = {}  # {symbol: DCAPosition}
        self.symbol_limits = {}  # {symbol: count}
        
        # Sync 락
        self.sync_lock = threading.Lock()
        self.file_lock = threading.Lock()
        
        # 중복 Notification 방지용 (체결 Notification 중복 방지) - File 기반 지속성 Add
        self._sent_fill_notifications = set()  # {symbol_stage_orderid} 형태
        self._load_sent_notifications()  # 재Starting 시 Legacy Notification 기록 Load
        
        # Exit 시스템 Initialize (누락된 속성들)
        self.advanced_exit_system = None  # 고급 Exit 시스템 (미구현)
        self.basic_exit_system = None     # 기본 Exit 시스템 (미구현)
        
        # Settings (Fixed 1.5% Entry with NO DCA - 추가매수 없이 고정 진입)
        self.config = {
            # DCA Entry Settings (DCA 비활성화 - 추가매수 없음)
            'initial_weight': 0.015,      # 최초 Entry 비중 (1.5%) - 전체 비중의 1.5%
            'initial_leverage': 10.0,     # 최초 Entry 레버리지
            'first_dca_trigger': -99.0,   # 1차 Add매수 트리거 (비활성화)
            'first_dca_weight': 0.025,    # 1차 Add매수 비중 (비활성화)
            'first_dca_leverage': 10.0,   # 1차 Add매수 레버리지 (비활성화)
            'second_dca_trigger': -99.0,  # 2차 Add매수 트리거 (비활성화)
            'second_dca_weight': 0.025,   # 2차 Add매수 비중 (비활성화)
            'second_dca_leverage': 10.0,  # 2차 Add매수 레버리지 (비활성화)

            # Stage별 손절 기준 (고정 -3% 손절)
            'stop_loss_by_stage': {
                'initial': -0.03,      # 초기 Entry: -3% 전량 손절
                'first_dca': -0.03,    # 1차 DCA 후: -3% 손절 (미사용)
                'second_dca': -0.03    # 2차 DCA 후: -3% 손절 (미사용)
            },

            # 수익 Exit 전략 (Trailing Stop 방식)
            'trailing_stop_enabled': True,       # Trailing Stop 활성화
            'trailing_profit_peak_min': 0.02,    # 최소 수익 2% 이상 도달 시 추적 시작
            'trailing_profit_peak_max': 0.03,    # 최대 수익 3% 기준
            'trailing_stop_drawdown': 0.015,     # 최고점 대비 1.5% 하락 시 전량 청산
            'mid_profit_threshold': 0.05,        # 5% 중간 수익 기준 (미사용)
            'half_profit_threshold': 0.10,       # 10% 절반 Exit 기준 (미사용)
            
            # 시스템 Settings
            'max_dca_stages': 2,            # 최대 Add매수 Stage
            'max_symbol_dca_count': 3,      # Symbol당 최대 Cyclic trading 사이클
            'max_total_positions': 10,      # 최대 보유 종목 수 (옵션A)
            'api_retry_count': 3,           # API 재Attempt 횟수
            'api_retry_delay': 1.0,         # API 재Attempt 지연 (초)
            'sync_interval': 15,            # Sync 주기 (초)
        }
        
        # 로거 Settings
        self.setup_logger()
        
        # New 5가지 Exit 방식만 Usage
        self.logger.info("New 5가지 Exit 방식 Active화: SuperTrend, Approx수익보호, Approx상승후급락리스크times피, BB600, DCACyclic trading")
        
        # 데이터 Load
        self.load_data()
        
        # 🔧 이미 체결된 주문들에 대한 Notification 기록 Add (중복 방지)
        self._register_existing_filled_orders()
        
        # 초기 Sync
        if self.exchange and hasattr(self.exchange, 'apiKey') and self.exchange.apiKey:
            self.logger.info("Trade소와 DCA System 초기 Sync Starting...")
            self.sync_with_exchange(force_sync=True)
        
        self.logger.info(f"count선된 DCA System Initialization complete")
        self.logger.info(f"Active positions: {len([p for p in self.positions.values() if p.is_active])}count")

    def _update_average_price_safely(self, position: DCAPosition, new_avg_price: float, context: str = "unknown") -> bool:
        """Average price 안전 Update (중앙화된 Average price 관리)"""
        try:
            with self.sync_lock:  # 스레드 안전성 보장
                old_avg_price = position.average_price
                price_change_pct = abs(new_avg_price - old_avg_price) / old_avg_price * 100 if old_avg_price > 0 else 0
                
                # Change사항 Verification
                if price_change_pct > 20.0:  # 20% 이상 change시 Warning
                    self.logger.error(f"🚨 Drastic average price change detected: {position.symbol} - {price_change_pct:.2f}% change ({context})")
                    self.logger.error(f"   Legacy: ${old_avg_price:.6f} → New: ${new_avg_price:.6f}")
                    return False  # 급격한 change는 차단
                
                # Average price update
                position.average_price = new_avg_price
                position.last_update = get_korea_time().isoformat()
                
                # 로깅
                if price_change_pct > 0.1:  # 0.1% 이상 change시에만 로깅
                    self.logger.info(f"💰 Average price update: {position.symbol} ({context})")
                    self.logger.info(f"   ${old_avg_price:.6f} → ${new_avg_price:.6f} ({price_change_pct:+.2f}%)")
                
                return True
                
        except Exception as e:
            self.logger.error(f"Average price update Failed {position.symbol}: {e}")
            return False

    def setup_logger(self):
        """로거 Settings"""
        self.logger = logging.getLogger('ImprovedDCAManager')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            # File 핸들러
            file_handler = logging.FileHandler('improved_dca_system.log', encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            
            # 콘솔 핸들러
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.WARNING)
            
            # 포맷터
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def load_data(self):
        """데이터 Load"""
        with self.file_lock:
            # Position 데이터 Load
            try:
                if os.path.exists(self.positions_file):
                    with open(self.positions_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for symbol, pos_data in data.items():
                            # DCAEntry 객체로 변환
                            entries = [DCAEntry(**entry) for entry in pos_data['entries']]
                            pos_data['entries'] = entries
                            
                            # Trailing 스탑 필드 마이그레이션 (Legacy Position 호환성)
                            if 'trailing_stop_active' not in pos_data:
                                pos_data['trailing_stop_active'] = False
                            if 'trailing_stop_high' not in pos_data:
                                pos_data['trailing_stop_high'] = 0.0
                            if 'trailing_stop_percentage' not in pos_data:
                                pos_data['trailing_stop_percentage'] = 0.05
                            
                            self.positions[symbol] = DCAPosition(**pos_data)
                    self.logger.info(f"Position 데이터 Load Complete: {len(self.positions)}count")
                else:
                    self.positions = {}
                    self.logger.info("Position file not found - 새로 Starting")
            except Exception as e:
                self.logger.error(f"Position 데이터 Load Failed: {e}")
                # Backup File Attempt
                if os.path.exists(self.backup_file):
                    try:
                        with open(self.backup_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            for symbol, pos_data in data.items():
                                entries = [DCAEntry(**entry) for entry in pos_data['entries']]
                                pos_data['entries'] = entries
                                self.positions[symbol] = DCAPosition(**pos_data)
                        self.logger.info(f"Backup File에서 Recover Complete: {len(self.positions)}count")
                    except Exception as be:
                        self.logger.error(f"Backup File Recover Failed: {be}")
                        self.positions = {}
                else:
                    self.positions = {}
            
            # 제한 데이터 Load
            try:
                if os.path.exists(self.limits_file):
                    with open(self.limits_file, 'r', encoding='utf-8') as f:
                        self.symbol_limits = json.load(f)
                    self.logger.info(f"제한 데이터 Load Complete: {len(self.symbol_limits)}count")
                else:
                    self.symbol_limits = {}
            except Exception as e:
                self.logger.error(f"Limit data load failed: {e}")
                self.symbol_limits = {}

    def save_data(self):
        """데이터 Save"""
        with self.file_lock:
            try:
                # Backup Create
                if os.path.exists(self.positions_file):
                    import shutil
                    shutil.copy2(self.positions_file, self.backup_file)
                
                # Position 데이터 Save
                data = {}
                for symbol, position in self.positions.items():
                    # DCAEntry를 dict로 변환
                    entries_dict = [asdict(entry) for entry in position.entries]
                    pos_dict = asdict(position)
                    pos_dict['entries'] = entries_dict
                    data[symbol] = pos_dict
                
                with open(self.positions_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                # 제한 데이터 Save
                with open(self.limits_file, 'w', encoding='utf-8') as f:
                    json.dump(self.symbol_limits, f, ensure_ascii=False, indent=2)
                
                self.logger.debug("Data save complete")
                
            except Exception as e:
                self.logger.error(f"Data save failed: {e}")

    def sync_with_exchange(self, force_sync=False):
        """Trade소와 Sync - 핵심 count선"""
        if not self.exchange:
            return {'success': False, 'error': 'Exchange not available'}
        
        with self.sync_lock:
            try:
                self.logger.info("🔄 Trade소와 DCA System Sync Starting...")
                
                # Trade소 Position 조times
                exchange_positions = self._fetch_exchange_positions_safe()
                
                # Position이 없으면 Orphan position만 정리
                if not exchange_positions:
                    # DCA Position이 있는데 Trade소에 없으면 정리
                    orphaned_count = 0
                    for symbol in list(self.positions.keys()):
                        self._cleanup_orphaned_position(symbol)
                        orphaned_count += 1
                    
                    if orphaned_count > 0:
                        self.logger.info(f"🧹 Orphan position {orphaned_count}count Cleanup Complete")
                    
                    return {
                        'success': True,
                        'new_detected': [],
                        'orphaned_cleaned': list(self.positions.keys()) if orphaned_count > 0 else [],
                        'updated': [],
                        'message': 'No position - 정리 Complete'
                    }
                
                # Current DCA Position과 비교
                dca_symbols = set(self.positions.keys())
                exchange_symbols = set(pos['symbol'] for pos in exchange_positions if pos['contracts'] > 0)
                
                sync_result = {
                    'success': True,
                    'new_detected': [],
                    'orphaned_cleaned': [],
                    'updated': [],
                    'errors': []
                }
                
                # 1. Trade소에 있지만 DCA에 없는 Position 감지 (Legacy Position)
                for pos in exchange_positions:
                    symbol = pos['symbol']
                    if pos['contracts'] > 0 and symbol not in dca_symbols:
                        # Legacy Position을 DCA 시스템에 Register
                        self._register_existing_position(symbol, pos)
                        sync_result['new_detected'].append(symbol)
                        self.logger.info(f"✅ Legacy Position Register: {symbol}")
                
                # 2. DCA에 있지만 Trade소에 없는 Position 정리 (Orphan position)
                for symbol in list(dca_symbols):
                    if symbol not in exchange_symbols:
                        self._cleanup_orphaned_position(symbol)
                        sync_result['orphaned_cleaned'].append(symbol)
                        self.logger.info(f"🧹 Orphan position Cleanup: {symbol}")
                
                # 3. 양쪽에 모두 있는 Position Sync
                for pos in exchange_positions:
                    symbol = pos['symbol']
                    if pos['contracts'] > 0 and symbol in dca_symbols:
                        if self._update_position_from_exchange(symbol, pos):
                            sync_result['updated'].append(symbol)
                
                # 데이터 Save
                self.save_data()
                
                self.logger.info(f"🔄 Sync Complete: NewDetected {len(sync_result['new_detected'])}count, "
                               f"고아정리 {len(sync_result['orphaned_cleaned'])}count, "
                               f"Update {len(sync_result['updated'])}count")
                
                return sync_result
                
            except Exception as e:
                self.logger.error(f"Sync Failed: {e}")
                self.logger.error(traceback.format_exc())
                return {'success': False, 'error': str(e)}

    def _fetch_exchange_positions_safe(self):
        """안전한 Trade소 Position 조times"""
        def safe_float(value, default=0.0):
            """안전한 float 변환"""
            if value is None:
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        for attempt in range(self.config['api_retry_count']):
            try:
                # Rate Limit Status 체크
                if (hasattr(self.strategy, '_api_rate_limited') and 
                    self.strategy._api_rate_limited):
                    self.logger.debug("🚨 Rate limit status - Position 조times 너뛰기")
                    return default
                
                positions = self.exchange.fetch_positions()
                
                # Position이 없으면 빈 리스트 반환
                if not positions:
                    self.logger.info("💵 Current 계좌에 No position")
                    return []
                
                # Position 데이터 Process
                active_positions = []
                for pos in positions:
                    if not pos or not pos.get('symbol'):
                        continue
                    
                    # Quantity이 0이면 비Active positions으로 간주
                    contracts = safe_float(pos.get('contracts'))
                    if contracts == 0:
                        continue
                    
                    active_positions.append({
                        'symbol': pos['symbol'],
                        'contracts': contracts,
                        'notional': safe_float(pos.get('notional')),
                        'side': pos.get('side'),
                        'entry_price': safe_float(pos.get('entryPrice')),
                        'mark_price': safe_float(pos.get('markPrice')),
                        'unrealized_pnl': safe_float(pos.get('unrealizedPnl')),
                        'percentage': safe_float(pos.get('percentage'))
                    })
                
                if not active_positions:
                    self.logger.info("💵 Active No position (All zero quantity)")
                    return []
                
                return active_positions
                
            except Exception as e:
                self.logger.warning(f"Position 조times Attempt {attempt + 1}/{self.config['api_retry_count']} Failed: {e}")
                if attempt < self.config['api_retry_count'] - 1:
                    time.sleep(self.config['api_retry_delay'] * (attempt + 1))
                else:
                    self.logger.info("💵 Position 조times Failed - No position으로 Process")
                    return []
        return []

    def _register_existing_position(self, symbol: str, exchange_pos: dict):
        """Legacy Position을 DCA 시스템에 Register"""
        try:
            entry_price = exchange_pos['entry_price']
            quantity = exchange_pos['contracts']
            notional = exchange_pos['notional']
            
            # DCAEntry Create
            entry = DCAEntry(
                stage="initial",
                entry_price=entry_price,
                quantity=quantity,
                notional=abs(notional),
                leverage=self.config['initial_leverage'],
                timestamp=get_korea_time().isoformat(),
                is_active=True
            )
            
            # DCAPosition Create
            position = DCAPosition(
                symbol=symbol,
                entries=[entry],
                current_stage=PositionStage.INITIAL.value,
                initial_entry_price=entry_price,
                average_price=entry_price,
                total_quantity=quantity,
                total_notional=abs(notional),
                is_active=True,
                created_at=get_korea_time().isoformat(),
                last_update=get_korea_time().isoformat(),
                cyclic_count=0,
                max_cyclic_count=3,
                cyclic_state=CyclicState.NORMAL_DCA.value,
                last_cyclic_entry="",
                total_cyclic_profit=0.0
            )
            
            self.positions[symbol] = position
            self.logger.info(f"Legacy Position Register: {symbol} - Entry가: {entry_price}, Quantity: {quantity}")
            
        except Exception as e:
            self.logger.error(f"Legacy Position Register Failed {symbol}: {e}")

    def _cleanup_orphaned_position(self, symbol: str):
        """Orphan position 정리"""
        try:
            if symbol in self.positions:
                # 미체결 지정가 주문 Cancel
                cancel_result = self._cancel_pending_orders(symbol)
                if cancel_result['success'] and cancel_result['cancelled_count'] > 0:
                    self.logger.info(f"📋 Orphan position Pending order cancel: {symbol} - {cancel_result['cancelled_count']}count")
                
                self.logger.info(f"Orphan position Cleanup: {symbol}")
                del self.positions[symbol]
                
                # 메인 전략의 active_positions도 정리
                if self.strategy and hasattr(self.strategy, 'active_positions'):
                    if symbol in self.strategy.active_positions:
                        del self.strategy.active_positions[symbol]
                        self.logger.info(f"Main strategy position also cleaned: {symbol}")
                
        except Exception as e:
            self.logger.error(f"Orphan position Cleanup Failed {symbol}: {e}")

    def _update_position_from_exchange(self, symbol: str, exchange_pos: dict) -> bool:
        """Trade소 Position으로부터 DCA Position Update - 강화된 Sync"""
        try:
            if symbol not in self.positions:
                return False
            
            position = self.positions[symbol]
            current_quantity = exchange_pos['contracts']
            current_notional = abs(exchange_pos['notional'])
            
            # Quantity 차이가 있으면 Update
            if abs(position.total_quantity - current_quantity) > 0.001:
                old_quantity = position.total_quantity
                
                # 🚨 핵심 Modify: entries 데이터도 Actual position에 맞게 조정
                if current_quantity < old_quantity:
                    # Actual position이 줄어든 경우 (부분Exit 발생)
                    reduction_ratio = current_quantity / old_quantity if old_quantity > 0 else 0
                    
                    # Active entries를 비례적으로 줄임
                    for entry in position.entries:
                        if entry.is_active and entry.is_filled:
                            entry.quantity *= reduction_ratio
                    
                    # current_stage 재계산
                    active_stages = [e.stage for e in position.entries if e.is_active and e.is_filled and e.quantity > 0.001]
                    if "second_dca" in active_stages:
                        position.current_stage = PositionStage.SECOND_DCA.value
                    elif "first_dca" in active_stages:
                        position.current_stage = PositionStage.FIRST_DCA.value
                    elif "initial" in active_stages:
                        position.current_stage = PositionStage.INITIAL.value
                    else:
                        position.current_stage = PositionStage.CLOSING.value
                    
                    # Average price 재계산
                    active_entries = [e for e in position.entries if e.is_active and e.is_filled and e.quantity > 0.001]
                    if active_entries:
                        total_notional = sum(e.entry_price * e.quantity for e in active_entries)
                        total_qty = sum(e.quantity for e in active_entries)
                        position.average_price = total_notional / total_qty if total_qty > 0 else position.initial_entry_price
                    
                    self.logger.info(f"🔄 Position reduction sync: {symbol}")
                    self.logger.info(f"   Quantity: {old_quantity:.6f} → {current_quantity:.6f} ({reduction_ratio:.2%})")
                    self.logger.info(f"   Stage: {position.current_stage}")
                    self.logger.info(f"   Average price: ${position.average_price:.6f}")
                
                position.total_quantity = current_quantity
                position.total_notional = current_notional
                position.last_update = get_korea_time().isoformat()
                
                self.logger.info(f"Position Quantity Sync: {symbol} - {old_quantity} → {current_quantity}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Position Update Failed {symbol}: {e}")
            return False

    def add_position(self, symbol: str, entry_price: float, quantity: float,
                    notional: float, leverage: float = 10.0, total_balance: float = None) -> bool:
        """New Position Add (DCA limit order 자동 Create 포함)"""
        try:
            with self.sync_lock:
                if symbol in self.positions and self.positions[symbol].is_active:
                    self.logger.warning(f"이미 Active positions 존재: {symbol}")
                    return False

                # DCAEntry Create (최초 Entry)
                entry = DCAEntry(
                    stage="initial",
                    entry_price=entry_price,
                    quantity=quantity,
                    notional=notional,
                    leverage=leverage,
                    timestamp=get_korea_time().isoformat(),
                    is_active=True,
                    is_filled=True  # 시장가 주문은 즉시 체결
                )

                # DCAPosition Create
                position = DCAPosition(
                    symbol=symbol,
                    entries=[entry],
                    current_stage=PositionStage.INITIAL.value,
                    initial_entry_price=entry_price,
                    average_price=entry_price,
                    total_quantity=quantity,
                    total_notional=notional,
                    is_active=True,
                    created_at=get_korea_time().isoformat(),
                    last_update=get_korea_time().isoformat(),
                    cyclic_count=0,
                    max_cyclic_count=3,
                    cyclic_state=CyclicState.NORMAL_DCA.value,
                    last_cyclic_entry="",
                    total_cyclic_profit=0.0
                )

                self.positions[symbol] = position
                self.save_data()

                self.logger.info(f"New position added: {symbol} - Entry가: {entry_price}, Quantity: {quantity}")

                # 📋 최초 Entry 즉시 DCA 1차, 2차 지정가 주문 자동 Create
                if total_balance and self.exchange:
                    self._create_initial_dca_limit_orders(position, total_balance)

                # 텔레그램 Notification Remove (메인 전략에서 통합 Notification 전송)
                # if self.telegram_bot:
                #     message = f"📈 DCA Position Add\nSymbol: {symbol}\nEntry가: ${entry_price:.4f}\nQuantity: {quantity}\n레버리지: {leverage}x"
                #     self.telegram_bot.send_message(message)

                return True

        except Exception as e:
            self.logger.error(f"Position Add Failed {symbol}: {e}")
            return False

    def _create_initial_dca_limit_orders(self, position: DCAPosition, total_balance: float):
        """최초 Entry시 DCA 1차, 2차 지정가 주문 자동 Create"""
        try:
            self.logger.info(f"🎯 {position.symbol} DCA limit order 자동 Create Starting...")
            self.logger.info(f"   Entry가: ${position.initial_entry_price:.6f}")

            # Current price 조times (DCA 주문 안전장치)
            try:
                ticker = self.exchange.fetch_ticker(position.symbol)
                current_price = ticker['last']
                self.logger.info(f"Current price check: {position.symbol} ${current_price:.6f}")
            except Exception as e:
                self.logger.error(f"Current price 조times Failed {position.symbol}: {e}")
                current_price = position.initial_entry_price  # Fallback

            # 1차 DCA limit order (-3%)
            first_dca_price = position.initial_entry_price * (1 + self.config['first_dca_trigger'])
            first_dca_amount = total_balance * self.config['first_dca_weight']
            first_dca_leverage = self.config['first_dca_leverage']
            first_dca_quantity = (first_dca_amount * first_dca_leverage) / first_dca_price

            # 🔒 안전장치: Current price가 DCA 가격보다 5% 이상 낮으면 주문 건너뜀 (극단적 하락 방지)
            if current_price < first_dca_price * 0.95:  # DCA 가격의 95% 미만일 때만 Skip
                self.logger.warning(f"⚠️ 1차 DCA order skipped: Current price(${current_price:.6f}) < DCA가격의 95%(${first_dca_price*0.95:.6f})")
                first_order_result = {'success': False, 'error': 'Current price too far below DCA trigger'}
            else:
                first_order_result = self._execute_limit_order(
                    position.symbol,
                    first_dca_quantity,
                    "buy",
                    first_dca_price
                )

            if first_order_result['success']:
                first_dca_entry = DCAEntry(
                    stage="first_dca",
                    entry_price=first_dca_price,
                    quantity=first_dca_quantity,
                    notional=first_dca_amount * first_dca_leverage,
                    leverage=first_dca_leverage,
                    timestamp=get_korea_time().isoformat(),
                    is_active=True,
                    order_type="limit",
                    order_id=first_order_result['order_id'],
                    is_filled=False  # 지정가 주문은 미체결
                )
                position.entries.append(first_dca_entry)
                self.logger.info(f"✅ 1차 DCA limit order placed: {position.symbol} @ ${first_dca_price:.4f} (ID: {first_order_result['order_id']})")
            else:
                self.logger.error(f"❌ 1차 DCA limit order Failed: {position.symbol}")

            # 2차 DCA limit order (-6%)
            second_dca_price = position.initial_entry_price * (1 + self.config['second_dca_trigger'])
            second_dca_amount = total_balance * self.config['second_dca_weight']
            second_dca_leverage = self.config['second_dca_leverage']
            second_dca_quantity = (second_dca_amount * second_dca_leverage) / second_dca_price

            # 🔒 안전장치: Current price가 DCA 가격보다 5% 이상 낮으면 주문 건너뜀 (극단적 하락 방지)
            if current_price < second_dca_price * 0.95:  # DCA 가격의 95% 미만일 때만 Skip
                self.logger.warning(f"⚠️ 2차 DCA order skipped: Current price(${current_price:.6f}) < DCA가격의 95%(${second_dca_price*0.95:.6f})")
                second_order_result = {'success': False, 'error': 'Current price too far below DCA trigger'}
            else:
                second_order_result = self._execute_limit_order(
                    position.symbol,
                    second_dca_quantity,
                    "buy",
                    second_dca_price
                )

            if second_order_result['success']:
                second_dca_entry = DCAEntry(
                    stage="second_dca",
                    entry_price=second_dca_price,
                    quantity=second_dca_quantity,
                    notional=second_dca_amount * second_dca_leverage,
                    leverage=second_dca_leverage,
                    timestamp=get_korea_time().isoformat(),
                    is_active=True,
                    order_type="limit",
                    order_id=second_order_result['order_id'],
                    is_filled=False  # 지정가 주문은 미체결
                )
                position.entries.append(second_dca_entry)
                self.logger.info(f"✅ 2차 DCA limit order placed: {position.symbol} @ ${second_dca_price:.4f} (ID: {second_order_result['order_id']})")
            else:
                self.logger.error(f"❌ 2차 DCA limit order Failed: {position.symbol}")

            # 데이터 Save
            self.save_data()

            # 텔레그램 Notification Remove (메인 전략의 통합 Notification에 DCA Info 포함됨)
            # if self.telegram_bot and (first_order_result['success'] or second_order_result['success']):
            #     orders_info = []
            #     if first_order_result['success']:
            #         orders_info.append(f"1차: ${first_dca_price:.4f} (-3%)")
            #     if second_order_result['success']:
            #         orders_info.append(f"2차: ${second_dca_price:.4f} (-6%)")
            #
            #     message = (f"📋 DCA limit order 자동 Register\n"
            #               f"Symbol: {position.symbol}\n"
            #               f"{chr(10).join(orders_info)}")
            #     self.telegram_bot.send_message(message)

            self.logger.info(f"🎉 {position.symbol} DCA limit order 자동 Create Complete")

        except Exception as e:
            self.logger.error(f"DCA limit order 자동 Create Failed {position.symbol}: {e}")

    def place_missing_dca_orders_after_partial_exit(self, symbol: str, current_price: float) -> Dict[str, Any]:
        """부분Exit 이후 빈 DCA Stage에 자동 지정가 주문 재Register (최대 3times Cyclic trading 지원)"""
        try:
            if symbol not in self.positions:
                return {'orders_placed': 0, 'error': 'Position not found'}
            
            position = self.positions[symbol]
            if not position.is_active:
                return {'orders_placed': 0, 'error': 'Position inactive'}
            
            # Cyclic trading 제한 Confirm
            if position.cyclic_count >= position.max_cyclic_count:
                return {'orders_placed': 0, 'error': f'Max cyclic limit reached: {position.cyclic_count}/{position.max_cyclic_count}'}
            
            self.logger.info(f"🔄 {symbol} DCA 재주문 검토 Starting (Cyclic trading {position.cyclic_count}/{position.max_cyclic_count}times)")
            
            # Current DCA Status Analysis
            stage_status = {}
            for entry in position.entries:
                stage_status[entry.stage] = {
                    'exists': True,
                    'is_active': entry.is_active,
                    'is_filled': entry.is_filled,
                    'order_id': entry.order_id
                }
            
            # 빈 Stage 또는 비Active화된 Stage Confirm
            missing_stages = []
            
            # 1차 DCA Confirm
            if ('first_dca' not in stage_status or 
                not stage_status['first_dca']['is_active'] or 
                stage_status['first_dca']['is_filled']):
                missing_stages.append('first_dca')
            
            # 2차 DCA Confirm
            if ('second_dca' not in stage_status or 
                not stage_status['second_dca']['is_active'] or 
                stage_status['second_dca']['is_filled']):
                missing_stages.append('second_dca')
            
            if not missing_stages:
                return {'orders_placed': 0, 'message': 'All DCA orders already active'}
            
            # 잔고 Confirm (간소화 - 기본값 Usage)
            try:
                balance = self.exchange.fetch_balance() if self.exchange else None
                total_balance = balance.get('USDT', {}).get('free', 100.0) if balance else 100.0
            except:
                total_balance = 100.0  # 기본값
            
            orders_placed = 0
            order_results = []
            
            # 각 빈 Stage에 대해 지정가 주문 Create
            for stage in missing_stages:
                try:
                    if stage == 'first_dca':
                        # 1차 DCA (-3%)
                        dca_price = position.initial_entry_price * (1 + self.config['first_dca_trigger'])
                        dca_amount = total_balance * self.config['first_dca_weight']
                        dca_leverage = self.config['first_dca_leverage']
                        
                    elif stage == 'second_dca':
                        # 2차 DCA (-6%)
                        dca_price = position.initial_entry_price * (1 + self.config['second_dca_trigger'])
                        dca_amount = total_balance * self.config['second_dca_weight']
                        dca_leverage = self.config['second_dca_leverage']
                    
                    else:
                        continue
                    
                    dca_quantity = (dca_amount * dca_leverage) / dca_price
                    
                    # 안전장치: Current price가 DCA 가격보다 5% 이상 낮으면 주문 건너뜀
                    if current_price < dca_price * 0.95:
                        self.logger.warning(f"⚠️ {stage} Re-order skipped: Current price(${current_price:.6f}) < DCA가격의 95%(${dca_price*0.95:.6f})")
                        continue
                    
                    # 지정가 주문 Execute
                    order_result = self._execute_limit_order(symbol, dca_quantity, "buy", dca_price)
                    
                    if order_result['success']:
                        # Legacy 같은 Stage 주문이 있다면 비Active화
                        for entry in position.entries:
                            if entry.stage == stage:
                                entry.is_active = False
                        
                        # 새 DCA Entry 기록 Add
                        new_dca_entry = DCAEntry(
                            stage=stage,
                            entry_price=dca_price,
                            quantity=dca_quantity,
                            notional=dca_amount * dca_leverage,
                            leverage=dca_leverage,
                            timestamp=get_korea_time().isoformat(),
                            is_active=True,
                            order_type="limit",
                            order_id=order_result['order_id'],
                            is_filled=False
                        )
                        position.entries.append(new_dca_entry)
                        orders_placed += 1
                        
                        order_results.append({
                            'stage': stage,
                            'price': dca_price,
                            'quantity': dca_quantity,
                            'order_id': order_result['order_id']
                        })
                        
                        self.logger.info(f"✅ {stage} Re-order placed: {symbol} @ ${dca_price:.4f} (ID: {order_result['order_id']})")
                    
                    else:
                        self.logger.error(f"❌ {stage} Re-order failed: {symbol} - {order_result.get('error', 'Unknown error')}")
                
                except Exception as stage_error:
                    self.logger.error(f"❌ {stage} Re-order processing failed: {stage_error}")
                    continue
            
            # 데이터 Save
            if orders_placed > 0:
                self.save_data()
                self.logger.info(f"🔄 {symbol} DCA 재주문 Complete: {orders_placed}orders placed")
            
            return {
                'orders_placed': orders_placed,
                'order_results': order_results,
                'missing_stages': missing_stages,
                'success': orders_placed > 0
            }
            
        except Exception as e:
            self.logger.error(f"DCA re-order failed {symbol}: {e}")
            return {
                'orders_placed': 0,
                'error': str(e),
                'success': False
            }

    def enter_new_position(self, symbol: str, entry_price: float, balance: float, leverage: float = 10.0) -> Dict[str, Any]:
        """New Position Entry (메인 전략 호환용 래퍼 메서드)"""
        try:
            # Entry 금액 및 Quantity 계산
            entry_amount = balance * self.config['initial_weight']
            position_value = entry_amount * leverage
            quantity = position_value / entry_price

            # 시장가 주문 Execute
            order_result = self._execute_market_order(symbol, quantity, "buy")

            if not order_result['success']:
                return {
                    'success': False,
                    'error': 'Market order failed'
                }

            # DCA Position Add (지정가 주문 자동 Create 포함)
            success = self.add_position(
                symbol=symbol,
                entry_price=entry_price,
                quantity=order_result['filled'],
                notional=position_value,
                leverage=leverage,
                total_balance=balance
            )

            if success:
                return {
                    'success': True,
                    'order_id': order_result['order_id'],
                    'entry_price': entry_price,
                    'quantity': order_result['filled'],
                    'notional': position_value,
                    'position_id': symbol
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to add DCA position'
                }

        except Exception as e:
            self.logger.error(f"Position Entry Failed {symbol}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def check_triggers(self, total_balance: float) -> Dict[str, Any]:
        """DCA 트리거 Confirm - 핵심 로직"""
        try:
            if not self.exchange:
                return {'error': 'Exchange not available'}
            
            results = {}
            
            for symbol, position in list(self.positions.items()):
                if not position.is_active:
                    continue
                
                try:
                    # Current price 조times
                    ticker = self.exchange.fetch_ticker(symbol)
                    current_price = float(ticker['last'])
                    
                    # 트리거 Confirm
                    trigger_result = self._check_position_triggers(symbol, current_price, total_balance)
                    if trigger_result:
                        results[symbol] = trigger_result
                
                except Exception as e:
                    self.logger.error(f"트리거 Confirmation failed {symbol}: {e}")
                    continue
            
            return results
            
        except Exception as e:
            self.logger.error(f"전체 트리거 Confirmation failed: {e}")
            return {'error': str(e)}

    def check_dca_triggers(self, symbol: str, current_price: float) -> Optional[Dict[str, Any]]:
        """메인 전략에서 호출하는 DCA 트리거 Confirm (SuperTrend Exit 포함)"""
        try:
            if symbol not in self.positions:
                return None
            
            position = self.positions[symbol]
            if not position.is_active:
                return None
            
            # Current Profit ratio 계산
            profit_pct = (current_price - position.average_price) / position.average_price
            
            # 1. SuperTrend Exit Confirm (최우선) 🔧 Modify됨
            supertrend_exit = self.check_supertrend_exit_signal(symbol, current_price, position)
            if supertrend_exit:
                # SuperTrend Exit Execute
                success = self._execute_emergency_exit(position, current_price, "supertrend_exit")
                if success:
                    position.supertrend_exit_done = True
                    self.save_data()
                    self.logger.critical(f"🔴 SuperTrend 전량Exit Complete: {symbol}")
                return {
                    'trigger_activated': True,
                    'action': 'supertrend_exit_executed' if success else 'supertrend_exit_failed',
                    'trigger_info': supertrend_exit
                }
            
            # 2. New Exit 시스템 Confirm (2-5순위 Exit)
            new_exit_signal = self.check_new_exit_conditions(symbol, current_price)
            if new_exit_signal:
                success = self.execute_new_exit(symbol, new_exit_signal)
                return {
                    'trigger_activated': True,
                    'action': 'new_exit_executed' if success else 'new_exit_failed',
                    'trigger_info': new_exit_signal
                }
            
            # 3. Legacy DCA 트리거 Confirm
            try:
                balance = self.exchange.fetch_balance() if self.exchange else None
                total_balance = balance.get('USDT', {}).get('free', 100.0) if balance else 100.0
            except:
                total_balance = 100.0
            
            return self._check_position_triggers(symbol, current_price, total_balance)
            
        except Exception as e:
            self.logger.error(f"DCA 트리거 Confirmation failed {symbol}: {e}")
            return None

    def _check_position_triggers(self, symbol: str, current_price: float, total_balance: float) -> Optional[Dict[str, Any]]:
        """count별 Position 트리거 Confirm"""
        try:
            position = self.positions[symbol]
            
            # Current Profit ratio 계산
            profit_pct = (current_price - position.average_price) / position.average_price
            
            # 1. 손절 Confirm (최우선)
            stop_loss_result = self._check_stop_loss_trigger(position, current_price, profit_pct)
            if stop_loss_result:
                return stop_loss_result
            
            # 2. 수익 Exit Confirm
            profit_exit_result = self._check_profit_exit_triggers(position, current_price, profit_pct)
            if profit_exit_result:
                return profit_exit_result
            
            # 3. DCA Add매수 Confirm
            dca_result = self._check_dca_triggers(position, current_price, total_balance, profit_pct)
            if dca_result:
                return dca_result
            
            return None
            
        except Exception as e:
            self.logger.error(f"Position 트리거 Confirmation failed {symbol}: {e}")
            return None

    def _check_stop_loss_trigger(self, position: DCAPosition, current_price: float, profit_pct: float) -> Optional[Dict[str, Any]]:
        """손절 트리거 Confirm - 고급 Exit 시스템 통합"""
        try:
            # 고급 Exit 시스템 우선 Usage
            if self.advanced_exit_system:
                exit_signal = self.advanced_exit_system.check_all_exit_conditions(
                    symbol=position.symbol,
                    current_price=current_price,
                    average_price=position.average_price,
                    current_stage=position.current_stage
                )
                
                if exit_signal:
                    signal_type = exit_signal['signal_type']
                    
                    # 손절 신호인 경우
                    if signal_type == ExitSignalType.ADAPTIVE_STOP_LOSS.value:
                        self.logger.critical(f"🚨 적응형 Stop loss 트리거: {position.symbol}")
                        self.logger.critical(f"   변동성: {exit_signal['volatility_level']}")
                        self.logger.critical(f"   Stop loss률: {exit_signal['stop_loss_pct']:.1f}%")
                        self.logger.critical(f"   Profit ratio: {exit_signal['profit_pct']:.2f}%")
                        
                        # 즉시 전량 Exit
                        success = self._execute_emergency_exit(position, current_price, "adaptive_stop_loss")
                        
                        return {
                            'trigger_activated': True,
                            'action': 'adaptive_stop_loss_executed' if success else 'adaptive_stop_loss_failed',
                            'trigger_info': {
                                'type': '적응형 손절 Exit',
                                'volatility_level': exit_signal['volatility_level'],
                                'stop_loss_pct': exit_signal['stop_loss_pct'],
                                'profit_pct': exit_signal['profit_pct'],
                                'current_stage': exit_signal['current_stage'],
                                'current_price': current_price
                            }
                        }
                    
                    # 기술적 Exit 신호인 경우
                    elif signal_type == ExitSignalType.TECHNICAL_EXIT.value:
                        self.logger.warning(f"🔥 복합 기술적 Exit 트리거: {position.symbol}")
                        self.logger.warning(f"   신호 count수: {exit_signal['signal_count']}")
                        self.logger.warning(f"   Average strength: {exit_signal['avg_strength']:.2f}")
                        
                        # 전량 Exit
                        success = self._execute_emergency_exit(position, current_price, "technical_exit")
                        
                        return {
                            'trigger_activated': True,
                            'action': 'technical_exit_executed' if success else 'technical_exit_failed',
                            'trigger_info': {
                                'type': '복합 기술적 Exit',
                                'signal_count': exit_signal['signal_count'],
                                'avg_strength': exit_signal['avg_strength'],
                                'signals': exit_signal['signals'],
                                'current_price': current_price
                            }
                        }
            
            # 기본 손절 로직 (fallback)
            stop_loss_pct = self.config['stop_loss_by_stage'].get(position.current_stage, -0.10)
            if profit_pct <= stop_loss_pct:
                self.logger.critical(f"🚨 기본 Stop loss 트리거: {position.symbol} ({profit_pct*100:.2f}%)")
                
                # 즉시 전량 Exit
                success = self._execute_emergency_exit(position, current_price, "basic_stop_loss")
                
                return {
                    'trigger_activated': True,
                    'action': 'basic_stop_loss_executed' if success else 'basic_stop_loss_failed',
                    'trigger_info': {
                        'type': '기본 손절 Exit',
                        'stop_loss_pct': stop_loss_pct * 100,
                        'profit_pct': profit_pct * 100,
                        'current_stage': position.current_stage,
                        'current_price': current_price
                    }
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Stop loss trigger check failed {position.symbol}: {e}")
            # Error시 기본 손절 로직으로 fallback
            stop_loss_pct = self.config['stop_loss_by_stage'].get(position.current_stage, -0.10)
            if profit_pct <= stop_loss_pct:
                success = self._execute_emergency_exit(position, current_price, "fallback_stop_loss")
                return {
                    'trigger_activated': True,
                    'action': 'fallback_stop_loss_executed' if success else 'fallback_stop_loss_failed',
                    'trigger_info': {
                        'type': 'Fallback 손절',
                        'error': str(e),
                        'current_price': current_price
                    }
                }
            return None

    def _check_profit_exit_triggers(self, position: DCAPosition, current_price: float, profit_pct: float) -> Optional[Dict[str, Any]]:
        """수익 Exit 트리거 Confirm - 커스텀 Trailing Stop 최우선 적용"""
        try:
            # 🎯 커스텀 Trailing Stop 로직 (최우선)
            if self.config.get('trailing_stop_enabled', False):
                trailing_min = self.config.get('trailing_profit_peak_min', 0.02)  # 2%
                trailing_max = self.config.get('trailing_profit_peak_max', 0.03)  # 3%
                trailing_drawdown = self.config.get('trailing_stop_drawdown', 0.015)  # 1.5%

                # 최고점 추적 시작 조건: 2-3% 수익 달성
                if profit_pct >= trailing_min:
                    # 최고점 갱신
                    if current_price > position.trailing_stop_high:
                        position.trailing_stop_high = current_price
                        position.trailing_stop_active = True

                        # 최고 수익률 기록
                        if profit_pct > position.max_profit_pct:
                            position.max_profit_pct = profit_pct
                            self.logger.info(f"📈 {position.symbol} 최고 수익률 갱신: {profit_pct:.2f}% (${current_price:.6f})")

                    # Trailing Stop 체크: 최고점 대비 하락 감지
                    if position.trailing_stop_active and position.trailing_stop_high > 0:
                        drawdown_from_peak = (position.trailing_stop_high - current_price) / position.trailing_stop_high

                        # 최고점 대비 1.5% 이상 하락 시 전량 청산
                        if drawdown_from_peak >= trailing_drawdown:
                            # 현재 수익률 계산
                            current_profit = (current_price - position.average_price) / position.average_price

                            # 손실 전환 전에만 청산 (현재 수익이 플러스일 때만)
                            if current_profit > 0:
                                self.logger.critical(f"🚨 {position.symbol} Trailing Stop 발동!")
                                self.logger.critical(f"   최고점: ${position.trailing_stop_high:.6f} (최고 수익률: {position.max_profit_pct:.2f}%)")
                                self.logger.critical(f"   현재가: ${current_price:.6f} (현재 수익률: {current_profit*100:.2f}%)")
                                self.logger.critical(f"   최고점 대비 하락: {drawdown_from_peak*100:.2f}%")

                                success = self._execute_emergency_exit(position, current_price, "custom_trailing_stop")

                                return {
                                    'trigger_activated': True,
                                    'action': 'custom_trailing_stop_executed' if success else 'custom_trailing_stop_failed',
                                    'trigger_info': {
                                        'type': '커스텀 Trailing Stop (손실전환 방지)',
                                        'highest_price': position.trailing_stop_high,
                                        'max_profit_pct': position.max_profit_pct * 100,
                                        'current_profit_pct': current_profit * 100,
                                        'drawdown_from_peak': drawdown_from_peak * 100,
                                        'current_price': current_price
                                    }
                                }

            # 🎯 SuperClaude 기본 Exit 시스템 최우선 Usage
            if self.basic_exit_system:
                basic_exit_signal = self.basic_exit_system.check_all_basic_exits(
                    symbol=position.symbol,
                    current_price=current_price,
                    average_price=position.average_price
                )
                
                if basic_exit_signal:
                    exit_type = basic_exit_signal['exit_type']
                    exit_ratio = basic_exit_signal['exit_ratio']
                    
                    self.logger.warning(f"🎯 SuperClaude 기본 Exit 트리거: {position.symbol}")
                    self.logger.warning(f"   Exit Type: {exit_type}")
                    self.logger.warning(f"   Exit 비율: {exit_ratio*100:.0f}%")
                    
                    # Exit Execute
                    if exit_ratio >= 1.0:  # 전량 Exit
                        success = self._execute_emergency_exit(position, current_price, exit_type)
                    else:  # 부분 Exit
                        success = self._execute_partial_exit(position, current_price, exit_ratio, exit_type)
                    
                    # Exit Complete 마킹
                    if success:
                        self.basic_exit_system.mark_exit_completed(position.symbol, exit_type)
                        self.basic_exit_system.send_exit_notification(position.symbol, basic_exit_signal, profit_pct * 100)
                    
                    return {
                        'trigger_activated': True,
                        'action': f"basic_exit_{exit_type}_executed" if success else f"basic_exit_{exit_type}_failed",
                        'trigger_info': {
                            'type': f"SuperClaude 기본 Exit ({exit_type})",
                            'exit_ratio': exit_ratio * 100,
                            'profit_pct': profit_pct * 100,
                            'trigger_details': basic_exit_signal.get('trigger_info', ''),
                            'current_price': current_price
                        }
                    }
            
            # 고급 Exit 시스템 (기본 Exit 시스템 이후)
            if self.advanced_exit_system:
                exit_signal = self.advanced_exit_system.check_all_exit_conditions(
                    symbol=position.symbol,
                    current_price=current_price,
                    average_price=position.average_price,
                    current_stage=position.current_stage
                )
                
                if exit_signal:
                    signal_type = exit_signal['signal_type']
                    
                    # 다Stage 익절 신호
                    if signal_type == ExitSignalType.MULTI_LEVEL_PROFIT.value:
                        self.logger.info(f"💰 {exit_signal['level_name']} Take profit trigger: {position.symbol}")
                        self.logger.info(f"   Profit ratio: {exit_signal['profit_pct']:.2f}%")
                        self.logger.info(f"   Exit비율: {exit_signal['exit_ratio']*100:.0f}%")
                        
                        success = self._execute_partial_exit(
                            position, current_price, 
                            exit_signal['exit_ratio'], 
                            f"multi_level_{exit_signal['level_name']}"
                        )
                        
                        return {
                            'trigger_activated': True,
                            'action': f"multi_level_executed" if success else f"multi_level_failed",
                            'trigger_info': {
                                'type': f"다Stage 익절 ({exit_signal['level_name']})",
                                'profit_pct': exit_signal['profit_pct'],
                                'exit_ratio': exit_signal['exit_ratio'] * 100,
                                'level_name': exit_signal['level_name'],
                                'current_price': current_price
                            }
                        }
                    
                    # Trailing 스톱 신호
                    elif signal_type == ExitSignalType.TRAILING_STOP.value:
                        self.logger.info(f"🛑 Trailing stop trigger: {position.symbol}")
                        self.logger.info(f"   Highest price: ${exit_signal['highest_price']:.6f}")
                        self.logger.info(f"   Trailing price: ${exit_signal['trailing_price']:.6f}")
                        self.logger.info(f"   Trailing: {exit_signal['trailing_pct']:.1f}%")
                        
                        success = self._execute_emergency_exit(position, current_price, "trailing_stop")
                        
                        return {
                            'trigger_activated': True,
                            'action': 'trailing_stop_executed' if success else 'trailing_stop_failed',
                            'trigger_info': {
                                'type': 'Trailing 스톱',
                                'highest_price': exit_signal['highest_price'],
                                'trailing_price': exit_signal['trailing_price'],
                                'trailing_pct': exit_signal['trailing_pct'],
                                'current_price': current_price
                            }
                        }
            
            # DCA Stage별 Exit Confirm (손실~10% 미만 수익 구간에서 Execute)
            # DCA 부분Exit은 손실 구간에서도 Execute되어야 함 (Average price 최적화 목적)
            stage_exit_result = self._check_stage_exit_triggers(position, current_price, profit_pct)
            if stage_exit_result:
                return stage_exit_result
            
            return None
            
        except Exception as e:
            self.logger.error(f"수익 Exit 트리거 Confirmation failed {position.symbol}: {e}")
            # Error시에도 기본 10% 절반Exit Remove (BB600 돌파 50% Exit만 Maintain)
            return None

    def _check_stage_exit_triggers(self, position: DCAPosition, current_price: float, profit_pct: float) -> Optional[Dict[str, Any]]:
        """Stage별 Exit 트리거 Confirm - DCA 부분Exit 로직 (손실~본절 구간 전용)"""
        
        # 🚨 DCA 부분Exit은 손실 구간에서만 Execute (Average price 최적화 목적)
        # 10% 이상 수익시에는 DCA 부분Exit 차단 (기술적 Exit만 Usage)
        if profit_pct >= 0.10:
            return None
        
        # 🎯 2차 DCA Stage: 1차 Entry가 times복시 2차 DCA 물량만 부분Exit
        if position.current_stage == PositionStage.SECOND_DCA.value:
            first_dca_entries = [e for e in position.entries if e.stage == "first_dca" and e.is_active and e.is_filled]
            if first_dca_entries:
                first_dca_price = first_dca_entries[0].entry_price
                
                # 1차 Entry가 times복시 2차 DCA 물량 부분Exit (손실 구간에서만)
                if current_price >= first_dca_price:
                    self.logger.info(f"📈 2차 DCA 부분Exit: {position.symbol} - 1차 Entry가 times복 (Average price 최적화)")
                    
                    success = self._execute_stage_exit(position, current_price, "second_dca")
                    
                    return {
                        'trigger_activated': True,
                        'action': 'second_dca_exit_executed' if success else 'second_dca_exit_failed',
                        'trigger_info': {
                            'type': '2차 DCA 부분Exit',
                            'target_price': first_dca_price,
                            'current_price': current_price,
                            'profit_pct': profit_pct * 100,
                            'purpose': 'Average price 최적화 (손실 구간)'
                        }
                    }
        
        # 🎯 1차 DCA Stage: 최초 Entry가 times복시 1차 DCA 물량만 부분Exit
        elif position.current_stage == PositionStage.FIRST_DCA.value:
            # 최초 Entry가 times복시 1차 DCA 물량 부분Exit (손실 구간에서만)
            if current_price >= position.initial_entry_price:
                self.logger.info(f"📈 1차 DCA 부분Exit: {position.symbol} - 최초 Entry가 times복 (Average price 최적화)")
                
                success = self._execute_stage_exit(position, current_price, "first_dca")
                
                return {
                    'trigger_activated': True,
                    'action': 'first_dca_exit_executed' if success else 'first_dca_exit_failed',
                    'trigger_info': {
                        'type': '1차 DCA 부분Exit',
                        'target_price': position.initial_entry_price,
                        'current_price': current_price,
                        'profit_pct': profit_pct * 100,
                        'purpose': 'Average price 최적화 (손실 구간)'
                    }
                }
        
        return None

    def _check_dca_triggers(self, position: DCAPosition, current_price: float, total_balance: float, profit_pct: float) -> Optional[Dict[str, Any]]:
        """DCA Add매수 트리거 Confirm (지정가 주문은 최초 Entry시 이미 Create됨)"""

        # 5% 이상 수익시 Add매수 차단
        if profit_pct >= 0.05:
            return None

        # 📋 지정가 주문은 최초 Entry시 자동 Create되므로 여기서는 체결 Status만 Confirm
        # check_and_update_limit_orders() 메서드가 주기적으로 호출되어 체결 Status Update

        # 🔄 Cyclic trading 재Entry 체크 (Cyclic trading시에는 New 지정가 주문 Create Required)
        cyclic_reentry_result = self._check_cyclic_reentry(position, current_price, total_balance, profit_pct)
        if cyclic_reentry_result:
            return cyclic_reentry_result

        return None

    def _check_cyclic_reentry(self, position: DCAPosition, current_price: float, total_balance: float, profit_pct: float) -> Optional[Dict[str, Any]]:
        """Cyclic trading 재Entry 체크"""
        try:
            # Cyclic trading 재Entry 조건 체크
            if (position.current_stage == PositionStage.INITIAL.value and 
                position.cyclic_state == CyclicState.CYCLIC_PAUSED.value and
                profit_pct <= self.config['first_dca_trigger']):
                
                # Cyclic trading 제한 체크
                if position.cyclic_count >= position.max_cyclic_count:
                    self.logger.warning(f"🚫 Cyclic trading 제한 Exceeded: {position.symbol} - {position.cyclic_count}/{position.max_cyclic_count}times")
                    return None
                
                self.logger.info(f"🔄 Cyclic trading 재Entry 트리거: {position.symbol} ({position.cyclic_count + 1}/{position.max_cyclic_count}times차) (Drop rate {abs(profit_pct)*100:.2f}%)")
                
                # 1차 DCA 재Starting
                success = self._execute_first_dca(position, current_price, total_balance)
                
                if success:
                    # Cyclic trading Status Update
                    position.cyclic_state = CyclicState.CYCLIC_ACTIVE.value
                
                return {
                    'trigger_activated': True,
                    'action': 'cyclic_reentry_executed' if success else 'cyclic_reentry_failed',
                    'trigger_info': {
                        'type': f'Cyclic trading 재Entry ({position.cyclic_count}/{position.max_cyclic_count}times차)',
                        'drop_pct': abs(profit_pct) * 100,
                        'current_price': current_price
                    }
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Cyclic trading 체크 Failed {position.symbol}: {e}")
            return None

    def _execute_first_dca(self, position: DCAPosition, current_price: float, total_balance: float) -> bool:
        """1차 DCA Execute (지정가 주문)"""
        try:
            # Add매수 금액 계산
            dca_amount = total_balance * self.config['first_dca_weight']
            leverage = self.config['first_dca_leverage']
            
            # 1차 DCA 트리거 가격 계산 (-3% 하락가)
            dca_trigger_price = position.initial_entry_price * (1 + self.config['first_dca_trigger'])
            quantity = (dca_amount * leverage) / dca_trigger_price
            
            # 지정가 주문 Execute
            order_result = self._execute_limit_order(position.symbol, quantity, "buy", dca_trigger_price)
            if not order_result['success']:
                self.logger.error(f"1차 DCA limit order Failed: {position.symbol}")
                return False
            
            # DCA Entry 기록 (미체결 Status로 Starting)
            dca_entry = DCAEntry(
                stage="first_dca",
                entry_price=dca_trigger_price,
                quantity=quantity,
                notional=dca_amount * leverage,
                leverage=leverage,
                timestamp=get_korea_time().isoformat(),
                is_active=True,
                order_type="limit",
                order_id=order_result['order_id'],
                is_filled=False  # 지정가 주문은 미체결로 Starting
            )
            
            position.entries.append(dca_entry)
            
            # Position Status Update (아직 체결되지 않았으므로 Average price는 Change하지 않음)
            position.current_stage = PositionStage.FIRST_DCA.value
            position.last_update = get_korea_time().isoformat()
            
            # 데이터 Save
            self.save_data()
            
            self.logger.info(f"✅ 1차 DCA limit order placed: {position.symbol} - 주문가: ${dca_trigger_price:.4f}, Quantity: {quantity:.4f}")
            
            # 텔레그램 Notification
            if self.telegram_bot:
                message = (f"📋 1차 DCA limit order placed\n"
                          f"Symbol: {position.symbol}\n"
                          f"주문가: ${dca_trigger_price:.4f} (-3%)\n"
                          f"Quantity: {quantity:.4f}\n"
                          f"주문ID: {order_result['order_id']}")
                self.telegram_bot.send_message(message)
            
            return True
            
        except Exception as e:
            self.logger.error(f"1차 DCA Execute Failed {position.symbol}: {e}")
            return False

    def _execute_second_dca(self, position: DCAPosition, current_price: float, total_balance: float) -> bool:
        """2차 DCA Execute (지정가 주문)"""
        try:
            # Add매수 금액 계산
            dca_amount = total_balance * self.config['second_dca_weight']
            leverage = self.config['second_dca_leverage']
            
            # 2차 DCA 트리거 가격 계산 (-6% 하락가)
            dca_trigger_price = position.initial_entry_price * (1 + self.config['second_dca_trigger'])
            quantity = (dca_amount * leverage) / dca_trigger_price
            
            # 지정가 주문 Execute
            order_result = self._execute_limit_order(position.symbol, quantity, "buy", dca_trigger_price)
            if not order_result['success']:
                self.logger.error(f"2차 DCA limit order Failed: {position.symbol}")
                return False
            
            # DCA Entry 기록 (미체결 Status로 Starting)
            dca_entry = DCAEntry(
                stage="second_dca",
                entry_price=dca_trigger_price,
                quantity=quantity,
                notional=dca_amount * leverage,
                leverage=leverage,
                timestamp=get_korea_time().isoformat(),
                is_active=True,
                order_type="limit",
                order_id=order_result['order_id'],
                is_filled=False  # 지정가 주문은 미체결로 Starting
            )
            
            position.entries.append(dca_entry)
            
            # Position Status Update (아직 체결되지 않았으므로 Average price는 Change하지 않음)
            position.current_stage = PositionStage.SECOND_DCA.value
            position.last_update = get_korea_time().isoformat()
            
            # 🔄 Cyclic trading 카운트 증가 로직 (2차 DCA 주문 Register 시 Cyclic trading 1times 카운팅)
            position.cyclic_count += 1
            position.cyclic_state = CyclicState.CYCLIC_ACTIVE.value
            position.last_cyclic_entry = get_korea_time().isoformat()
            
            # Cyclic trading 제한 체크
            if position.cyclic_count >= position.max_cyclic_count:
                position.cyclic_state = CyclicState.CYCLIC_COMPLETE.value
                self.logger.warning(f"🔴 Cyclic trading Complete: {position.symbol} - 최대 횟수 {position.max_cyclic_count}times 달성")
            
            # 데이터 Save
            self.save_data()
            
            self.logger.info(f"✅ 2차 DCA limit order placed: {position.symbol} - 주문가: ${dca_trigger_price:.4f}, Quantity: {quantity:.4f} (Cyclic trading {position.cyclic_count}/{position.max_cyclic_count}times차)")
            
            # 텔레그램 Notification
            if self.telegram_bot:
                cyclic_status = "Complete" if position.cyclic_state == CyclicState.CYCLIC_COMPLETE.value else "Progress중"
                message = (f"📋 2차 DCA limit order placed (Cyclic trading {position.cyclic_count}times차)\n"
                          f"Symbol: {position.symbol}\n"
                          f"주문가: ${dca_trigger_price:.4f} (-6%)\n"
                          f"Quantity: {quantity:.4f}\n"
                          f"주문ID: {order_result['order_id']}\n"
                          f"🔄 Cyclic trading Status: {cyclic_status}")
                self.telegram_bot.send_message(message)
            
            return True
            
        except Exception as e:
            self.logger.error(f"2차 DCA Execute Failed {position.symbol}: {e}")
            return False

    def _execute_emergency_exit(self, position: DCAPosition, current_price: float, reason: str) -> bool:
        """긴급 전량 Exit (미체결 지정가 주문 Auto cancel 포함)"""
        try:
            # 1. 미체결 지정가 주문 Cancel
            cancel_result = self._cancel_pending_orders(position.symbol)
            if cancel_result['success'] and cancel_result['cancelled_count'] > 0:
                self.logger.info(f"📋 Pending order cancel: {position.symbol} - {cancel_result['cancelled_count']}count 주문 Cancel")
            
            # 2. 🚨 버그 Modify: 실제 Trade소 Position 기준으로 Exit량 계산
            try:
                # Trade소에서 Actual position Quantity 조times
                actual_positions = self.exchange.fetch_positions([position.symbol])
                actual_quantity = 0
                
                for pos in actual_positions:
                    if pos['symbol'] == position.symbol and float(pos.get('contracts', 0)) != 0:
                        actual_quantity = abs(float(pos.get('contracts', 0)))
                        break
                
                if actual_quantity <= 0:
                    self.logger.warning(f"Exit할 No position: {position.symbol} - Actual position: {actual_quantity}")
                    # DCA 데이터도 Sync
                    position.is_active = False
                    position.total_quantity = 0
                    self.save_data()
                    return False
                
                # Actual position Quantity Usage (Legacy entries 기준 대신)
                total_quantity = actual_quantity
                self.logger.info(f"🔄 Actual position 기준 Exit: {position.symbol} - {total_quantity}")
                
            except Exception as e:
                self.logger.error(f"Actual position 조times Failed: {position.symbol} - {e}")
                # Backup: DCA record total_quantity Usage (entries 합계 대신)
                total_quantity = position.total_quantity
                if total_quantity <= 0:
                    self.logger.warning(f"Exit할 No position (Backup): {position.symbol} - DCA record: {total_quantity}")
                    return False
            
            # 3. 전량 매도 주문 (시장가)
            order_result = self._execute_market_order(position.symbol, total_quantity, "sell")
            
            # silent 플래그 Process
            silent = order_result.get('silent', False)
            
            if order_result['success']:
                # Position 정리
                position.is_active = False
                position.current_stage = PositionStage.CLOSING.value
                position.last_update = get_korea_time().isoformat()
                
                # 모든 Entry 비Active화
                for entry in position.entries:
                    entry.is_active = False
                
                # 메인 전략 Sync
                if self.strategy and hasattr(self.strategy, 'active_positions'):
                    if position.symbol in self.strategy.active_positions:
                        del self.strategy.active_positions[position.symbol]
                
                # New Exit 시스템 Status Initialize (Complete)
                # Legacy basic_exit_system Remove됨 - New 4가지 Exit 방식 Usage
                
                # 데이터 Save
                self.save_data()
                
                # Profit ratio 계산
                profit_pct = (current_price - position.average_price) / position.average_price * 100
                
                # Exit Type별 Message Create
                exit_emoji, exit_title, exit_description = self._get_exit_message_info(reason, profit_pct, position)
                
                self.logger.critical(f"{exit_emoji} {exit_title}: {position.symbol} - Profit ratio: {profit_pct:.2f}% (Reason: {reason})")
                
                # 텔레그램 Notification
                if self.telegram_bot:
                    message = (f"{exit_emoji} {exit_title}\n"
                              f"Symbol: {position.symbol}\n"
                              f"Exit가: ${current_price:.4f}\n"
                              f"Profit ratio: {profit_pct:.2f}%\n"
                              f"상세: {exit_description}")
                    self.telegram_bot.send_message(message)
                
                return {'success': True, 'silent': silent}
            
            return {'success': False, 'silent': silent}
            
        except Exception as e:
            self.logger.error(f"긴급 Exit Failed {position.symbol}: {e}")
            return {'success': False, 'silent': False}

    def _get_exit_message_info(self, reason: str, profit_pct: float, position: DCAPosition) -> Tuple[str, str, str]:
        """Exit Type별 Message Info Create"""
        try:
            reason_lower = reason.lower()
            max_profit_pct = getattr(position, 'max_profit_pct', 0) * 100  # 최대 Profit ratio을 %로 변환
            
            # SuperTrend 전량Exit
            if 'supertrend' in reason_lower:
                return "📈", "SuperTrend 전량Exit Complete", f"트렌드 반전 감지 Exit"
            
            # 본절 보호Exit (breakeven_protection)
            elif 'breakeven_protection' in reason_lower:
                half_threshold = max_profit_pct * 0.5
                return "🛡️", "절반 하락 보호Exit Complete", f"최대 {max_profit_pct:.1f}% → {profit_pct:.1f}% (Threshold {half_threshold:.1f}%)"
            
            # Approx상승 후 급락 리스크 times피
            elif 'weak_rise_dump' in reason_lower or 'dump_protection' in reason_lower:
                return "⚡", "급락 리스크 times피Exit Complete", f"Approx상승 후 급락 패턴 감지"
            
            # BB600 익절Exit
            elif 'bb600' in reason_lower:
                return "🎯", "BB600 익절Exit Complete", f"볼린저밴드 상단 돌파 후 50% 익절"
            
            # DCA Cyclic trading 부분Exit
            elif 'cyclic' in reason_lower:
                return "🔄", "Cyclic trading 부분Exit Complete", f"5%+ 수익에서 30% 부분Exit"
            
            # Trailing 스톱
            elif 'trailing' in reason_lower:
                return "📉", "Trailing 스톱 Exit Complete", f"고점 vs 5% 하락 감지"
            
            # Other (Legacy 긴급Exit)
            else:
                return "🚨", "긴급 Exit Complete", f"Reason: {reason}"
                
        except Exception as e:
            self.logger.error(f"Exit Message Create Failed: {e}")
            return "🚨", "긴급 Exit Complete", f"Reason: {reason}"

    def _execute_partial_exit(self, position: DCAPosition, current_price: float, ratio: float, reason: str) -> bool:
        """부분 Exit (체결된 Position만 대상)"""
        try:
            # 체결된 Position만으로 Exit할 Quantity 계산
            filled_entries = [e for e in position.entries if e.is_active and e.is_filled]
            total_filled_quantity = sum(e.quantity for e in filled_entries)
            exit_quantity = total_filled_quantity * ratio
            
            if exit_quantity <= 0:
                self.logger.warning(f"부분 Exit할 Quantity Absent: {position.symbol} - 체결된 Quantity: {total_filled_quantity}")
                return False
            
            # 부분 매도 주문 (시장가)
            order_result = self._execute_market_order(position.symbol, exit_quantity, "sell")
            
            if order_result['success']:
                # 🚨 Modify: 부분Exit 시 비례적으로 모든 Entry에서 Exit (특정 Entry 전체 Delete 방지)
                remaining_to_exit = exit_quantity
                total_active_quantity = sum(e.quantity for e in position.entries if e.is_active)
                
                if total_active_quantity > 0:
                    # 비례적 부분Exit: 각 Entry에서 비율만큼 차감
                    exit_ratio_per_entry = remaining_to_exit / total_active_quantity
                    
                    for entry in position.entries:
                        if entry.is_active and exit_ratio_per_entry > 0:
                            entry_exit_qty = entry.quantity * exit_ratio_per_entry
                            
                            # Entry Quantity 차감 (전체 Delete하지 않고 비율만큼만)
                            entry.quantity -= entry_exit_qty
                            entry.notional = entry.quantity * entry.entry_price
                            
                            # 🚨 Modify: 극소량도 Maintain (0에 가까워도 완전 Delete하지 않음)
                            if entry.quantity < 0.000001:  # 최소 보유량
                                entry.quantity = 0.000001
                                entry.notional = entry.quantity * entry.entry_price
                            
                            self.logger.debug(f"   Entry {entry.stage}: {entry.quantity + entry_exit_qty:.6f} → {entry.quantity:.6f}")
                
                # Position Info Update - 스레드 안전성 강화
                with self.sync_lock:  # 스레드 안전성 보장
                    active_entries = [e for e in position.entries if e.is_active]
                    
                    # 🚨 Modify: 부분Exit은 항상 Position을 Maintain (완전 Delete 방지)
                    if active_entries and ratio < 1.0:  # 부분Exit인 경우
                        # Legacy Average price Backup (로깅용)
                        old_avg_price = position.average_price
                        old_quantity = position.total_quantity
                        
                        # Average price 재계산 (가중평균)
                        new_quantity = sum(e.quantity for e in active_entries)
                        new_notional = sum(e.notional for e in active_entries)
                        total_cost = sum(e.quantity * e.entry_price for e in active_entries)
                        new_avg_price = total_cost / new_quantity if new_quantity > 0 else current_price
                        
                        # Change사항 Verification
                        price_change_pct = abs(new_avg_price - old_avg_price) / old_avg_price * 100 if old_avg_price > 0 else 0
                        quantity_change_pct = abs(new_quantity - old_quantity) / old_quantity * 100 if old_quantity > 0 else 0
                        
                        # Position Info Update
                        position.total_quantity = new_quantity
                        position.total_notional = new_notional
                        position.average_price = new_avg_price
                        
                        # 🚨 중요: 부분Exit 후에도 Position Active Status Maintain
                        position.is_active = True
                        
                        # 상세 로깅 (부분 Exit 후 Average price change)
                        self.logger.info(f"💰 부분 Exit 후 Average price 재계산: {position.symbol}")
                        self.logger.info(f"   이전 Average price: ${old_avg_price:.6f} → 새 Average price: ${new_avg_price:.6f} ({price_change_pct:+.2f}%)")
                        self.logger.info(f"   이전 Quantity: {old_quantity:.6f} → 새 Quantity: {new_quantity:.6f} ({quantity_change_pct:+.2f}%)")
                        self.logger.info(f"   잔여 Entry: {len(active_entries)}count")
                        self.logger.info(f"   🚨 부분Exit 후 Position Maintain: TAO 신호 등 Continue additional monitoring")
                    else:
                        # 전량 Exit됨 또는 ratio >= 1.0
                        self.logger.warning(f"🏁 전량 Exit Complete: {position.symbol}")
                        position.is_active = False
                        position.current_stage = PositionStage.CLOSING.value
                        
                        # New Exit 시스템 Status Initialize (전량 Exit시 - Complete)
                        # Legacy basic_exit_system Remove됨 - New 4가지 Exit 방식 Usage
                        self.logger.info(f"🔄 New Exit System Status Initialize: {position.symbol}")
                    
                    position.last_update = get_korea_time().isoformat()
                
                # 데이터 Save
                self.save_data()
                
                # Profit ratio 계산
                profit_pct = (current_price - position.average_price) / position.average_price * 100
                
                self.logger.info(f"💰 부분 Exit Complete: {position.symbol} - {ratio*100:.0f}% Exit, Profit ratio: {profit_pct:.2f}% (Reason: {reason})")
                
                # 텔레그램 Notification
                if self.telegram_bot:
                    message = (f"💰 부분 Exit Complete\n"
                              f"Symbol: {position.symbol}\n"
                              f"Exit가: ${current_price:.4f}\n"
                              f"Exit비율: {ratio*100:.0f}%\n"
                              f"Profit ratio: {profit_pct:.2f}%\n"
                              f"Reason: {reason}")
                    self.telegram_bot.send_message(message)
                
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"부분 Exit Failed {position.symbol}: {e}")
            return False

    def _execute_stage_exit(self, position: DCAPosition, current_price: float, target_stage: str) -> bool:
        """Stage별 Exit"""
        try:
            # 대상 Stage의 Entry 찾기
            target_entries = [e for e in position.entries if e.stage == target_stage and e.is_active]
            if not target_entries:
                self.logger.warning(f"Stage별 Exit 대상 Absent: {position.symbol} - {target_stage}")
                return False
            
            # 🚨 버그 Modify: Actual holding 중인 해당 Stage Quantity만 Exit
            try:
                # 실제 Trade소 Position 조times
                actual_positions = self.exchange.fetch_positions([position.symbol])
                actual_total_quantity = 0
                
                for pos in actual_positions:
                    if pos['symbol'] == position.symbol and float(pos.get('contracts', 0)) != 0:
                        actual_total_quantity = abs(float(pos.get('contracts', 0)))
                        break
                
                if actual_total_quantity <= 0:
                    self.logger.warning(f"Stage별 Exit 불가: {position.symbol} - Actual position: {actual_total_quantity}")
                    return False
                
                # DCA record 기준 해당 Stage Quantity
                entries_stage_quantity = sum(e.quantity for e in target_entries)
                
                # 실제 Exit할 Quantity = min(기록상 Stage Quantity, Actual holding Quantity)
                stage_quantity = min(entries_stage_quantity, actual_total_quantity)
                
                self.logger.info(f"🔄 Stage별 Exit Quantity 조정: {position.symbol}")
                self.logger.info(f"   대상 Stage: {target_stage}")
                self.logger.info(f"   기록상 Quantity: {entries_stage_quantity}")
                self.logger.info(f"   Actual holding: {actual_total_quantity}")
                self.logger.info(f"   Exit Quantity: {stage_quantity}")
                
            except Exception as e:
                self.logger.error(f"Actual position 조times Failed: {position.symbol} - {e}")
                # Backup: 기록 기준 (위험하지만 완전 Failed보다는 나음)
                stage_quantity = sum(e.quantity for e in target_entries)
                self.logger.warning(f"Backup Exit량 Usage: {position.symbol} - {stage_quantity}")
            
            # Stage별 매도 주문
            order_result = self._execute_market_order(position.symbol, stage_quantity, "sell")
            
            if order_result['success']:
                # 대상 Stage Entry 비Active화
                for entry in target_entries:
                    entry.is_active = False
                
                # Position Info Update - 스레드 안전성 강화
                with self.sync_lock:  # 스레드 안전성 보장
                    active_entries = [e for e in position.entries if e.is_active]
                    if active_entries:
                        # Legacy Average price Backup (로깅용)
                        old_avg_price = position.average_price
                        old_quantity = position.total_quantity
                        old_stage = position.current_stage
                        
                        # Average price 재계산 (가중평균)
                        new_quantity = sum(e.quantity for e in active_entries)
                        new_notional = sum(e.notional for e in active_entries)
                        total_cost = sum(e.quantity * e.entry_price for e in active_entries)
                        new_avg_price = total_cost / new_quantity if new_quantity > 0 else current_price
                        
                        # Change사항 Verification
                        price_change_pct = abs(new_avg_price - old_avg_price) / old_avg_price * 100 if old_avg_price > 0 else 0
                        quantity_change_pct = abs(new_quantity - old_quantity) / old_quantity * 100 if old_quantity > 0 else 0
                        
                        # Position Info Update
                        position.total_quantity = new_quantity
                        position.total_notional = new_notional
                        position.average_price = new_avg_price
                        
                        # Stage Update
                        if target_stage == "second_dca":
                            position.current_stage = PositionStage.FIRST_DCA.value
                        elif target_stage == "first_dca":
                            position.current_stage = PositionStage.INITIAL.value
                        
                        # 상세 로깅 (Stage별 Exit 후 Average price change)
                        self.logger.info(f"📈 Stage별 Exit 후 Average price 재계산: {position.symbol}")
                        self.logger.info(f"   Exit Stage: {target_stage}")
                        self.logger.info(f"   Exit Quantity: {stage_quantity:.6f}")
                        self.logger.info(f"   이전 Average price: ${old_avg_price:.6f} → 새 Average price: ${new_avg_price:.6f} ({price_change_pct:+.2f}%)")
                        self.logger.info(f"   이전 Quantity: {old_quantity:.6f} → 새 Quantity: {new_quantity:.6f} ({quantity_change_pct:+.2f}%)")
                        self.logger.info(f"   Position Stage: {old_stage} → {position.current_stage}")
                        self.logger.info(f"   잔여 Entry: {len(active_entries)}count")
                    else:
                        # 전량 Exit됨
                        self.logger.warning(f"🏁 Stage별 Exit으로 전량 Exit: {position.symbol}")
                        position.is_active = False
                        position.current_stage = PositionStage.CLOSING.value
                    
                    position.last_update = get_korea_time().isoformat()
                
                # 데이터 Save
                self.save_data()
                
                # Profit ratio 계산
                profit_pct = (current_price - position.average_price) / position.average_price * 100
                
                # 🔄 Cyclic trading 수익 Cumulative
                stage_profit = (current_price - sum(e.entry_price for e in target_entries) / len(target_entries)) * stage_quantity
                position.total_cyclic_profit += stage_profit
                
                # 🔄 Cyclic trading 재Entry 체크 (전량 Exit이 아닌 경우에만)
                cyclic_reentry_triggered = False
                if active_entries and position.cyclic_state == CyclicState.CYCLIC_ACTIVE.value:
                    # 1차 DCA Stage로 돌아간 경우 Cyclic trading 재Entry 대기 Status로 전환
                    if position.current_stage == PositionStage.INITIAL.value:
                        position.cyclic_state = CyclicState.CYCLIC_PAUSED.value
                        cyclic_reentry_triggered = True
                        self.logger.info(f"🔄 Cyclic trading 재Entry Waiting: {position.symbol} - 다음 -3% 하락시 Cyclic trading 재Starting")
                
                self.logger.info(f"📈 Stage별 Exit Complete: {position.symbol} - {target_stage} Exit, Profit ratio: {profit_pct:.2f}%{' (Cyclic trading 재Entry Waiting)' if cyclic_reentry_triggered else ''}")
                
                # 텔레그램 Notification
                if self.telegram_bot:
                    # 해당 Stage 평균 Entry가 계산
                    stage_avg_price = sum(e.entry_price for e in target_entries) / len(target_entries) if target_entries else 0

                    cyclic_info = ""
                    if position.cyclic_state != CyclicState.NORMAL_DCA.value:
                        cyclic_info = f"\n🔄 Cyclic trading: {position.cyclic_count}/{position.max_cyclic_count}times차"
                        if cyclic_reentry_triggered:
                            cyclic_info += " (재Entry 대기)"

                    message = (f"📈 Stage별 Exit Complete\n"
                              f"Symbol: {position.symbol}\n"
                              f"Exit Stage: {target_stage}\n"
                              f"Entry가: ${stage_avg_price:.4f}\n"
                              f"Exit가: ${current_price:.4f}\n"
                              f"Exit Quantity: {stage_quantity:.6f}\n"
                              f"Profit ratio: {profit_pct:.2f}%"
                              f"{cyclic_info}")
                    self.telegram_bot.send_message(message)
                
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Stage별 Exit Failed {position.symbol}: {e}")
            return False

    def _execute_market_order(self, symbol: str, quantity: float, side: str) -> Dict[str, Any]:
        """시장가 주문 Execute (초기 Entry 및 Exit용) - Rate Limit 대응 강화"""
        try:
            if not self.exchange:
                return {'success': False, 'error': 'Exchange not available'}
            
            # Rate Limit 체크 - 418 에러 방지
            if (hasattr(self.strategy, '_api_rate_limited') and 
                self.strategy._api_rate_limited):
                self.logger.warning(f"🚨 Rate Limit Status - 시장가 주문 너뛰기: {symbol}")
                return {'success': False, 'error': 'Rate limited - skip market order'}
            
            # Quantity Verification 및 정밀도 조정
            validated_amount = self._validate_order_amount(symbol, abs(quantity))
            if validated_amount <= 0:
                error_msg = f"주문량 Verification Failed: {symbol} - 원래량: {quantity}, Verification후: {validated_amount}"
                self.logger.warning(error_msg)
                return {'success': False, 'error': error_msg}
            
            # 최소 주문 금액 체크 (바이낸스 $5 요구사항)
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                current_price = ticker['last']
                notional_value = validated_amount * current_price
                
                if notional_value < 5.0:  # $5 미만
                    # 조용히 Process - Error Log 출력하지 않음
                    self.logger.debug(f"🔕 소액 Position Exit 너뛰기: {symbol} - 주문금액: ${notional_value:.2f} < $5")
                    return {'success': False, 'error': 'notional_too_small', 'silent': True}
                    
            except Exception as price_error:
                # 가격 조times Failed해도 주문은 Attempt (Legacy 로직 Maintain)
                self.logger.debug(f"가격 조times Failed하여 최소금액 체크 생략: {symbol} - {price_error}")
                pass
            
            # 주문 Execute (Rate Limit 대응)
            try:
                order = self.exchange.create_market_order(
                    symbol=symbol,
                    side=side,
                    amount=validated_amount
                )
            except ccxt.RateLimitExceeded as e:
                self.logger.error(f"🚨 Rate Limit Exceeded - 시장가 Order failed: {symbol} {side} {quantity} - {e}")
                return {'success': False, 'error': f'Rate limit exceeded: {str(e)}'}
            except Exception as e:
                # 418 에러 등 Other API 에러 Process
                if "418" in str(e) or "too many requests" in str(e).lower():
                    self.logger.error(f"🚨 API 과부하 - 시장가 Order failed: {symbol} {side} {quantity} - {e}")
                    # Rate Limit Status 플래그 Settings (있는 경우)
                    if hasattr(self.strategy, '_api_rate_limited'):
                        self.strategy._api_rate_limited = True
                    return {'success': False, 'error': f'API overload: {str(e)}'}
                elif "notional must be no smaller than 5" in str(e):
                    # 최소 주문 금액 Error - 조용히 Process
                    self.logger.debug(f"🔕 최소 주문금액 부족으로 Exit 너뛰기: {symbol} - 주문량: {quantity}")
                    return {'success': False, 'error': 'notional_too_small', 'silent': True}
                else:
                    raise e
            
            if order and order.get('id'):
                self.logger.info(f"시장가 주문 Success: {symbol} {side} {quantity} - ID: {order['id']}")
                return {
                    'success': True,
                    'order_id': order['id'],
                    'filled': order.get('filled', quantity),
                    'price': order.get('average', 0),
                    'order_type': 'market'
                }
            else:
                self.logger.error(f"시장가 Order failed: {symbol} {side} {quantity}")
                return {'success': False, 'error': 'Market order creation failed'}
                
        except Exception as e:
            # 418 에러 등 전체적인 API 에러 Process
            if "418" in str(e) or "too many requests" in str(e).lower():
                self.logger.error(f"🚨 API 과부하로 인한 시장가 주문 Execute Failed: {symbol} {side} {quantity} - {e}")
            elif "notional must be no smaller than 5" in str(e):
                # 최소 주문 금액 Error - 조용히 Process
                self.logger.debug(f"🔕 최소 주문금액 부족으로 Exit 너뛰기: {symbol} - 주문량: {quantity}")
                return {'success': False, 'error': 'notional_too_small', 'silent': True}
            else:
                self.logger.error(f"시장가 주문 Execute Failed: {symbol} {side} {quantity} - {e}")
            return {'success': False, 'error': str(e)}

    def _validate_order_amount(self, symbol: str, amount: float) -> float:
        """주문량 Verification 및 정밀도 조정"""
        try:
            # Symbol별 최소 정밀도 Settings (TAO는 3자리)
            precision_map = {
                'TAO/USDT:USDT': 3,
                'TAO/USDT': 3,
            }
            
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            precision = precision_map.get(symbol, 4)  # 기본 4자리
            
            # 정밀도에 맞게 반올림
            validated_amount = round(amount, precision)
            
            # Symbol별 최소 주문량 Settings
            min_amounts = {
                'TAO/USDT:USDT': 0.001,  # TAO 최소 0.001
                'TAO/USDT': 0.001,
            }
            
            min_amount = min_amounts.get(symbol, 0.0001)  # 기본 최소량
            
            # 최소 주문량 Confirm
            if validated_amount < min_amount:
                self.logger.warning(f"주문량이 최소량보다 작음: {symbol} - {validated_amount} < {min_amount}")
                return 0.0
            
            return validated_amount
            
        except Exception as e:
            self.logger.error(f"주문량 Verification Failed {symbol}: {e}")
            return amount  # Error 시 원래 값 반환

    def _execute_limit_order(self, symbol: str, quantity: float, side: str, price: float) -> Dict[str, Any]:
        """지정가 주문 Execute (DCA Entry용) - 안전장치 강화"""
        try:
            if not self.exchange:
                return {'success': False, 'error': 'Exchange not available'}
            
            # 🔒 Add 안전장치: Current price와 지정가 비교
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                current_price = ticker['last']
                
                # 매수 지정가 주문: 지정가가 Current price보다 높으면 즉시 체결되므로 차단
                if side.lower() == 'buy' and price >= current_price:
                    self.logger.warning(f"🚨 지정가 주문 차단: {symbol} 매수 지정가(${price:.6f}) ≥ Current price(${current_price:.6f})")
                    return {'success': False, 'error': f'Buy limit price {price:.6f} >= current price {current_price:.6f}'}
                
                # 매도 지정가 주문: 지정가가 Current price보다 낮으면 즉시 체결되므로 차단  
                if side.lower() == 'sell' and price <= current_price:
                    self.logger.warning(f"🚨 지정가 주문 차단: {symbol} 매도 지정가(${price:.6f}) ≤ Current price(${current_price:.6f})")
                    return {'success': False, 'error': f'Sell limit price {price:.6f} <= current price {current_price:.6f}'}
                    
            except Exception as e:
                self.logger.warning(f"Current price 비교 Failed - 주문 계속 Progress: {symbol} - {e}")
            
            # 지정가 주문 Execute
            order = self.exchange.create_limit_order(
                symbol=symbol,
                side=side,
                amount=abs(quantity),
                price=price
            )
            
            if order and order.get('id'):
                self.logger.info(f"지정가 주문 Success: {symbol} {side} {quantity} @ ${price:.4f} - ID: {order['id']}")
                return {
                    'success': True,
                    'order_id': order['id'],
                    'filled': order.get('filled', 0),
                    'remaining': order.get('remaining', quantity),
                    'price': price,
                    'order_type': 'limit',
                    'status': order.get('status', 'open')
                }
            else:
                self.logger.error(f"지정가 Order failed: {symbol} {side} {quantity} @ ${price:.4f}")
                return {'success': False, 'error': 'Limit order creation failed'}
                
        except Exception as e:
            self.logger.error(f"지정가 주문 Execute Failed: {symbol} {side} {quantity} @ ${price:.4f} - {e}")
            return {'success': False, 'error': str(e)}

    def _cancel_pending_orders(self, symbol: str) -> Dict[str, Any]:
        """해당 Symbol의 미체결 지정가 주문 Cancel - Rate Limit 대응 강화"""
        try:
            if not self.exchange:
                return {'success': False, 'error': 'Exchange not available'}
            
            # Rate Limit 체크 - 418 에러 방지
            if (hasattr(self.strategy, '_api_rate_limited') and 
                self.strategy._api_rate_limited):
                self.logger.warning(f"🚨 Rate Limit Status - 주문 Cancel 너뛰기: {symbol}")
                return {'success': False, 'error': 'Rate limited - skip cancel orders'}
            
            # 미체결 주문 조times (Rate Limit 대응)
            try:
                open_orders = self.exchange.fetch_open_orders(symbol)
            except ccxt.RateLimitExceeded as e:
                self.logger.error(f"🚨 Rate Limit Exceeded - 주문 조times Failed: {symbol} - {e}")
                return {'success': False, 'error': f'Rate limit exceeded: {str(e)}'}
            except Exception as e:
                # 418 에러 등 Other API 에러 Process
                if "418" in str(e) or "too many requests" in str(e).lower():
                    self.logger.error(f"🚨 API 과부하 - 주문 조times Failed: {symbol} - {e}")
                    return {'success': False, 'error': f'API overload: {str(e)}'}
                else:
                    raise e
            
            cancelled_orders = []
            
            for order in open_orders:
                try:
                    # Rate Limit 체크 (각 주문 Cancel 전)
                    if (hasattr(self.strategy, '_api_rate_limited') and 
                        self.strategy._api_rate_limited):
                        self.logger.warning(f"🚨 Rate Limit Detected - 주문 Cancel 중단: {symbol}")
                        break
                    
                    # DCA 관련 주문만 Cancel (Required시 주문에 태그를 달아 구분)
                    cancel_result = self.exchange.cancel_order(order['id'], symbol)
                    cancelled_orders.append({
                        'order_id': order['id'],
                        'side': order['side'],
                        'amount': order['amount'],
                        'price': order['price']
                    })
                    self.logger.info(f"주문 Cancel Success: {symbol} - ID: {order['id']}")
                    
                    # 주문 Cancel 후 잠시 대기 (Rate Limit 방지)
                    time.sleep(0.1)
                    
                except ccxt.RateLimitExceeded as e:
                    self.logger.error(f"🚨 Rate Limit Exceeded - 주문 Cancel Failed: {symbol} - ID: {order['id']} - {e}")
                    break  # Rate Limit 발생시 즉시 중단
                except Exception as e:
                    # 418 에러 등 Other API 에러 Process
                    if "418" in str(e) or "too many requests" in str(e).lower():
                        self.logger.error(f"🚨 API 과부하 - 주문 Cancel Failed: {symbol} - ID: {order['id']} - {e}")
                        break  # API 과부하시 즉시 중단
                    else:
                        self.logger.warning(f"주문 Cancel Failed: {symbol} - ID: {order['id']} - {e}")
                        continue
            
            return {
                'success': True,
                'cancelled_count': len(cancelled_orders),
                'cancelled_orders': cancelled_orders
            }
                
        except Exception as e:
            # 418 에러 등 전체적인 API 에러 Process
            if "418" in str(e) or "too many requests" in str(e).lower():
                self.logger.error(f"🚨 API 과부하로 인한 Pending order cancel Failed: {symbol} - {e}")
            else:
                self.logger.error(f"Pending order cancel Failed: {symbol} - {e}")
            return {'success': False, 'error': str(e)}

    def get_pending_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """해당 Symbol의 미체결 지정가 주문 조times (메인 전략 호환용)"""
        try:
            if symbol not in self.positions:
                return []

            position = self.positions[symbol]
            pending_orders = []

            # Position의 모든 entry 중 미체결 지정가 주문 찾기
            for entry in position.entries:
                if entry.order_type == "limit" and not entry.is_filled and entry.is_active:
                    pending_orders.append({
                        'stage': entry.stage,
                        'order_id': entry.order_id,
                        'price': entry.entry_price,
                        'amount': entry.quantity,
                        'side': 'buy',
                        'status': 'open'
                    })

            return pending_orders

        except Exception as e:
            self.logger.error(f"미체결 주문 조times Failed {symbol}: {e}")
            return []

    def check_and_update_limit_orders(self) -> Dict[str, Any]:
        """미체결 지정가 주문 Status Confirm 및 Update"""
        try:
            if not self.exchange:
                return {'success': False, 'error': 'Exchange not available'}
            
            updated_positions = []
            
            for symbol, position in list(self.positions.items()):
                if not position.is_active:
                    continue
                
                # 미체결 지정가 주문이 있는 Entry 찾기
                pending_entries = [e for e in position.entries if e.is_active and not e.is_filled and e.order_type == "limit" and e.order_id]
                
                if not pending_entries:
                    continue
                
                try:
                    # Rate Limit Status 체크
                    if (hasattr(self.strategy, '_api_rate_limited') and 
                        self.strategy._api_rate_limited):
                        self.logger.debug(f"🚨 Rate limit status - 주문 Status Confirm 너뛰기 ({symbol})")
                        continue
                        
                    # 해당 Symbol의 모든 주문 Status Confirm (Rate Limit 대응 강화)
                    try:
                        orders = self.exchange.fetch_orders(symbol)
                        order_status_map = {order['id']: order for order in orders}
                    except ccxt.RateLimitExceeded as e:
                        self.logger.warning(f"🚨 Rate Limit Exceeded - 주문 Status Confirm 너뛰기: {symbol} - {e}")
                        continue
                    except Exception as e:
                        # 418 에러 등 Other API 에러 Process
                        if "418" in str(e) or "too many requests" in str(e).lower():
                            self.logger.warning(f"🚨 API 과부하 - 주문 Status Confirm 너뛰기: {symbol} - {e}")
                            # Rate Limit Status 플래그 Settings (있는 경우)
                            if hasattr(self.strategy, '_api_rate_limited'):
                                self.strategy._api_rate_limited = True
                            continue
                        else:
                            raise e
                    
                    position_updated = False
                    
                    for entry in pending_entries:
                        if entry.order_id in order_status_map:
                            order = order_status_map[entry.order_id]
                            
                            # 주문이 체결되었는지 Confirm
                            if order['status'] == 'closed' and order['filled'] > 0:
                                # 체결 Complete
                                entry.is_filled = True
                                entry.quantity = order['filled']  # 실제 체결 Quantity으로 Update
                                entry.entry_price = order['average'] if order['average'] else entry.entry_price
                                
                                self.logger.info(f"✅ DCA limit order 체결: {symbol} {entry.stage} - 체결가: ${entry.entry_price:.4f}, Quantity: {entry.quantity:.4f}")
                                
                                # 중복 방지: 체결 Notification (Symbol_Stage_주문ID 조합으로 중복 체크)
                                notification_key = f"{symbol}_{entry.stage}_{entry.order_id}"
                                
                                # 🔍 디버깅: 체결 Notification 발송 조건 상세 Log
                                self.logger.info(f"🔍 체결 Detected: {symbol} {entry.stage}")
                                self.logger.info(f"🔍 주문 Status: {order['status']}, 체결량: {order['filled']}")
                                self.logger.info(f"🔍 NotificationKey: {notification_key}")
                                self.logger.info(f"🔍 이미 발송됨: {notification_key in self._sent_fill_notifications}")
                                self.logger.info(f"🔍 전체 발송 기록: {len(self._sent_fill_notifications)}count")
                                
                                if self.telegram_bot and notification_key not in self._sent_fill_notifications:
                                    message = (f"✅ DCA 지정가 체결\n"
                                              f"Symbol: {symbol}\n"
                                              f"Stage: {entry.stage}\n"
                                              f"체결가: ${entry.entry_price:.4f}\n"
                                              f"Quantity: {entry.quantity:.4f}")
                                    self.telegram_bot.send_message(message)
                                    self._sent_fill_notifications.add(notification_key)
                                    self._save_sent_notifications()  # Notification 기록 즉시 Save
                                    self.logger.info(f"📨 DCA 체결 Notification 발송 Complete: {notification_key}")
                                else:
                                    self.logger.info(f"📨 DCA 체결 Notification 너뛰기 (중복): {notification_key}")
                                
                                position_updated = True
                            
                            elif order['status'] == 'canceled':
                                # 주문이 Cancel됨
                                entry.is_active = False
                                self.logger.warning(f"❌ DCA limit order Cancel됨: {symbol} {entry.stage}")
                                position_updated = True
                    
                    # Position Info 재계산 (체결된 Entry만으로) - 스레드 안전성 강화
                    if position_updated:
                        with self.sync_lock:  # 스레드 안전성 보장
                            filled_entries = [e for e in position.entries if e.is_active and e.is_filled]
                            if filled_entries:
                                # Legacy Average price Backup (로깅용)
                                old_avg_price = position.average_price
                                old_quantity = position.total_quantity
                                
                                # Average price 재계산 (가중평균)
                                total_cost = sum(e.quantity * e.entry_price for e in filled_entries)
                                total_quantity = sum(e.quantity for e in filled_entries)
                                new_avg_price = total_cost / total_quantity if total_quantity > 0 else position.average_price
                                
                                # Change사항 Verification
                                price_change_pct = abs(new_avg_price - old_avg_price) / old_avg_price * 100 if old_avg_price > 0 else 0
                                quantity_change_pct = abs(total_quantity - old_quantity) / old_quantity * 100 if old_quantity > 0 else 0
                                
                                # Average price update
                                position.average_price = new_avg_price
                                position.total_quantity = total_quantity
                                position.total_notional = sum(e.notional for e in filled_entries)
                                position.last_update = get_korea_time().isoformat()

                                # 📋 Position Stage Update (가장 높은 Stage로 Settings)
                                old_stage = position.current_stage
                                if any(e.stage == "second_dca" and e.is_filled for e in position.entries):
                                    position.current_stage = PositionStage.SECOND_DCA.value
                                elif any(e.stage == "first_dca" and e.is_filled for e in position.entries):
                                    position.current_stage = PositionStage.FIRST_DCA.value
                                else:
                                    position.current_stage = PositionStage.INITIAL.value

                                updated_positions.append(symbol)

                                # 상세 로깅 (Change사항 추적)
                                self.logger.info(f"🔄 Average price 재계산: {symbol}")
                                self.logger.info(f"   이전 Average price: ${old_avg_price:.6f} → 새 Average price: ${new_avg_price:.6f} ({price_change_pct:+.2f}%)")
                                self.logger.info(f"   이전 Quantity: {old_quantity:.6f} → 새 Quantity: {total_quantity:.6f} ({quantity_change_pct:+.2f}%)")
                                self.logger.info(f"   Position Stage: {old_stage} → {position.current_stage}")
                                self.logger.info(f"   체결된 Entry: {len(filled_entries)}count")
                                
                                # 체결된 Entry 상세 Info
                                for i, entry in enumerate(filled_entries):
                                    self.logger.debug(f"     Entry{i+1}: {entry.stage} - ${entry.entry_price:.6f} x {entry.quantity:.6f}")
                                
                                # 큰 change 감지시 Warning
                                if price_change_pct > 5.0:
                                    self.logger.warning(f"⚠️ Average price 큰 change Detected: {symbol} - {price_change_pct:.2f}% change")
                                if quantity_change_pct > 10.0:
                                    self.logger.warning(f"⚠️ Quantity 큰 change Detected: {symbol} - {quantity_change_pct:.2f}% change")
                
                except Exception as e:
                    # Rate Limit 에러 특별 Process
                    if "418" in str(e) or "too many requests" in str(e).lower():
                        if hasattr(self.strategy, '_api_rate_limited'):
                            self.strategy._api_rate_limited = True
                        self.logger.debug(f"Rate limit detected - 주문 Status Confirm 중단 ({symbol})")
                        break  # 다른 Symbol 체크도 중단
                    else:
                        self.logger.error(f"주문 Status Confirmation failed {symbol}: {e}")
                    continue
            
            # Update된 Position이 있으면 Save
            if updated_positions:
                self.save_data()
            
            return {
                'success': True,
                'updated_positions': updated_positions,
                'updated_count': len(updated_positions)
            }
            
        except Exception as e:
            self.logger.error(f"지정가 주문 Status Confirmation failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_position_summary(self) -> Dict[str, Any]:
        """Position 요Approx Info"""
        try:
            active_positions = [p for p in self.positions.values() if p.is_active]
            
            if not active_positions:
                return {
                    'total_positions': 0,
                    'total_notional': 0,
                    'total_unrealized_pnl': 0,
                    'positions': []
                }
            
            total_notional = sum(p.total_notional for p in active_positions)
            
            positions_info = []
            total_unrealized_pnl = 0
            
            for position in active_positions:
                try:
                    if self.exchange:
                        ticker = self.exchange.fetch_ticker(position.symbol)
                        current_price = float(ticker['last'])
                    else:
                        current_price = position.average_price
                    
                    unrealized_pnl = (current_price - position.average_price) * position.total_quantity
                    profit_pct = (current_price - position.average_price) / position.average_price * 100
                    
                    total_unrealized_pnl += unrealized_pnl
                    
                    positions_info.append({
                        'symbol': position.symbol,
                        'stage': position.current_stage,
                        'avg_price': position.average_price,
                        'current_price': current_price,
                        'quantity': position.total_quantity,
                        'notional': position.total_notional,
                        'unrealized_pnl': unrealized_pnl,
                        'profit_pct': profit_pct,
                        'entries_count': len([e for e in position.entries if e.is_active]),
                        'cyclic_count': position.cyclic_count,
                        'cyclic_state': position.cyclic_state,
                        'total_cyclic_profit': position.total_cyclic_profit
                    })
                
                except Exception as e:
                    self.logger.error(f"Position Info 계산 Failed {position.symbol}: {e}")
                    continue
            
            return {
                'total_positions': len(active_positions),
                'total_notional': total_notional,
                'total_unrealized_pnl': total_unrealized_pnl,
                'positions': positions_info
            }
            
        except Exception as e:
            self.logger.error(f"Position 요Approx Create Failed: {e}")
            return {'error': str(e)}
    
    def get_cyclic_statistics(self) -> Dict[str, Any]:
        """🔄 Cyclic trading 통계 Info"""
        try:
            all_positions = list(self.positions.values())
            
            # Cyclic trading 통계
            cyclic_positions = [p for p in all_positions if p.cyclic_count > 0]
            active_cyclic = [p for p in cyclic_positions if p.is_active]
            completed_cyclic = [p for p in cyclic_positions if not p.is_active]
            
            # Cyclic trading Status별 분류
            cyclic_active = [p for p in active_cyclic if p.cyclic_state == CyclicState.CYCLIC_ACTIVE.value]
            cyclic_paused = [p for p in active_cyclic if p.cyclic_state == CyclicState.CYCLIC_PAUSED.value]
            cyclic_complete = [p for p in all_positions if p.cyclic_state == CyclicState.CYCLIC_COMPLETE.value]
            
            # Cumulative Cyclic trading 수익
            total_cyclic_profit = sum(p.total_cyclic_profit for p in all_positions)
            
            # Cyclic trading times차별 통계
            cyclic_count_stats = {}
            for i in range(1, 4):  # 1~3times차
                count = len([p for p in all_positions if p.cyclic_count == i])
                cyclic_count_stats[f'cycle_{i}'] = count
            
            return {
                'total_cyclic_positions': len(cyclic_positions),
                'active_cyclic_positions': len(active_cyclic),
                'completed_cyclic_positions': len(completed_cyclic),
                'cyclic_states': {
                    'active': len(cyclic_active),
                    'paused': len(cyclic_paused),
                    'complete': len(cyclic_complete)
                },
                'cyclic_count_distribution': cyclic_count_stats,
                'total_cyclic_profit': total_cyclic_profit,
                'active_positions_detail': [
                    {
                        'symbol': p.symbol,
                        'cyclic_count': p.cyclic_count,
                        'cyclic_state': p.cyclic_state,
                        'current_stage': p.current_stage,
                        'cyclic_profit': p.total_cyclic_profit
                    }
                    for p in active_cyclic
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Cyclic trading 통계 Create Failed: {e}")
            return {'error': str(e)}

    def log_cyclic_status(self):
        """Cyclic trading Status 로깅"""
        try:
            stats = self.get_cyclic_statistics()
            if 'error' not in stats:
                self.logger.info(f"🔄 Cyclic trading 현황: 전체 {stats['total_cyclic_positions']}count, Active {stats['active_cyclic_positions']}count, Complete {stats['completed_cyclic_positions']}count")
                self.logger.info(f"🔄 Status별: Progress {stats['cyclic_states']['active']}count, Waiting {stats['cyclic_states']['paused']}count, Complete {stats['cyclic_states']['complete']}count")
                self.logger.info(f"💰 Cumulative Cyclic trading 수익: ${stats['total_cyclic_profit']:.2f}")
        except Exception as e:
            self.logger.error(f"Cyclic trading 로깅 Failed: {e}")

    def cleanup_inactive_positions(self):
        """비Active positions 정리"""
        try:
            inactive_symbols = [symbol for symbol, pos in self.positions.items() if not pos.is_active]
            
            if inactive_symbols:
                for symbol in inactive_symbols:
                    del self.positions[symbol]
                    self.logger.info(f"비Active positions Cleanup: {symbol}")
                
                self.save_data()
                self.logger.info(f"Position Cleanup Complete: {len(inactive_symbols)}count")
            
        except Exception as e:
            self.logger.error(f"Position Cleanup Failed: {e}")

    def get_active_positions(self) -> Dict[str, DCAPosition]:
        """Active positions 반환"""
        return {symbol: pos for symbol, pos in self.positions.items() if pos.is_active}

    def has_active_position(self, symbol: str) -> bool:
        """Active positions 존재 여부"""
        return symbol in self.positions and self.positions[symbol].is_active

    def force_exit_position(self, symbol: str, reason: str = "manual") -> dict:
        """강제 Position Exit"""
        try:
            if symbol not in self.positions or not self.positions[symbol].is_active:
                self.logger.warning(f"강제 Exit 대상 Absent: {symbol}")
                return {'success': False, 'silent': False}
            
            position = self.positions[symbol]
            
            if self.exchange:
                ticker = self.exchange.fetch_ticker(symbol)
                current_price = float(ticker['last'])
            else:
                current_price = position.average_price
            
            return self._execute_emergency_exit(position, current_price, f"강제Exit: {reason}")
            
        except Exception as e:
            self.logger.error(f"강제 Exit Failed {symbol}: {e}")
            return {'success': False, 'silent': False}

    def notify_liquidation_from_strategy(self, symbol: str, reason: str = "strategy_liquidation") -> bool:
        """메인 전략에서 Exit Complete 즉시 통지 (Sync 갭 해결)"""
        try:
            with self.sync_lock:
                if symbol not in self.positions:
                    self.logger.info(f"🔄 Exit 통지: DCA No position - {symbol}")
                    return True
                
                position = self.positions[symbol]
                
                # 즉시 Position 비Active화
                position.is_active = False
                position.current_stage = PositionStage.CLOSING.value
                position.last_update = get_korea_time().isoformat()
                
                # 모든 Entry 비Active화
                for entry in position.entries:
                    entry.is_active = False
                
                # 미체결 지정가 주문 Cancel
                cancel_result = self._cancel_pending_orders(symbol)
                if cancel_result['success'] and cancel_result['cancelled_count'] > 0:
                    self.logger.info(f"📋 Exit 후 Pending order cancel: {symbol} - {cancel_result['cancelled_count']}count")
                
                # DCA Position Remove
                del self.positions[symbol]
                
                # 데이터 Save
                self.save_data()
                
                self.logger.critical(f"🚨 메인 전략 Exit 통지 Process Complete: {symbol} (Reason: {reason})")
                
                # 텔레그램 Notification
                if self.telegram_bot:
                    message = (f"🚨 DCA 시스템 Sync\n"
                              f"메인 전략 Exit 감지: {symbol}\n"
                              f"DCA Position 즉시 정리 Complete\n"
                              f"Reason: {reason}")
                    self.telegram_bot.send_message(message)
                
                return True
            
        except Exception as e:
            self.logger.error(f"Exit 통지 Process Failed {symbol}: {e}")
            return False

    def handle_main_strategy_exit(self, symbol: str, exit_reason: str, partial_ratio: float = 1.0) -> Dict[str, Any]:
        """메인 전략 Exit 요청 Process - 호환성 브리지 메서드"""
        try:
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            
            # Position 존재 Confirm
            if clean_symbol not in self.positions:
                return {
                    'success': False, 
                    'exit_type': 'not_found',
                    'message': f'DCA 시스템에서 Position을 찾을 수 Absent: {clean_symbol}',
                    'error': 'Position not found in DCA system'
                }
            
            position = self.positions[clean_symbol]
            
            # Current 가격 가져오기 (Rate Limit 대응)
            current_price = None
            try:
                # Rate Limit 체크
                if (hasattr(self.strategy, '_api_rate_limited') and 
                    self.strategy._api_rate_limited):
                    current_price = position.average_price  # 폴백
                    self.logger.debug(f"🚨 Rate Limit Status - 평균가로 가격 대체: {symbol}")
                else:
                    ticker = self.exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
            except Exception as e:
                # Rate Limit 감지 및 Process
                error_str = str(e).lower()
                if ("418" in str(e) or "429" in str(e) or 
                    "too many requests" in error_str or "rate limit" in error_str):
                    self.logger.warning(f"🚨 가격 조times 중 Rate Limit Detected: {symbol} - {e}")
                    if hasattr(self.strategy, '_api_rate_limited'):
                        self.strategy._api_rate_limited = True
                current_price = position.average_price  # 폴백
                
            self.logger.info(f"📋 메인 전략 Exit 요청: {clean_symbol} - {exit_reason} (비율: {partial_ratio*100:.1f}%)")
            
            # Exit 비율에 따른 Process
            if partial_ratio >= 1.0:
                # 전량 Exit
                success = self.force_exit_position(clean_symbol, exit_reason)
                return {
                    'success': success,
                    'exit_type': 'full_exit', 
                    'message': f'{exit_reason} - 전량Exit {"Success" if success else "Failed"}',
                    'partial_ratio': 1.0
                }
            else:
                # 부분 Exit
                result = self._execute_partial_exit(position, current_price, partial_ratio, exit_reason)
                return {
                    'success': result if isinstance(result, bool) else True,
                    'exit_type': 'partial_exit',
                    'message': f'{exit_reason} - {partial_ratio*100:.1f}% 부분Exit Complete',
                    'partial_ratio': partial_ratio
                }
                
        except Exception as e:
            error_msg = f"메인 전략 Exit Process Failed {symbol}: {str(e)}"
            self.logger.error(error_msg)
            return {
                'success': False,
                'exit_type': 'error',
                'message': error_msg,
                'error': str(e)
            }

    def validate_data_integrity(self) -> Dict[str, Any]:
        """데이터 무결성 Verification 및 메인 전략과의 Sync Status Confirm"""
        try:
            validation_result = {
                'valid': True,
                'errors': [],
                'warnings': [],
                'fixed': [],
                'sync_issues': []
            }
            
            # 메인 전략과의 Sync Status Confirm
            if self.strategy and hasattr(self.strategy, 'active_positions'):
                main_symbols = set(self.strategy.active_positions.keys())
                dca_symbols = set(pos.symbol for pos in self.positions.values() if pos.is_active)
                
                # DCA에는 있지만 메인 전략에 없는 Symbol (Orphan position 후보)
                orphaned_in_dca = dca_symbols - main_symbols
                for symbol in orphaned_in_dca:
                    validation_result['sync_issues'].append(f"DCA Orphan position: {symbol} (메인 전략에 Absent)")
                    # 자동 정리
                    try:
                        self._cleanup_orphaned_position(symbol.replace('/USDT:USDT', '').replace('/USDT', ''))
                        validation_result['fixed'].append(f"Orphan position 자동 정리: {symbol}")
                    except Exception as e:
                        validation_result['errors'].append(f"Orphan position 정리 Failed: {symbol} - {e}")
            
            for symbol, position in list(self.positions.items()):
                # 기본 Verification
                if not position.entries:
                    validation_result['errors'].append(f"{symbol}: Entry 기록 Absent")
                    validation_result['valid'] = False
                    continue
                
                # Quantity Verification
                calculated_quantity = sum(e.quantity for e in position.entries if e.is_active)
                if abs(calculated_quantity - position.total_quantity) > 0.001:
                    validation_result['warnings'].append(f"{symbol}: Quantity 불일치 - 계산값: {calculated_quantity}, Save값: {position.total_quantity}")
                    # 자동 Modify
                    position.total_quantity = calculated_quantity
                    validation_result['fixed'].append(f"{symbol}: Quantity 자동 Modify")
                
                # Average price Verification 및 Cyclic trading 데이터 정합성 Confirm
                active_entries = [e for e in position.entries if e.is_active]
                if position.total_quantity > 0 and active_entries:
                    # Average price 재계산
                    calculated_avg = sum(e.quantity * e.entry_price for e in active_entries) / position.total_quantity
                    if abs(calculated_avg - position.average_price) > 0.001:
                        old_avg = position.average_price
                        validation_result['warnings'].append(f"{symbol}: Average price 불일치 - Legacy: ${old_avg:.6f}, 계산: ${calculated_avg:.6f}")
                        # 자동 Modify
                        position.average_price = calculated_avg
                        validation_result['fixed'].append(f"{symbol}: Average price 자동 Modify (${old_avg:.6f} → ${calculated_avg:.6f})")
                        self.logger.warning(f"🔧 Average price 자동 Modify: {symbol} - ${old_avg:.6f} → ${calculated_avg:.6f}")
                    
                    # Cyclic trading Status Verification
                    if position.cyclic_state != CyclicState.NORMAL_DCA.value:
                        # Cyclic trading 카운트와 실제 Entry 수 일치성 Confirm
                        total_entries = len([e for e in position.entries if e.is_active])
                        expected_entries = 1  # 기본 초기 Entry
                        if position.current_stage == PositionStage.FIRST_DCA.value:
                            expected_entries = 2
                        elif position.current_stage == PositionStage.SECOND_DCA.value:
                            expected_entries = 3
                        
                        if total_entries != expected_entries:
                            validation_result['warnings'].append(f"{symbol}: Cyclic trading Entry 수 불일치 - 실제: {total_entries}, Expected: {expected_entries}")
                        
                        # Cyclic trading 수익 Cumulative Verification
                        if position.total_cyclic_profit < 0 and position.cyclic_count > 0:
                            validation_result['warnings'].append(f"{symbol}: Cyclic trading 수익 음수 - {position.total_cyclic_profit:.4f} USDT")
                        
                        # Cyclic trading 카운트 상한 Verification
                        if position.cyclic_count > position.max_cyclic_count:
                            validation_result['warnings'].append(f"{symbol}: Cyclic trading 카운트 Exceeded - {position.cyclic_count}/{position.max_cyclic_count}")
                            position.cyclic_count = position.max_cyclic_count
                            validation_result['fixed'].append(f"{symbol}: Cyclic trading 카운트 Modify")
            
            # Modify사항이 있으면 Save
            if validation_result['fixed']:
                self.save_data()
            
            return validation_result
            
        except Exception as e:
            self.logger.error(f"데이터 Verification Failed: {e}")
            return {'valid': False, 'error': str(e)}

    def get_system_health(self) -> Dict[str, Any]:
        """시스템 Status Confirm"""
        try:
            health_info = {
                'status': 'healthy',
                'timestamp': get_korea_time().isoformat(),
                'positions': {
                    'total': len(self.positions),
                    'active': len([p for p in self.positions.values() if p.is_active]),
                    'inactive': len([p for p in self.positions.values() if not p.is_active])
                },
                'files': {
                    'positions_file_exists': os.path.exists(self.positions_file),
                    'limits_file_exists': os.path.exists(self.limits_file),
                    'backup_file_exists': os.path.exists(self.backup_file)
                },
                'exchange': {
                    'connected': self.exchange is not None,
                    'has_api_key': bool(self.exchange and hasattr(self.exchange, 'apiKey') and self.exchange.apiKey)
                }
            }
            
            # 데이터 무결성 Verification
            validation_result = self.validate_data_integrity()
            health_info['data_integrity'] = validation_result
            
            if not validation_result['valid'] or validation_result['errors']:
                health_info['status'] = 'warning'
            
            return health_info
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': get_korea_time().isoformat()
            }
    
    # ========================================================================================
    # New 4가지 Exit 방식 구현
    # ========================================================================================
    
    def calculate_supertrend(self, df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
        """SuperTrend(10-3) 계산"""
        try:
            if len(df) < period + 1:
                # 데이터가 부족한 경우 기본값 반환
                current_price = df['close'].iloc[-1]
                supertrend = pd.Series([current_price * 0.98] * len(df), index=df.index)
                trend = pd.Series([1] * len(df), index=df.index)
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
            # 에러시 기본값 반환
            current_price = df['close'].iloc[-1]
            supertrend = pd.Series([current_price * 0.98] * len(df), index=df.index)
            trend = pd.Series([1] * len(df), index=df.index)
            return supertrend, trend
    
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
    
    def check_supertrend_exit_signal(self, symbol: str, current_price: float, position: DCAPosition) -> Optional[Dict[str, Any]]:
        """1. SuperTrend 전량Exit Confirm: 5minute candles SuperTrend Exit시그널시 무조건 전량Exit (Profit ratio 무관)"""
        try:
            if position.supertrend_exit_done:
                return None
            
            # Current Profit ratio 계산
            current_profit_pct = (current_price - position.average_price) / position.average_price
            
            # 최대 Profit ratio Update
            if current_profit_pct > position.max_profit_pct:
                position.max_profit_pct = current_profit_pct
                position.last_update = get_korea_time().isoformat()
                self.save_data()
            
            # 🔧 Modify: SuperTrend Exit은 Profit ratio 조건 없이 신호만으로 Execute
            # 문서에 "SuperTrend 전량Exit: 5minute candles SuperTrend(10-3) Exit시그널시 전량Exit"이라고 명시됨
            
            # 5minute candles 데이터 조times
            ohlcv = self.exchange.fetch_ohlcv(symbol, '5m', limit=50)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            if len(df) < 15:
                return None
            
            # SuperTrend 계산
            supertrend, trend = self.calculate_supertrend(df, period=10, multiplier=3.0)
            
            # Exit 시그널 Confirm: 상승(1) → 하락(-1) 전환
            if len(trend) >= 2:
                prev_trend = trend.iloc[-2]
                current_trend = trend.iloc[-1]
                
                if prev_trend == 1 and current_trend == -1:
                    self.logger.warning(f"🔴 SuperTrend Exit 시그널: {symbol} (Profit ratio 무관 전량Exit)")
                    self.logger.warning(f"   최대수익: {position.max_profit_pct*100:.1f}%")
                    self.logger.warning(f"   Current수익: {current_profit_pct*100:.1f}%")
                    self.logger.warning(f"   트렌드 전환: {prev_trend} → {current_trend}")
                    
                    return {
                        'exit_type': ExitType.SUPERTREND_EXIT.value,
                        'exit_ratio': 1.0,  # 전량 Exit
                        'max_profit_pct': position.max_profit_pct * 100,
                        'current_profit_pct': current_profit_pct * 100,
                        'supertrend_signal': f"상승({prev_trend}) → 하락({current_trend})",
                        'trigger_info': "5minute candles SuperTrend(10-3) Exit시그널 (Profit ratio 무관)"
                    }
            
            return None
            
        except Exception as e:
            self.logger.error(f"SuperTrend Exit Confirmation failed {symbol}: {e}")
            return None
    
    def check_bb600_exit_signal(self, symbol: str, current_price: float, position: DCAPosition) -> Optional[Dict[str, Any]]:
        """2. BB600 Trailing 스탑: 3minute candles/5minute candles/15minute candles/30minute candles 캔들 고점이 BB600 상단선 돌파시 50% 익절 + Trailing 스탑 Active화"""
        try:
            # 이미 BB600 50% Exit을 했다면 Trailing 스탑만 체크
            if position.bb600_exit_done and not position.trailing_stop_active:
                return None

            # Trailing 스탑이 Active화된 경우, Trailing 스탑 로직 Execute
            if position.trailing_stop_active:
                return self._check_trailing_stop(symbol, current_price, position)

            # 🚀 10% 이상 수익 달성시 자동 50% 익절 (BB600 기술적 조건 무관)
            current_profit_pct = (current_price - position.average_price) / position.average_price
            if current_profit_pct >= 0.10 and not position.bb600_exit_done:
                self.logger.info(f"💰 10% 이상 수익 달성 - 자동 50% Take profit: {symbol} (Profit ratio: {current_profit_pct*100:.1f}%)")
                
                # Trailing 스탑 Active화
                position.trailing_stop_active = True
                position.trailing_stop_high = current_price
                position.last_update = get_korea_time().isoformat()
                self.save_data()
                
                return {
                    'exit_type': ExitType.BB600_PARTIAL_EXIT.value,
                    'exit_ratio': 0.5,  # 50% Exit
                    'timeframe': 'profit_threshold',
                    'current_price': current_price,
                    'current_profit_pct': current_profit_pct * 100,
                    'trigger_info': f"10% 이상 수익 달성 자동 50% 익절 ({current_profit_pct*100:.1f}%)"
                }

            # BB600 돌파 체크 (3minute candles, 5minute candles, 15minute candles, 30minute candles)
            for timeframe in ['3m', '5m', '15m', '30m']:
                try:
                    # 데이터 조times
                    ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=650)  # BB600 계산을 위해 충분한 데이터
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    
                    if len(df) < 10:
                        continue
                    
                    # BB600 계산 (표준편차 2.9 Usage)
                    bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(df, period=600, std=2.9)
                    
                    # 최근 몇 count 캔들의 고점이 BB600 상단선을 돌파했는지 Confirm (Current 포함 최근 3봉)
                    for i in range(-3, 0):  # 최근 3봉 체크
                        if abs(i) > len(df):
                            continue
                            
                        candle_high = df['high'].iloc[i]
                        bb_upper_at_time = bb_upper.iloc[i] if abs(i) <= len(bb_upper) else None
                        
                        if pd.notna(bb_upper_at_time) and candle_high > bb_upper_at_time:
                            self.logger.info(f"💰 BB600 캔들 고점 돌파 Detected: {symbol} ({timeframe})")
                            self.logger.info(f"   캔들 고점: ${candle_high:.6f}")
                            self.logger.info(f"   BB600 상단: ${bb_upper_at_time:.6f}")
                            
                            current_profit_pct = (current_price - position.average_price) / position.average_price * 100
                            
                            # Trailing 스탑 Active화
                            position.trailing_stop_active = True
                            position.trailing_stop_high = current_price
                            position.last_update = get_korea_time().isoformat()
                            self.save_data()
                            
                            # 텔레그램 Notification
                            if self.telegram_bot:
                                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                                message = (f"🎯 [BB600 돌파 + Trailing 스탑 Active화] {clean_symbol}\n"
                                         f"Time프레임: {timeframe}\n"
                                         f"캔들 고점: ${candle_high:.6f}\n"
                                         f"BB600 상단: ${bb_upper_at_time:.6f}\n"
                                         f"Current Profit ratio: {current_profit_pct:.1f}%\n"
                                         f"🔄 50% 익절 + Trailing 스탑 Starting")
                                self.telegram_bot.send_message(message)
                            
                            return {
                                'exit_type': ExitType.BB600_PARTIAL_EXIT.value,
                                'exit_ratio': 0.5,  # 50% Exit
                                'timeframe': timeframe,
                                'current_price': current_price,
                                'candle_high': candle_high,
                                'bb600_upper': bb_upper_at_time,
                                'current_profit_pct': current_profit_pct,
                                'trigger_info': f"{timeframe}봉 캔들 고점 BB600 돌파 (50% 익절 + Trailing 스탑 Active화)",
                                'trailing_stop_activated': True
                            }
                        
                except Exception as e:
                    self.logger.debug(f"BB600 Confirmation failed {symbol} {timeframe}: {e}")
                    continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"BB600 돌파 Confirmation failed {symbol}: {e}")
            return None
    
    def _check_trailing_stop(self, symbol: str, current_price: float, position: DCAPosition) -> Optional[Dict[str, Any]]:
        """Trailing 스탑 로직: Highest price에서 5% 하락시 나머지 50% Exit"""
        try:
            # Current price가 New Highest price인지 Confirm
            if current_price > position.trailing_stop_high:
                position.trailing_stop_high = current_price
                position.last_update = get_korea_time().isoformat()
                self.save_data()
                
                # New Highest price 갱신 시 텔레그램 Notification (너무 빈번하지 않게 Log 레벨 조정)
                self.logger.debug(f"🔄 Trailing 스탑 Highest price 갱신: {symbol} ${current_price:.6f}")
            
            # Trailing 스탑 트리거 체크: Highest price에서 5% 하락
            trailing_stop_price = position.trailing_stop_high * (1 - position.trailing_stop_percentage)
            
            if current_price <= trailing_stop_price:
                current_profit_pct = (current_price - position.average_price) / position.average_price * 100
                high_to_current_drop = ((position.trailing_stop_high - current_price) / position.trailing_stop_high) * 100
                
                self.logger.warning(f"🔴 Trailing 스탑 Exit 트리거: {symbol}")
                self.logger.warning(f"   Highest price: ${position.trailing_stop_high:.6f}")
                self.logger.warning(f"   Current price: ${current_price:.6f}")
                self.logger.warning(f"   Trailing 스탑가: ${trailing_stop_price:.6f}")
                self.logger.warning(f"   Highest price vs 하락: {high_to_current_drop:.1f}%")
                
                # 텔레그램 Notification
                if self.telegram_bot:
                    clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                    message = (f"🔴 [Trailing 스탑 Exit] {clean_symbol}\n"
                             f"Highest price: ${position.trailing_stop_high:.6f}\n"
                             f"Current price: ${current_price:.6f}\n"
                             f"Drop rate: {high_to_current_drop:.1f}%\n"
                             f"Current Profit ratio: {current_profit_pct:.1f}%\n"
                             f"💰 나머지 50% 전량Exit")
                    self.telegram_bot.send_message(message)
                
                return {
                    'exit_type': 'trailing_stop_exit',
                    'exit_ratio': 0.5,  # 나머지 50% Exit
                    'current_price': current_price,
                    'trailing_stop_high': position.trailing_stop_high,
                    'trailing_stop_price': trailing_stop_price,
                    'high_to_current_drop_pct': high_to_current_drop,
                    'current_profit_pct': current_profit_pct,
                    'trigger_info': f"Trailing 스탑 Exit (Highest price vs {high_to_current_drop:.1f}% 하락)"
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Trailing 스탑 체크 Failed {symbol}: {e}")
            return None
    
    def check_breakeven_protection_exit(self, symbol: str, current_price: float, position: DCAPosition) -> Optional[Dict[str, Any]]:
        """3. 본절Exit: Profit ratio별 차등 Exit (3%~5%: 손실전환전, 5%~10%: 절반하락시)"""
        try:
            # 🚨 중복 Exit 방지: 이미 본절보호Exit이 Complete된 경우 Skip
            if hasattr(position, 'breakeven_exit_done') and position.breakeven_exit_done:
                return None
            
            # Current Profit ratio 계산
            current_profit_pct = (current_price - position.average_price) / position.average_price
            
            # 최대 Profit ratio Update
            if current_profit_pct > position.max_profit_pct:
                position.max_profit_pct = current_profit_pct
                position.last_update = get_korea_time().isoformat()
                self.save_data()
            
            # 3% 이상 수익 달성시 보호 모드 Active화
            if position.max_profit_pct >= 0.03:
                if not position.breakeven_protection_active:
                    position.breakeven_protection_active = True
                    position.last_update = get_korea_time().isoformat()
                    self.save_data()
                    
                    # Profit ratio 구간별 보호 전략 결정
                    protection_strategy = ""
                    if position.max_profit_pct >= 0.20:
                        protection_strategy = "20%+ 초고수익 Trailing 스톱 (15% 하락 허용)"
                    elif position.max_profit_pct >= 0.15:
                        protection_strategy = "15~20% 고수익 Trailing 스톱 (20% 하락 허용)"
                    elif position.max_profit_pct >= 0.10:
                        protection_strategy = "10~15% Trailing 스톱 (25% 하락 허용)"
                    elif position.max_profit_pct >= 0.05:
                        protection_strategy = "5~10% 절반하락 보호"
                    else:
                        protection_strategy = "3~5% Approx수익 보호 (70% 하락시 Exit)"
                    
                    # 텔레그램 Notification
                    if self.telegram_bot:
                        clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                        # Profit ratio에 따라 적절한 제목 Settings
                        if position.max_profit_pct >= 0.10:
                            alert_title = "📈 [Trailing 스톱 Active화]"
                        elif position.max_profit_pct >= 0.05:
                            alert_title = "🛡️ [수익보호 Active화]"
                        else:
                            alert_title = "🛡️ [본절보호 Active화]"
                        
                        message = (f"{alert_title} {clean_symbol}\n"
                                 f"최대수익: {position.max_profit_pct*100:.1f}%\n"
                                 f"보호전략: {protection_strategy}\n"
                                 f"Current price: ${current_price:.6f}")
                        self.telegram_bot.send_message(message)
                        self.logger.info(f"{alert_title} {symbol} (최대수익: {position.max_profit_pct*100:.1f}%) - {protection_strategy}")
            
            # 보호 모드가 Active화된 Status에서 Profit ratio 구간별 Exit 조건 적용
            if position.breakeven_protection_active:
                exit_trigger = None
                trigger_reason = ""
                
                if position.max_profit_pct >= 0.10:
                    # 10% 이상: Trailing 스톱 적용 (최고점 vs 허용 하락폭 Settings)
                    # Profit ratio별 Trailing 스톱 비율
                    if position.max_profit_pct >= 0.20:  # 20% 이상
                        allowed_drop = 0.15  # 15% 하락 허용 (85% Maintain)
                        protection_type = "20%+ 초고수익"
                    elif position.max_profit_pct >= 0.15:  # 15~20%
                        allowed_drop = 0.20  # 20% 하락 허용 (80% Maintain)
                        protection_type = "15~20% 고수익"
                    else:  # 10~15%
                        allowed_drop = 0.25  # 25% 하락 허용 (75% Maintain)
                        protection_type = "10~15% 수익"

                    trailing_threshold = position.max_profit_pct * (1 - allowed_drop)
                    # 🔧 Modify: Current Profit ratio이 양수 범위에서만 Trailing 스톱 Exit
                    if current_profit_pct > 0 and current_profit_pct <= trailing_threshold:
                        exit_trigger = True
                        trigger_reason = f"{protection_type} Trailing 스톱 (최대 {position.max_profit_pct*100:.1f}% → Current {current_profit_pct*100:.1f}%, {allowed_drop*100:.0f}% 하락 허용)"
                        
                elif position.max_profit_pct >= 0.05:
                    # 5%~10% 미만: 절반하락시 전량Exit
                    half_drop_threshold = position.max_profit_pct * 0.5
                    # 🔧 Modify: Current Profit ratio이 양수 범위에서만 절반 하락시 Exit
                    if current_profit_pct > 0 and current_profit_pct <= half_drop_threshold:
                        exit_trigger = True
                        trigger_reason = f"5~10% 절반하락 보호 (최대수익 {position.max_profit_pct*100:.1f}% → Current {current_profit_pct*100:.1f}%)"
                        
                else:
                    # 3%~5% 미만: 더 적극적인 Approx수익 보호 (최대수익의 30% 지점에서 Exit)
                    protection_threshold = position.max_profit_pct * 0.3  # 최대수익의 30%까지만 허용
                    if current_profit_pct <= protection_threshold:
                        exit_trigger = True
                        trigger_reason = f"Approx수익 보호Exit (최대수익 {position.max_profit_pct*100:.1f}% → Current {current_profit_pct*100:.1f}%, 70% 하락)"
                
                # Exit 트리거 발동시
                if exit_trigger:
                    self.logger.critical(f"💙 본절Exit 트리거: {symbol}")
                    self.logger.critical(f"   {trigger_reason}")
                    self.logger.critical(f"   최대수익: {position.max_profit_pct*100:.1f}%")
                    self.logger.critical(f"   Current수익: {current_profit_pct*100:.1f}%")
                    
                    return {
                        'exit_type': ExitType.BREAKEVEN_PROTECTION.value,
                        'exit_ratio': 1.0,  # 전량 Exit
                        'max_profit_pct': position.max_profit_pct * 100,
                        'current_profit_pct': current_profit_pct * 100,
                        'secured_profit': current_profit_pct * 100,  # 실제 확보 P&L
                        'trigger_info': trigger_reason
                    }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Approx수익 보호 Confirmation failed {symbol}: {e}")
            return None
    
    def check_weak_rise_dump_protection_exit(self, symbol: str, current_price: float, position: DCAPosition) -> Optional[Dict[str, Any]]:
        """5. Approx상승후 급락 리스크 times피: 원금기준 최대Profit ratio 2%이상 → 손실부근 하락 + 5minute candles 5봉이내 SuperTrend(10-2) Exit신호"""
        try:
            if position.weak_rise_dump_exit_done:
                return None
            
            # Current Profit ratio 계산
            current_profit_pct = (current_price - position.average_price) / position.average_price
            
            # 최대 Profit ratio Update
            if current_profit_pct > position.max_profit_pct:
                position.max_profit_pct = current_profit_pct
                position.last_update = get_korea_time().isoformat()
                self.save_data()
            
            # 조건 1: 최대Profit ratio 2% 이상 달성했었는지 Confirm
            if position.max_profit_pct < 0.02:  # 2% 미만이면 조건 불충족
                return None
            
            # 조건 2: Current 손실 부근까지 하락했는지 Confirm (0% 근처 또는 마이너스)
            if current_profit_pct > 0.005:  # 0.5% 이상 수익이면 아직 손실 부근이 아님
                return None
            
            # 조건 3: 5minute candles 데이터 조times하여 SuperTrend(10-2) Exit 신호 Confirm
            ohlcv = self.exchange.fetch_ohlcv(symbol, '5m', limit=20)  # 5봉 이내 Confirm을 위해 여유있게 20봉
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            if len(df) < 15:
                return None
            
            # SuperTrend(10-2) 계산 (Legacy 10-3과 다른 파라미터)
            supertrend_10_2, trend_10_2 = self.calculate_supertrend(df, period=10, multiplier=2.0)
            
            # 5봉 이내 Exit 신호 Confirm: 상승(1) → 하락(-1) 전환
            recent_5_trends = trend_10_2.tail(5)  # 최근 5봉
            
            found_exit_signal = False
            signal_position = -1
            
            for i in range(len(recent_5_trends) - 1):
                prev_trend = recent_5_trends.iloc[i]
                current_trend = recent_5_trends.iloc[i + 1]
                
                # 상승에서 하락으로 전환 Confirm
                if prev_trend == 1 and current_trend == -1:
                    found_exit_signal = True
                    signal_position = i + 1
                    break
            
            if found_exit_signal:
                self.logger.warning(f"🚨 Approx상승후 급락 리스크 times피 Exit: {symbol}")
                self.logger.warning(f"   최대수익: {position.max_profit_pct*100:.1f}%")
                self.logger.warning(f"   Current수익: {current_profit_pct*100:.1f}%")
                self.logger.warning(f"   SuperTrend(10-2): 5봉이내 Exit신호 Detected (위치: {signal_position})")
                
                return {
                    'exit_type': ExitType.WEAK_RISE_DUMP_PROTECTION.value,
                    'exit_ratio': 1.0,  # 전량 Exit
                    'max_profit_pct': position.max_profit_pct * 100,
                    'current_profit_pct': current_profit_pct * 100,
                    'supertrend_signal_position': signal_position,
                    'trigger_info': f"Approx상승후 급락 리스크 times피 (최대{position.max_profit_pct*100:.1f}% → {current_profit_pct*100:.1f}%, SuperTrend(10-2) 5봉이내 Exit신호)"
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Approx상승후 급락 리스크 times피 Confirmation failed {symbol}: {e}")
            return None
    
    def check_all_new_exit_signals(self, symbol: str, current_price: float) -> Optional[Dict[str, Any]]:
        """New 5가지 Exit 방식 종합 Confirm (우선순위 적용)"""
        try:
            if symbol not in self.positions:
                return None
            
            position = self.positions[symbol]
            if not position.is_active:
                return None
            
            # 1순위: SuperTrend 전량Exit (Profit ratio 조건 + SuperTrend 시그널)
            supertrend_exit = self.check_supertrend_exit_signal(symbol, current_price, position)
            if supertrend_exit:
                return supertrend_exit
            
            # 2순위: BB600 50% 익절 (10% 이상에서 우선 Execute)
            bb600_exit = self.check_bb600_exit_signal(symbol, current_price, position)
            if bb600_exit:
                return bb600_exit
            
            # 3순위: Approx상승후 급락 리스크 times피 (New 5번째 Exit)
            weak_rise_dump_exit = self.check_weak_rise_dump_protection_exit(symbol, current_price, position)
            if weak_rise_dump_exit:
                return weak_rise_dump_exit
            
            # 4순위: 본절보호Exit (Trailing 스톱, 절반하락 보호, Approx수익 보호)
            breakeven_exit = self.check_breakeven_protection_exit(symbol, current_price, position)
            if breakeven_exit:
                return breakeven_exit
            
            # 5순위: DCA Cyclic trading 일부Exit은 Legacy 시스템 Maintain
            
            return None
            
        except Exception as e:
            self.logger.error(f"New Exit Confirmation failed {symbol}: {e}")
            return None
    
    def check_new_exit_conditions(self, symbol: str, current_price: float) -> bool:
        """New Exit 조건 Confirm (미구현)"""
        # TODO: New Exit 조건들 구현
        return False
    
    def execute_new_exit(self, symbol: str, exit_signal: Dict[str, Any]) -> dict:
        """New Exit 방식 Execute"""
        try:
            if symbol not in self.positions:
                return {'success': False, 'silent': False}
            
            position = self.positions[symbol]
            exit_type = exit_signal['exit_type']
            exit_ratio = exit_signal['exit_ratio']
            
            # 텔레그램 Notification 전송
            self.send_new_exit_notification(symbol, exit_signal, position)
            
            # Exit Execute (Legacy partial_exit 또는 force_exit 활용)
            if exit_ratio >= 1.0:
                # 전량 Exit
                result = self.force_exit_position(symbol, reason=f"new_exit_{exit_type}")
                if isinstance(result, dict):
                    success = result.get('success', False)
                    silent = result.get('silent', False)
                    
                    # API 밴으로 Failed한 경우 메인 전략에서 Exit하도록 요청
                    if not success and not silent and "418" in str(result.get('error', '')):
                        self.logger.warning(f"🚨 API 밴으로 DCA Exit Failed - 메인 전략 Exit 요청: {symbol}")
                        if self.strategy and hasattr(self.strategy, '_emergency_exit_requests'):
                            if not hasattr(self.strategy, '_emergency_exit_requests'):
                                self.strategy._emergency_exit_requests = set()
                            self.strategy._emergency_exit_requests.add(symbol)
                            self.logger.info(f"📋 메인 전략 긴급 Exit 요청 Register: {symbol}")
                else:
                    success = result
                    silent = False
            else:
                # 부분 Exit (50%)
                result = self._execute_partial_exit(position, exit_signal['current_price'], exit_ratio, f"new_exit_{exit_type}")
                if isinstance(result, dict):
                    success = result.get('success', False)
                    silent = result.get('silent', False)
                else:
                    success = result
                    silent = False
            
            if success:
                # Exit Complete 마킹
                self.mark_new_exit_completed(symbol, exit_type, exit_signal)
                self.logger.info(f"✅ New Exit Complete: {symbol} - {exit_type} ({exit_ratio*100:.0f}%)")
            
            return {'success': success, 'silent': silent}
            
        except Exception as e:
            self.logger.error(f"New Exit Execute Failed {symbol}: {e}")
            return {'success': False, 'silent': False}
    
    def mark_new_exit_completed(self, symbol: str, exit_type: str, exit_signal: Dict[str, Any] = None):
        """New Exit Complete 마킹"""
        try:
            if symbol not in self.positions:
                return
            
            position = self.positions[symbol]
            
            if exit_type == ExitType.SUPERTREND_EXIT.value:
                position.supertrend_exit_done = True
            elif exit_type == ExitType.BB600_PARTIAL_EXIT.value:
                position.bb600_exit_done = True
                # Trailing 스탑이 Active화된 경우 Maintain
                if exit_signal and 'trailing_stop_activated' in exit_signal and exit_signal['trailing_stop_activated']:
                    self.logger.info(f"🔄 Trailing 스탑 Active화 Maintain: {symbol}")
            elif exit_type == 'trailing_stop_exit':
                # Trailing 스탑으로 나머지 50% Exit Complete
                position.trailing_stop_active = False
                self.logger.info(f"✅ Trailing 스탑 Complete: {symbol}")
            elif exit_type == ExitType.BREAKEVEN_PROTECTION.value:
                # 본절보호Exit은 전량 Exit이므로 모든 Exit Complete Process
                position.breakeven_exit_done = True
                position.supertrend_exit_done = True
                position.bb600_exit_done = True
                position.weak_rise_dump_exit_done = True
            elif exit_type == ExitType.WEAK_RISE_DUMP_PROTECTION.value:
                # Approx상승후 급락 리스크 times피는 전량 Exit이므로 모든 Exit Complete Process
                position.weak_rise_dump_exit_done = True
                position.supertrend_exit_done = True
                position.bb600_exit_done = True
            
            position.last_update = get_korea_time().isoformat()
            self.save_data()
            
        except Exception as e:
            self.logger.error(f"New Exit Complete 마킹 Failed {symbol}: {e}")
    
    def send_new_exit_notification(self, symbol: str, exit_signal: Dict[str, Any], position: DCAPosition):
        """New Exit Notification 전송"""
        try:
            if not self.telegram_bot:
                return
            
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            exit_type = exit_signal['exit_type']
            # current_price 안전하게 가져오기 (Key가 없을 경우 대체값 Usage)
            current_price = exit_signal.get('current_price', position.current_price if hasattr(position, 'current_price') else position.average_price)
            current_profit_pct = (current_price - position.average_price) / position.average_price * 100
            
            # Exit Type별 Message Create
            if exit_type == ExitType.SUPERTREND_EXIT.value:
                emoji = "🔴"
                title = "SuperTrend 전량Exit"
                details = (f"Profit ratio조건: 최대{exit_signal['max_profit_pct']:.1f}% OR Current{exit_signal['current_profit_pct']:.1f}%\n"
                          f"SuperTrend: {exit_signal['supertrend_signal']}\n"
                          f"Exit량: 100% (전량)")
                
            elif exit_type == ExitType.BB600_PARTIAL_EXIT.value:
                emoji = "💰"
                title = f"BB600 50% 익절 ({exit_signal['timeframe']})"
                details = (f"돌파유형: {exit_signal['timeframe']}봉 BB600 상단선\n"
                          f"BB600상단: ${exit_signal['bb600_upper']:.6f}\n"
                          f"Exit량: 50%\n잔여Position: 50%")
                
            elif exit_type == ExitType.BREAKEVEN_PROTECTION.value:
                # Profit ratio에 따라 제목 구분
                max_profit = exit_signal.get('max_profit_pct', 0)
                if max_profit >= 10.0:
                    emoji = "📈"
                    title = "Trailing 스톱 Exit"
                elif max_profit >= 5.0:
                    emoji = "🛡️" 
                    title = "절반 하락 Exit"
                else:
                    emoji = "💙"
                    title = "Approx수익 보호Exit"
                    
                details = (f"최대수익: {exit_signal['max_profit_pct']:.1f}%\n"
                          f"확보수익: {exit_signal['secured_profit']:.1f}%\n"
                          f"Exit량: 100% (전량)")
            
            elif exit_type == ExitType.WEAK_RISE_DUMP_PROTECTION.value:
                emoji = "🚨"
                title = "Approx상승후 급락 리스크 times피"
                details = (f"최대수익: {exit_signal['max_profit_pct']:.1f}%\n"
                          f"Current수익: {exit_signal['current_profit_pct']:.1f}%\n"
                          f"SuperTrend(10-2): 5봉이내 Exit신호\n"
                          f"Exit량: 100% (전량)")
            
            else:
                emoji = "📤"
                title = "Exit Complete"
                details = "New Exit 방식"
            
            message = (f"{emoji} [{title}] {clean_symbol}\n"
                      f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                      f"💵 Exit가: ${current_price:.6f}\n"
                      f"📊 Profit ratio: {current_profit_pct:+.1f}%\n"
                      f"{details}\n"
                      f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                      f"⚡️ {exit_signal.get('trigger_info', 'Exit 조건 충족')}\n"
                      f"🕐 ExitTime: {datetime.now().strftime('%H:%M:%S')}")
            
            self.telegram_bot.send_message(message)
            self.logger.info(f"{emoji} New Exit Notification 전송: {clean_symbol} - {title}")
            
        except Exception as e:
            self.logger.error(f"New Exit Notification 전송 Failed {symbol}: {e}")
    
    def cleanup_sent_notifications(self):
        """중복 Notification 기록 정리 (메모리 절Approx)"""
        try:
            # 24Time이 지난 기록들은 Remove (Required시)
            if len(self._sent_fill_notifications) > 1000:
                # 기록이 너무 많아지면 절반 정도 정리
                notifications_list = list(self._sent_fill_notifications)
                keep_count = 500
                self._sent_fill_notifications = set(notifications_list[-keep_count:])
                self.logger.debug(f"📝 중복 Notification 기록 Cleanup: {len(notifications_list)} → {keep_count}count")
        except Exception as e:
            self.logger.error(f"중복 Notification 기록 Cleanup Failed: {e}")
    
    def _register_existing_filled_orders(self):
        """이미 체결된 주문들에 대한 Notification 기록 Register (중복 방지)"""
        try:
            registered_count = 0
            for symbol, position in self.positions.items():
                if not position.is_active:
                    continue
                
                for entry in position.entries:
                    if entry.is_filled and entry.order_id:
                        notification_key = f"{symbol}_{entry.stage}_{entry.order_id}"
                        if notification_key not in self._sent_fill_notifications:
                            self._sent_fill_notifications.add(notification_key)
                            registered_count += 1
            
            if registered_count > 0:
                self._save_sent_notifications()  # 기록 Save
                self.logger.info(f"🔧 Legacy 체결 주문 {registered_count}count Notification 기록 Register (중복 방지)")
            
        except Exception as e:
            self.logger.error(f"Legacy 체결 주문 Register Failed: {e}")

    def _load_sent_notifications(self):
        """재Starting 시 이미 발송된 Notification 기록 Load"""
        try:
            notifications_file = os.path.join(os.path.dirname(self.data_file), 'sent_notifications.json')
            if os.path.exists(notifications_file):
                with open(notifications_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._sent_fill_notifications = set(data.get('notifications', []))
                    self.logger.info(f"📥 Notification 기록 Load: {len(self._sent_fill_notifications)}count")
            else:
                self.logger.debug("📥 Notification 기록 File Absent - 새로 Starting")
        except Exception as e:
            self.logger.warning(f"Notification 기록 Load Failed: {e}")
            self._sent_fill_notifications = set()
    
    def _save_sent_notifications(self):
        """발송된 Notification 기록 Save"""
        try:
            notifications_file = os.path.join(os.path.dirname(self.data_file), 'sent_notifications.json')
            
            # 최근 1000count만 Maintain (메모리 관리)
            if len(self._sent_fill_notifications) > 1000:
                notifications_list = list(self._sent_fill_notifications)
                self._sent_fill_notifications = set(notifications_list[-500:])  # 최근 500count만 Maintain
                self.logger.debug(f"📝 Notification 기록 자동 Cleanup: 1000+ → 500count")
            
            data = {
                'notifications': list(self._sent_fill_notifications),
                'last_updated': get_korea_time().isoformat(),
                'count': len(self._sent_fill_notifications)
            }
            
            with open(notifications_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.error(f"Notification 기록 Save Failed: {e}")

    def monitor_cyclic_opportunities(self, active_positions: Dict, current_prices: Dict) -> List[Dict]:
        """Cyclic trading 기times 모니터링"""
        try:
            opportunities = []
            
            for symbol in active_positions.keys():
                if symbol in self.positions:
                    position = self.positions[symbol]
                    if not position.is_active:
                        continue
                    
                    # Cyclic trading 제한 Confirm
                    if position.cyclic_count >= position.max_cyclic_count:
                        continue
                    
                    # Current price 조times
                    current_price = current_prices.get(symbol) or self.get_current_price(symbol)
                    if not current_price:
                        continue
                    
                    # Profit ratio 계산
                    profit_pct = (current_price - position.average_price) / position.average_price
                    
                    # Cyclic trading 조건 체크: 3% 이상 수익일 때
                    if profit_pct >= 0.03:  # 3% 이상 수익
                        # 최대 Profit ratio Update
                        if profit_pct > position.max_profit_pct:
                            position.max_profit_pct = profit_pct
                            position.last_update = get_korea_time().isoformat()
                            self.save_data()
                        
                        # Cyclic trading 기times 조건 (간소화)
                        # 1. Profit ratio이 5% 이상
                        # 2. 최대 Profit ratio vs 10% 이상 하락 시 일부 Exit
                        if (profit_pct >= 0.05 and 
                            position.max_profit_pct >= 0.05 and
                            profit_pct <= position.max_profit_pct * 0.9):  # 10% 하락
                            
                            opportunities.append({
                                'symbol': symbol,
                                'position': position,
                                'current_price': current_price,
                                'profit_pct': profit_pct,
                                'max_profit_pct': position.max_profit_pct,
                                'cyclic_count': position.cyclic_count,
                                'partial_ratio': 0.3,  # 30% 부분Exit
                                'trigger_type': 'cyclic_profit_taking'
                            })
            
            return opportunities
            
        except Exception as e:
            self.logger.error(f"Cyclic trading 기times 모니터링 Failed: {e}")
            return []

    def execute_cyclic_trading(self, opportunities: List[Dict]) -> Dict[str, Any]:
        """Cyclic trading Execute"""
        try:
            results = []
            executed_count = 0
            
            for opportunity in opportunities:
                try:
                    symbol = opportunity['symbol']
                    position = opportunity['position']
                    current_price = opportunity['current_price']
                    partial_ratio = opportunity['partial_ratio']
                    
                    # 부분Exit Execute (30%)
                    success = self._execute_partial_exit(
                        position, current_price, partial_ratio, 
                        f"Cyclic trading {position.cyclic_count + 1}times차"
                    )
                    
                    if success:
                        executed_count += 1
                        
                        # Cyclic trading 카운트 증가
                        position.cyclic_count += 1
                        position.last_cyclic_entry = get_korea_time().isoformat()
                        
                        # Cyclic trading Complete 체크
                        if position.cyclic_count >= position.max_cyclic_count:
                            position.cyclic_state = CyclicState.CYCLIC_COMPLETE.value
                        else:
                            position.cyclic_state = CyclicState.CYCLIC_ACTIVE.value
                        
                        position.last_update = get_korea_time().isoformat()
                        self.save_data()
                        
                        # 수익 계산
                        executed_amount = position.total_quantity * partial_ratio
                        realized_profit = executed_amount * (current_price - position.average_price)
                        position.total_cyclic_profit += realized_profit
                        
                        results.append({
                            'success': True,
                            'symbol': symbol,
                            'result': {
                                'executed_amount': executed_amount,
                                'realized_profit': realized_profit,
                                'cyclic_count': position.cyclic_count
                            }
                        })
                        
                        # 텔레그램 Notification
                        if self.telegram_bot:
                            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                            profit_pct = opportunity['profit_pct'] * 100
                            message = (f"🔄 Cyclic trading {position.cyclic_count}times차 Execute\n"
                                     f"Symbol: {clean_symbol}\n"
                                     f"Exit율: {partial_ratio*100:.0f}%\n"
                                     f"Profit ratio: {profit_pct:.1f}%\n"
                                     f"실현P&L: ${realized_profit:+.4f}\n"
                                     f"Progress: {position.cyclic_count}/{position.max_cyclic_count}times")
                            self.telegram_bot.send_message(message)
                        
                        self.logger.info(f"✅ Cyclic trading Execute: {symbol} {position.cyclic_count}times차 - {partial_ratio*100:.0f}% Exit")
                    
                    else:
                        results.append({
                            'success': False,
                            'symbol': symbol,
                            'error': 'Partial exit failed'
                        })
                        
                except Exception as opp_error:
                    self.logger.error(f"Cyclic trading Execute Failed {opportunity['symbol']}: {opp_error}")
                    results.append({
                        'success': False,
                        'symbol': opportunity['symbol'],
                        'error': str(opp_error)
                    })
            
            return {
                'executed': executed_count,
                'total_opportunities': len(opportunities),
                'results': results
            }
            
        except Exception as e:
            self.logger.error(f"Cyclic trading Execute Failed: {e}")
            return {
                'executed': 0,
                'total_opportunities': len(opportunities) if opportunities else 0,
                'results': [],
                'error': str(e)
            }

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Current price 조times"""
        try:
            if self.exchange:
                ticker = self.exchange.fetch_ticker(symbol)
                return float(ticker['last'])
            return None
        except Exception as e:
            self.logger.error(f"Current price 조times Failed {symbol}: {e}")
            return None

    def _execute_partial_exit(self, position: DCAPosition, current_price: float, partial_ratio: float, reason: str) -> bool:
        """부분Exit Execute"""
        try:
            # Exit할 Quantity 계산
            exit_quantity = position.total_quantity * partial_ratio
            
            # 시장가 매도 주문 Execute
            order_result = self._execute_market_order(position.symbol, exit_quantity, "sell")
            
            if order_result['success']:
                # Position Quantity Update
                position.total_quantity -= exit_quantity
                position.last_update = get_korea_time().isoformat()
                self.save_data()
                
                self.logger.info(f"✅ 부분Exit Complete: {position.symbol} - {partial_ratio*100:.0f}% ({reason})")
                return True
            else:
                self.logger.error(f"❌ 부분Exit Failed: {position.symbol} - {order_result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            self.logger.error(f"부분Exit Execute Failed {position.symbol}: {e}")
            return False

# 모듈 Test용 함수들
def test_dca_system():
    """DCA 시스템 Test"""
    print("=== DCA System Test ===")
    
    # Mock exchange (Test용)
    class MockExchange:
        def __init__(self):
            self.apiKey = "test_key"
        
        def fetch_positions(self):
            return []
        
        def fetch_ticker(self, symbol):
            return {'last': 50000.0}  # Test 가격
        
        def create_market_order(self, symbol, side, amount):
            return {
                'id': 'test_order_123',
                'filled': amount,
                'average': 50000.0
            }
    
    # DCA 시스템 Initialize
    mock_exchange = MockExchange()
    dca_manager = ImprovedDCAPositionManager(exchange=mock_exchange)
    
    # Test Position Add
    success = dca_manager.add_position(
        symbol="BTCUSDT",
        entry_price=50000.0,
        quantity=0.001,
        notional=500.0,
        leverage=10.0
    )
    
    print(f"Position Add Success: {success}")
    
    # Position 요Approx
    summary = dca_manager.get_position_summary()
    print(f"Position 요Approx: {summary}")
    
    # 시스템 Status
    health = dca_manager.get_system_health()
    print(f"System Status: {health['status']}")
    
    print("=== Test Complete ===")

if __name__ == "__main__":
    test_dca_system()