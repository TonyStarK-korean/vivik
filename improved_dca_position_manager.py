# -*- coding: utf-8 -*-
"""
🔄 개선된 순환매수 시스템 (DCA Position Manager)
SuperClaude Expert Mode Implementation

핵심 개선사항:
1. 동기화 문제 해결 - 거래소와 DCA 파일 간 실시간 동기화 강화
2. 청산 로직 통합 - 단일 책임 원칙 적용
3. 오류 처리 강화 - 네트워크/API 오류 대응
4. 중복 제거 - 불필요한 복잡성 제거
5. 테스트 가능한 구조로 개선
6. 고급 청산 시스템 통합 - 적응형 손절, 다단계 익절, 트레일링 스톱, 복합 기술적 청산
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

# 기존 고급/기본 청산 시스템 제거 - 새로운 4가지 청산 방식만 사용

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
    """한국 표준시(KST) 현재 시간을 반환 (UTC +9시간)"""
    return datetime.now(timezone(timedelta(hours=9)))

class PositionStage(Enum):
    """포지션 단계"""
    INITIAL = "initial"           # 최초 진입
    FIRST_DCA = "first_dca"      # 1차 추가매수
    SECOND_DCA = "second_dca"    # 2차 추가매수
    CLOSING = "closing"          # 청산 중

class ExitType(Enum):
    """청산 타입 - 새로운 8가지 청산 방식"""
    SUPERTREND_EXIT = "supertrend_exit"       # SuperTrend 전량청산
    PROFIT_10_PERCENT_EXIT = "profit_10_percent_exit" # 10% 수익 달성시 50% 익절청산
    BB600_PARTIAL_EXIT = "bb600_partial_exit" # BB600 50% 익절청산
    BREAKEVEN_PROTECTION = "breakeven_protection" # 절반 하락 청산
    WEAK_RISE_DUMP_PROTECTION = "weak_rise_dump_protection" # 약상승후 급락 리스크 회피
    BB80_BB600_REVERSAL_EXIT = "bb80_bb600_reversal_exit" # BB80-BB600 역전 기간 전량청산
    DCA_CYCLIC_EXIT = "dca_cyclic_exit"       # DCA 순환매 일부청산
    TIME_BASED_EXIT = "time_based_exit"       # 시간 기반 자동 청산 (2시간+5% 미만)

class CyclicState(Enum):
    """순환매 상태"""
    NORMAL_DCA = "normal_dca"           # 일반 DCA (순환매 아님)
    CYCLIC_ACTIVE = "cyclic_active"     # 순환매 활성 상태
    CYCLIC_PAUSED = "cyclic_paused"     # 순환매 일시 중단
    CYCLIC_COMPLETE = "cyclic_complete" # 순환매 완료 (3회 달성)

@dataclass
class DCAEntry:
    """DCA 진입 기록"""
    stage: str              # 진입 단계
    entry_price: float      # 진입가
    quantity: float         # 수량
    notional: float         # 명목가치 (USDT)
    leverage: float         # 레버리지
    timestamp: str          # 진입 시간
    is_active: bool = True  # 활성 상태
    order_type: str = "market"    # 주문 타입 (market/limit)
    order_id: str = ""            # 주문 ID (지정가 주문용)
    is_filled: bool = True        # 체결 상태 (시장가는 즉시 True, 지정가는 체결시 True)

@dataclass
class DCAPosition:
    """DCA 포지션 데이터"""
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
    last_cyclic_entry: str = ""  # 마지막 순환매 진입 시간
    total_cyclic_profit: float = 0.0  # 누적 순환매 수익
    
    # 새로운 5가지 청산 방식 추적
    max_profit_pct: float = 0.0  # 최대 수익률 추적
    bb600_exit_done: bool = False  # BB600 50% 청산 완료 여부
    breakeven_protection_active: bool = False  # 약수익 보호 활성화 여부
    breakeven_exit_done: bool = False  # 본절보호청산 완료 여부 (중복 방지용)
    supertrend_exit_done: bool = False  # SuperTrend 청산 완료 여부
    weak_rise_dump_exit_done: bool = False  # 약상승후 급락 리스크 회피 청산 완료 여부
    
    # 트레일링 스탑 관련 필드
    trailing_stop_active: bool = False  # 트레일링 스탑 활성화 여부
    trailing_stop_high: float = 0.0  # 트레일링 스탑 최고가 추적
    trailing_stop_percentage: float = 0.05  # 트레일링 스탑 비율 (5%)
    
    # 시간 기반 청산 관련 필드
    time_based_exit_done: bool = False  # 시간 기반 청산 완료 여부 (중복 방지)

class ImprovedDCAPositionManager:
    """개선된 순환매수 포지션 관리자"""
    
    def __init__(self, exchange=None, telegram_bot=None, stats_callback=None, strategy=None):
        self.exchange = exchange
        self.telegram_bot = telegram_bot
        self.stats_callback = stats_callback
        self.strategy = strategy
        
        # Logger 설정
        self.logger = logging.getLogger(__name__)
        
        # 파일 경로
        self.positions_file = "dca_positions.json"
        self.data_file = "dca_positions.json"  # _load_sent_notifications에서 사용
        self.limits_file = "dca_limits.json"
        self.backup_file = "dca_positions_backup.json"
        
        # 포지션 데이터
        self.positions = {}  # {symbol: DCAPosition}
        self.symbol_limits = {}  # {symbol: count}
        
        # 동기화 락
        self.sync_lock = threading.Lock()
        self.file_lock = threading.Lock()
        
        # 중복 알림 방지용 (체결 알림 중복 방지) - 파일 기반 지속성 추가
        self._sent_fill_notifications = set()  # {symbol_stage_orderid} 형태
        self._load_sent_notifications()  # 재시작 시 기존 알림 기록 로드
        
        # 청산 시스템 초기화 (누락된 속성들)
        self.advanced_exit_system = None  # 고급 청산 시스템 (미구현)
        self.basic_exit_system = None     # 기본 청산 시스템 (미구현)
        
        # 설정 (현재 2% 진입 상태에 맞춘 조정)
        self.config = {
            # DCA 진입 설정
            'initial_weight': 0.020,      # 최초 진입 비중 (2.0%) - 실제 진입 반영
            'initial_leverage': 10.0,     # 최초 진입 레버리지
            'first_dca_trigger': -0.03,   # 1차 추가매수 트리거 (-3%)
            'first_dca_weight': 0.025,    # 1차 추가매수 비중 (2.5%) - 최초 대비 1.25배
            'first_dca_leverage': 10.0,   # 1차 추가매수 레버리지
            'second_dca_trigger': -0.06,  # 2차 추가매수 트리거 (-6%)
            'second_dca_weight': 0.025,   # 2차 추가매수 비중 (2.5%) - 최초 대비 1.25배
            'second_dca_leverage': 10.0,  # 2차 추가매수 레버리지

            # 초기 진입가 기준 고정 손절 (-10% 고정)
            'stop_loss_fixed': -0.10,  # 초기 진입가 기준 -10% 고정 손절
            'stop_loss_by_stage': {
                'initial': -0.10,      # 초기 진입: -10% 손절 (초기 진입가 기준)
                'first_dca': -0.10,    # 1차 DCA 후: -10% 손절 (초기 진입가 기준)
                'second_dca': -0.10    # 2차 DCA 후: -10% 손절 (초기 진입가 기준)
            },

            # 수익 청산 전략
            'mid_profit_threshold': 0.05,   # 5% 중간 수익 기준
            'half_profit_threshold': 0.10,  # 10% 절반 청산 기준
            
            # 시스템 설정
            'max_dca_stages': 2,            # 최대 추가매수 단계
            'max_symbol_dca_count': 3,      # 심볼당 최대 순환매 사이클
            'max_total_positions': 10,      # 최대 보유 종목 수 (옵션A)
            'api_retry_count': 3,           # API 재시도 횟수
            'api_retry_delay': 1.0,         # API 재시도 지연 (초)
            'sync_interval': 15,            # 동기화 주기 (초)
        }
        
        # 로거 설정
        self.setup_logger()
        
        # 새로운 5가지 청산 방식만 사용
        self.logger.info("새로운 5가지 청산 방식 활성화: SuperTrend, 약수익보호, 약상승후급락리스크회피, BB600, DCA순환매")
        
        # 데이터 로드
        self.load_data()
        
        # 🔧 이미 체결된 주문들에 대한 알림 기록 추가 (중복 방지)
        self._register_existing_filled_orders()
        
        # 🔧 Exchange 연결 상태 추적 초기화
        self._exchange_connection_issues = 0
        self._last_exchange_check = 0
        
        # 초기 동기화 - 🔧 Exchange 연결 검증 강화
        if self.exchange:
            self.logger.info(f"🔍 Exchange 연결 상태 검증...")
            self.logger.info(f"🔍 Exchange type: {type(self.exchange).__name__}")
            self.logger.info(f"🔍 Has apiKey: {hasattr(self.exchange, 'apiKey')}")
            
            if hasattr(self.exchange, 'apiKey') and self.exchange.apiKey:
                api_key_preview = self.exchange.apiKey[:8] + "..." if len(self.exchange.apiKey) > 8 else self.exchange.apiKey
                self.logger.info(f"🔍 API Key: {api_key_preview} (길이: {len(self.exchange.apiKey)})")
                
                # 🔧 실제 API 연결 테스트
                try:
                    test_balance = self.exchange.fetch_balance()
                    self.logger.info(f"✅ API 연결 테스트 성공 - USDT 잔고 확인")
                    self.logger.info(f"거래소와 DCA 시스템 초기 동기화 시작...")
                    self.sync_with_exchange(force_sync=True)
                except Exception as api_test_error:
                    self.logger.error(f"❌ API 연결 테스트 실패: {api_test_error}")
                    if "apiKey" in str(api_test_error):
                        self.logger.error(f"🚨 API 키 문제 감지 - DCA 동기화 건너뛰기")
                        self._exchange_connection_issues += 1
                    
            else:
                self.logger.warning(f"⚠️ API 키 없음 - DCA 동기화 건너뛰기")
        else:
            self.logger.warning(f"⚠️ Exchange 없음 - DCA 동기화 건너뛰기")
        
        self.logger.info(f"개선된 DCA 시스템 초기화 완료")
        self.logger.info(f"활성 포지션: {len([p for p in self.positions.values() if p.is_active])}개")

    def _verify_exchange_connection(self) -> bool:
        """Exchange 연결 상태 검증"""
        try:
            if not self.exchange:
                return False
            
            # 현재 시간 체크 (너무 자주 체크하지 않도록)
            current_time = time.time()
            if current_time - self._last_exchange_check < 30:  # 30초 간격
                return True
            
            self._last_exchange_check = current_time
            
            # API 키 존재 여부 확인
            if not hasattr(self.exchange, 'apiKey') or not self.exchange.apiKey:
                self.logger.warning(f"❌ Exchange API 키 없음")
                return False
            
            # 간단한 API 호출 테스트
            try:
                self.exchange.fetch_balance()
                self._exchange_connection_issues = 0  # 성공시 리셋
                return True
            except Exception as e:
                self._exchange_connection_issues += 1
                if "apiKey" in str(e):
                    self.logger.error(f"❌ Exchange API 키 문제 #{self._exchange_connection_issues}: {e}")
                    # 메인 전략에 재연결 요청
                    if self.strategy and hasattr(self.strategy, '_request_exchange_reconnect'):
                        self.strategy._request_exchange_reconnect = True
                        self.logger.info(f"📨 메인 전략에 Exchange 재연결 요청 전송")
                else:
                    self.logger.warning(f"⚠️ Exchange 연결 문제 #{self._exchange_connection_issues}: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Exchange 연결 검증 실패: {e}")
            return False

    def refresh_exchange_connection(self, new_exchange):
        """메인 전략에서 호출 - Exchange 연결 갱신"""
        try:
            self.logger.info(f"🔄 Exchange 연결 갱신 요청 받음")
            
            if new_exchange and hasattr(new_exchange, 'apiKey') and new_exchange.apiKey:
                old_exchange_id = id(self.exchange) if self.exchange else None
                new_exchange_id = id(new_exchange)
                
                self.exchange = new_exchange
                self._exchange_connection_issues = 0
                self._last_exchange_check = 0
                
                self.logger.info(f"✅ Exchange 연결 갱신 완료")
                self.logger.info(f"🔍 Old Exchange ID: {old_exchange_id}")
                self.logger.info(f"🔍 New Exchange ID: {new_exchange_id}")
                self.logger.info(f"🔍 API Key: {new_exchange.apiKey[:8]}... (길이: {len(new_exchange.apiKey)})")
                
                # 연결 테스트
                try:
                    test_balance = self.exchange.fetch_balance()
                    self.logger.info(f"✅ 갱신된 Exchange 연결 테스트 성공")
                    return True
                except Exception as test_error:
                    self.logger.error(f"❌ 갱신된 Exchange 연결 테스트 실패: {test_error}")
                    return False
            else:
                self.logger.error(f"❌ 유효하지 않은 Exchange 객체")
                return False
                
        except Exception as e:
            self.logger.error(f"Exchange 연결 갱신 실패: {e}")
            return False

    def _update_average_price_safely(self, position: DCAPosition, new_avg_price: float, context: str = "unknown") -> bool:
        """평단가 안전 업데이트 (중앙화된 평단가 관리)"""
        try:
            with self.sync_lock:  # 스레드 안전성 보장
                old_avg_price = position.average_price
                price_change_pct = abs(new_avg_price - old_avg_price) / old_avg_price * 100 if old_avg_price > 0 else 0
                
                # 변경사항 검증
                if price_change_pct > 20.0:  # 20% 이상 변화시 경고
                    self.logger.error(f"🚨 평단가 급격한 변화 감지: {position.symbol} - {price_change_pct:.2f}% 변화 ({context})")
                    self.logger.error(f"   기존: ${old_avg_price:.6f} → 신규: ${new_avg_price:.6f}")
                    return False  # 급격한 변화는 차단
                
                # 평단가 업데이트
                position.average_price = new_avg_price
                position.last_update = get_korea_time().isoformat()
                
                # 로깅
                if price_change_pct > 0.1:  # 0.1% 이상 변화시에만 로깅
                    self.logger.info(f"💰 평단가 업데이트: {position.symbol} ({context})")
                    self.logger.info(f"   ${old_avg_price:.6f} → ${new_avg_price:.6f} ({price_change_pct:+.2f}%)")
                
                return True
                
        except Exception as e:
            self.logger.error(f"평단가 업데이트 실패 {position.symbol}: {e}")
            return False

    def setup_logger(self):
        """로거 설정"""
        self.logger = logging.getLogger('ImprovedDCAManager')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            # 파일 핸들러
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
        """데이터 로드"""
        with self.file_lock:
            # 포지션 데이터 로드
            try:
                if os.path.exists(self.positions_file):
                    with open(self.positions_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for symbol, pos_data in data.items():
                            # DCAEntry 객체로 변환
                            entries = [DCAEntry(**entry) for entry in pos_data['entries']]
                            pos_data['entries'] = entries
                            
                            # 트레일링 스탑 필드 마이그레이션 (기존 포지션 호환성)
                            if 'trailing_stop_active' not in pos_data:
                                pos_data['trailing_stop_active'] = False
                            if 'trailing_stop_high' not in pos_data:
                                pos_data['trailing_stop_high'] = 0.0
                            if 'trailing_stop_percentage' not in pos_data:
                                pos_data['trailing_stop_percentage'] = 0.05
                            
                            self.positions[symbol] = DCAPosition(**pos_data)
                    self.logger.info(f"포지션 데이터 로드 완료: {len(self.positions)}개")
                else:
                    self.positions = {}
                    self.logger.info("포지션 파일 없음 - 새로 시작")
            except Exception as e:
                self.logger.error(f"포지션 데이터 로드 실패: {e}")
                # 백업 파일 시도
                if os.path.exists(self.backup_file):
                    try:
                        with open(self.backup_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            for symbol, pos_data in data.items():
                                entries = [DCAEntry(**entry) for entry in pos_data['entries']]
                                pos_data['entries'] = entries
                                self.positions[symbol] = DCAPosition(**pos_data)
                        self.logger.info(f"백업 파일에서 복구 완료: {len(self.positions)}개")
                    except Exception as be:
                        self.logger.error(f"백업 파일 복구 실패: {be}")
                        self.positions = {}
                else:
                    self.positions = {}
            
            # 제한 데이터 로드
            try:
                if os.path.exists(self.limits_file):
                    with open(self.limits_file, 'r', encoding='utf-8') as f:
                        self.symbol_limits = json.load(f)
                    self.logger.info(f"제한 데이터 로드 완료: {len(self.symbol_limits)}개")
                else:
                    self.symbol_limits = {}
            except Exception as e:
                self.logger.error(f"제한 데이터 로드 실패: {e}")
                self.symbol_limits = {}

    def save_data(self):
        """데이터 저장"""
        with self.file_lock:
            try:
                # 백업 생성
                if os.path.exists(self.positions_file):
                    import shutil
                    shutil.copy2(self.positions_file, self.backup_file)
                
                # 포지션 데이터 저장
                data = {}
                for symbol, position in self.positions.items():
                    # DCAEntry를 dict로 변환
                    entries_dict = [asdict(entry) for entry in position.entries]
                    pos_dict = asdict(position)
                    pos_dict['entries'] = entries_dict
                    data[symbol] = pos_dict
                
                with open(self.positions_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                # 제한 데이터 저장
                with open(self.limits_file, 'w', encoding='utf-8') as f:
                    json.dump(self.symbol_limits, f, ensure_ascii=False, indent=2)
                
                self.logger.debug("데이터 저장 완료")
                
            except Exception as e:
                self.logger.error(f"데이터 저장 실패: {e}")

    def force_sync_with_exchange(self, actual_positions=None):
        """
        강제 DCA 포지션 동기화 - 전략 시스템과 완전 동기화
        
        Args:
            actual_positions: 전략 시스템에서 전달받은 실제 거래소 포지션 데이터
        """
        try:
            print(f"[DCA강제동기화] 🔄 DCA 시스템 강제 동기화 시작...")
            
            # 기존 포지션 상태 저장
            old_active_count = len([p for p in self.positions.values() if p.is_active])
            
            if actual_positions:
                # 전략 시스템에서 받은 실제 포지션 데이터 사용
                existing_symbols = set(actual_positions.keys())
                
                # DCA 포지션 중 실제 거래소에 없는 것들은 비활성화
                for symbol, dca_position in self.positions.items():
                    if dca_position.is_active:
                        if symbol not in existing_symbols:
                            print(f"[DCA강제동기화] 🧹 {symbol} DCA 포지션 정리 (거래소에 없음)")
                            dca_position.is_active = False
                            dca_position.current_stage = PositionStage.CLOSING.value
                            
                # 거래소에만 있고 DCA에 없는 포지션은 새로 추가 (수동 진입의 경우)
                for symbol in existing_symbols:
                    if symbol not in self.positions:
                        print(f"[DCA강제동기화] ➕ {symbol} 새 포지션 감지 (DCA 등록 필요)")
                        # 필요시 여기서 새 DCA 포지션 생성 로직 추가
                        
            else:
                # 거래소에서 직접 조회
                exchange_positions = self._fetch_exchange_positions_safe()
                existing_symbols = set([p['symbol'] for p in exchange_positions]) if exchange_positions else set()
                
                # DCA 포지션 정리
                for symbol, dca_position in self.positions.items():
                    if dca_position.is_active:
                        if symbol not in existing_symbols:
                            print(f"[DCA강제동기화] 🧹 {symbol} DCA 포지션 정리")
                            dca_position.is_active = False
                            dca_position.current_stage = PositionStage.CLOSING.value
            
            # 변경사항 저장
            self.save_positions()
            
            # 새로운 활성 포지션 수 계산
            new_active_count = len([p for p in self.positions.values() if p.is_active])
            
            print(f"[DCA강제동기화] ✅ 완료: {old_active_count}개 → {new_active_count}개")
            
            return new_active_count
            
        except Exception as e:
            print(f"[DCA강제동기화] ❌ 오류 발생: {e}")
            return len([p for p in self.positions.values() if p.is_active]) if hasattr(self, 'positions') else 0

    def sync_with_exchange(self, force_sync=False):
        """거래소와 동기화 - 핵심 개선"""
        if not self.exchange:
            return {'success': False, 'error': 'Exchange not available'}
        
        with self.sync_lock:
            try:
                self.logger.info("🔄 거래소와 DCA 시스템 동기화 시작...")
                
                # 거래소 포지션 조회
                exchange_positions = self._fetch_exchange_positions_safe()
                
                # 포지션이 없으면 고아 포지션만 정리
                if not exchange_positions:
                    # DCA 포지션이 있는데 거래소에 없으면 정리
                    orphaned_count = 0
                    for symbol in list(self.positions.keys()):
                        self._cleanup_orphaned_position(symbol)
                        orphaned_count += 1
                    
                    if orphaned_count > 0:
                        self.logger.info(f"🧹 고아 포지션 {orphaned_count}개 정리 완료")
                    
                    return {
                        'success': True,
                        'new_detected': [],
                        'orphaned_cleaned': list(self.positions.keys()) if orphaned_count > 0 else [],
                        'updated': [],
                        'message': '포지션 없음 - 정리 완료'
                    }
                
                # 현재 DCA 포지션과 비교
                dca_symbols = set(self.positions.keys())
                exchange_symbols = set(pos['symbol'] for pos in exchange_positions if pos['contracts'] > 0)
                
                sync_result = {
                    'success': True,
                    'new_detected': [],
                    'orphaned_cleaned': [],
                    'updated': [],
                    'errors': []
                }
                
                # 1. 거래소에 있지만 DCA에 없는 포지션 감지 (기존 포지션)
                for pos in exchange_positions:
                    symbol = pos['symbol']
                    if pos['contracts'] > 0 and symbol not in dca_symbols:
                        # 기존 포지션을 DCA 시스템에 등록
                        self._register_existing_position(symbol, pos)
                        sync_result['new_detected'].append(symbol)
                        self.logger.info(f"✅ 기존 포지션 등록: {symbol}")
                
                # 2. DCA에 있지만 거래소에 없는 포지션 정리 (고아 포지션)
                for symbol in list(dca_symbols):
                    if symbol not in exchange_symbols:
                        self._cleanup_orphaned_position(symbol)
                        sync_result['orphaned_cleaned'].append(symbol)
                        self.logger.info(f"🧹 고아 포지션 정리: {symbol}")
                
                # 3. 양쪽에 모두 있는 포지션 동기화
                for pos in exchange_positions:
                    symbol = pos['symbol']
                    if pos['contracts'] > 0 and symbol in dca_symbols:
                        if self._update_position_from_exchange(symbol, pos):
                            sync_result['updated'].append(symbol)
                
                # 데이터 저장
                self.save_data()
                
                self.logger.info(f"🔄 동기화 완료: 신규감지 {len(sync_result['new_detected'])}개, "
                               f"고아정리 {len(sync_result['orphaned_cleaned'])}개, "
                               f"업데이트 {len(sync_result['updated'])}개")
                
                return sync_result
                
            except Exception as e:
                self.logger.error(f"동기화 실패: {e}")
                self.logger.error(traceback.format_exc())
                return {'success': False, 'error': str(e)}

    def _fetch_exchange_positions_safe(self):
        """안전한 거래소 포지션 조회"""
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
                # Rate Limit 상태 체크
                if (hasattr(self.strategy, '_api_rate_limited') and 
                    self.strategy._api_rate_limited):
                    self.logger.debug("🚨 Rate limit 상태 - 포지션 조회 건너뛰기")
                    return []
                
                positions = self.exchange.fetch_positions()
                
                # 포지션이 없으면 빈 리스트 반환
                if not positions:
                    self.logger.info("💵 현재 계좌에 포지션 없음")
                    return []
                
                # 포지션 데이터 처리
                active_positions = []
                for pos in positions:
                    if not pos or not pos.get('symbol'):
                        continue
                    
                    # 수량이 0이면 비활성 포지션으로 간주
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
                    self.logger.info("💵 활성 포지션 없음 (모두 0 수량)")
                    return []
                
                return active_positions
                
            except Exception as e:
                self.logger.warning(f"포지션 조회 시도 {attempt + 1}/{self.config['api_retry_count']} 실패: {e}")
                if attempt < self.config['api_retry_count'] - 1:
                    time.sleep(self.config['api_retry_delay'] * (attempt + 1))
                else:
                    self.logger.info("💵 포지션 조회 실패 - 포지션 없음으로 처리")
                    return []
        return []

    def _register_existing_position(self, symbol: str, exchange_pos: dict):
        """기존 포지션을 DCA 시스템에 등록"""
        try:
            entry_price = exchange_pos['entry_price']
            quantity = exchange_pos['contracts']
            notional = exchange_pos['notional']
            
            # DCAEntry 생성
            entry = DCAEntry(
                stage="initial",
                entry_price=entry_price,
                quantity=quantity,
                notional=abs(notional),
                leverage=self.config['initial_leverage'],
                timestamp=get_korea_time().isoformat(),
                is_active=True
            )
            
            # DCAPosition 생성
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
            self.logger.info(f"기존 포지션 등록: {symbol} - 진입가: {entry_price}, 수량: {quantity}")
            
        except Exception as e:
            self.logger.error(f"기존 포지션 등록 실패 {symbol}: {e}")

    def _cleanup_orphaned_position(self, symbol: str):
        """고아 포지션 정리"""
        try:
            if symbol in self.positions:
                # 미체결 지정가 주문 취소
                cancel_result = self._cancel_pending_orders(symbol)
                if cancel_result['success'] and cancel_result['cancelled_count'] > 0:
                    self.logger.info(f"📋 고아 포지션 미체결 주문 취소: {symbol} - {cancel_result['cancelled_count']}개")
                
                self.logger.info(f"고아 포지션 정리: {symbol}")
                del self.positions[symbol]
                
                # 메인 전략의 active_positions도 정리
                if self.strategy and hasattr(self.strategy, 'active_positions'):
                    if symbol in self.strategy.active_positions:
                        del self.strategy.active_positions[symbol]
                        self.logger.info(f"메인 전략 포지션도 정리: {symbol}")
                
        except Exception as e:
            self.logger.error(f"고아 포지션 정리 실패 {symbol}: {e}")

    def _update_position_from_exchange(self, symbol: str, exchange_pos: dict) -> bool:
        """거래소 포지션으로부터 DCA 포지션 업데이트 - 강화된 동기화"""
        try:
            if symbol not in self.positions:
                return False
            
            position = self.positions[symbol]
            current_quantity = exchange_pos['contracts']
            current_notional = abs(exchange_pos['notional'])
            
            # 수량 차이가 있으면 업데이트
            if abs(position.total_quantity - current_quantity) > 0.001:
                old_quantity = position.total_quantity
                
                # 🚨 핵심 수정: entries 데이터도 실제 포지션에 맞게 조정
                if current_quantity < old_quantity:
                    # 실제 포지션이 줄어든 경우 (부분청산 발생)
                    reduction_ratio = current_quantity / old_quantity if old_quantity > 0 else 0
                    
                    # 활성 entries를 비례적으로 줄임
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
                    
                    # 평단가 재계산
                    active_entries = [e for e in position.entries if e.is_active and e.is_filled and e.quantity > 0.001]
                    if active_entries:
                        total_notional = sum(e.entry_price * e.quantity for e in active_entries)
                        total_qty = sum(e.quantity for e in active_entries)
                        position.average_price = total_notional / total_qty if total_qty > 0 else position.initial_entry_price
                    
                    self.logger.info(f"🔄 포지션 축소 동기화: {symbol}")
                    self.logger.info(f"   수량: {old_quantity:.6f} → {current_quantity:.6f} ({reduction_ratio:.2%})")
                    self.logger.info(f"   단계: {position.current_stage}")
                    self.logger.info(f"   평단가: ${position.average_price:.6f}")
                
                position.total_quantity = current_quantity
                position.total_notional = current_notional
                position.last_update = get_korea_time().isoformat()
                
                self.logger.info(f"포지션 수량 동기화: {symbol} - {old_quantity} → {current_quantity}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"포지션 업데이트 실패 {symbol}: {e}")
            return False

    def add_position(self, symbol: str, entry_price: float, quantity: float,
                    notional: float, leverage: float = 10.0, total_balance: float = None) -> bool:
        """새로운 포지션 추가 (DCA 지정가 주문 자동 생성 포함)"""
        try:
            with self.sync_lock:
                if symbol in self.positions and self.positions[symbol].is_active:
                    self.logger.warning(f"이미 활성 포지션 존재: {symbol}")
                    return False

                # DCAEntry 생성 (최초 진입)
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

                # DCAPosition 생성
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

                self.logger.info(f"새 포지션 추가: {symbol} - 진입가: {entry_price}, 수량: {quantity}")

                # 📋 최초 진입 즉시 DCA 1차, 2차 지정가 주문 자동 생성
                self.logger.info(f"🔍 DCA 지정가 주문 자동 생성 조건 확인: total_balance={total_balance}, exchange={self.exchange is not None}")
                if total_balance and self.exchange:
                    self.logger.info(f"🎯 DCA 지정가 주문 자동 생성 호출 시작: {symbol}")
                    self._create_initial_dca_limit_orders(position, total_balance)
                    self.logger.info(f"🎯 DCA 지정가 주문 자동 생성 호출 완료: {symbol}")
                else:
                    if not total_balance:
                        self.logger.warning(f"⚠️ DCA 지정가 주문 건너뛰기: total_balance가 없음 ({total_balance})")
                    if not self.exchange:
                        self.logger.warning(f"⚠️ DCA 지정가 주문 건너뛰기: exchange가 없음")

                # 텔레그램 알림 제거 (메인 전략에서 통합 알림 전송)
                # if self.telegram_bot:
                #     message = f"📈 DCA 포지션 추가\n심볼: {symbol}\n진입가: ${entry_price:.4f}\n수량: {quantity}\n레버리지: {leverage}x"
                #     self.telegram_bot.send_message(message)

                return True

        except Exception as e:
            self.logger.error(f"포지션 추가 실패 {symbol}: {e}")
            return False

    def _create_initial_dca_limit_orders(self, position: DCAPosition, total_balance: float):
        """최초 진입시 DCA 1차, 2차 지정가 주문 자동 생성"""
        try:
            self.logger.info(f"🎯 {position.symbol} DCA 지정가 주문 자동 생성 시작...")
            self.logger.info(f"   진입가: ${position.initial_entry_price:.6f}")

            # 현재가 조회 (DCA 주문 안전장치)
            try:
                ticker = self.exchange.fetch_ticker(position.symbol)
                current_price = ticker['last']
                self.logger.info(f"현재가 확인: {position.symbol} ${current_price:.6f}")
            except Exception as e:
                self.logger.error(f"현재가 조회 실패 {position.symbol}: {e}")
                current_price = position.initial_entry_price  # Fallback

            # 1차 DCA 지정가 주문 (-3%)
            first_dca_price = position.initial_entry_price * (1 + self.config['first_dca_trigger'])
            first_dca_amount = total_balance * self.config['first_dca_weight']
            first_dca_leverage = self.config['first_dca_leverage']
            first_dca_quantity = (first_dca_amount * first_dca_leverage) / first_dca_price

            # 🔒 DCA 지정가 주문 안전장치 개선 (하락매수 허용)
            try:
                current_price = float(current_price)
                first_dca_price = float(first_dca_price)
            except (ValueError, TypeError):
                self.logger.error(f"❌ 타입 변환 실패: current_price={current_price}, first_dca_price={first_dca_price}")
                first_order_result = {'success': False, 'error': 'Price type conversion failed'}
                
            # ✅ 수정된 안전장치: DCA는 하락매수이므로 현재가가 DCA가격보다 높아야 정상
            # 현재가가 DCA 가격보다 20% 이상 낮으면 과도한 하락으로 판단하여 주문 보류
            if current_price < first_dca_price * 0.80:  # DCA 가격의 80% 미만일 때만 스킵
                self.logger.warning(f"⚠️ 1차 DCA 주문 보류: 과도한 하락 - 현재가(${current_price:.6f}) < DCA가격의 80%(${first_dca_price*0.80:.6f})")
                first_order_result = {'success': False, 'error': 'Excessive price drop - DCA order postponed'}
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
                self.logger.info(f"✅ 1차 DCA 지정가 주문 등록: {position.symbol} @ ${first_dca_price:.4f} (ID: {first_order_result['order_id']})")
            else:
                self.logger.error(f"❌ 1차 DCA 지정가 주문 실패: {position.symbol}")

            # 2차 DCA 지정가 주문 (-6%)
            second_dca_price = position.initial_entry_price * (1 + self.config['second_dca_trigger'])
            second_dca_amount = total_balance * self.config['second_dca_weight']
            second_dca_leverage = self.config['second_dca_leverage']
            second_dca_quantity = (second_dca_amount * second_dca_leverage) / second_dca_price

            # 🔒 DCA 지정가 주문 안전장치 개선 (하락매수 허용)
            try:
                current_price = float(current_price)
                second_dca_price = float(second_dca_price)
            except (ValueError, TypeError):
                self.logger.error(f"❌ 타입 변환 실패: current_price={current_price}, second_dca_price={second_dca_price}")
                second_order_result = {'success': False, 'error': 'Price type conversion failed'}
                
            # ✅ 수정된 안전장치: DCA는 하락매수이므로 현재가가 DCA가격보다 높아야 정상
            # 현재가가 DCA 가격보다 20% 이상 낮으면 과도한 하락으로 판단하여 주문 보류
            if current_price < second_dca_price * 0.80:  # DCA 가격의 80% 미만일 때만 스킵
                self.logger.warning(f"⚠️ 2차 DCA 주문 보류: 과도한 하락 - 현재가(${current_price:.6f}) < DCA가격의 80%(${second_dca_price*0.80:.6f})")
                second_order_result = {'success': False, 'error': 'Excessive price drop - DCA order postponed'}
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
                self.logger.info(f"✅ 2차 DCA 지정가 주문 등록: {position.symbol} @ ${second_dca_price:.4f} (ID: {second_order_result['order_id']})")
            else:
                self.logger.error(f"❌ 2차 DCA 지정가 주문 실패: {position.symbol}")

            # 데이터 저장
            self.save_data()

            # 텔레그램 알림 제거 (메인 전략의 통합 알림에 DCA 정보 포함됨)
            # if self.telegram_bot and (first_order_result['success'] or second_order_result['success']):
            #     orders_info = []
            #     if first_order_result['success']:
            #         orders_info.append(f"1차: ${first_dca_price:.4f} (-3%)")
            #     if second_order_result['success']:
            #         orders_info.append(f"2차: ${second_dca_price:.4f} (-6%)")
            #
            #     message = (f"📋 DCA 지정가 주문 자동 등록\n"
            #               f"심볼: {position.symbol}\n"
            #               f"{chr(10).join(orders_info)}")
            #     self.telegram_bot.send_message(message)

            self.logger.info(f"🎉 {position.symbol} DCA 지정가 주문 자동 생성 완료")

        except Exception as e:
            self.logger.error(f"DCA 지정가 주문 자동 생성 실패 {position.symbol}: {e}")

    def place_missing_dca_orders_after_partial_exit(self, symbol: str, current_price: float) -> Dict[str, Any]:
        """부분청산 이후 빈 DCA 단계에 자동 지정가 주문 재등록 (최대 3회 순환매 지원)"""
        try:
            if symbol not in self.positions:
                return {'orders_placed': 0, 'error': 'Position not found'}
            
            position = self.positions[symbol]
            if not position.is_active:
                return {'orders_placed': 0, 'error': 'Position inactive'}
            
            # 순환매 제한 확인
            if position.cyclic_count >= position.max_cyclic_count:
                return {'orders_placed': 0, 'error': f'Max cyclic limit reached: {position.cyclic_count}/{position.max_cyclic_count}'}
            
            self.logger.info(f"🔄 {symbol} DCA 재주문 검토 시작 (순환매 {position.cyclic_count}/{position.max_cyclic_count}회)")
            
            # 현재 DCA 상태 분석
            stage_status = {}
            for entry in position.entries:
                stage_status[entry.stage] = {
                    'exists': True,
                    'is_active': entry.is_active,
                    'is_filled': entry.is_filled,
                    'order_id': entry.order_id
                }
            
            # 빈 단계 또는 비활성화된 단계 확인
            missing_stages = []
            
            # 1차 DCA 확인
            if ('first_dca' not in stage_status or 
                not stage_status['first_dca']['is_active'] or 
                stage_status['first_dca']['is_filled']):
                missing_stages.append('first_dca')
            
            # 2차 DCA 확인
            if ('second_dca' not in stage_status or 
                not stage_status['second_dca']['is_active'] or 
                stage_status['second_dca']['is_filled']):
                missing_stages.append('second_dca')
            
            if not missing_stages:
                return {'orders_placed': 0, 'message': 'All DCA orders already active'}
            
            # 잔고 확인 (간소화 - 기본값 사용)
            try:
                balance = self.exchange.fetch_balance() if self.exchange else None
                total_balance = balance.get('USDT', {}).get('free', 100.0) if balance else 100.0
            except:
                total_balance = 100.0  # 기본값
            
            orders_placed = 0
            order_results = []
            
            # 각 빈 단계에 대해 지정가 주문 생성
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
                    
                    # 안전장치: 현재가가 DCA 가격보다 5% 이상 낮으면 주문 건너뜀
                    try:
                        current_price = float(current_price)
                        dca_price = float(dca_price)
                    except (ValueError, TypeError):
                        self.logger.error(f"❌ 재주문 타입 변환 실패: current_price={current_price}, dca_price={dca_price}")
                        continue
                        
                    if current_price < dca_price * 0.95:
                        self.logger.warning(f"⚠️ {stage} 재주문 건너뜀: 현재가(${current_price:.6f}) < DCA가격의 95%(${dca_price*0.95:.6f})")
                        continue
                    
                    # 지정가 주문 실행
                    order_result = self._execute_limit_order(symbol, dca_quantity, "buy", dca_price)
                    
                    if order_result['success']:
                        # 기존 같은 단계 주문이 있다면 비활성화
                        for entry in position.entries:
                            if entry.stage == stage:
                                entry.is_active = False
                        
                        # 새 DCA 진입 기록 추가
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
                        
                        self.logger.info(f"✅ {stage} 재주문 등록: {symbol} @ ${dca_price:.4f} (ID: {order_result['order_id']})")
                    
                    else:
                        self.logger.error(f"❌ {stage} 재주문 실패: {symbol} - {order_result.get('error', 'Unknown error')}")
                
                except Exception as stage_error:
                    self.logger.error(f"❌ {stage} 재주문 처리 실패: {stage_error}")
                    continue
            
            # 데이터 저장
            if orders_placed > 0:
                self.save_data()
                self.logger.info(f"🔄 {symbol} DCA 재주문 완료: {orders_placed}개 주문 등록")
            
            return {
                'orders_placed': orders_placed,
                'order_results': order_results,
                'missing_stages': missing_stages,
                'success': orders_placed > 0
            }
            
        except Exception as e:
            self.logger.error(f"DCA 재주문 실패 {symbol}: {e}")
            return {
                'orders_placed': 0,
                'error': str(e),
                'success': False
            }

    def enter_new_position(self, symbol: str, entry_price: float, balance: float, leverage: float = 10.0) -> Dict[str, Any]:
        """새로운 포지션 진입 (메인 전략 호환용 래퍼 메서드)"""
        try:
            # 🔧 심볼 포맷 변환 (Binance Futures 호환성)
            converted_symbol = self._convert_to_binance_futures_symbol(symbol)
            if not converted_symbol:
                return {
                    'success': False,
                    'error': f'Symbol conversion failed: {symbol}'
                }
            
            # 진입 금액 및 수량 계산 (타입 안전성 강화)
            try:
                balance = float(balance) if balance is not None else 0.0
                entry_price = float(entry_price) if entry_price is not None else 0.0
                leverage = float(leverage) if leverage is not None else 10.0
                initial_weight = float(self.config['initial_weight']) if self.config.get('initial_weight') is not None else 0.02
                
                # 값 검증
                if balance <= 0:
                    return {'success': False, 'error': f'잘못된 잔고: {balance}'}
                if entry_price <= 0:
                    return {'success': False, 'error': f'잘못된 진입가: {entry_price}'}
                if leverage <= 0:
                    return {'success': False, 'error': f'잘못된 레버리지: {leverage}'}
                    
            except (ValueError, TypeError) as type_error:
                self.logger.error(f'[DCA진입] 타입 변환 실패: balance={balance} ({type(balance)}), entry_price={entry_price} ({type(entry_price)}), leverage={leverage} ({type(leverage)}) - {type_error}')
                return {
                    'success': False,
                    'error': f'타입 변환 실패: balance={balance} ({type(balance)}), entry_price={entry_price} ({type(entry_price)}), leverage={leverage} ({type(leverage)}) - {type_error}'
                }
                
            entry_amount = balance * initial_weight
            position_value = entry_amount * leverage
            quantity = position_value / entry_price

            # 🔧 주문 수량 검증 및 조정
            validated_quantity = self._validate_order_amount(converted_symbol, quantity)
            if validated_quantity <= 0:
                return {
                    'success': False,
                    'error': f'Invalid quantity after validation: {validated_quantity} (original: {quantity})'
                }
            
            # 🔧 최소 주문 금액 체크 ($5 이상)
            notional_value = validated_quantity * entry_price
            if notional_value < 5.0:
                return {
                    'success': False,
                    'error': f'Notional value too small: ${notional_value:.2f} < $5.00'
                }

            # 시장가 주문 실행 (변환된 심볼 사용)
            order_result = self._execute_market_order(converted_symbol, validated_quantity, "buy")

            if not order_result['success']:
                return {
                    'success': False,
                    'error': 'Market order failed'
                }

            # DCA 포지션 추가 (지정가 주문 자동 생성 포함) - 변환된 심볼 사용
            success = self.add_position(
                symbol=converted_symbol,
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
                    'position_id': converted_symbol  # 변환된 심볼 반환
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to add DCA position'
                }

        except Exception as e:
            self.logger.error(f"포지션 진입 실패 {symbol}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def check_triggers(self, total_balance: float) -> Dict[str, Any]:
        """DCA 트리거 확인 - 핵심 로직"""
        try:
            if not self.exchange:
                return {'error': 'Exchange not available'}
            
            results = {}
            
            for symbol, position in list(self.positions.items()):
                if not position.is_active:
                    continue
                
                try:
                    # 현재가 조회
                    ticker = self.exchange.fetch_ticker(symbol)
                    current_price = float(ticker['last'])
                    
                    # 트리거 확인
                    trigger_result = self._check_position_triggers(symbol, current_price, total_balance)
                    if trigger_result:
                        results[symbol] = trigger_result
                
                except Exception as e:
                    self.logger.error(f"트리거 확인 실패 {symbol}: {e}")
                    continue
            
            return results
            
        except Exception as e:
            self.logger.error(f"전체 트리거 확인 실패: {e}")
            return {'error': str(e)}

    def check_dca_triggers(self, symbol: str, current_price: float) -> Optional[Dict[str, Any]]:
        """메인 전략에서 호출하는 DCA 트리거 확인 (SuperTrend 청산 포함)"""
        try:
            if symbol not in self.positions:
                return None
            
            position = self.positions[symbol]
            if not position.is_active:
                return None
            
            # 🔄 실제 거래소 포지션 동기화 체크 (포지션 동기화 문제 해결)
            try:
                real_positions = self.exchange.fetch_positions([symbol])
                active_position = None
                for pos in real_positions:
                    if pos['symbol'] == symbol and pos['contracts'] > 0:
                        active_position = pos
                        break
                
                if not active_position:
                    self.logger.warning(f"⚠️ {symbol} DCA 파일에 있지만 실제 거래소 포지션 없음 - 동기화 수행")
                    # DCA 파일에서 해당 포지션을 비활성화
                    position.is_active = False
                    position.current_stage = "closing"
                    position.last_update = get_korea_time().isoformat()
                    self.save_data()
                    self.logger.info(f"✅ {symbol} DCA 포지션 비활성화 완료 (실제 포지션 없음)")
                    return None
                    
            except Exception as e:
                self.logger.warning(f"⚠️ {symbol} 거래소 포지션 동기화 확인 실패: {e} - DCA 체크 계속 진행")
            
            # 🚨 중요: 가격이 None이면 거래소에서 직접 조회 (손절 실패 방지)
            if current_price is None:
                try:
                    self.logger.warning(f"⚠️ {symbol} 가격 정보 없음 - 손절을 위해 거래소 직접 조회")
                    ticker = self.exchange.fetch_ticker(symbol)
                    current_price = float(ticker['last'])
                    self.logger.info(f"✅ {symbol} 거래소 가격 조회 성공: ${current_price:.6f}")
                except Exception as e:
                    self.logger.error(f"❌ {symbol} 거래소 가격 조회 실패 - 손절 건너뜀: {e}")
                    return None
            
            # 현재 수익률 계산 (초기 진입가 기준으로 변경) - 타입 안전성 강화
            try:
                current_price = float(current_price)
                initial_entry_price = float(position.initial_entry_price)
                if initial_entry_price <= 0:
                    self.logger.error(f"잘못된 초기 진입가: {initial_entry_price}")
                    return None
                profit_pct = (current_price - initial_entry_price) / initial_entry_price
            except (ValueError, TypeError, ZeroDivisionError) as calc_error:
                self.logger.error(f"수익률 계산 실패 {symbol}: current_price={current_price} ({type(current_price)}), initial_entry_price={position.initial_entry_price} ({type(position.initial_entry_price)}) - {calc_error}")
                return None
            
            # 1. 기본 손절 체크 (최우선) 🚨 수정: 메인 전략에서도 손절 체크
            stop_loss_result = self._check_stop_loss_trigger(position, current_price, profit_pct)
            if stop_loss_result:
                self.logger.critical(f"🚨 손절 트리거 감지: {symbol} - 수익률: {profit_pct*100:.2f}%")
                return stop_loss_result
                
            # 1.2. 시간 기반 청산 체크 (2시간 + 5% 미만 조건) - 새로운 2순위
            time_based_exit_trigger = self._check_time_based_exit(position, current_price, profit_pct)
            if time_based_exit_trigger:
                self.logger.critical(f"⏰ 시간 기반 청산 조건 충족: {symbol} - 보유시간: {time_based_exit_trigger['hold_hours']:.1f}시간, 수익률: {profit_pct*100:.2f}%")
                # 실제 청산 실행
                success = self._execute_emergency_exit(position, current_price, "time_based_exit")
                if success:
                    position.time_based_exit_done = True
                    self.save_data()
                    self.logger.critical(f"⏰ 시간 기반 청산 완료: {symbol}")
                return {
                    'trigger_activated': True,
                    'action': 'time_based_exit_executed' if success else 'time_based_exit_failed',
                    'trigger_info': time_based_exit_trigger
                }
                
            # 1.5. BB80 > BB600 조건 + 원금수익률 5% 이상시 수동청산 전환 체크 (새로운 3순위)
            manual_exit_trigger = self._check_bb80_bb600_manual_exit(symbol, current_price, profit_pct)
            if manual_exit_trigger:
                self.logger.critical(f"🎯 BB80>BB600 수동청산 조건 충족: {symbol} - 원금수익률: {profit_pct*100:.2f}%")
                # 수동청산 전환이므로 실제 청산하지 않고 신호만 반환
                return {
                    'trigger_activated': True,
                    'action': 'manual_exit_required',
                    'trigger_info': manual_exit_trigger,
                    'manual_exit': True  # 수동청산 플래그
                }
                
            # 1.6. 최대 수익률 6-10% 구간에서 5% 보호 청산 체크 (새로운 1.5순위)
            profit_protection_trigger = self._check_profit_protection_exit(symbol, current_price, profit_pct, position)
            if profit_protection_trigger:
                self.logger.critical(f"💰 수익 보호 청산 조건 충족: {symbol} - 최대수익률: {position.max_profit_pct*100:.2f}%, 현재: {profit_pct*100:.2f}%")
                # 실제 청산 실행 (5% 수익 보장)
                success = self._execute_emergency_exit(position, current_price, "profit_protection_exit")
                if success:
                    position.breakeven_protection_active = False  # 보호 모드 해제
                    self.save_data()
                    self.logger.critical(f"💰 수익 보호 청산 완료: {symbol}")
                return {
                    'trigger_activated': True,
                    'action': 'profit_protection_executed' if success else 'profit_protection_failed',
                    'trigger_info': profit_protection_trigger
                }
                
            # 2. SuperTrend 청산 확인 🔧 수정됨
            supertrend_exit = self.check_supertrend_exit_signal(symbol, current_price, position)
            if supertrend_exit:
                # SuperTrend 청산 실행
                success = self._execute_emergency_exit(position, current_price, "supertrend_exit")
                if success:
                    position.supertrend_exit_done = True
                    self.save_data()
                    self.logger.critical(f"🔴 SuperTrend 전량청산 완료: {symbol}")
                return {
                    'trigger_activated': True,
                    'action': 'supertrend_exit_executed' if success else 'supertrend_exit_failed',
                    'trigger_info': supertrend_exit
                }
            
            # 3. 새로운 청산 시스템 확인 (3-5순위 청산)
            new_exit_signal = self.check_new_exit_conditions(symbol, current_price)
            if new_exit_signal:
                success = self.execute_new_exit(symbol, new_exit_signal)
                return {
                    'trigger_activated': True,
                    'action': 'new_exit_executed' if success else 'new_exit_failed',
                    'trigger_info': new_exit_signal
                }
            
            # 3. 기존 DCA 트리거 확인
            try:
                balance = self.exchange.fetch_balance() if self.exchange else None
                total_balance = balance.get('USDT', {}).get('free', 100.0) if balance else 100.0
            except:
                total_balance = 100.0
            
            return self._check_position_triggers(symbol, current_price, total_balance)
            
        except Exception as e:
            self.logger.error(f"DCA 트리거 확인 실패 {symbol}: {e}")
            return None

    def _check_position_triggers(self, symbol: str, current_price: float, total_balance: float) -> Optional[Dict[str, Any]]:
        """개별 포지션 트리거 확인"""
        try:
            position = self.positions[symbol]
            
            # 현재 수익률 계산 (초기 진입가 기준으로 변경) - 타입 안전성 강화
            try:
                current_price = float(current_price)
                initial_entry_price = float(position.initial_entry_price)
                if initial_entry_price <= 0:
                    self.logger.error(f"잘못된 초기 진입가: {initial_entry_price}")
                    return None
                profit_pct = (current_price - initial_entry_price) / initial_entry_price
            except (ValueError, TypeError, ZeroDivisionError) as calc_error:
                self.logger.error(f"수익률 계산 실패 {symbol}: current_price={current_price} ({type(current_price)}), initial_entry_price={position.initial_entry_price} ({type(position.initial_entry_price)}) - {calc_error}")
                return None
            
            # 1. 손절 확인 (최우선)
            stop_loss_result = self._check_stop_loss_trigger(position, current_price, profit_pct)
            if stop_loss_result:
                return stop_loss_result
            
            # 2. 수익 청산 확인
            profit_exit_result = self._check_profit_exit_triggers(position, current_price, profit_pct)
            if profit_exit_result:
                return profit_exit_result
            
            # 3. DCA 추가매수 확인
            dca_result = self._check_dca_triggers(position, current_price, total_balance, profit_pct)
            if dca_result:
                return dca_result
            
            return None
            
        except Exception as e:
            self.logger.error(f"포지션 트리거 확인 실패 {symbol}: {e}")
            return None

    def _check_stop_loss_trigger(self, position: DCAPosition, current_price: float, profit_pct: float) -> Optional[Dict[str, Any]]:
        """손절 트리거 확인 - 고급 청산 시스템 통합"""
        try:
            # 고급 청산 시스템 우선 사용
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
                        self.logger.critical(f"🚨 적응형 손절 트리거: {position.symbol}")
                        self.logger.critical(f"   변동성: {exit_signal['volatility_level']}")
                        self.logger.critical(f"   손절률: {exit_signal['stop_loss_pct']:.1f}%")
                        self.logger.critical(f"   수익률: {exit_signal['profit_pct']:.2f}%")
                        
                        # 즉시 전량 청산
                        success = self._execute_emergency_exit(position, current_price, "adaptive_stop_loss")
                        
                        return {
                            'trigger_activated': True,
                            'action': 'adaptive_stop_loss_executed' if success else 'adaptive_stop_loss_failed',
                            'trigger_info': {
                                'type': '적응형 손절 청산',
                                'volatility_level': exit_signal['volatility_level'],
                                'stop_loss_pct': exit_signal['stop_loss_pct'],
                                'profit_pct': exit_signal['profit_pct'],
                                'current_stage': exit_signal['current_stage'],
                                'current_price': current_price
                            }
                        }
                    
                    # 기술적 청산 신호인 경우
                    elif signal_type == ExitSignalType.TECHNICAL_EXIT.value:
                        self.logger.warning(f"🔥 복합 기술적 청산 트리거: {position.symbol}")
                        self.logger.warning(f"   신호 개수: {exit_signal['signal_count']}")
                        self.logger.warning(f"   평균 강도: {exit_signal['avg_strength']:.2f}")
                        
                        # 전량 청산
                        success = self._execute_emergency_exit(position, current_price, "technical_exit")
                        
                        return {
                            'trigger_activated': True,
                            'action': 'technical_exit_executed' if success else 'technical_exit_failed',
                            'trigger_info': {
                                'type': '복합 기술적 청산',
                                'signal_count': exit_signal['signal_count'],
                                'avg_strength': exit_signal['avg_strength'],
                                'signals': exit_signal['signals'],
                                'current_price': current_price
                            }
                        }
            
            # 기본 손절 로직 (fallback)
            stop_loss_pct = self.config['stop_loss_by_stage'].get(position.current_stage, -0.10)
            
            # 🚨 중요: 손절 조건 강화 (floating point 정밀도 고려)
            if profit_pct <= (stop_loss_pct + 0.001):  # 0.1% 버퍼 추가
                self.logger.critical(f"🚨 기본 손절 트리거: {position.symbol}")
                self.logger.critical(f"   현재 수익률: {profit_pct*100:.4f}%")
                self.logger.critical(f"   손절 기준: {stop_loss_pct*100:.2f}%")
                self.logger.critical(f"   초기진입가: ${position.initial_entry_price:.6f}")
                self.logger.critical(f"   현재가격: ${current_price:.6f}")
                
                # 즉시 전량 청산
                success = self._execute_emergency_exit(position, current_price, "basic_stop_loss")
                
                if not success:
                    # 손절 실패시 재시도 로직
                    self.logger.error(f"🚨 손절 실패! 3초 후 재시도: {position.symbol}")
                    import time
                    time.sleep(3)
                    retry_success = self._execute_emergency_exit(position, current_price, "basic_stop_loss_retry")
                    success = retry_success
                
                return {
                    'trigger_activated': True,
                    'action': 'basic_stop_loss_executed' if success else 'basic_stop_loss_failed',
                    'trigger_info': {
                        'type': '기본 손절 청산',
                        'stop_loss_pct': stop_loss_pct * 100,
                        'profit_pct': profit_pct * 100,
                        'current_stage': position.current_stage,
                        'current_price': current_price,
                        'initial_entry_price': position.initial_entry_price,
                        'retry_attempted': not success
                    }
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"손절 트리거 확인 실패 {position.symbol}: {e}")
            # 🚨 중요: 오류시에도 강제 손절 확인 (손절 실패 방지)
            try:
                stop_loss_pct = self.config['stop_loss_by_stage'].get(position.current_stage, -0.10)
                if profit_pct <= (stop_loss_pct + 0.001):  # 버퍼 포함
                    self.logger.critical(f"🚨 예외 상황에서 강제 손절: {position.symbol} (수익률: {profit_pct*100:.4f}%)")
                    success = self._execute_emergency_exit(position, current_price, "fallback_stop_loss")
                    
                    # 손절 실패시 재시도
                    if not success:
                        import time
                        time.sleep(2)
                        success = self._execute_emergency_exit(position, current_price, "fallback_stop_loss_retry")
                    
                    return {
                        'trigger_activated': True,
                        'action': 'fallback_stop_loss_executed' if success else 'fallback_stop_loss_failed',
                        'trigger_info': {
                            'type': 'Fallback 강제 손절',
                            'error': str(e),
                            'profit_pct': profit_pct * 100,
                            'stop_loss_pct': stop_loss_pct * 100,
                            'current_price': current_price,
                            'retry_attempted': True
                        }
                    }
            except Exception as fallback_error:
                self.logger.critical(f"🚨 Fallback 손절마저 실패: {position.symbol} - {fallback_error}")
            
            return None

    def _check_profit_exit_triggers(self, position: DCAPosition, current_price: float, profit_pct: float) -> Optional[Dict[str, Any]]:
        """수익 청산 트리거 확인 - SuperClaude 기본 청산 시스템 우선 적용"""
        try:
            # 🎯 SuperClaude 기본 청산 시스템 최우선 사용
            if self.basic_exit_system:
                basic_exit_signal = self.basic_exit_system.check_all_basic_exits(
                    symbol=position.symbol,
                    current_price=current_price,
                    average_price=position.average_price
                )
                
                if basic_exit_signal:
                    exit_type = basic_exit_signal['exit_type']
                    exit_ratio = basic_exit_signal['exit_ratio']
                    
                    self.logger.warning(f"🎯 SuperClaude 기본 청산 트리거: {position.symbol}")
                    self.logger.warning(f"   청산 타입: {exit_type}")
                    self.logger.warning(f"   청산 비율: {exit_ratio*100:.0f}%")
                    
                    # 청산 실행
                    if exit_ratio >= 1.0:  # 전량 청산
                        success = self._execute_emergency_exit(position, current_price, exit_type)
                    else:  # 부분 청산
                        success = self._execute_partial_exit(position, current_price, exit_ratio, exit_type)
                    
                    # 청산 완료 마킹
                    if success:
                        self.basic_exit_system.mark_exit_completed(position.symbol, exit_type)
                        self.basic_exit_system.send_exit_notification(position.symbol, basic_exit_signal, profit_pct * 100)
                    
                    return {
                        'trigger_activated': True,
                        'action': f"basic_exit_{exit_type}_executed" if success else f"basic_exit_{exit_type}_failed",
                        'trigger_info': {
                            'type': f"SuperClaude 기본 청산 ({exit_type})",
                            'exit_ratio': exit_ratio * 100,
                            'profit_pct': profit_pct * 100,
                            'trigger_details': basic_exit_signal.get('trigger_info', ''),
                            'current_price': current_price
                        }
                    }
            
            # 고급 청산 시스템 (기본 청산 시스템 이후)
            if self.advanced_exit_system:
                exit_signal = self.advanced_exit_system.check_all_exit_conditions(
                    symbol=position.symbol,
                    current_price=current_price,
                    average_price=position.average_price,
                    current_stage=position.current_stage
                )
                
                if exit_signal:
                    signal_type = exit_signal['signal_type']
                    
                    # 다단계 익절 신호
                    if signal_type == ExitSignalType.MULTI_LEVEL_PROFIT.value:
                        self.logger.info(f"💰 {exit_signal['level_name']} 익절 트리거: {position.symbol}")
                        self.logger.info(f"   수익률: {exit_signal['profit_pct']:.2f}%")
                        self.logger.info(f"   청산비율: {exit_signal['exit_ratio']*100:.0f}%")
                        
                        success = self._execute_partial_exit(
                            position, current_price, 
                            exit_signal['exit_ratio'], 
                            f"multi_level_{exit_signal['level_name']}"
                        )
                        
                        return {
                            'trigger_activated': True,
                            'action': f"multi_level_executed" if success else f"multi_level_failed",
                            'trigger_info': {
                                'type': f"다단계 익절 ({exit_signal['level_name']})",
                                'profit_pct': exit_signal['profit_pct'],
                                'exit_ratio': exit_signal['exit_ratio'] * 100,
                                'level_name': exit_signal['level_name'],
                                'current_price': current_price
                            }
                        }
                    
                    # 트레일링 스톱 신호
                    elif signal_type == ExitSignalType.TRAILING_STOP.value:
                        self.logger.info(f"🛑 트레일링 스톱 트리거: {position.symbol}")
                        self.logger.info(f"   최고가: ${exit_signal['highest_price']:.6f}")
                        self.logger.info(f"   트레일링가: ${exit_signal['trailing_price']:.6f}")
                        self.logger.info(f"   트레일링: {exit_signal['trailing_pct']:.1f}%")
                        
                        success = self._execute_emergency_exit(position, current_price, "trailing_stop")
                        
                        return {
                            'trigger_activated': True,
                            'action': 'trailing_stop_executed' if success else 'trailing_stop_failed',
                            'trigger_info': {
                                'type': '트레일링 스톱',
                                'highest_price': exit_signal['highest_price'],
                                'trailing_price': exit_signal['trailing_price'],
                                'trailing_pct': exit_signal['trailing_pct'],
                                'current_price': current_price
                            }
                        }
            
            # DCA 단계별 청산 확인 (손실~10% 미만 수익 구간에서 실행)
            # DCA 부분청산은 손실 구간에서도 실행되어야 함 (평단가 최적화 목적)
            stage_exit_result = self._check_stage_exit_triggers(position, current_price, profit_pct)
            if stage_exit_result:
                return stage_exit_result
            
            return None
            
        except Exception as e:
            self.logger.error(f"수익 청산 트리거 확인 실패 {position.symbol}: {e}")
            # 오류시에도 기본 10% 절반청산 제거 (BB600 돌파 50% 청산만 유지)
            return None

    def _check_stage_exit_triggers(self, position: DCAPosition, current_price: float, profit_pct: float) -> Optional[Dict[str, Any]]:
        """단계별 청산 트리거 확인 - DCA 부분청산 로직 (손실~본절 구간 전용)"""
        
        # 🚨 DCA 부분청산은 손실 구간에서만 실행 (평단가 최적화 목적)
        # 10% 이상 수익시에는 DCA 부분청산 차단 (기술적 청산만 사용)
        if profit_pct >= 0.10:
            return None
        
        # 🎯 2차 DCA 단계: 1차 진입가 회복시 2차 DCA 물량만 부분청산
        if position.current_stage == PositionStage.SECOND_DCA.value:
            first_dca_entries = [e for e in position.entries if e.stage == "first_dca" and e.is_active and e.is_filled]
            if first_dca_entries:
                first_dca_price = first_dca_entries[0].entry_price
                
                # 1차 진입가 회복시 2차 DCA 물량 부분청산 (손실 구간에서만)
                if current_price >= first_dca_price:
                    self.logger.info(f"📈 2차 DCA 부분청산: {position.symbol} - 1차 진입가 회복 (평단가 최적화)")
                    
                    success = self._execute_stage_exit(position, current_price, "second_dca")
                    
                    return {
                        'trigger_activated': True,
                        'action': 'second_dca_exit_executed' if success else 'second_dca_exit_failed',
                        'trigger_info': {
                            'type': '2차 DCA 부분청산',
                            'target_price': first_dca_price,
                            'current_price': current_price,
                            'profit_pct': profit_pct * 100,
                            'purpose': '평단가 최적화 (손실 구간)'
                        }
                    }
        
        # 🎯 1차 DCA 단계: 최초 진입가 회복시 1차 DCA 물량만 부분청산
        elif position.current_stage == PositionStage.FIRST_DCA.value:
            # 최초 진입가 회복시 1차 DCA 물량 부분청산 (손실 구간에서만)
            if current_price >= position.initial_entry_price:
                self.logger.info(f"📈 1차 DCA 부분청산: {position.symbol} - 최초 진입가 회복 (평단가 최적화)")
                
                success = self._execute_stage_exit(position, current_price, "first_dca")
                
                return {
                    'trigger_activated': True,
                    'action': 'first_dca_exit_executed' if success else 'first_dca_exit_failed',
                    'trigger_info': {
                        'type': '1차 DCA 부분청산',
                        'target_price': position.initial_entry_price,
                        'current_price': current_price,
                        'profit_pct': profit_pct * 100,
                        'purpose': '평단가 최적화 (손실 구간)'
                    }
                }
        
        return None

    def _check_dca_triggers(self, position: DCAPosition, current_price: float, total_balance: float, profit_pct: float) -> Optional[Dict[str, Any]]:
        """DCA 추가매수 트리거 확인 (지정가 주문은 최초 진입시 이미 생성됨)"""

        # 5% 이상 수익시 추가매수 차단
        if profit_pct >= 0.05:
            return None

        # 📋 지정가 주문은 최초 진입시 자동 생성되므로 여기서는 체결 상태만 확인
        # check_and_update_limit_orders() 메서드가 주기적으로 호출되어 체결 상태 업데이트

        # 🔄 순환매 재진입 체크 (순환매시에는 새로운 지정가 주문 생성 필요)
        cyclic_reentry_result = self._check_cyclic_reentry(position, current_price, total_balance, profit_pct)
        if cyclic_reentry_result:
            return cyclic_reentry_result

        return None

    def _check_cyclic_reentry(self, position: DCAPosition, current_price: float, total_balance: float, profit_pct: float) -> Optional[Dict[str, Any]]:
        """순환매 재진입 체크"""
        try:
            # 순환매 재진입 조건 체크
            if (position.current_stage == PositionStage.INITIAL.value and 
                position.cyclic_state == CyclicState.CYCLIC_PAUSED.value and
                profit_pct <= self.config['first_dca_trigger']):
                
                # 순환매 제한 체크
                if position.cyclic_count >= position.max_cyclic_count:
                    self.logger.warning(f"🚫 순환매 제한 초과: {position.symbol} - {position.cyclic_count}/{position.max_cyclic_count}회")
                    return None
                
                self.logger.info(f"🔄 순환매 재진입 트리거: {position.symbol} ({position.cyclic_count + 1}/{position.max_cyclic_count}회차) (하락률 {abs(profit_pct)*100:.2f}%)")
                
                # 1차 DCA 재시작
                success = self._execute_first_dca(position, current_price, total_balance)
                
                if success:
                    # 순환매 상태 업데이트
                    position.cyclic_state = CyclicState.CYCLIC_ACTIVE.value
                
                return {
                    'trigger_activated': True,
                    'action': 'cyclic_reentry_executed' if success else 'cyclic_reentry_failed',
                    'trigger_info': {
                        'type': f'순환매 재진입 ({position.cyclic_count}/{position.max_cyclic_count}회차)',
                        'drop_pct': abs(profit_pct) * 100,
                        'current_price': current_price
                    }
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"순환매 체크 실패 {position.symbol}: {e}")
            return None

    def _execute_first_dca(self, position: DCAPosition, current_price: float, total_balance: float) -> bool:
        """1차 DCA 실행 (지정가 주문)"""
        try:
            # 추가매수 금액 계산
            dca_amount = total_balance * self.config['first_dca_weight']
            leverage = self.config['first_dca_leverage']
            
            # 1차 DCA 트리거 가격 계산 (-3% 하락가)
            dca_trigger_price = position.initial_entry_price * (1 + self.config['first_dca_trigger'])
            quantity = (dca_amount * leverage) / dca_trigger_price
            
            # 지정가 주문 실행
            order_result = self._execute_limit_order(position.symbol, quantity, "buy", dca_trigger_price)
            if not order_result['success']:
                self.logger.error(f"1차 DCA 지정가 주문 실패: {position.symbol}")
                return False
            
            # DCA 진입 기록 (미체결 상태로 시작)
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
                is_filled=False  # 지정가 주문은 미체결로 시작
            )
            
            position.entries.append(dca_entry)
            
            # 포지션 상태 업데이트 (아직 체결되지 않았으므로 평단가는 변경하지 않음)
            position.current_stage = PositionStage.FIRST_DCA.value
            position.last_update = get_korea_time().isoformat()
            
            # 데이터 저장
            self.save_data()
            
            self.logger.info(f"✅ 1차 DCA 지정가 주문 등록: {position.symbol} - 주문가: ${dca_trigger_price:.4f}, 수량: {quantity:.4f}")
            
            # 텔레그램 알림
            if self.telegram_bot:
                message = (f"📋 1차 DCA 지정가 주문 등록\n"
                          f"심볼: {position.symbol}\n"
                          f"주문가: ${dca_trigger_price:.4f} (-3%)\n"
                          f"수량: {quantity:.4f}\n"
                          f"주문ID: {order_result['order_id']}")
                self.telegram_bot.send_message(message)
            
            return True
            
        except Exception as e:
            self.logger.error(f"1차 DCA 실행 실패 {position.symbol}: {e}")
            return False

    def _execute_second_dca(self, position: DCAPosition, current_price: float, total_balance: float) -> bool:
        """2차 DCA 실행 (지정가 주문)"""
        try:
            # 추가매수 금액 계산
            dca_amount = total_balance * self.config['second_dca_weight']
            leverage = self.config['second_dca_leverage']
            
            # 2차 DCA 트리거 가격 계산 (-6% 하락가)
            dca_trigger_price = position.initial_entry_price * (1 + self.config['second_dca_trigger'])
            quantity = (dca_amount * leverage) / dca_trigger_price
            
            # 지정가 주문 실행
            order_result = self._execute_limit_order(position.symbol, quantity, "buy", dca_trigger_price)
            if not order_result['success']:
                self.logger.error(f"2차 DCA 지정가 주문 실패: {position.symbol}")
                return False
            
            # DCA 진입 기록 (미체결 상태로 시작)
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
                is_filled=False  # 지정가 주문은 미체결로 시작
            )
            
            position.entries.append(dca_entry)
            
            # 포지션 상태 업데이트 (아직 체결되지 않았으므로 평단가는 변경하지 않음)
            position.current_stage = PositionStage.SECOND_DCA.value
            position.last_update = get_korea_time().isoformat()
            
            # 🔄 순환매 카운트 증가 로직 (2차 DCA 주문 등록 시 순환매 1회 카운팅)
            position.cyclic_count += 1
            position.cyclic_state = CyclicState.CYCLIC_ACTIVE.value
            position.last_cyclic_entry = get_korea_time().isoformat()
            
            # 순환매 제한 체크 (참고용 - 실제 청산 모드는 최초진입가 기준으로 결정)
            if position.cyclic_count >= position.max_cyclic_count:
                self.logger.warning(f"⚠️ 순환매 {position.max_cyclic_count}회 달성: {position.symbol} - 청산 모드는 최초진입가 기준으로 결정")
            
            # 데이터 저장
            self.save_data()
            
            self.logger.info(f"✅ 2차 DCA 지정가 주문 등록: {position.symbol} - 주문가: ${dca_trigger_price:.4f}, 수량: {quantity:.4f} (순환매 {position.cyclic_count}/{position.max_cyclic_count}회차)")
            
            # 텔레그램 알림
            if self.telegram_bot:
                cyclic_status = "완료" if position.cyclic_state == CyclicState.CYCLIC_COMPLETE.value else "진행중"
                message = (f"📋 2차 DCA 지정가 주문 등록 (순환매 {position.cyclic_count}회차)\n"
                          f"심볼: {position.symbol}\n"
                          f"주문가: ${dca_trigger_price:.4f} (-6%)\n"
                          f"수량: {quantity:.4f}\n"
                          f"주문ID: {order_result['order_id']}\n"
                          f"🔄 순환매 상태: {cyclic_status}")
                self.telegram_bot.send_message(message)
            
            return True
            
        except Exception as e:
            self.logger.error(f"2차 DCA 실행 실패 {position.symbol}: {e}")
            return False

    def _execute_emergency_exit(self, position: DCAPosition, current_price: float, reason: str) -> bool:
        """긴급 전량 청산 (미체결 지정가 주문 자동 취소 포함)"""
        try:
            # API 키 검증
            if not self.exchange:
                self.logger.error(f"청산 실패 - 거래소 연결 없음: {position.symbol}")
                return {'success': False, 'silent': False, 'error': 'no_exchange'}
            
            if not hasattr(self.exchange, 'apiKey') or not self.exchange.apiKey:
                self.logger.error(f"청산 실패 - API 키 없음: {position.symbol}")
                return {'success': False, 'silent': False, 'error': 'no_api_key'}
            
            # 🚨 중요: 긴급 청산 시 실제 시장가 재조회 (잘못된 폴백 가격 방지)
            try:
                # 실제 거래소에서 현재가 조회
                ticker = self.exchange.fetch_ticker(position.symbol)
                verified_price = float(ticker['last'])
                
                # 폴백 가격 감지 및 교체
                if current_price is None or current_price <= 1.0 or abs(verified_price - current_price) / verified_price > 0.5:
                    self.logger.warning(f"🚨 잘못된 청산가 감지: {current_price} → 실제가 {verified_price}로 교체")
                    current_price = verified_price
                else:
                    self.logger.info(f"✅ 청산가 검증 완료: {position.symbol} ${current_price:.6f}")
                    
            except Exception as price_error:
                self.logger.error(f"실제 가격 조회 실패 {position.symbol}: {price_error}")
                # 🚨 중요: 손절 상황에서는 가격 조회 실패해도 진행 (손절 실패 방지)
                if "stop_loss" in reason.lower():
                    self.logger.critical(f"🚨 손절 상황 - 가격 조회 실패해도 청산 진행: {position.symbol}")
                    if current_price is None or current_price <= 0:
                        # 최후의 수단: 초기 진입가 기준으로 예상가 사용
                        current_price = position.initial_entry_price * 0.85  # -15% 가정
                        self.logger.warning(f"⚠️ 긴급 예상가 사용: ${current_price:.6f}")
                else:
                    # 손절이 아닌 경우에만 청산 중단
                    return {'success': False, 'silent': False}
            
            # 1. 미체결 지정가 주문 취소
            cancel_result = self._cancel_pending_orders(position.symbol)
            if cancel_result['success'] and cancel_result['cancelled_count'] > 0:
                self.logger.info(f"📋 미체결 주문 취소: {position.symbol} - {cancel_result['cancelled_count']}개 주문 취소")
            
            # 2. 🚨 버그 수정: 실제 거래소 포지션 기준으로 청산량 계산
            try:
                # 거래소에서 실제 포지션 수량 조회
                actual_positions = self.exchange.fetch_positions([position.symbol])
                actual_quantity = 0
                
                for pos in actual_positions:
                    if pos['symbol'] == position.symbol and float(pos.get('contracts', 0)) != 0:
                        actual_quantity = abs(float(pos.get('contracts', 0)))
                        break
                
                if actual_quantity <= 0:
                    self.logger.warning(f"청산할 포지션 없음: {position.symbol} - 실제 포지션: {actual_quantity}")
                    # DCA 데이터도 동기화
                    position.is_active = False
                    position.total_quantity = 0
                    self.save_data()
                    return False
                
                # 실제 포지션 수량 사용 (기존 entries 기준 대신)
                total_quantity = actual_quantity
                self.logger.info(f"🔄 실제 포지션 기준 청산: {position.symbol} - {total_quantity}")
                
            except Exception as e:
                if "apiKey" in str(e):
                    self.logger.error(f"실제 포지션 조회 실패 - API 키 오류: {position.symbol} - {e}")
                    # 🔧 수정: API 키 오류 시에도 백업 데이터로 청산 시도
                    self.logger.warning(f"⚠️ API 키 문제로 백업 데이터 사용하여 청산 시도: {position.symbol}")
                    # 메인 전략에 API 재연결 요청
                    if hasattr(self.strategy, '_request_exchange_reconnect'):
                        self.strategy._request_exchange_reconnect = True
                else:
                    self.logger.error(f"실제 포지션 조회 실패: {position.symbol} - {e}")
                # 백업: DCA 기록 total_quantity 사용 (entries 합계 대신)
                total_quantity = position.total_quantity
                if total_quantity <= 0:
                    self.logger.warning(f"청산할 포지션 없음 (백업): {position.symbol} - DCA 기록: {total_quantity}")
                    return False
            
            # 3. 전량 매도 주문 (시장가)
            order_result = self._execute_market_order(position.symbol, total_quantity, "sell")
            
            # silent 플래그 처리
            silent = order_result.get('silent', False)
            
            if order_result['success']:
                # 포지션 정리
                position.is_active = False
                position.current_stage = PositionStage.CLOSING.value
                position.last_update = get_korea_time().isoformat()
                
                # 모든 진입 비활성화
                for entry in position.entries:
                    entry.is_active = False
                
                # 메인 전략 동기화
                if self.strategy and hasattr(self.strategy, 'active_positions'):
                    if position.symbol in self.strategy.active_positions:
                        del self.strategy.active_positions[position.symbol]
                
                # 새로운 청산 시스템 상태 초기화 (완료)
                # 기존 basic_exit_system 제거됨 - 새로운 4가지 청산 방식 사용
                
                # 데이터 저장
                self.save_data()
                
                # 수익률 계산 (초기 진입가 기준으로 변경)
                profit_pct = (current_price - position.initial_entry_price) / position.initial_entry_price * 100
                
                # 청산 타입별 메시지 생성
                exit_emoji, exit_title, exit_description = self._get_exit_message_info(reason, profit_pct, position)
                
                self.logger.critical(f"{exit_emoji} {exit_title}: {position.symbol} - 수익률: {profit_pct:.2f}% (사유: {reason})")
                
                # 텔레그램 알림
                if self.telegram_bot:
                    message = (f"{exit_emoji} {exit_title}\n"
                              f"심볼: {position.symbol}\n"
                              f"청산가: ${current_price:.4f}\n"
                              f"수익률: {profit_pct:.2f}%\n"
                              f"상세: {exit_description}")
                    self.telegram_bot.send_message(message)
                
                return {'success': True, 'silent': silent}
            
            return {'success': False, 'silent': silent}
            
        except Exception as e:
            self.logger.error(f"긴급 청산 실패 {position.symbol}: {e}")
            return {'success': False, 'silent': False}

    def _get_exit_message_info(self, reason: str, profit_pct: float, position: DCAPosition) -> Tuple[str, str, str]:
        """청산 타입별 메시지 정보 생성"""
        try:
            reason_lower = reason.lower()
            max_profit_pct = getattr(position, 'max_profit_pct', 0) * 100  # 최대 수익률을 %로 변환
            
            # SuperTrend 전량청산
            if 'supertrend' in reason_lower:
                return "📈", "SuperTrend 전량청산 완료", f"트렌드 반전 감지 청산"
            
            # 본절 보호청산 (breakeven_protection)
            elif 'breakeven_protection' in reason_lower:
                half_threshold = max_profit_pct * 0.5
                return "🛡️", "절반 하락 보호청산 완료", f"최대 {max_profit_pct:.1f}% → {profit_pct:.1f}% (임계값 {half_threshold:.1f}%)"
            
            # 약상승 후 급락 리스크 회피
            elif 'weak_rise_dump' in reason_lower or 'dump_protection' in reason_lower:
                return "⚡", "급락 리스크 회피청산 완료", f"약상승 후 급락 패턴 감지"
            
            # BB600 익절청산
            elif 'bb600' in reason_lower:
                return "🎯", "BB600 익절청산 완료", f"볼린저밴드 상단 돌파 후 50% 익절"
            
            # DCA 순환매 부분청산
            elif 'cyclic' in reason_lower:
                return "🔄", "순환매 부분청산 완료", f"5%+ 수익에서 30% 부분청산"
            
            # 트레일링 스톱
            elif 'trailing' in reason_lower:
                return "📉", "트레일링 스톱 청산 완료", f"고점 대비 5% 하락 감지"
            
            # 시간 기반 자동 청산
            elif 'time_based' in reason_lower:
                return "⏰", "시간 기반 청산 완료", f"2시간+ 보유 후 0~5% 수익구간 청산"
            
            # 기타 (기존 긴급청산)
            else:
                return "🚨", "긴급 청산 완료", f"사유: {reason}"
                
        except Exception as e:
            self.logger.error(f"청산 메시지 생성 실패: {e}")
            return "🚨", "긴급 청산 완료", f"사유: {reason}"

    def _execute_partial_exit(self, position: DCAPosition, current_price: float, ratio: float, reason: str) -> bool:
        """부분 청산 (체결된 포지션만 대상)"""
        try:
            # 체결된 포지션만으로 청산할 수량 계산
            filled_entries = [e for e in position.entries if e.is_active and e.is_filled]
            total_filled_quantity = sum(e.quantity for e in filled_entries)
            exit_quantity = total_filled_quantity * ratio
            
            if exit_quantity <= 0:
                self.logger.warning(f"부분 청산할 수량 없음: {position.symbol} - 체결된 수량: {total_filled_quantity}")
                return False
            
            # 부분 매도 주문 (시장가)
            order_result = self._execute_market_order(position.symbol, exit_quantity, "sell")
            
            if order_result['success']:
                # 🚨 수정: 부분청산 시 비례적으로 모든 엔트리에서 청산 (특정 엔트리 전체 삭제 방지)
                remaining_to_exit = exit_quantity
                total_active_quantity = sum(e.quantity for e in position.entries if e.is_active)
                
                if total_active_quantity > 0:
                    # 비례적 부분청산: 각 엔트리에서 비율만큼 차감
                    exit_ratio_per_entry = remaining_to_exit / total_active_quantity
                    
                    for entry in position.entries:
                        if entry.is_active and exit_ratio_per_entry > 0:
                            entry_exit_qty = entry.quantity * exit_ratio_per_entry
                            
                            # 엔트리 수량 차감 (전체 삭제하지 않고 비율만큼만)
                            entry.quantity -= entry_exit_qty
                            entry.notional = entry.quantity * entry.entry_price
                            
                            # 🚨 수정: 극소량도 유지 (0에 가까워도 완전 삭제하지 않음)
                            if entry.quantity < 0.000001:  # 최소 보유량
                                entry.quantity = 0.000001
                                entry.notional = entry.quantity * entry.entry_price
                            
                            self.logger.debug(f"   엔트리 {entry.stage}: {entry.quantity + entry_exit_qty:.6f} → {entry.quantity:.6f}")
                
                # 포지션 정보 업데이트 - 스레드 안전성 강화
                with self.sync_lock:  # 스레드 안전성 보장
                    active_entries = [e for e in position.entries if e.is_active]
                    
                    # 🚨 수정: 부분청산은 항상 포지션을 유지 (완전 삭제 방지)
                    if active_entries and ratio < 1.0:  # 부분청산인 경우
                        # 기존 평단가 백업 (로깅용)
                        old_avg_price = position.average_price
                        old_quantity = position.total_quantity
                        
                        # 평단가 재계산 (가중평균)
                        new_quantity = sum(e.quantity for e in active_entries)
                        new_notional = sum(e.notional for e in active_entries)
                        total_cost = sum(e.quantity * e.entry_price for e in active_entries)
                        new_avg_price = total_cost / new_quantity if new_quantity > 0 else current_price
                        
                        # 변경사항 검증
                        price_change_pct = abs(new_avg_price - old_avg_price) / old_avg_price * 100 if old_avg_price > 0 else 0
                        quantity_change_pct = abs(new_quantity - old_quantity) / old_quantity * 100 if old_quantity > 0 else 0
                        
                        # 포지션 정보 업데이트
                        position.total_quantity = new_quantity
                        position.total_notional = new_notional
                        position.average_price = new_avg_price
                        
                        # 🚨 중요: 부분청산 후에도 포지션 활성 상태 유지
                        position.is_active = True
                        
                        # 상세 로깅 (부분 청산 후 평단가 변화)
                        self.logger.info(f"💰 부분 청산 후 평단가 재계산: {position.symbol}")
                        self.logger.info(f"   이전 평단가: ${old_avg_price:.6f} → 새 평단가: ${new_avg_price:.6f} ({price_change_pct:+.2f}%)")
                        self.logger.info(f"   이전 수량: {old_quantity:.6f} → 새 수량: {new_quantity:.6f} ({quantity_change_pct:+.2f}%)")
                        self.logger.info(f"   잔여 엔트리: {len(active_entries)}개")
                        self.logger.info(f"   🚨 부분청산 후 포지션 유지: TAO 신호 등 추가 모니터링 계속")
                    else:
                        # 전량 청산됨 또는 ratio >= 1.0
                        self.logger.warning(f"🏁 전량 청산 완료: {position.symbol}")
                        position.is_active = False
                        position.current_stage = PositionStage.CLOSING.value
                        
                        # 새로운 청산 시스템 상태 초기화 (전량 청산시 - 완료)
                        # 기존 basic_exit_system 제거됨 - 새로운 4가지 청산 방식 사용
                        self.logger.info(f"🔄 새로운 청산 시스템 상태 초기화: {position.symbol}")
                    
                    position.last_update = get_korea_time().isoformat()
                
                # 데이터 저장
                self.save_data()
                
                # 수익률 계산 (초기 진입가 기준으로 변경)
                profit_pct = (current_price - position.initial_entry_price) / position.initial_entry_price * 100
                
                self.logger.info(f"💰 부분 청산 완료: {position.symbol} - {ratio*100:.0f}% 청산, 수익률: {profit_pct:.2f}% (사유: {reason})")
                
                # 텔레그램 알림
                if self.telegram_bot:
                    message = (f"💰 부분 청산 완료\n"
                              f"심볼: {position.symbol}\n"
                              f"청산가: ${current_price:.4f}\n"
                              f"청산비율: {ratio*100:.0f}%\n"
                              f"수익률: {profit_pct:.2f}%\n"
                              f"사유: {reason}")
                    self.telegram_bot.send_message(message)
                
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"부분 청산 실패 {position.symbol}: {e}")
            return False

    def _execute_stage_exit(self, position: DCAPosition, current_price: float, target_stage: str) -> bool:
        """단계별 청산"""
        try:
            # 대상 단계의 진입 찾기
            target_entries = [e for e in position.entries if e.stage == target_stage and e.is_active]
            if not target_entries:
                self.logger.warning(f"단계별 청산 대상 없음: {position.symbol} - {target_stage}")
                return False
            
            # 🚨 버그 수정: 실제 보유 중인 해당 단계 수량만 청산
            try:
                # 실제 거래소 포지션 조회
                actual_positions = self.exchange.fetch_positions([position.symbol])
                actual_total_quantity = 0
                
                for pos in actual_positions:
                    if pos['symbol'] == position.symbol and float(pos.get('contracts', 0)) != 0:
                        actual_total_quantity = abs(float(pos.get('contracts', 0)))
                        break
                
                if actual_total_quantity <= 0:
                    self.logger.warning(f"단계별 청산 불가: {position.symbol} - 실제 포지션: {actual_total_quantity}")
                    return False
                
                # DCA 기록 기준 해당 단계 수량
                entries_stage_quantity = sum(e.quantity for e in target_entries)
                
                # 실제 청산할 수량 = min(기록상 단계 수량, 실제 보유 수량)
                stage_quantity = min(entries_stage_quantity, actual_total_quantity)
                
                self.logger.info(f"🔄 단계별 청산 수량 조정: {position.symbol}")
                self.logger.info(f"   대상 단계: {target_stage}")
                self.logger.info(f"   기록상 수량: {entries_stage_quantity}")
                self.logger.info(f"   실제 보유: {actual_total_quantity}")
                self.logger.info(f"   청산 수량: {stage_quantity}")
                
            except Exception as e:
                self.logger.error(f"실제 포지션 조회 실패: {position.symbol} - {e}")
                # 백업: 기록 기준 (위험하지만 완전 실패보다는 나음)
                stage_quantity = sum(e.quantity for e in target_entries)
                self.logger.warning(f"백업 청산량 사용: {position.symbol} - {stage_quantity}")
            
            # 단계별 매도 주문
            order_result = self._execute_market_order(position.symbol, stage_quantity, "sell")
            
            if order_result['success']:
                # 대상 단계 진입 비활성화
                for entry in target_entries:
                    entry.is_active = False
                
                # 포지션 정보 업데이트 - 스레드 안전성 강화
                with self.sync_lock:  # 스레드 안전성 보장
                    active_entries = [e for e in position.entries if e.is_active]
                    if active_entries:
                        # 기존 평단가 백업 (로깅용)
                        old_avg_price = position.average_price
                        old_quantity = position.total_quantity
                        old_stage = position.current_stage
                        
                        # 평단가 재계산 (가중평균)
                        new_quantity = sum(e.quantity for e in active_entries)
                        new_notional = sum(e.notional for e in active_entries)
                        total_cost = sum(e.quantity * e.entry_price for e in active_entries)
                        new_avg_price = total_cost / new_quantity if new_quantity > 0 else current_price
                        
                        # 변경사항 검증
                        price_change_pct = abs(new_avg_price - old_avg_price) / old_avg_price * 100 if old_avg_price > 0 else 0
                        quantity_change_pct = abs(new_quantity - old_quantity) / old_quantity * 100 if old_quantity > 0 else 0
                        
                        # 포지션 정보 업데이트
                        position.total_quantity = new_quantity
                        position.total_notional = new_notional
                        position.average_price = new_avg_price
                        
                        # 단계 업데이트
                        if target_stage == "second_dca":
                            position.current_stage = PositionStage.FIRST_DCA.value
                        elif target_stage == "first_dca":
                            position.current_stage = PositionStage.INITIAL.value
                        
                        # 상세 로깅 (단계별 청산 후 평단가 변화)
                        self.logger.info(f"📈 단계별 청산 후 평단가 재계산: {position.symbol}")
                        self.logger.info(f"   청산 단계: {target_stage}")
                        self.logger.info(f"   청산 수량: {stage_quantity:.6f}")
                        self.logger.info(f"   이전 평단가: ${old_avg_price:.6f} → 새 평단가: ${new_avg_price:.6f} ({price_change_pct:+.2f}%)")
                        self.logger.info(f"   이전 수량: {old_quantity:.6f} → 새 수량: {new_quantity:.6f} ({quantity_change_pct:+.2f}%)")
                        self.logger.info(f"   포지션 단계: {old_stage} → {position.current_stage}")
                        self.logger.info(f"   잔여 엔트리: {len(active_entries)}개")
                    else:
                        # 전량 청산됨
                        self.logger.warning(f"🏁 단계별 청산으로 전량 청산: {position.symbol}")
                        position.is_active = False
                        position.current_stage = PositionStage.CLOSING.value
                    
                    position.last_update = get_korea_time().isoformat()
                
                # 데이터 저장
                self.save_data()
                
                # 수익률 계산 (초기 진입가 기준으로 변경)
                profit_pct = (current_price - position.initial_entry_price) / position.initial_entry_price * 100
                
                # 🔄 순환매 수익 누적
                stage_profit = (current_price - sum(e.entry_price for e in target_entries) / len(target_entries)) * stage_quantity
                position.total_cyclic_profit += stage_profit
                
                # 🔄 순환매 재진입 체크 (전량 청산이 아닌 경우에만)
                cyclic_reentry_triggered = False
                if active_entries and position.cyclic_state == CyclicState.CYCLIC_ACTIVE.value:
                    # 1차 DCA 단계로 돌아간 경우 순환매 재진입 대기 상태로 전환
                    if position.current_stage == PositionStage.INITIAL.value:
                        position.cyclic_state = CyclicState.CYCLIC_PAUSED.value
                        cyclic_reentry_triggered = True
                        self.logger.info(f"🔄 순환매 재진입 대기: {position.symbol} - 다음 -3% 하락시 순환매 재시작")
                
                self.logger.info(f"📈 단계별 청산 완료: {position.symbol} - {target_stage} 청산, 수익률: {profit_pct:.2f}%{' (순환매 재진입 대기)' if cyclic_reentry_triggered else ''}")
                
                # 텔레그램 알림
                if self.telegram_bot:
                    # 해당 단계 평균 진입가 계산
                    stage_avg_price = sum(e.entry_price for e in target_entries) / len(target_entries) if target_entries else 0

                    cyclic_info = ""
                    if position.cyclic_state != CyclicState.NORMAL_DCA.value:
                        cyclic_info = f"\n🔄 순환매: {position.cyclic_count}/{position.max_cyclic_count}회차"
                        if cyclic_reentry_triggered:
                            cyclic_info += " (재진입 대기)"

                    message = (f"📈 단계별 청산 완료\n"
                              f"심볼: {position.symbol}\n"
                              f"청산 단계: {target_stage}\n"
                              f"진입가: ${stage_avg_price:.4f}\n"
                              f"청산가: ${current_price:.4f}\n"
                              f"청산 수량: {stage_quantity:.6f}\n"
                              f"수익률: {profit_pct:.2f}%"
                              f"{cyclic_info}")
                    self.telegram_bot.send_message(message)
                
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"단계별 청산 실패 {position.symbol}: {e}")
            return False

    def _execute_market_order(self, symbol: str, quantity: float, side: str) -> Dict[str, Any]:
        """시장가 주문 실행 (초기 진입 및 청산용) - Rate Limit 대응 강화"""
        try:
            if not self.exchange:
                return {'success': False, 'error': 'Exchange not available'}
            
            # 🔧 디버깅: Exchange 객체 상태 확인
            self.logger.debug(f"🔍 Exchange 상태 확인: {symbol} {side} {quantity}")
            self.logger.debug(f"🔍 Exchange type: {type(self.exchange).__name__}")
            self.logger.debug(f"🔍 Has apiKey attr: {hasattr(self.exchange, 'apiKey')}")
            if hasattr(self.exchange, 'apiKey'):
                api_key_status = "present" if self.exchange.apiKey else "empty"
                api_key_length = len(self.exchange.apiKey) if self.exchange.apiKey else 0
                self.logger.debug(f"🔍 API Key status: {api_key_status} (length: {api_key_length})")
            
            # 🔧 수정: API 키 검증 로직 개선 - 실제 거래 가능 여부 확인
            try:
                # 간단한 API 호출로 연결 상태 확인 (실제 거래 가능성 검증)
                test_ticker = self.exchange.fetch_ticker(symbol if '/USDT:USDT' in symbol else f"{symbol.replace('/USDT', '')}/USDT:USDT")
                self.logger.debug(f"🔍 API 연결 테스트 성공: {symbol}")
            except Exception as api_test_error:
                if "apiKey" in str(api_test_error):
                    self.logger.error(f"❌ API 키 문제 확인됨: {symbol} {side} {quantity} - {api_test_error}")
                    return {'success': False, 'error': f'API key issue: {str(api_test_error)}', 'silent': False}
                else:
                    # API 키 문제가 아닌 다른 오류는 무시하고 계속 진행
                    self.logger.debug(f"🔍 API 테스트 실패 (키 문제 아님): {api_test_error}")
            
            # 🔧 기존 단순한 API 키 체크는 제거 - 실제 호출에서 오류 발생시 처리
            
            # 🔧 심볼 변환 (이미 변환된 심볼일 수도 있으므로 안전하게 처리)
            if '/USDT:USDT' not in symbol:
                converted_symbol = self._convert_to_binance_futures_symbol(symbol)
                if not converted_symbol:
                    return {'success': False, 'error': f'Symbol conversion failed: {symbol}'}
                symbol = converted_symbol
            
            # Rate Limit 체크 - 418 에러 방지
            if (hasattr(self.strategy, '_api_rate_limited') and 
                self.strategy._api_rate_limited):
                self.logger.warning(f"🚨 Rate Limit 상태 - 시장가 주문 건너뛰기: {symbol}")
                return {'success': False, 'error': 'Rate limited - skip market order'}
            
            # 수량 검증 및 정밀도 조정
            validated_amount = self._validate_order_amount(symbol, abs(quantity))
            if validated_amount <= 0:
                error_msg = f"주문량 검증 실패: {symbol} - 원래량: {quantity}, 검증후: {validated_amount}"
                self.logger.warning(error_msg)
                return {'success': False, 'error': error_msg}
            
            # 최소 주문 금액 체크 (바이낸스 $5 요구사항)
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                # 🔧 타입 안전성: 현재가 강제 float 변환
                try:
                    current_price = float(ticker['last'])
                    if current_price <= 0:
                        raise ValueError(f"Invalid price: {current_price}")
                except (ValueError, TypeError, KeyError) as price_error:
                    self.logger.debug(f"가격 타입 변환 실패: {ticker.get('last')} ({type(ticker.get('last'))}) - {price_error}")
                    pass  # 가격 조회 실패해도 주문은 시도
                    return {'success': False, 'error': f'Price conversion failed: {price_error}'}
                    
                notional_value = validated_amount * current_price
                
                if notional_value < 5.0:  # $5 미만
                    # 조용히 처리 - 오류 로그 출력하지 않음
                    self.logger.debug(f"🔕 소액 포지션 청산 건너뛰기: {symbol} - 주문금액: ${notional_value:.2f} < $5")
                    return {'success': False, 'error': 'notional_too_small', 'silent': True}
                    
            except Exception as price_error:
                # 가격 조회 실패해도 주문은 시도 (기존 로직 유지)
                self.logger.debug(f"가격 조회 실패하여 최소금액 체크 생략: {symbol} - {price_error}")
                pass
            
            # 주문 실행 (Rate Limit 대응)
            try:
                order = self.exchange.create_market_order(
                    symbol=symbol,
                    side=side,
                    amount=validated_amount
                )
            except ccxt.RateLimitExceeded as e:
                self.logger.error(f"🚨 Rate Limit 초과 - 시장가 주문 실패: {symbol} {side} {quantity} - {e}")
                return {'success': False, 'error': f'Rate limit exceeded: {str(e)}'}
            except Exception as e:
                error_str = str(e).lower()
                # 🔧 API 키 관련 오류 처리 강화
                if "apikey" in error_str or "api key" in error_str or "credential" in error_str:
                    self.logger.error(f"🚨 API 키 문제로 시장가 주문 실패: {symbol} {side} {quantity} - {e}")
                    # Exchange 재연결 요청
                    if self.strategy and hasattr(self.strategy, '_request_exchange_reconnect'):
                        self.strategy._request_exchange_reconnect = True
                        self.logger.info(f"📨 메인 전략에 Exchange 재연결 요청 전송 (시장가 주문)")
                    return {'success': False, 'error': f'API key error: {str(e)}'}
                elif "418" in str(e) or "too many requests" in error_str:
                    self.logger.error(f"🚨 API 과부하 - 시장가 주문 실패: {symbol} {side} {quantity} - {e}")
                    # Rate Limit 상태 플래그 설정 (있는 경우)
                    if hasattr(self.strategy, '_api_rate_limited'):
                        self.strategy._api_rate_limited = True
                    return {'success': False, 'error': f'API overload: {str(e)}'}
                elif "notional must be no smaller than 5" in str(e):
                    # 최소 주문 금액 오류 - 조용히 처리
                    self.logger.debug(f"🔕 최소 주문금액 부족으로 청산 건너뛰기: {symbol} - 주문량: {quantity}")
                    return {'success': False, 'error': 'notional_too_small', 'silent': True}
                else:
                    raise e
            
            if order and order.get('id'):
                self.logger.info(f"시장가 주문 성공: {symbol} {side} {quantity} - ID: {order['id']}")
                return {
                    'success': True,
                    'order_id': order['id'],
                    'filled': order.get('filled', quantity),
                    'price': order.get('average', 0),
                    'order_type': 'market'
                }
            else:
                self.logger.error(f"시장가 주문 실패: {symbol} {side} {quantity}")
                return {'success': False, 'error': 'Market order creation failed'}
                
        except Exception as e:
            # 418 에러 등 전체적인 API 에러 처리
            if "418" in str(e) or "too many requests" in str(e).lower():
                self.logger.error(f"🚨 API 과부하로 인한 시장가 주문 실행 실패: {symbol} {side} {quantity} - {e}")
            elif "notional must be no smaller than 5" in str(e):
                # 최소 주문 금액 오류 - 조용히 처리
                self.logger.debug(f"🔕 최소 주문금액 부족으로 청산 건너뛰기: {symbol} - 주문량: {quantity}")
                return {'success': False, 'error': 'notional_too_small', 'silent': True}
            else:
                self.logger.error(f"시장가 주문 실행 실패: {symbol} {side} {quantity} - {e}")
            return {'success': False, 'error': str(e)}

    def _validate_order_amount(self, symbol: str, amount: float) -> float:
        """주문량 검증 및 정밀도 조정 (타입 안전성 강화)"""
        try:
            # 🔧 타입 안전성: 입력 매개변수 변환
            try:
                symbol = str(symbol) if symbol is not None else ""
                amount = float(amount) if amount is not None else 0.0
                if amount <= 0:
                    return 0.0
            except (ValueError, TypeError) as convert_error:
                self.logger.error(f"주문량 검증 타입 변환 실패: symbol={symbol} ({type(symbol)}), amount={amount} ({type(amount)}) - {convert_error}")
                return 0.0
            
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            
            # 심볼별 정밀도 자동 결정 (가격대별)
            if amount >= 1.0:
                precision = 3  # 1 이상: 3자리 (예: 1.234)
            elif amount >= 0.1:
                precision = 4  # 0.1 이상: 4자리 (예: 0.1234)
            elif amount >= 0.01:
                precision = 5  # 0.01 이상: 5자리 (예: 0.01234)
            else:
                precision = 6  # 0.01 미만: 6자리 (예: 0.001234)
            
            # 정밀도에 맞게 반올림
            validated_amount = round(amount, precision)
            
            # 심볼별 최소 주문량 설정 (정밀도 고려)
            if clean_symbol in ['BTC', 'ETH']:
                min_amount = 0.001    # 메이저 코인: 0.001
            elif clean_symbol in ['TAO', 'SOL', 'BNB']:
                min_amount = 0.01     # 중가 코인: 0.01  
            elif clean_symbol in ['CVC', 'FORTH', 'ARC', 'KERNEL', 'GPS', 'TRB', 'NMR', 'RATS', 'TA', '1000RATS', 'GIGGLE', 'ZEC']:
                # 정수 단위 코인: 1.0 이상, 정수로 반올림
                if amount < 1.0:
                    validated_amount = 1.0
                else:
                    validated_amount = round(amount)
                self.logger.debug(f"정수 단위 코인 주문량 조정: {symbol} - {amount} → {validated_amount}")
                return validated_amount
            else:
                min_amount = 0.1      # 기타 코인: 0.1
            
            # 최소 주문량 확인
            if validated_amount < min_amount:
                # 최소량으로 자동 조정
                validated_amount = min_amount
                self.logger.debug(f"주문량 최소값 조정: {symbol} - {amount} → {validated_amount}")
            
            # 최종 검증
            if validated_amount <= 0:
                self.logger.warning(f"검증된 주문량이 0: {symbol} - 원래량: {amount}")
                return 0.0
            
            return validated_amount
            
        except Exception as e:
            self.logger.error(f"주문량 검증 실패 {symbol}: {e}")
            # 안전한 기본값 반환
            try:
                return max(0.1, float(amount)) if amount else 0.0
            except:
                return 0.0

    def _execute_limit_order(self, symbol: str, quantity: float, side: str, price: float) -> Dict[str, Any]:
        """지정가 주문 실행 (DCA 진입용) - 안전장치 강화"""
        try:
            if not self.exchange:
                return {'success': False, 'error': 'Exchange not available'}
            
            # 🔧 Exchange 연결 상태 검증
            if not self._verify_exchange_connection():
                self.logger.error(f"❌ Exchange 연결 실패로 지정가 주문 실패: {symbol} {side} {quantity} @ ${price:.6f}")
                return {'success': False, 'error': 'Exchange connection failed', 'silent': False}
            
            # 🔧 심볼 변환 (이미 변환된 심볼일 수도 있으므로 안전하게 처리)
            if '/USDT:USDT' not in symbol:
                converted_symbol = self._convert_to_binance_futures_symbol(symbol)
                if not converted_symbol:
                    return {'success': False, 'error': f'Symbol conversion failed: {symbol}'}
                symbol = converted_symbol
            
            # 🔧 주문 수량 검증 및 조정
            validated_quantity = self._validate_order_amount(symbol, quantity)
            if validated_quantity <= 0:
                return {'success': False, 'error': f'Invalid quantity after validation: {validated_quantity}'}
            
            # 🔧 최소 주문 금액 체크 ($5 이상)
            notional_value = validated_quantity * price
            if notional_value < 5.0:
                return {'success': False, 'error': f'Notional value too small: ${notional_value:.2f} < $5.00'}
            
            quantity = validated_quantity
            
            # 🔒 추가 안전장치: 현재가와 지정가 비교 (타입 안전성)
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                # 🔧 타입 안전성: 현재가 변환
                try:
                    current_price = float(ticker['last'])
                    price = float(price)
                    quantity = float(quantity)
                    if current_price <= 0 or price <= 0 or quantity <= 0:
                        return {'success': False, 'error': f'Invalid values: price={price}, quantity={quantity}, current_price={current_price}'}
                except (ValueError, TypeError) as price_convert_error:
                    self.logger.error(f"지정가 주문 타입 변환 실패: ticker_last={ticker.get('last')} ({type(ticker.get('last'))}), price={price} ({type(price)}), quantity={quantity} ({type(quantity)}) - {price_convert_error}")
                    return {'success': False, 'error': f'Price type conversion failed: {price_convert_error}'}
                
                # DCA 매수 지정가 주문 안전장치 (하락 매수용)
                if side.lower() == 'buy':
                    # DCA 하락 매수: 지정가가 현재가보다 낮아야 정상
                    if price >= current_price:
                        self.logger.warning(f"⚠️ DCA 하락매수 확인: {symbol} 매수 지정가(${price:.6f}) ≥ 현재가(${current_price:.6f})")
                        # DCA 매수는 즉시 체결되더라도 허용 (하락 상황에서 유리한 진입)
                    
                    # 너무 낮은 가격 체크 (현재가의 50% 이하)
                    if price < current_price * 0.5:
                        self.logger.warning(f"🚨 지정가 주문 차단: {symbol} 매수 지정가(${price:.6f}) < 현재가의 50%(${current_price*0.5:.6f})")
                        return {'success': False, 'error': f'Buy limit price too low: {price:.6f} < 50% of current price'}
                
                # 매도 지정가 주문: 지정가가 현재가보다 낮으면 즉시 체결되므로 차단  
                elif side.lower() == 'sell' and price <= current_price:
                    self.logger.warning(f"🚨 지정가 주문 차단: {symbol} 매도 지정가(${price:.6f}) ≤ 현재가(${current_price:.6f})")
                    return {'success': False, 'error': f'Sell limit price {price:.6f} <= current price {current_price:.6f}'}
                    
            except Exception as e:
                self.logger.warning(f"현재가 비교 실패 - 주문 계속 진행: {symbol} - {e}")
            
            # 지정가 주문 실행
            self.logger.info(f"🔧 지정가 주문 실행 시도: {symbol} {side} {abs(quantity)} @ ${price:.6f}")
            self.logger.info(f"🔧 Exchange 정보: {type(self.exchange).__name__}, apiKey 존재: {bool(getattr(self.exchange, 'apiKey', None))}")
            
            order = self.exchange.create_limit_order(
                symbol=symbol,
                side=side,
                amount=abs(quantity),
                price=price
            )
            
            self.logger.info(f"🔧 지정가 주문 응답: {order}")
            
            if order and order.get('id'):
                self.logger.info(f"지정가 주문 성공: {symbol} {side} {quantity} @ ${price:.4f} - ID: {order['id']}")
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
                self.logger.error(f"지정가 주문 실패: {symbol} {side} {quantity} @ ${price:.4f}")
                return {'success': False, 'error': 'Limit order creation failed'}
                
        except Exception as e:
            error_str = str(e).lower()
            # 🔧 API 키 관련 오류 처리 강화
            if "apikey" in error_str or "api key" in error_str or "credential" in error_str:
                self.logger.error(f"🚨 API 키 문제로 지정가 주문 실패: {symbol} {side} {quantity} @ ${price:.4f} - {e}")
                # Exchange 재연결 요청
                if self.strategy and hasattr(self.strategy, '_request_exchange_reconnect'):
                    self.strategy._request_exchange_reconnect = True
                    self.logger.info(f"📨 메인 전략에 Exchange 재연결 요청 전송 (지정가 주문)")
                return {'success': False, 'error': f'API key error: {str(e)}'}
            else:
                self.logger.error(f"지정가 주문 실행 실패: {symbol} {side} {quantity} @ ${price:.4f} - {e}")
                return {'success': False, 'error': str(e)}

    def _cancel_pending_orders(self, symbol: str) -> Dict[str, Any]:
        """해당 심볼의 미체결 지정가 주문 취소 - Rate Limit 대응 강화"""
        try:
            if not self.exchange:
                return {'success': False, 'error': 'Exchange not available'}
            
            # 🔧 API 키 검증 로직 개선 - 실제 API 호출에서 오류 처리
            
            # 🔧 심볼 변환 (이미 변환된 심볼일 수도 있으므로 안전하게 처리)
            if '/USDT:USDT' not in symbol:
                converted_symbol = self._convert_to_binance_futures_symbol(symbol)
                if not converted_symbol:
                    return {'success': False, 'error': f'Symbol conversion failed: {symbol}'}
                symbol = converted_symbol
            
            # Rate Limit 체크 - 418 에러 방지
            if (hasattr(self.strategy, '_api_rate_limited') and 
                self.strategy._api_rate_limited):
                self.logger.warning(f"🚨 Rate Limit 상태 - 주문 취소 건너뛰기: {symbol}")
                return {'success': False, 'error': 'Rate limited - skip cancel orders'}
            
            # 미체결 주문 조회 (Rate Limit 대응)
            try:
                open_orders = self.exchange.fetch_open_orders(symbol)
            except ccxt.RateLimitExceeded as e:
                self.logger.error(f"🚨 Rate Limit 초과 - 주문 조회 실패: {symbol} - {e}")
                return {'success': False, 'error': f'Rate limit exceeded: {str(e)}'}
            except Exception as e:
                error_str = str(e).lower()
                # 🔧 API 키 관련 오류 처리 강화
                if "apikey" in error_str or "api key" in error_str or "credential" in error_str:
                    self.logger.error(f"🚨 API 키 문제로 주문 조회 실패: {symbol} - {e}")
                    if self.strategy and hasattr(self.strategy, '_request_exchange_reconnect'):
                        self.strategy._request_exchange_reconnect = True
                        self.logger.info(f"📨 메인 전략에 Exchange 재연결 요청 전송 (주문 조회)")
                    return {'success': False, 'error': f'API key error: {str(e)}'}
                elif "418" in str(e) or "too many requests" in error_str:
                    self.logger.error(f"🚨 API 과부하 - 주문 조회 실패: {symbol} - {e}")
                    return {'success': False, 'error': f'API overload: {str(e)}'}
                else:
                    raise e
            
            cancelled_orders = []
            
            for order in open_orders:
                try:
                    # Rate Limit 체크 (각 주문 취소 전)
                    if (hasattr(self.strategy, '_api_rate_limited') and 
                        self.strategy._api_rate_limited):
                        self.logger.warning(f"🚨 Rate Limit 감지 - 주문 취소 중단: {symbol}")
                        break
                    
                    # DCA 관련 주문만 취소 (필요시 주문에 태그를 달아 구분)
                    cancel_result = self.exchange.cancel_order(order['id'], symbol)
                    cancelled_orders.append({
                        'order_id': order['id'],
                        'side': order['side'],
                        'amount': order['amount'],
                        'price': order['price']
                    })
                    self.logger.info(f"주문 취소 성공: {symbol} - ID: {order['id']}")
                    
                    # 주문 취소 후 잠시 대기 (Rate Limit 방지)
                    time.sleep(0.1)
                    
                except ccxt.RateLimitExceeded as e:
                    self.logger.error(f"🚨 Rate Limit 초과 - 주문 취소 실패: {symbol} - ID: {order['id']} - {e}")
                    break  # Rate Limit 발생시 즉시 중단
                except Exception as e:
                    error_str = str(e).lower()
                    # 🔧 API 키 관련 오류 처리 강화
                    if "apikey" in error_str or "api key" in error_str or "credential" in error_str:
                        self.logger.error(f"🚨 API 키 문제로 주문 취소 실패: {symbol} - ID: {order['id']} - {e}")
                        if self.strategy and hasattr(self.strategy, '_request_exchange_reconnect'):
                            self.strategy._request_exchange_reconnect = True
                            self.logger.info(f"📨 메인 전략에 Exchange 재연결 요청 전송 (주문 취소)")
                        break  # API 키 문제시 즉시 중단
                    elif "418" in str(e) or "too many requests" in error_str:
                        self.logger.error(f"🚨 API 과부하 - 주문 취소 실패: {symbol} - ID: {order['id']} - {e}")
                        break  # API 과부하시 즉시 중단
                    else:
                        self.logger.warning(f"주문 취소 실패: {symbol} - ID: {order['id']} - {e}")
                        continue
            
            return {
                'success': True,
                'cancelled_count': len(cancelled_orders),
                'cancelled_orders': cancelled_orders
            }
                
        except Exception as e:
            error_str = str(e).lower()
            # 🔧 API 키 관련 오류 처리 강화
            if "apikey" in error_str or "api key" in error_str or "credential" in error_str:
                self.logger.error(f"🚨 API 키 문제로 인한 미체결 주문 취소 실패: {symbol} - {e}")
                if self.strategy and hasattr(self.strategy, '_request_exchange_reconnect'):
                    self.strategy._request_exchange_reconnect = True
                    self.logger.info(f"📨 메인 전략에 Exchange 재연결 요청 전송 (전체 주문 취소)")
                return {'success': False, 'error': f'API key error: {str(e)}'}
            elif "418" in str(e) or "too many requests" in error_str:
                self.logger.error(f"🚨 API 과부하로 인한 미체결 주문 취소 실패: {symbol} - {e}")
                return {'success': False, 'error': f'API overload: {str(e)}'}
            else:
                self.logger.error(f"미체결 주문 취소 실패: {symbol} - {e}")
                return {'success': False, 'error': str(e)}

    def get_pending_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """해당 심볼의 미체결 지정가 주문 조회 (메인 전략 호환용)"""
        try:
            if symbol not in self.positions:
                return []

            position = self.positions[symbol]
            pending_orders = []

            # 포지션의 모든 entry 중 미체결 지정가 주문 찾기
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
            self.logger.error(f"미체결 주문 조회 실패 {symbol}: {e}")
            return []

    def check_and_update_limit_orders(self) -> Dict[str, Any]:
        """미체결 지정가 주문 상태 확인 및 업데이트"""
        try:
            if not self.exchange:
                return {'success': False, 'error': 'Exchange not available'}
            
            updated_positions = []
            
            for symbol, position in list(self.positions.items()):
                if not position.is_active:
                    continue
                
                # 미체결 지정가 주문이 있는 엔트리 찾기
                pending_entries = [e for e in position.entries if e.is_active and not e.is_filled and e.order_type == "limit" and e.order_id]
                
                if not pending_entries:
                    continue
                
                try:
                    # Rate Limit 상태 체크
                    if (hasattr(self.strategy, '_api_rate_limited') and 
                        self.strategy._api_rate_limited):
                        self.logger.debug(f"🚨 Rate limit 상태 - 주문 상태 확인 건너뛰기 ({symbol})")
                        continue
                        
                    # 해당 심볼의 모든 주문 상태 확인 (Rate Limit 대응 강화)
                    try:
                        orders = self.exchange.fetch_orders(symbol)
                        order_status_map = {order['id']: order for order in orders}
                    except ccxt.RateLimitExceeded as e:
                        self.logger.warning(f"🚨 Rate Limit 초과 - 주문 상태 확인 건너뛰기: {symbol} - {e}")
                        continue
                    except Exception as e:
                        # 418 에러 등 기타 API 에러 처리
                        if "418" in str(e) or "too many requests" in str(e).lower():
                            self.logger.warning(f"🚨 API 과부하 - 주문 상태 확인 건너뛰기: {symbol} - {e}")
                            # Rate Limit 상태 플래그 설정 (있는 경우)
                            if hasattr(self.strategy, '_api_rate_limited'):
                                self.strategy._api_rate_limited = True
                            continue
                        else:
                            raise e
                    
                    position_updated = False
                    
                    for entry in pending_entries:
                        if entry.order_id in order_status_map:
                            order = order_status_map[entry.order_id]
                            
                            # 주문이 체결되었는지 확인
                            if order['status'] == 'closed' and order['filled'] > 0:
                                # 체결 완료
                                entry.is_filled = True
                                entry.quantity = order['filled']  # 실제 체결 수량으로 업데이트
                                entry.entry_price = order['average'] if order['average'] else entry.entry_price
                                
                                self.logger.info(f"✅ DCA 지정가 주문 체결: {symbol} {entry.stage} - 체결가: ${entry.entry_price:.4f}, 수량: {entry.quantity:.4f}")
                                
                                # 중복 방지: 체결 알림 (심볼_단계_주문ID 조합으로 중복 체크)
                                notification_key = f"{symbol}_{entry.stage}_{entry.order_id}"
                                
                                # 🔍 디버깅: 체결 알림 발송 조건 상세 로그
                                self.logger.info(f"🔍 체결 감지: {symbol} {entry.stage}")
                                self.logger.info(f"🔍 주문 상태: {order['status']}, 체결량: {order['filled']}")
                                self.logger.info(f"🔍 알림키: {notification_key}")
                                self.logger.info(f"🔍 이미 발송됨: {notification_key in self._sent_fill_notifications}")
                                self.logger.info(f"🔍 전체 발송 기록: {len(self._sent_fill_notifications)}개")
                                
                                if self.telegram_bot and notification_key not in self._sent_fill_notifications:
                                    message = (f"✅ DCA 지정가 체결\n"
                                              f"심볼: {symbol}\n"
                                              f"단계: {entry.stage}\n"
                                              f"체결가: ${entry.entry_price:.4f}\n"
                                              f"수량: {entry.quantity:.4f}")
                                    self.telegram_bot.send_message(message)
                                    self._sent_fill_notifications.add(notification_key)
                                    self._save_sent_notifications()  # 알림 기록 즉시 저장
                                    self.logger.info(f"📨 DCA 체결 알림 발송 완료: {notification_key}")
                                else:
                                    self.logger.info(f"📨 DCA 체결 알림 건너뛰기 (중복): {notification_key}")
                                
                                position_updated = True
                            
                            elif order['status'] == 'canceled':
                                # 주문이 취소됨
                                entry.is_active = False
                                self.logger.warning(f"❌ DCA 지정가 주문 취소됨: {symbol} {entry.stage}")
                                position_updated = True
                    
                    # 포지션 정보 재계산 (체결된 엔트리만으로) - 스레드 안전성 강화
                    if position_updated:
                        with self.sync_lock:  # 스레드 안전성 보장
                            filled_entries = [e for e in position.entries if e.is_active and e.is_filled]
                            if filled_entries:
                                # 기존 평단가 백업 (로깅용)
                                old_avg_price = position.average_price
                                old_quantity = position.total_quantity
                                
                                # 평단가 재계산 (가중평균)
                                total_cost = sum(e.quantity * e.entry_price for e in filled_entries)
                                total_quantity = sum(e.quantity for e in filled_entries)
                                new_avg_price = total_cost / total_quantity if total_quantity > 0 else position.average_price
                                
                                # 변경사항 검증
                                price_change_pct = abs(new_avg_price - old_avg_price) / old_avg_price * 100 if old_avg_price > 0 else 0
                                quantity_change_pct = abs(total_quantity - old_quantity) / old_quantity * 100 if old_quantity > 0 else 0
                                
                                # 평단가 업데이트
                                position.average_price = new_avg_price
                                position.total_quantity = total_quantity
                                position.total_notional = sum(e.notional for e in filled_entries)
                                position.last_update = get_korea_time().isoformat()

                                # 📋 포지션 단계 업데이트 (가장 높은 단계로 설정)
                                old_stage = position.current_stage
                                if any(e.stage == "second_dca" and e.is_filled for e in position.entries):
                                    position.current_stage = PositionStage.SECOND_DCA.value
                                elif any(e.stage == "first_dca" and e.is_filled for e in position.entries):
                                    position.current_stage = PositionStage.FIRST_DCA.value
                                else:
                                    position.current_stage = PositionStage.INITIAL.value

                                updated_positions.append(symbol)

                                # 상세 로깅 (변경사항 추적)
                                self.logger.info(f"🔄 평단가 재계산: {symbol}")
                                self.logger.info(f"   이전 평단가: ${old_avg_price:.6f} → 새 평단가: ${new_avg_price:.6f} ({price_change_pct:+.2f}%)")
                                self.logger.info(f"   이전 수량: {old_quantity:.6f} → 새 수량: {total_quantity:.6f} ({quantity_change_pct:+.2f}%)")
                                self.logger.info(f"   포지션 단계: {old_stage} → {position.current_stage}")
                                self.logger.info(f"   체결된 엔트리: {len(filled_entries)}개")
                                
                                # 체결된 엔트리 상세 정보
                                for i, entry in enumerate(filled_entries):
                                    self.logger.debug(f"     엔트리{i+1}: {entry.stage} - ${entry.entry_price:.6f} x {entry.quantity:.6f}")
                                
                                # 큰 변화 감지시 경고
                                if price_change_pct > 5.0:
                                    self.logger.warning(f"⚠️ 평단가 큰 변화 감지: {symbol} - {price_change_pct:.2f}% 변화")
                                if quantity_change_pct > 10.0:
                                    self.logger.warning(f"⚠️ 수량 큰 변화 감지: {symbol} - {quantity_change_pct:.2f}% 변화")
                
                except Exception as e:
                    # Rate Limit 에러 특별 처리
                    if "418" in str(e) or "too many requests" in str(e).lower():
                        if hasattr(self.strategy, '_api_rate_limited'):
                            self.strategy._api_rate_limited = True
                        self.logger.debug(f"Rate limit 감지 - 주문 상태 확인 중단 ({symbol})")
                        break  # 다른 심볼 체크도 중단
                    else:
                        self.logger.error(f"주문 상태 확인 실패 {symbol}: {e}")
                    continue
            
            # 업데이트된 포지션이 있으면 저장
            if updated_positions:
                self.save_data()
            
            return {
                'success': True,
                'updated_positions': updated_positions,
                'updated_count': len(updated_positions)
            }
            
        except Exception as e:
            self.logger.error(f"지정가 주문 상태 확인 실패: {e}")
            return {'success': False, 'error': str(e)}

    def get_position_summary(self) -> Dict[str, Any]:
        """포지션 요약 정보"""
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
                    self.logger.error(f"포지션 정보 계산 실패 {position.symbol}: {e}")
                    continue
            
            return {
                'total_positions': len(active_positions),
                'total_notional': total_notional,
                'total_unrealized_pnl': total_unrealized_pnl,
                'positions': positions_info
            }
            
        except Exception as e:
            self.logger.error(f"포지션 요약 생성 실패: {e}")
            return {'error': str(e)}
    
    def get_cyclic_statistics(self) -> Dict[str, Any]:
        """🔄 순환매 통계 정보"""
        try:
            all_positions = list(self.positions.values())
            
            # 순환매 통계
            cyclic_positions = [p for p in all_positions if p.cyclic_count > 0]
            active_cyclic = [p for p in cyclic_positions if p.is_active]
            completed_cyclic = [p for p in cyclic_positions if not p.is_active]
            
            # 순환매 상태별 분류
            cyclic_active = [p for p in active_cyclic if p.cyclic_state == CyclicState.CYCLIC_ACTIVE.value]
            cyclic_paused = [p for p in active_cyclic if p.cyclic_state == CyclicState.CYCLIC_PAUSED.value]
            cyclic_complete = [p for p in all_positions if p.cyclic_state == CyclicState.CYCLIC_COMPLETE.value]
            
            # 누적 순환매 수익
            total_cyclic_profit = sum(p.total_cyclic_profit for p in all_positions)
            
            # 순환매 회차별 통계
            cyclic_count_stats = {}
            for i in range(1, 4):  # 1~3회차
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
            self.logger.error(f"순환매 통계 생성 실패: {e}")
            return {'error': str(e)}

    def log_cyclic_status(self):
        """순환매 상태 로깅"""
        try:
            stats = self.get_cyclic_statistics()
            if 'error' not in stats:
                self.logger.info(f"🔄 순환매 현황: 전체 {stats['total_cyclic_positions']}개, 활성 {stats['active_cyclic_positions']}개, 완료 {stats['completed_cyclic_positions']}개")
                self.logger.info(f"🔄 상태별: 진행 {stats['cyclic_states']['active']}개, 대기 {stats['cyclic_states']['paused']}개, 완료 {stats['cyclic_states']['complete']}개")
                self.logger.info(f"💰 누적 순환매 수익: ${stats['total_cyclic_profit']:.2f}")
        except Exception as e:
            self.logger.error(f"순환매 로깅 실패: {e}")

    def cleanup_inactive_positions(self):
        """비활성 포지션 정리"""
        try:
            inactive_symbols = [symbol for symbol, pos in self.positions.items() if not pos.is_active]
            
            if inactive_symbols:
                for symbol in inactive_symbols:
                    del self.positions[symbol]
                    self.logger.info(f"비활성 포지션 정리: {symbol}")
                
                self.save_data()
                self.logger.info(f"포지션 정리 완료: {len(inactive_symbols)}개")
            
        except Exception as e:
            self.logger.error(f"포지션 정리 실패: {e}")

    def get_active_positions(self) -> Dict[str, DCAPosition]:
        """활성 포지션 반환"""
        return {symbol: pos for symbol, pos in self.positions.items() if pos.is_active}

    def has_active_position(self, symbol: str) -> bool:
        """활성 포지션 존재 여부"""
        return symbol in self.positions and self.positions[symbol].is_active

    def force_exit_position(self, symbol: str, reason: str = "manual") -> dict:
        """강제 포지션 청산"""
        try:
            if symbol not in self.positions or not self.positions[symbol].is_active:
                self.logger.warning(f"강제 청산 대상 없음: {symbol}")
                return {'success': False, 'silent': False}
            
            position = self.positions[symbol]
            
            if self.exchange:
                ticker = self.exchange.fetch_ticker(symbol)
                current_price = float(ticker['last'])
            else:
                current_price = position.average_price
            
            return self._execute_emergency_exit(position, current_price, f"강제청산: {reason}")
            
        except Exception as e:
            self.logger.error(f"강제 청산 실패 {symbol}: {e}")
            return {'success': False, 'silent': False}

    def notify_liquidation_from_strategy(self, symbol: str, reason: str = "strategy_liquidation") -> bool:
        """메인 전략에서 청산 완료 즉시 통지 (동기화 갭 해결)"""
        try:
            with self.sync_lock:
                if symbol not in self.positions:
                    self.logger.info(f"🔄 청산 통지: DCA 포지션 없음 - {symbol}")
                    return True
                
                position = self.positions[symbol]
                
                # 즉시 포지션 비활성화
                position.is_active = False
                position.current_stage = PositionStage.CLOSING.value
                position.last_update = get_korea_time().isoformat()
                
                # 모든 진입 비활성화
                for entry in position.entries:
                    entry.is_active = False
                
                # 미체결 지정가 주문 취소
                cancel_result = self._cancel_pending_orders(symbol)
                if cancel_result['success'] and cancel_result['cancelled_count'] > 0:
                    self.logger.info(f"📋 청산 후 미체결 주문 취소: {symbol} - {cancel_result['cancelled_count']}개")
                
                # DCA 포지션 제거
                del self.positions[symbol]
                
                # 데이터 저장
                self.save_data()
                
                self.logger.critical(f"🚨 메인 전략 청산 통지 처리 완료: {symbol} (사유: {reason})")
                
                # 텔레그램 알림
                if self.telegram_bot:
                    message = (f"🚨 DCA 시스템 동기화\n"
                              f"메인 전략 청산 감지: {symbol}\n"
                              f"DCA 포지션 즉시 정리 완료\n"
                              f"사유: {reason}")
                    self.telegram_bot.send_message(message)
                
                return True
            
        except Exception as e:
            self.logger.error(f"청산 통지 처리 실패 {symbol}: {e}")
            return False

    def handle_main_strategy_exit(self, symbol: str, exit_reason: str, partial_ratio: float = 1.0) -> Dict[str, Any]:
        """메인 전략 청산 요청 처리 - 호환성 브리지 메서드"""
        try:
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            
            # 포지션 존재 확인
            if clean_symbol not in self.positions:
                return {
                    'success': False, 
                    'exit_type': 'not_found',
                    'message': f'DCA 시스템에서 포지션을 찾을 수 없음: {clean_symbol}',
                    'error': 'Position not found in DCA system'
                }
            
            position = self.positions[clean_symbol]
            
            # 현재 가격 가져오기 (Rate Limit 대응)
            current_price = None
            try:
                # Rate Limit 체크
                if (hasattr(self.strategy, '_api_rate_limited') and 
                    self.strategy._api_rate_limited):
                    current_price = position.average_price  # 폴백
                    self.logger.debug(f"🚨 Rate Limit 상태 - 평균가로 가격 대체: {symbol}")
                else:
                    ticker = self.exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
            except Exception as e:
                # Rate Limit 감지 및 처리
                error_str = str(e).lower()
                if ("418" in str(e) or "429" in str(e) or 
                    "too many requests" in error_str or "rate limit" in error_str):
                    self.logger.warning(f"🚨 가격 조회 중 Rate Limit 감지: {symbol} - {e}")
                    if hasattr(self.strategy, '_api_rate_limited'):
                        self.strategy._api_rate_limited = True
                current_price = position.average_price  # 폴백
                
            self.logger.info(f"📋 메인 전략 청산 요청: {clean_symbol} - {exit_reason} (비율: {partial_ratio*100:.1f}%)")
            
            # 청산 비율에 따른 처리
            if partial_ratio >= 1.0:
                # 전량 청산
                success = self.force_exit_position(clean_symbol, exit_reason)
                return {
                    'success': success,
                    'exit_type': 'full_exit', 
                    'message': f'{exit_reason} - 전량청산 {"성공" if success else "실패"}',
                    'partial_ratio': 1.0
                }
            else:
                # 부분 청산
                result = self._execute_partial_exit(position, current_price, partial_ratio, exit_reason)
                return {
                    'success': result if isinstance(result, bool) else True,
                    'exit_type': 'partial_exit',
                    'message': f'{exit_reason} - {partial_ratio*100:.1f}% 부분청산 완료',
                    'partial_ratio': partial_ratio
                }
                
        except Exception as e:
            error_msg = f"메인 전략 청산 처리 실패 {symbol}: {str(e)}"
            self.logger.error(error_msg)
            return {
                'success': False,
                'exit_type': 'error',
                'message': error_msg,
                'error': str(e)
            }

    def validate_data_integrity(self) -> Dict[str, Any]:
        """데이터 무결성 검증 및 메인 전략과의 동기화 상태 확인"""
        try:
            validation_result = {
                'valid': True,
                'errors': [],
                'warnings': [],
                'fixed': [],
                'sync_issues': []
            }
            
            # 메인 전략과의 동기화 상태 확인
            if self.strategy and hasattr(self.strategy, 'active_positions'):
                main_symbols = set(self.strategy.active_positions.keys())
                dca_symbols = set(pos.symbol for pos in self.positions.values() if pos.is_active)
                
                # DCA에는 있지만 메인 전략에 없는 심볼 (고아 포지션 후보)
                orphaned_in_dca = dca_symbols - main_symbols
                for symbol in orphaned_in_dca:
                    validation_result['sync_issues'].append(f"DCA 고아 포지션: {symbol} (메인 전략에 없음)")
                    # 자동 정리
                    try:
                        self._cleanup_orphaned_position(symbol.replace('/USDT:USDT', '').replace('/USDT', ''))
                        validation_result['fixed'].append(f"고아 포지션 자동 정리: {symbol}")
                    except Exception as e:
                        validation_result['errors'].append(f"고아 포지션 정리 실패: {symbol} - {e}")
            
            for symbol, position in list(self.positions.items()):
                # 기본 검증
                if not position.entries:
                    validation_result['errors'].append(f"{symbol}: 진입 기록 없음")
                    validation_result['valid'] = False
                    continue
                
                # 수량 검증
                calculated_quantity = sum(e.quantity for e in position.entries if e.is_active)
                if abs(calculated_quantity - position.total_quantity) > 0.001:
                    validation_result['warnings'].append(f"{symbol}: 수량 불일치 - 계산값: {calculated_quantity}, 저장값: {position.total_quantity}")
                    # 자동 수정
                    position.total_quantity = calculated_quantity
                    validation_result['fixed'].append(f"{symbol}: 수량 자동 수정")
                
                # 평단가 검증 및 순환매 데이터 정합성 확인
                active_entries = [e for e in position.entries if e.is_active]
                if position.total_quantity > 0 and active_entries:
                    # 평단가 재계산
                    calculated_avg = sum(e.quantity * e.entry_price for e in active_entries) / position.total_quantity
                    if abs(calculated_avg - position.average_price) > 0.001:
                        old_avg = position.average_price
                        validation_result['warnings'].append(f"{symbol}: 평단가 불일치 - 기존: ${old_avg:.6f}, 계산: ${calculated_avg:.6f}")
                        # 자동 수정
                        position.average_price = calculated_avg
                        validation_result['fixed'].append(f"{symbol}: 평단가 자동 수정 (${old_avg:.6f} → ${calculated_avg:.6f})")
                        self.logger.warning(f"🔧 평단가 자동 수정: {symbol} - ${old_avg:.6f} → ${calculated_avg:.6f}")
                    
                    # 순환매 상태 검증
                    if position.cyclic_state != CyclicState.NORMAL_DCA.value:
                        # 순환매 카운트와 실제 엔트리 수 일치성 확인
                        total_entries = len([e for e in position.entries if e.is_active])
                        expected_entries = 1  # 기본 초기 진입
                        if position.current_stage == PositionStage.FIRST_DCA.value:
                            expected_entries = 2
                        elif position.current_stage == PositionStage.SECOND_DCA.value:
                            expected_entries = 3
                        
                        if total_entries != expected_entries:
                            validation_result['warnings'].append(f"{symbol}: 순환매 엔트리 수 불일치 - 실제: {total_entries}, 예상: {expected_entries}")
                        
                        # 순환매 수익 누적 검증
                        if position.total_cyclic_profit < 0 and position.cyclic_count > 0:
                            validation_result['warnings'].append(f"{symbol}: 순환매 수익 음수 - {position.total_cyclic_profit:.4f} USDT")
                        
                        # 순환매 카운트 상한 검증
                        if position.cyclic_count > position.max_cyclic_count:
                            validation_result['warnings'].append(f"{symbol}: 순환매 카운트 초과 - {position.cyclic_count}/{position.max_cyclic_count}")
                            position.cyclic_count = position.max_cyclic_count
                            validation_result['fixed'].append(f"{symbol}: 순환매 카운트 수정")
            
            # 수정사항이 있으면 저장
            if validation_result['fixed']:
                self.save_data()
            
            return validation_result
            
        except Exception as e:
            self.logger.error(f"데이터 검증 실패: {e}")
            return {'valid': False, 'error': str(e)}

    def get_system_health(self) -> Dict[str, Any]:
        """시스템 상태 확인"""
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
            
            # 데이터 무결성 검증
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
    # BB80 > BB600 수동청산 조건 구현 (새로운 1순위 청산 조건)
    # ========================================================================================
    
    def _check_bb80_bb600_manual_exit(self, symbol: str, current_price: float, profit_pct: float) -> Optional[Dict[str, Any]]:
        """15분봉 BB80 > BB600 조건 + 원금수익률 5% 이상시 수동청산 전환 체크"""
        try:
            # 실제 거래소 포지션 존재 확인 (중요: 포지션 동기화 문제 해결)
            try:
                real_positions = self.exchange.fetch_positions([symbol])
                active_position = None
                for pos in real_positions:
                    if pos['symbol'] == symbol and pos['contracts'] > 0:
                        active_position = pos
                        break
                
                if not active_position:
                    self.logger.debug(f"📍 {symbol} 실제 거래소 포지션 없음 - BB80>BB600 체크 스킵")
                    return None
                    
            except Exception as e:
                self.logger.warning(f"⚠️ {symbol} 거래소 포지션 확인 실패: {e} - BB80>BB600 체크 계속 진행")
            
            # 원금수익률 5% 이상 조건 확인
            if profit_pct < 0.05:  # 5% 미만이면 조건 미충족
                return None
                
            # 15분봉 데이터 조회
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, '15m', limit=600)
                if len(ohlcv) < 600:
                    self.logger.warning(f"⚠️ {symbol} 15분봉 데이터 부족: {len(ohlcv)}개")
                    return None
                    
                # DataFrame 변환
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
            except Exception as e:
                self.logger.error(f"❌ {symbol} 15분봉 데이터 조회 실패: {e}")
                return None
            
            # BB80 (80기간 볼린저밴드) 계산
            bb80_period = 80
            bb80_upper = self._calculate_bollinger_band_upper(df['close'], bb80_period, std_dev=2.0)
            
            # BB600 (600기간 볼린저밴드) 계산  
            bb600_period = 600
            bb600_upper = self._calculate_bollinger_band_upper(df['close'], bb600_period, std_dev=2.0)
            
            # 현재 시점의 BB 값들
            current_bb80_upper = bb80_upper.iloc[-1] if len(bb80_upper) > 0 else None
            current_bb600_upper = bb600_upper.iloc[-1] if len(bb600_upper) > 0 else None
            
            if current_bb80_upper is None or current_bb600_upper is None:
                self.logger.warning(f"⚠️ {symbol} BB 계산 실패: BB80={current_bb80_upper}, BB600={current_bb600_upper}")
                return None
            
            # BB80 > BB600 조건 확인 (의미있는 차이 0.1% 이상 필요)
            if current_bb80_upper > current_bb600_upper:
                # 차이 계산 (백분율)
                bb_diff_pct = ((current_bb80_upper - current_bb600_upper) / current_bb600_upper) * 100
                
                # 최소 임계값 1.0% 이상일 때만 신호 발생 (차트/API 데이터 차이 고려)
                if bb_diff_pct >= 1.0:
                    self.logger.info(f"🎯 {symbol} BB80>BB600 수동청산 조건 충족:")
                    self.logger.info(f"   원금수익률: {profit_pct*100:.2f}% (≥5%)")
                    self.logger.info(f"   BB80 상단: ${current_bb80_upper:.6f}")
                    self.logger.info(f"   BB600 상단: ${current_bb600_upper:.6f}")
                    self.logger.info(f"   BB 차이: {bb_diff_pct:.2f}% (≥1.0%)")
                    self.logger.info(f"   현재가: ${current_price:.6f}")
                    
                    return {
                        'trigger_type': 'bb80_bb600_manual_exit',
                        'priority': 1,  # 최고 우선순위
                        'profit_pct': profit_pct * 100,
                        'bb80_upper': current_bb80_upper,
                        'bb600_upper': current_bb600_upper,
                        'bb_diff_pct': bb_diff_pct,
                        'current_price': current_price,
                        'reason': f'BB80({current_bb80_upper:.6f}) > BB600({current_bb600_upper:.6f}) 차이{bb_diff_pct:.2f}% + 원금수익률 {profit_pct*100:.2f}%'
                    }
                else:
                    # 차이가 너무 미세한 경우 로그만 출력
                    self.logger.debug(f"🔍 {symbol} BB80>BB600 차이 미세: {bb_diff_pct:.2f}% (1.0% 미만, 신호 무시)")
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ BB80/BB600 수동청산 조건 확인 실패 {symbol}: {e}")
            return None
    
    def _check_profit_protection_exit(self, symbol: str, current_price: float, profit_pct: float, position) -> Optional[Dict[str, Any]]:
        """최대 수익률 6-10% 구간에서 5% 보호 청산 조건 확인"""
        try:
            # 최대 수익률이 6% 이상 도달했는지 확인
            if position.max_profit_pct < 0.06:  # 6% 미만이면 보호 조건 미충족
                return None
            
            # 최대 수익률이 6% 이상이면 보호 청산 대상 (상한 없음)
            # 10% 초과해도 5% 보호 원칙은 동일하게 적용
            
            # 현재 수익률이 5% 아래로 떨어졌는지 확인
            if profit_pct >= 0.05:  # 현재 수익률이 5% 이상이면 아직 보호 불필요
                return None
            
            # 보호 청산 조건 충족
            protection_trigger_pct = 0.05  # 5% 보호선
            max_profit_achieved = position.max_profit_pct * 100
            current_profit = profit_pct * 100
            protection_line = protection_trigger_pct * 100
            
            self.logger.info(f"💰 {symbol} 수익 보호 청산 조건 분석:")
            self.logger.info(f"   최대 수익률: {max_profit_achieved:.2f}% (≥6%)")
            self.logger.info(f"   현재 수익률: {current_profit:.2f}%")
            self.logger.info(f"   보호선: {protection_line:.2f}%")
            self.logger.info(f"   보호 조건: 최대수익률 6% 이상 달성 후 5% 아래 하락시 전량청산")
            
            return {
                'trigger_type': 'profit_protection_exit',
                'priority': 1.5,  # BB80>BB600 다음 순위
                'max_profit_pct': max_profit_achieved,
                'current_profit_pct': current_profit,
                'protection_line_pct': protection_line,
                'protection_price': position.initial_entry_price * (1 + protection_trigger_pct),
                'current_price': current_price,
                'exit_ratio': 1.0,  # 전량 청산
                'reason': f'최대수익률 {max_profit_achieved:.2f}% 달성 후 {protection_line:.0f}% 보호선 하회'
            }
            
        except Exception as e:
            self.logger.error(f"❌ 수익 보호 청산 조건 확인 실패 {symbol}: {e}")
            return None
    
    def _check_time_based_exit(self, position: DCAPosition, current_price: float, profit_pct: float) -> Optional[Dict[str, Any]]:
        """시간 기반 자동 청산 조건 확인 - 2시간 이상 보유하고 원금 수익률이 0~5% 이하인 경우"""
        try:
            # 이미 시간 기반 청산이 완료된 경우 스킵
            if position.time_based_exit_done:
                return None
            
            # 실제 거래소 포지션 존재 확인 (중요: 포지션 동기화 문제 해결)
            try:
                real_positions = self.exchange.fetch_positions([position.symbol])
                active_position = None
                for pos in real_positions:
                    if pos['symbol'] == position.symbol and pos['contracts'] > 0:
                        active_position = pos
                        break
                
                if not active_position:
                    self.logger.debug(f"📍 {position.symbol} 실제 거래소 포지션 없음 - 시간 기반 청산 체크 스킵")
                    return None
                    
            except Exception as e:
                self.logger.warning(f"⚠️ {position.symbol} 거래소 포지션 확인 실패: {e} - 시간 기반 청산 체크 계속 진행")
            
            # 포지션 생성 시간 파싱
            try:
                created_time = datetime.fromisoformat(position.created_at.replace('Z', '+00:00'))
            except (ValueError, AttributeError) as e:
                self.logger.warning(f"⚠️ {position.symbol} 포지션 생성 시간 파싱 실패: {position.created_at}, {e}")
                # 백업: 한국 시간 형식으로 시도
                try:
                    created_time = datetime.strptime(position.created_at, '%Y-%m-%d %H:%M:%S')
                    # 한국시간으로 가정하고 UTC로 변환
                    created_time = created_time.replace(tzinfo=timezone(timedelta(hours=9)))
                except ValueError:
                    self.logger.error(f"❌ {position.symbol} 시간 파싱 완전 실패, 시간 기반 청산 스킵")
                    return None
            
            # 현재 시간 (UTC)
            current_time = datetime.now(timezone.utc)
            
            # 보유 시간 계산 (시간 단위)
            hold_duration = current_time - created_time
            hold_hours = hold_duration.total_seconds() / 3600
            
            # 2시간 이상 보유 조건 확인
            if hold_hours < 2.0:
                return None
            
            # 원금 수익률이 0~5% 이하 조건 확인 (수정된 조건)
            if profit_pct < 0 or profit_pct > 0.05:  # 0% 미만이거나 5% 초과시 조건 미충족
                return None
            
            # 시간 기반 청산 조건 충족
            self.logger.info(f"⏰ {position.symbol} 시간 기반 청산 조건 분석:")
            self.logger.info(f"   보유 시간: {hold_hours:.1f}시간 (≥2시간)")
            self.logger.info(f"   현재 수익률: {profit_pct*100:.2f}% (0~5% 범위)")
            self.logger.info(f"   청산 조건: 2시간 이상 보유 + 원금수익률 0~5% 이하")
            
            return {
                'trigger_type': 'time_based_exit',
                'priority': 2,  # 손절 다음 우선순위
                'hold_hours': hold_hours,
                'current_profit_pct': profit_pct * 100,
                'current_price': current_price,
                'position_age': f"{int(hold_hours)}시간 {int((hold_hours % 1) * 60)}분",
                'exit_ratio': 1.0,  # 전량 청산
                'reason': f'{hold_hours:.1f}시간 보유, 수익률 {profit_pct*100:.2f}% (2시간+0~5% 조건)'
            }
            
        except Exception as e:
            self.logger.error(f"❌ 시간 기반 청산 조건 확인 실패 {position.symbol}: {e}")
            return None
    
    def _calculate_bollinger_band_upper(self, close_prices: pd.Series, period: int, std_dev: float = 2.0) -> pd.Series:
        """볼린저밴드 상단선 계산"""
        try:
            if len(close_prices) < period:
                # 데이터 부족시 현재가 기준으로 상단선 추정
                current_price = close_prices.iloc[-1]
                return pd.Series([current_price * 1.02] * len(close_prices), index=close_prices.index)
            
            # 이동평균선 계산
            sma = close_prices.rolling(window=period).mean()
            
            # 표준편차 계산
            std = close_prices.rolling(window=period).std()
            
            # 볼린저밴드 상단선 = 이동평균선 + (표준편차 * 계수)
            bb_upper = sma + (std * std_dev)
            
            return bb_upper
            
        except Exception as e:
            self.logger.error(f"볼린저밴드 계산 실패: {e}")
            # 에러 시 현재가 기준 기본값 반환
            current_price = close_prices.iloc[-1]
            return pd.Series([current_price * 1.02] * len(close_prices), index=close_prices.index)

    # ========================================================================================
    # 새로운 4가지 청산 방식 구현
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
            
            # 초기값 설정
            supertrend.iloc[0] = lower_band.iloc[0]
            trend.iloc[0] = 1
            
            for i in range(1, len(df)):
                # 현재 상한선/하한선 조정
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
            self.logger.error(f"SuperTrend 계산 실패: {e}")
            # 에러시 기본값 반환
            current_price = df['close'].iloc[-1]
            supertrend = pd.Series([current_price * 0.98] * len(df), index=df.index)
            trend = pd.Series([1] * len(df), index=df.index)
            return supertrend, trend
    
    def calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 600, std: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """볼린저 밴드 계산"""
        try:
            if len(df) < period:
                # 데이터가 부족한 경우 현재가 기준으로 임시 계산
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
            self.logger.error(f"볼린저 밴드 계산 실패: {e}")
            # 에러시 현재가 기준 반환
            current_price = df['close'].iloc[-1]
            bb_middle = pd.Series([current_price] * len(df), index=df.index)
            bb_upper = bb_middle * 1.02
            bb_lower = bb_middle * 0.98
            return bb_upper, bb_middle, bb_lower
    
    def check_supertrend_exit_signal(self, symbol: str, current_price: float, position: DCAPosition) -> Optional[Dict[str, Any]]:
        """1. SuperTrend 전량청산 확인: 5분봉 SuperTrend 청산시그널시 무조건 전량청산 (수익률 무관)"""
        try:
            if position.supertrend_exit_done:
                return None
            
            # 현재 수익률 계산
            current_profit_pct = (current_price - position.average_price) / position.average_price
            
            # 최대 수익률 업데이트
            if current_profit_pct > position.max_profit_pct:
                position.max_profit_pct = current_profit_pct
                position.last_update = get_korea_time().isoformat()
                self.save_data()
            
            # 🔧 수정: SuperTrend 청산은 수익률 조건 없이 신호만으로 실행
            # 문서에 "SuperTrend 전량청산: 5분봉 SuperTrend(10-3) 청산시그널시 전량청산"이라고 명시됨
            
            # 5분봉 데이터 조회
            ohlcv = self.exchange.fetch_ohlcv(symbol, '5m', limit=50)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            if len(df) < 15:
                return None
            
            # SuperTrend 계산
            supertrend, trend = self.calculate_supertrend(df, period=10, multiplier=3.0)
            
            # 청산 시그널 확인: 상승(1) → 하락(-1) 전환
            if len(trend) >= 2:
                prev_trend = trend.iloc[-2]
                current_trend = trend.iloc[-1]
                
                if prev_trend == 1 and current_trend == -1:
                    self.logger.warning(f"🔴 SuperTrend 청산 시그널: {symbol} (수익률 무관 전량청산)")
                    self.logger.warning(f"   최대수익: {position.max_profit_pct*100:.1f}%")
                    self.logger.warning(f"   현재수익: {current_profit_pct*100:.1f}%")
                    self.logger.warning(f"   트렌드 전환: {prev_trend} → {current_trend}")
                    
                    return {
                        'exit_type': ExitType.SUPERTREND_EXIT.value,
                        'exit_ratio': 1.0,  # 전량 청산
                        'max_profit_pct': position.max_profit_pct * 100,
                        'current_profit_pct': current_profit_pct * 100,
                        'supertrend_signal': f"상승({prev_trend}) → 하락({current_trend})",
                        'trigger_info': "5분봉 SuperTrend(10-3) 청산시그널 (수익률 무관)"
                    }
            
            return None
            
        except Exception as e:
            self.logger.error(f"SuperTrend 청산 확인 실패 {symbol}: {e}")
            return None
    
    def check_bb600_exit_signal(self, symbol: str, current_price: float, position: DCAPosition) -> Optional[Dict[str, Any]]:
        """2. BB600 트레일링 스탑: 15분봉/30분봉 캔들 고점이 BB600 상단선 돌파시 50% 익절 + 트레일링 스탑 활성화"""
        try:
            # 이미 BB600 50% 청산을 했다면 트레일링 스탑만 체크
            if position.bb600_exit_done and not position.trailing_stop_active:
                return None

            # 트레일링 스탑이 활성화된 경우, 트레일링 스탑 로직 실행
            if position.trailing_stop_active:
                return self._check_trailing_stop(symbol, current_price, position)

            # BB600 돌파 체크 (15분봉, 30분봉만)
            current_profit_pct = (current_price - position.average_price) / position.average_price
            
            for timeframe in ['15m', '30m']:
                try:
                    # 데이터 조회
                    ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=650)  # BB600 계산을 위해 충분한 데이터
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    
                    if len(df) < 10:
                        continue
                    
                    # BB600 계산 (표준편차 2.9 사용)
                    bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(df, period=600, std=2.9)
                    
                    # 최근 몇 개 캔들의 고점이 BB600 상단선을 돌파했는지 확인 (현재 포함 최근 3봉)
                    for i in range(-3, 0):  # 최근 3봉 체크
                        if abs(i) > len(df):
                            continue
                            
                        candle_high = df['high'].iloc[i]
                        bb_upper_at_time = bb_upper.iloc[i] if abs(i) <= len(bb_upper) else None
                        
                        if pd.notna(bb_upper_at_time) and candle_high > bb_upper_at_time:
                            self.logger.info(f"💰 BB600 캔들 고점 돌파 감지: {symbol} ({timeframe})")
                            self.logger.info(f"   캔들 고점: ${candle_high:.6f}")
                            self.logger.info(f"   BB600 상단: ${bb_upper_at_time:.6f}")
                            
                            current_profit_pct = (current_price - position.average_price) / position.average_price * 100
                            
                            # 트레일링 스탑 활성화
                            position.trailing_stop_active = True
                            position.trailing_stop_high = current_price
                            position.last_update = get_korea_time().isoformat()
                            self.save_data()
                            
                            # 텔레그램 알림
                            if self.telegram_bot:
                                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                                message = (f"🎯 [BB600 돌파 + 트레일링 스탑 활성화] {clean_symbol}\n"
                                         f"시간프레임: {timeframe}\n"
                                         f"캔들 고점: ${candle_high:.6f}\n"
                                         f"BB600 상단: ${bb_upper_at_time:.6f}\n"
                                         f"현재 수익률: {current_profit_pct:.1f}%\n"
                                         f"🔄 50% 익절 + 트레일링 스탑 시작")
                                self.telegram_bot.send_message(message)
                            
                            return {
                                'exit_type': ExitType.BB600_PARTIAL_EXIT.value,
                                'exit_ratio': 0.5,  # 50% 청산
                                'timeframe': timeframe,
                                'current_price': current_price,
                                'candle_high': candle_high,
                                'bb600_upper': bb_upper_at_time,
                                'current_profit_pct': current_profit_pct,
                                'trigger_info': f"{timeframe}봉 캔들 고점 BB600 돌파 (50% 익절 + 트레일링 스탑 활성화)",
                                'trailing_stop_activated': True
                            }
                        
                except Exception as e:
                    self.logger.debug(f"BB600 확인 실패 {symbol} {timeframe}: {e}")
                    continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"BB600 돌파 확인 실패 {symbol}: {e}")
            return None
    
    def _check_trailing_stop(self, symbol: str, current_price: float, position: DCAPosition) -> Optional[Dict[str, Any]]:
        """트레일링 스탑 로직: 최고가에서 5% 하락시 나머지 50% 청산"""
        try:
            # 현재가가 새로운 최고가인지 확인
            if current_price > position.trailing_stop_high:
                position.trailing_stop_high = current_price
                position.last_update = get_korea_time().isoformat()
                self.save_data()
                
                # 새로운 최고가 갱신 시 텔레그램 알림 (너무 빈번하지 않게 로그 레벨 조정)
                self.logger.debug(f"🔄 트레일링 스탑 최고가 갱신: {symbol} ${current_price:.6f}")
            
            # 트레일링 스탑 트리거 체크: 최고가에서 5% 하락
            trailing_stop_price = position.trailing_stop_high * (1 - position.trailing_stop_percentage)
            
            if current_price <= trailing_stop_price:
                current_profit_pct = (current_price - position.average_price) / position.average_price * 100
                high_to_current_drop = ((position.trailing_stop_high - current_price) / position.trailing_stop_high) * 100
                
                self.logger.warning(f"🔴 트레일링 스탑 청산 트리거: {symbol}")
                self.logger.warning(f"   최고가: ${position.trailing_stop_high:.6f}")
                self.logger.warning(f"   현재가: ${current_price:.6f}")
                self.logger.warning(f"   트레일링 스탑가: ${trailing_stop_price:.6f}")
                self.logger.warning(f"   최고가 대비 하락: {high_to_current_drop:.1f}%")
                
                # 텔레그램 알림
                if self.telegram_bot:
                    clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                    message = (f"🔴 [트레일링 스탑 청산] {clean_symbol}\n"
                             f"최고가: ${position.trailing_stop_high:.6f}\n"
                             f"현재가: ${current_price:.6f}\n"
                             f"하락률: {high_to_current_drop:.1f}%\n"
                             f"현재 수익률: {current_profit_pct:.1f}%\n"
                             f"💰 나머지 50% 전량청산")
                    self.telegram_bot.send_message(message)
                
                return {
                    'exit_type': 'trailing_stop_exit',
                    'exit_ratio': 0.5,  # 나머지 50% 청산
                    'current_price': current_price,
                    'trailing_stop_high': position.trailing_stop_high,
                    'trailing_stop_price': trailing_stop_price,
                    'high_to_current_drop_pct': high_to_current_drop,
                    'current_profit_pct': current_profit_pct,
                    'trigger_info': f"트레일링 스탑 청산 (최고가 대비 {high_to_current_drop:.1f}% 하락)"
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"트레일링 스탑 체크 실패 {symbol}: {e}")
            return None
    
    def check_breakeven_protection_exit(self, symbol: str, current_price: float, position: DCAPosition) -> Optional[Dict[str, Any]]:
        """3. 본절청산: 수익률별 차등 청산 (3%~5%: 손실전환전, 5%~10%: 절반하락시)"""
        try:
            # 🚨 중복 청산 방지: 이미 본절보호청산이 완료된 경우 스킵
            if hasattr(position, 'breakeven_exit_done') and position.breakeven_exit_done:
                return None
            
            # 현재 수익률 계산
            current_profit_pct = (current_price - position.average_price) / position.average_price
            
            # 최대 수익률 업데이트
            if current_profit_pct > position.max_profit_pct:
                position.max_profit_pct = current_profit_pct
                position.last_update = get_korea_time().isoformat()
                self.save_data()
            
            # 3% 이상 수익 달성시 보호 모드 활성화
            if position.max_profit_pct >= 0.03:
                if not position.breakeven_protection_active:
                    position.breakeven_protection_active = True
                    position.last_update = get_korea_time().isoformat()
                    self.save_data()
                    
                    # 수익률 구간별 보호 전략 결정
                    protection_strategy = ""
                    if position.max_profit_pct >= 0.20:
                        protection_strategy = "20%+ 초고수익 트레일링 스톱 (15% 하락 허용)"
                    elif position.max_profit_pct >= 0.15:
                        protection_strategy = "15~20% 고수익 트레일링 스톱 (20% 하락 허용)"
                    elif position.max_profit_pct >= 0.10:
                        protection_strategy = "10~15% 트레일링 스톱 (25% 하락 허용)"
                    elif position.max_profit_pct >= 0.05:
                        protection_strategy = "5~10% 절반하락 보호"
                    else:
                        protection_strategy = "3~5% 약수익 보호 (70% 하락시 청산)"
                    
                    # 텔레그램 알림
                    if self.telegram_bot:
                        clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                        # 수익률에 따라 적절한 제목 설정
                        if position.max_profit_pct >= 0.10:
                            alert_title = "📈 [트레일링 스톱 활성화]"
                        elif position.max_profit_pct >= 0.05:
                            alert_title = "🛡️ [수익보호 활성화]"
                        else:
                            alert_title = "🛡️ [본절보호 활성화]"
                        
                        message = (f"{alert_title} {clean_symbol}\n"
                                 f"최대수익: {position.max_profit_pct*100:.1f}%\n"
                                 f"보호전략: {protection_strategy}\n"
                                 f"현재가: ${current_price:.6f}")
                        self.telegram_bot.send_message(message)
                        self.logger.info(f"{alert_title} {symbol} (최대수익: {position.max_profit_pct*100:.1f}%) - {protection_strategy}")
            
            # 보호 모드가 활성화된 상태에서 수익률 구간별 청산 조건 적용
            if position.breakeven_protection_active:
                exit_trigger = None
                trigger_reason = ""
                
                if position.max_profit_pct >= 0.10:
                    # 10% 이상: 트레일링 스톱 적용 (최고점 대비 허용 하락폭 설정)
                    # 수익률별 트레일링 스톱 비율
                    if position.max_profit_pct >= 0.20:  # 20% 이상
                        allowed_drop = 0.15  # 15% 하락 허용 (85% 유지)
                        protection_type = "20%+ 초고수익"
                    elif position.max_profit_pct >= 0.15:  # 15~20%
                        allowed_drop = 0.20  # 20% 하락 허용 (80% 유지)
                        protection_type = "15~20% 고수익"
                    else:  # 10~15%
                        allowed_drop = 0.25  # 25% 하락 허용 (75% 유지)
                        protection_type = "10~15% 수익"

                    trailing_threshold = position.max_profit_pct * (1 - allowed_drop)
                    # 🔧 수정: 현재 수익률이 양수 범위에서만 트레일링 스톱 청산
                    if current_profit_pct > 0 and current_profit_pct <= trailing_threshold:
                        exit_trigger = True
                        trigger_reason = f"{protection_type} 트레일링 스톱 (최대 {position.max_profit_pct*100:.1f}% → 현재 {current_profit_pct*100:.1f}%, {allowed_drop*100:.0f}% 하락 허용)"
                        
                elif position.max_profit_pct >= 0.05:
                    # 5%~10% 미만: 절반하락시 전량청산 (단, 최소 5% 보장)
                    half_drop_threshold = position.max_profit_pct * 0.5
                    # 🔥 핵심 수정: 5% 최소 보장! 절반하락 기준점이 5% 아래로 내려가지 않도록 제한
                    guaranteed_min_profit = 0.05  # 5% 최소 보장
                    actual_exit_threshold = max(half_drop_threshold, guaranteed_min_profit)
                    
                    # 🔧 수정: 현재 수익률이 양수 범위에서만 절반 하락시 청산 (5% 최소 보장)
                    if current_profit_pct > 0 and current_profit_pct <= actual_exit_threshold:
                        exit_trigger = True
                        if actual_exit_threshold > half_drop_threshold:
                            trigger_reason = f"5% 최소보장 청산 (최대수익 {position.max_profit_pct*100:.1f}% → 현재 {current_profit_pct*100:.1f}%, 5% 보장)"
                        else:
                            trigger_reason = f"5~10% 절반하락 보호 (최대수익 {position.max_profit_pct*100:.1f}% → 현재 {current_profit_pct*100:.1f}%)"
                        
                else:
                    # 3%~5% 미만: 더 적극적인 약수익 보호 (최대수익의 30% 지점에서 청산)
                    protection_threshold = position.max_profit_pct * 0.3  # 최대수익의 30%까지만 허용
                    if current_profit_pct <= protection_threshold:
                        exit_trigger = True
                        trigger_reason = f"약수익 보호청산 (최대수익 {position.max_profit_pct*100:.1f}% → 현재 {current_profit_pct*100:.1f}%, 70% 하락)"
                
                # 청산 트리거 발동시
                if exit_trigger:
                    self.logger.critical(f"💙 본절청산 트리거: {symbol}")
                    self.logger.critical(f"   {trigger_reason}")
                    self.logger.critical(f"   최대수익: {position.max_profit_pct*100:.1f}%")
                    self.logger.critical(f"   현재수익: {current_profit_pct*100:.1f}%")
                    
                    return {
                        'exit_type': ExitType.BREAKEVEN_PROTECTION.value,
                        'exit_ratio': 1.0,  # 전량 청산
                        'max_profit_pct': position.max_profit_pct * 100,
                        'current_profit_pct': current_profit_pct * 100,
                        'secured_profit': current_profit_pct * 100,  # 실제 확보 손익
                        'trigger_info': trigger_reason
                    }
            
            return None
            
        except Exception as e:
            self.logger.error(f"약수익 보호 확인 실패 {symbol}: {e}")
            return None
    
    def check_10_percent_profit_exit(self, symbol: str, current_price: float, position: DCAPosition) -> Optional[Dict[str, Any]]:
        """2. 10% 수익률 달성시 50% 익절청산 + 트레일링 스탑 활성화"""
        try:
            # 이미 10% 수익 청산을 했다면 스킵
            if hasattr(position, 'profit_10_exit_done') and position.profit_10_exit_done:
                return None
                
            # 현재 수익률 계산 (원금 기준)
            current_profit_pct = (current_price - position.average_price) / position.average_price
            
            # 10% 수익률 달성시 50% 익절
            if current_profit_pct >= 0.10:
                self.logger.info(f"💰 10% 원금 수익률 달성 - 50% 익절청산: {symbol} (수익률: {current_profit_pct*100:.1f}%)")
                
                # 10% 수익 청산 마킹
                position.profit_10_exit_done = True
                
                # 트레일링 스탑 활성화
                position.trailing_stop_active = True
                position.trailing_stop_high = current_price
                position.last_update = get_korea_time().isoformat()
                self.save_data()
                
                # 텔레그램 알림
                if self.telegram_bot:
                    clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                    message = (f"💰 [10% 수익률 익절] {clean_symbol}\n"
                             f"진입가: ${position.average_price:.6f}\n"
                             f"현재가: ${current_price:.6f}\n"
                             f"수익률: {current_profit_pct*100:.1f}%\n"
                             f"🔄 50% 익절 + 트레일링 스탑 시작")
                    self.telegram_bot.send_message(message)
                
                return {
                    'exit_type': 'profit_10_percent_exit',
                    'exit_ratio': 0.5,  # 50% 청산
                    'current_price': current_price,
                    'current_profit_pct': current_profit_pct * 100,
                    'trigger_info': f"10% 원금 수익률 달성 50% 익절 ({current_profit_pct*100:.1f}%)",
                    'trailing_stop_activated': True
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"10% 수익률 익절 확인 실패 {symbol}: {e}")
            return None
    
    def check_weak_rise_dump_protection_exit(self, symbol: str, current_price: float, position: DCAPosition) -> Optional[Dict[str, Any]]:
        """5. 약상승후 급락 리스크 회피: 원금기준 최대수익률 2%이상 → 손실부근 하락 + 5분봉 5봉이내 SuperTrend(10-2) 청산신호"""
        try:
            if position.weak_rise_dump_exit_done:
                return None
            
            # 현재 수익률 계산
            current_profit_pct = (current_price - position.average_price) / position.average_price
            
            # 최대 수익률 업데이트
            if current_profit_pct > position.max_profit_pct:
                position.max_profit_pct = current_profit_pct
                position.last_update = get_korea_time().isoformat()
                self.save_data()
            
            # 조건 1: 최대수익률 2% 이상 달성했었는지 확인
            if position.max_profit_pct < 0.02:  # 2% 미만이면 조건 불충족
                return None
            
            # 조건 2: 현재 손실 부근까지 하락했는지 확인 (0% 근처 또는 마이너스)
            if current_profit_pct > 0.005:  # 0.5% 이상 수익이면 아직 손실 부근이 아님
                return None
            
            # 조건 3: 5분봉 데이터 조회하여 SuperTrend(10-2) 청산 신호 확인
            ohlcv = self.exchange.fetch_ohlcv(symbol, '5m', limit=20)  # 5봉 이내 확인을 위해 여유있게 20봉
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            if len(df) < 15:
                return None
            
            # SuperTrend(10-2) 계산 (기존 10-3과 다른 파라미터)
            supertrend_10_2, trend_10_2 = self.calculate_supertrend(df, period=10, multiplier=2.0)
            
            # 5봉 이내 청산 신호 확인: 상승(1) → 하락(-1) 전환
            recent_5_trends = trend_10_2.tail(5)  # 최근 5봉
            
            found_exit_signal = False
            signal_position = -1
            
            for i in range(len(recent_5_trends) - 1):
                prev_trend = recent_5_trends.iloc[i]
                current_trend = recent_5_trends.iloc[i + 1]
                
                # 상승에서 하락으로 전환 확인
                if prev_trend == 1 and current_trend == -1:
                    found_exit_signal = True
                    signal_position = i + 1
                    break
            
            if found_exit_signal:
                self.logger.warning(f"🚨 약상승후 급락 리스크 회피 청산: {symbol}")
                self.logger.warning(f"   최대수익: {position.max_profit_pct*100:.1f}%")
                self.logger.warning(f"   현재수익: {current_profit_pct*100:.1f}%")
                self.logger.warning(f"   SuperTrend(10-2): 5봉이내 청산신호 감지 (위치: {signal_position})")
                
                return {
                    'exit_type': ExitType.WEAK_RISE_DUMP_PROTECTION.value,
                    'exit_ratio': 1.0,  # 전량 청산
                    'max_profit_pct': position.max_profit_pct * 100,
                    'current_profit_pct': current_profit_pct * 100,
                    'supertrend_signal_position': signal_position,
                    'trigger_info': f"약상승후 급락 리스크 회피 (최대{position.max_profit_pct*100:.1f}% → {current_profit_pct*100:.1f}%, SuperTrend(10-2) 5봉이내 청산신호)"
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"약상승후 급락 리스크 회피 확인 실패 {symbol}: {e}")
            return None
    
    def check_bb80_bb600_reversal_exit(self, symbol: str, current_price: float, position: DCAPosition) -> Optional[Dict[str, Any]]:
        """6. BB80-BB600 역전 기반 전량청산: BB80상단>BB600상단 & MA5-BB600상단 이격도≥10% & 15분봉 시가>MA5 & 1분봉 10봉이내 MA5-BB80 데드크로스"""
        try:
            # WebSocket 데이터 제공자 확인
            if not hasattr(self, 'strategy') or not hasattr(self.strategy, 'ws_provider') or not self.strategy.ws_provider:
                return None
                
            ws_provider = self.strategy.ws_provider
            
            # 15분봉 데이터 가져오기 (MA5, BB80, BB600 계산용)
            data_15m = ws_provider.get_ohlcv(symbol, '15m', 120)
            if not data_15m or len(data_15m) < 100:
                return None
                
            # 1분봉 데이터 가져오기 (MA5-BB80 데드크로스 확인용)
            data_1m = ws_provider.get_ohlcv(symbol, '1m', 20)
            if not data_1m or len(data_1m) < 15:
                return None
                
            # 15분봉 DataFrame 변환
            df_15m = pd.DataFrame(data_15m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_15m = df_15m.astype({
                'open': 'float64', 'high': 'float64', 'low': 'float64', 'close': 'float64', 'volume': 'float64'
            })
            
            # 1분봉 DataFrame 변환
            df_1m = pd.DataFrame(data_1m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_1m = df_1m.astype({
                'open': 'float64', 'high': 'float64', 'low': 'float64', 'close': 'float64', 'volume': 'float64'
            })
            
            # 15분봉 기술적 지표 계산
            df_15m['MA5'] = df_15m['close'].rolling(window=5).mean()
            
            # BB80 (80일 볼린저밴드)
            bb80_mean = df_15m['close'].rolling(window=80).mean()
            bb80_std = df_15m['close'].rolling(window=80).std()
            df_15m['BB80_upper'] = bb80_mean + (bb80_std * 2.0)
            df_15m['BB80_lower'] = bb80_mean - (bb80_std * 2.0)
            
            # BB600 (600일 볼린저밴드)
            bb600_mean = df_15m['close'].rolling(window=100).mean()  # 15분봉에서는 100개로 제한
            bb600_std = df_15m['close'].rolling(window=100).std()
            df_15m['BB600_upper'] = bb600_mean + (bb600_std * 2.0)
            df_15m['BB600_lower'] = bb600_mean - (bb600_std * 2.0)
            
            # 1분봉 기술적 지표 계산
            df_1m['MA5'] = df_1m['close'].rolling(window=5).mean()
            bb80_mean_1m = df_1m['close'].rolling(window=15).mean()  # 1분봉에서는 15개로 제한
            bb80_std_1m = df_1m['close'].rolling(window=15).std()
            df_1m['BB80_upper'] = bb80_mean_1m + (bb80_std_1m * 2.0)
            
            # 최신 15분봉 데이터
            latest_15m = df_15m.iloc[-1]
            bb80_upper_15m = latest_15m['BB80_upper']
            bb600_upper_15m = latest_15m['BB600_upper']
            ma5_15m = latest_15m['MA5']
            open_15m = latest_15m['open']
            
            # 조건 1: BB80 상단선 > BB600 상단선
            condition1 = bb80_upper_15m > bb600_upper_15m
            
            # 조건 2: MA5와 BB600 상단선 이격도가 10% 이상
            if bb600_upper_15m > 0:
                ma5_bb600_gap_pct = abs((ma5_15m - bb600_upper_15m) / bb600_upper_15m) * 100
                condition2 = ma5_bb600_gap_pct >= 10.0
            else:
                condition2 = False
                
            # 조건 3: 15분봉상 시가 > MA5
            condition3 = open_15m > ma5_15m
            
            # 조건 4: 1분봉상 10봉 이내 MA5-BB80 데드크로스
            condition4 = False
            deadcross_candle = None
            
            if len(df_1m) >= 10:
                for i in range(min(10, len(df_1m) - 1)):
                    current_idx = len(df_1m) - 1 - i
                    prev_idx = current_idx - 1
                    
                    if (current_idx >= 0 and prev_idx >= 0 and 
                        not pd.isna(df_1m.iloc[current_idx]['MA5']) and 
                        not pd.isna(df_1m.iloc[current_idx]['BB80_upper']) and
                        not pd.isna(df_1m.iloc[prev_idx]['MA5']) and 
                        not pd.isna(df_1m.iloc[prev_idx]['BB80_upper'])):
                        
                        # 이전: MA5 > BB80상단, 현재: MA5 <= BB80상단 (데드크로스)
                        prev_above = df_1m.iloc[prev_idx]['MA5'] > df_1m.iloc[prev_idx]['BB80_upper']
                        current_below = df_1m.iloc[current_idx]['MA5'] <= df_1m.iloc[current_idx]['BB80_upper']
                        
                        if prev_above and current_below:
                            condition4 = True
                            deadcross_candle = i + 1
                            break
            
            # 디버그 로그
            self.logger.debug(f"BB80-BB600 역전 청산 체크 {symbol}: "
                            f"BB80상단({bb80_upper_15m:.4f}) > BB600상단({bb600_upper_15m:.4f}): {condition1}, "
                            f"MA5-BB600 이격도 {ma5_bb600_gap_pct:.1f}%≥10%: {condition2}, "
                            f"시가({open_15m:.4f}) > MA5({ma5_15m:.4f}): {condition3}, "
                            f"1분봉 MA5-BB80 데드크로스(10봉이내): {condition4}")
            
            # 모든 조건 만족시 전량청산 신호
            if condition1 and condition2 and condition3 and condition4:
                return {
                    'exit_type': ExitType.BB80_BB600_REVERSAL_EXIT.value,
                    'exit_ratio': 1.0,  # 전량청산
                    'current_price': current_price,
                    'reason': 'BB80-BB600 역전 + MA5-BB600 이격도≥10% + 시가>MA5 + MA5-BB80 데드크로스',
                    'bb80_upper': bb80_upper_15m,
                    'bb600_upper': bb600_upper_15m,
                    'ma5_bb600_gap_pct': ma5_bb600_gap_pct,
                    'open_15m': open_15m,
                    'ma5_15m': ma5_15m,
                    'deadcross_candle': deadcross_candle,
                    'trigger_info': f"BB80-BB600 역전청산 (BB80상단:{bb80_upper_15m:.4f} > BB600상단:{bb600_upper_15m:.4f}, MA5-BB600 이격:{ma5_bb600_gap_pct:.1f}%, {deadcross_candle}봉전 데드크로스)"
                }
                
            return None
            
        except Exception as e:
            self.logger.error(f"BB80-BB600 역전 청산 확인 실패 {symbol}: {e}")
            return None
    
    def check_all_new_exit_signals(self, symbol: str, current_price: float) -> Optional[Dict[str, Any]]:
        """새로운 7가지 청산 방식 종합 확인 (우선순위 적용)"""
        try:
            if symbol not in self.positions:
                return None
            
            position = self.positions[symbol]
            if not position.is_active:
                return None
            
            # 🎯 청산 모드 판단: 최초 진입가 기준으로 일반청산 vs 순환매 결정
            is_profitable = current_price > position.initial_entry_price
            profit_pct_from_initial = ((current_price - position.initial_entry_price) / position.initial_entry_price) * 100
            
            if is_profitable:
                # 최초 진입가 대비 수익 상황 → 일반 청산 모드 적용
                self.logger.debug(f"💚 일반청산모드: {symbol} - 최초진입가 대비 +{profit_pct_from_initial:.2f}%")
                
                # 1순위: SuperTrend 전량청산 (수익률 조건 + SuperTrend 시그널)
                supertrend_exit = self.check_supertrend_exit_signal(symbol, current_price, position)
                if supertrend_exit:
                    return supertrend_exit
                
                # 2순위: 10% 수익률 달성시 50% 익절청산
                profit_partial_exit = self.check_10_percent_profit_exit(symbol, current_price, position)
                if profit_partial_exit:
                    return profit_partial_exit
                
                # 3순위: BB600 50% 익절 (기술적 조건)
                bb600_exit = self.check_bb600_exit_signal(symbol, current_price, position)
                if bb600_exit:
                    return bb600_exit
                
                # 4순위: 약상승후 급락 리스크 회피
                weak_rise_dump_exit = self.check_weak_rise_dump_protection_exit(symbol, current_price, position)
                if weak_rise_dump_exit:
                    return weak_rise_dump_exit
                
                # 5순위: 브레이크이븐 보호청산 (트레일링 스톱, 절반하락 보호, 약수익 보호)
                breakeven_exit = self.check_breakeven_protection_exit(symbol, current_price, position)
                if breakeven_exit:
                    return breakeven_exit
                
                # 6순위: BB80-BB600 역전 기반 전량청산 (수익/손실 구분 없이 적용)
                bb80_bb600_reversal_exit = self.check_bb80_bb600_reversal_exit(symbol, current_price, position)
                if bb80_bb600_reversal_exit:
                    return bb80_bb600_reversal_exit
                
            else:
                # 최초 진입가 대비 손실 상황 → 순환매 모드 (카운트 무관)
                self.logger.debug(f"🔄 순환매모드: {symbol} - 최초진입가 대비 {profit_pct_from_initial:.2f}%")
                
                # 우선: BB80-BB600 역전 기반 전량청산 (손실 상황에서도 적용)
                bb80_bb600_reversal_exit = self.check_bb80_bb600_reversal_exit(symbol, current_price, position)
                if bb80_bb600_reversal_exit:
                    return bb80_bb600_reversal_exit
                
                # 순환매 3회 제한은 참고용으로만 사용 (실제 모드 전환과는 무관)
                if position.cyclic_count < position.max_cyclic_count:
                    # 7순위: DCA 순환매 일부청산 (손실 상황에서만 적용)
                    # 기존 순환매 시스템 호출은 여기서 하지 않고, 별도 메서드에서 처리
                    pass
            
            return None
            
        except Exception as e:
            self.logger.error(f"새로운 청산 확인 실패 {symbol}: {e}")
            return None
    
    def check_new_exit_conditions(self, symbol: str, current_price: float) -> bool:
        """새로운 청산 조건 확인 (미구현)"""
        # TODO: 새로운 청산 조건들 구현
        return False
    
    def execute_new_exit(self, symbol: str, exit_signal: Dict[str, Any]) -> dict:
        """새로운 청산 방식 실행"""
        try:
            if symbol not in self.positions:
                return {'success': False, 'silent': False}
            
            position = self.positions[symbol]
            exit_type = exit_signal['exit_type']
            exit_ratio = exit_signal['exit_ratio']
            
            # 텔레그램 알림 전송
            self.send_new_exit_notification(symbol, exit_signal, position)
            
            # 청산 실행 (기존 partial_exit 또는 force_exit 활용)
            if exit_ratio >= 1.0:
                # 전량 청산
                result = self.force_exit_position(symbol, reason=f"new_exit_{exit_type}")
                if isinstance(result, dict):
                    success = result.get('success', False)
                    silent = result.get('silent', False)
                    
                    # API 밴으로 실패한 경우 메인 전략에서 청산하도록 요청
                    if not success and not silent and "418" in str(result.get('error', '')):
                        self.logger.warning(f"🚨 API 밴으로 DCA 청산 실패 - 메인 전략 청산 요청: {symbol}")
                        if self.strategy and hasattr(self.strategy, '_emergency_exit_requests'):
                            if not hasattr(self.strategy, '_emergency_exit_requests'):
                                self.strategy._emergency_exit_requests = set()
                            self.strategy._emergency_exit_requests.add(symbol)
                            self.logger.info(f"📋 메인 전략 긴급 청산 요청 등록: {symbol}")
                else:
                    success = result
                    silent = False
            else:
                # 부분 청산 (50%)
                result = self._execute_partial_exit(position, exit_signal['current_price'], exit_ratio, f"new_exit_{exit_type}")
                if isinstance(result, dict):
                    success = result.get('success', False)
                    silent = result.get('silent', False)
                else:
                    success = result
                    silent = False
            
            if success:
                # 청산 완료 마킹
                self.mark_new_exit_completed(symbol, exit_type, exit_signal)
                self.logger.info(f"✅ 새로운 청산 완료: {symbol} - {exit_type} ({exit_ratio*100:.0f}%)")
            
            return {'success': success, 'silent': silent}
            
        except Exception as e:
            self.logger.error(f"새로운 청산 실행 실패 {symbol}: {e}")
            return {'success': False, 'silent': False}
    
    def mark_new_exit_completed(self, symbol: str, exit_type: str, exit_signal: Dict[str, Any] = None):
        """새로운 청산 완료 마킹"""
        try:
            if symbol not in self.positions:
                return
            
            position = self.positions[symbol]
            
            if exit_type == ExitType.SUPERTREND_EXIT.value:
                position.supertrend_exit_done = True
            elif exit_type == ExitType.BB600_PARTIAL_EXIT.value:
                position.bb600_exit_done = True
                # 트레일링 스탑이 활성화된 경우 유지
                if exit_signal and 'trailing_stop_activated' in exit_signal and exit_signal['trailing_stop_activated']:
                    self.logger.info(f"🔄 트레일링 스탑 활성화 유지: {symbol}")
            elif exit_type == 'trailing_stop_exit':
                # 트레일링 스탑으로 나머지 50% 청산 완료
                position.trailing_stop_active = False
                self.logger.info(f"✅ 트레일링 스탑 완료: {symbol}")
            elif exit_type == ExitType.BREAKEVEN_PROTECTION.value:
                # 본절보호청산은 전량 청산이므로 모든 청산 완료 처리
                position.breakeven_exit_done = True
                position.supertrend_exit_done = True
                position.bb600_exit_done = True
                position.weak_rise_dump_exit_done = True
            elif exit_type == ExitType.WEAK_RISE_DUMP_PROTECTION.value:
                # 약상승후 급락 리스크 회피는 전량 청산이므로 모든 청산 완료 처리
                position.weak_rise_dump_exit_done = True
                position.supertrend_exit_done = True
                position.bb600_exit_done = True
            
            position.last_update = get_korea_time().isoformat()
            self.save_data()
            
        except Exception as e:
            self.logger.error(f"새로운 청산 완료 마킹 실패 {symbol}: {e}")
    
    def send_new_exit_notification(self, symbol: str, exit_signal: Dict[str, Any], position: DCAPosition):
        """새로운 청산 알림 전송"""
        try:
            if not self.telegram_bot:
                return
            
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            exit_type = exit_signal['exit_type']
            # current_price 안전하게 가져오기 (키가 없을 경우 대체값 사용)
            current_price = exit_signal.get('current_price', position.current_price if hasattr(position, 'current_price') else position.average_price)
            current_profit_pct = (current_price - position.average_price) / position.average_price * 100
            
            # 청산 타입별 메시지 생성
            if exit_type == ExitType.SUPERTREND_EXIT.value:
                emoji = "🔴"
                title = "SuperTrend 전량청산"
                details = (f"수익률조건: 최대{exit_signal['max_profit_pct']:.1f}% OR 현재{exit_signal['current_profit_pct']:.1f}%\n"
                          f"SuperTrend: {exit_signal['supertrend_signal']}\n"
                          f"청산량: 100% (전량)")
                
            elif exit_type == ExitType.BB600_PARTIAL_EXIT.value:
                emoji = "💰"
                title = f"BB600 50% 익절 ({exit_signal['timeframe']})"
                details = (f"돌파유형: {exit_signal['timeframe']}봉 BB600 상단선\n"
                          f"BB600상단: ${exit_signal['bb600_upper']:.6f}\n"
                          f"청산량: 50%\n잔여포지션: 50%")
                
            elif exit_type == ExitType.BREAKEVEN_PROTECTION.value:
                # 수익률에 따라 제목 구분
                max_profit = exit_signal.get('max_profit_pct', 0)
                if max_profit >= 10.0:
                    emoji = "📈"
                    title = "트레일링 스톱 청산"
                elif max_profit >= 5.0:
                    emoji = "🛡️" 
                    title = "절반 하락 청산"
                else:
                    emoji = "💙"
                    title = "약수익 보호청산"
                    
                details = (f"최대수익: {exit_signal['max_profit_pct']:.1f}%\n"
                          f"확보수익: {exit_signal['secured_profit']:.1f}%\n"
                          f"청산량: 100% (전량)")
            
            elif exit_type == ExitType.WEAK_RISE_DUMP_PROTECTION.value:
                emoji = "🚨"
                title = "약상승후 급락 리스크 회피"
                details = (f"최대수익: {exit_signal['max_profit_pct']:.1f}%\n"
                          f"현재수익: {exit_signal['current_profit_pct']:.1f}%\n"
                          f"SuperTrend(10-2): 5봉이내 청산신호\n"
                          f"청산량: 100% (전량)")
            
            else:
                emoji = "📤"
                title = "청산 완료"
                details = "새로운 청산 방식"
            
            message = (f"{emoji} [{title}] {clean_symbol}\n"
                      f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                      f"💵 청산가: ${current_price:.6f}\n"
                      f"📊 수익률: {current_profit_pct:+.1f}%\n"
                      f"{details}\n"
                      f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                      f"⚡️ {exit_signal.get('trigger_info', '청산 조건 충족')}\n"
                      f"🕐 청산시간: {datetime.now().strftime('%H:%M:%S')}")
            
            self.telegram_bot.send_message(message)
            self.logger.info(f"{emoji} 새로운 청산 알림 전송: {clean_symbol} - {title}")
            
        except Exception as e:
            self.logger.error(f"새로운 청산 알림 전송 실패 {symbol}: {e}")
    
    def cleanup_sent_notifications(self):
        """중복 알림 기록 정리 (메모리 절약)"""
        try:
            # 24시간이 지난 기록들은 제거 (필요시)
            if len(self._sent_fill_notifications) > 1000:
                # 기록이 너무 많아지면 절반 정도 정리
                notifications_list = list(self._sent_fill_notifications)
                keep_count = 500
                self._sent_fill_notifications = set(notifications_list[-keep_count:])
                self.logger.debug(f"📝 중복 알림 기록 정리: {len(notifications_list)} → {keep_count}개")
        except Exception as e:
            self.logger.error(f"중복 알림 기록 정리 실패: {e}")
    
    def _register_existing_filled_orders(self):
        """이미 체결된 주문들에 대한 알림 기록 등록 (중복 방지)"""
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
                self._save_sent_notifications()  # 기록 저장
                self.logger.info(f"🔧 기존 체결 주문 {registered_count}개 알림 기록 등록 (중복 방지)")
            
        except Exception as e:
            self.logger.error(f"기존 체결 주문 등록 실패: {e}")

    def _load_sent_notifications(self):
        """재시작 시 이미 발송된 알림 기록 로드"""
        try:
            notifications_file = os.path.join(os.path.dirname(self.data_file), 'sent_notifications.json')
            if os.path.exists(notifications_file):
                with open(notifications_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._sent_fill_notifications = set(data.get('notifications', []))
                    self.logger.info(f"📥 알림 기록 로드: {len(self._sent_fill_notifications)}개")
            else:
                self.logger.debug("📥 알림 기록 파일 없음 - 새로 시작")
        except Exception as e:
            self.logger.warning(f"알림 기록 로드 실패: {e}")
            self._sent_fill_notifications = set()
    
    def _save_sent_notifications(self):
        """발송된 알림 기록 저장"""
        try:
            notifications_file = os.path.join(os.path.dirname(self.data_file), 'sent_notifications.json')
            
            # 최근 1000개만 유지 (메모리 관리)
            if len(self._sent_fill_notifications) > 1000:
                notifications_list = list(self._sent_fill_notifications)
                self._sent_fill_notifications = set(notifications_list[-500:])  # 최근 500개만 유지
                self.logger.debug(f"📝 알림 기록 자동 정리: 1000+ → 500개")
            
            data = {
                'notifications': list(self._sent_fill_notifications),
                'last_updated': get_korea_time().isoformat(),
                'count': len(self._sent_fill_notifications)
            }
            
            with open(notifications_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.error(f"알림 기록 저장 실패: {e}")

    def monitor_cyclic_opportunities(self, active_positions: Dict, current_prices: Dict) -> List[Dict]:
        """순환매 기회 모니터링"""
        try:
            opportunities = []
            
            for symbol in active_positions.keys():
                if symbol in self.positions:
                    position = self.positions[symbol]
                    if not position.is_active:
                        continue
                    
                    # 순환매 제한 확인
                    if position.cyclic_count >= position.max_cyclic_count:
                        continue
                    
                    # 현재가 조회
                    current_price = current_prices.get(symbol) or self.get_current_price(symbol)
                    if not current_price:
                        continue
                    
                    # 수익률 계산
                    profit_pct = (current_price - position.average_price) / position.average_price
                    
                    # 순환매 조건 체크: 3% 이상 수익일 때
                    if profit_pct >= 0.03:  # 3% 이상 수익
                        # 최대 수익률 업데이트
                        if profit_pct > position.max_profit_pct:
                            position.max_profit_pct = profit_pct
                            position.last_update = get_korea_time().isoformat()
                            self.save_data()
                        
                        # 순환매 기회 조건 (간소화)
                        # 1. 수익률이 5% 이상
                        # 2. 최대 수익률 대비 10% 이상 하락 시 일부 청산
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
                                'partial_ratio': 0.3,  # 30% 부분청산
                                'trigger_type': 'cyclic_profit_taking'
                            })
            
            return opportunities
            
        except Exception as e:
            self.logger.error(f"순환매 기회 모니터링 실패: {e}")
            return []

    def execute_cyclic_trading(self, opportunities: List[Dict]) -> Dict[str, Any]:
        """순환매 실행"""
        try:
            results = []
            executed_count = 0
            
            for opportunity in opportunities:
                try:
                    symbol = opportunity['symbol']
                    position = opportunity['position']
                    current_price = opportunity['current_price']
                    partial_ratio = opportunity['partial_ratio']
                    
                    # 부분청산 실행 (30%)
                    success = self._execute_partial_exit(
                        position, current_price, partial_ratio, 
                        f"순환매 {position.cyclic_count + 1}회차"
                    )
                    
                    if success:
                        executed_count += 1
                        
                        # 순환매 카운트 증가
                        position.cyclic_count += 1
                        position.last_cyclic_entry = get_korea_time().isoformat()
                        
                        # 순환매 상태 유지 (카운트와 무관하게 최초진입가 기준으로 청산 모드 결정)
                        position.cyclic_state = CyclicState.CYCLIC_ACTIVE.value
                        
                        # 순환매 3회 제한 로그 (참고용)
                        if position.cyclic_count >= position.max_cyclic_count:
                            self.logger.info(f"📊 순환매 {position.max_cyclic_count}회 달성: {symbol} - 이후 청산은 최초진입가 기준")
                        
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
                        
                        # 텔레그램 알림
                        if self.telegram_bot:
                            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                            profit_pct = opportunity['profit_pct'] * 100
                            message = (f"🔄 순환매 {position.cyclic_count}회차 실행\n"
                                     f"심볼: {clean_symbol}\n"
                                     f"청산율: {partial_ratio*100:.0f}%\n"
                                     f"수익률: {profit_pct:.1f}%\n"
                                     f"실현손익: ${realized_profit:+.4f}\n"
                                     f"진행: {position.cyclic_count}/{position.max_cyclic_count}회")
                            self.telegram_bot.send_message(message)
                        
                        self.logger.info(f"✅ 순환매 실행: {symbol} {position.cyclic_count}회차 - {partial_ratio*100:.0f}% 청산")
                    
                    else:
                        results.append({
                            'success': False,
                            'symbol': symbol,
                            'error': 'Partial exit failed'
                        })
                        
                except Exception as opp_error:
                    self.logger.error(f"순환매 실행 실패 {opportunity['symbol']}: {opp_error}")
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
            self.logger.error(f"순환매 실행 실패: {e}")
            return {
                'executed': 0,
                'total_opportunities': len(opportunities) if opportunities else 0,
                'results': [],
                'error': str(e)
            }

    def _convert_to_binance_futures_symbol(self, symbol: str) -> Optional[str]:
        """심볼을 Binance Futures 포맷으로 변환"""
        try:
            # 이미 올바른 포맷인지 확인
            if '/USDT:USDT' in symbol:
                return symbol
            
            # 심볼 정리 (slash, colon 제거)
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '').replace('/', '').strip()
            
            # 빈 문자열 체크
            if not clean_symbol:
                self.logger.error(f"Empty symbol after cleaning: {symbol}")
                return None
            
            # USDT로 끝나지 않으면 USDT 추가
            if not clean_symbol.endswith('USDT'):
                clean_symbol += 'USDT'
            
            # Binance Futures 포맷으로 변환
            binance_symbol = f"{clean_symbol[:-4]}/USDT:USDT"
            
            # 유효성 검증 (Exchange에 심볼이 존재하는지 확인)
            if self.exchange:
                try:
                    markets = self.exchange.load_markets()
                    if binance_symbol not in markets:
                        # 시장에 없는 심볼 - 로그에 기록하고 None 반환
                        self.logger.warning(f"심볼이 Binance Futures에 존재하지 않음: {symbol} → {binance_symbol}")
                        return None
                except Exception as market_error:
                    self.logger.debug(f"Market 확인 실패 (계속 진행): {market_error}")
                    # Market 로딩 실패해도 변환된 심볼 반환
            
            self.logger.debug(f"심볼 변환: {symbol} → {binance_symbol}")
            return binance_symbol
            
        except Exception as e:
            self.logger.error(f"심볼 변환 실패 {symbol}: {e}")
            return None

    def get_current_price(self, symbol: str) -> Optional[float]:
        """현재가 조회 (심볼 변환 포함)"""
        try:
            if self.exchange:
                # 🔧 심볼 변환 (이미 변환된 심볼일 수도 있으므로 안전하게 처리)
                if '/USDT:USDT' not in symbol:
                    converted_symbol = self._convert_to_binance_futures_symbol(symbol)
                    if not converted_symbol:
                        self.logger.error(f"심볼 변환 실패로 현재가 조회 불가: {symbol}")
                        return None
                    symbol = converted_symbol
                
                ticker = self.exchange.fetch_ticker(symbol)
                return float(ticker['last'])
            return None
        except Exception as e:
            self.logger.error(f"현재가 조회 실패 {symbol}: {e}")
            return None

    def _execute_partial_exit(self, position: DCAPosition, current_price: float, partial_ratio: float, reason: str) -> bool:
        """부분청산 실행"""
        try:
            # 청산할 수량 계산
            exit_quantity = position.total_quantity * partial_ratio
            
            # 시장가 매도 주문 실행
            order_result = self._execute_market_order(position.symbol, exit_quantity, "sell")
            
            if order_result['success']:
                # 포지션 수량 업데이트
                position.total_quantity -= exit_quantity
                position.last_update = get_korea_time().isoformat()
                self.save_data()
                
                self.logger.info(f"✅ 부분청산 완료: {position.symbol} - {partial_ratio*100:.0f}% ({reason})")
                return True
            else:
                self.logger.error(f"❌ 부분청산 실패: {position.symbol} - {order_result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            self.logger.error(f"부분청산 실행 실패 {position.symbol}: {e}")
            return False

    def sync_positions_with_exchange(self, total_balance: float = None) -> Dict[str, Any]:
        """주기적 포지션 동기화: 거래소 포지션과 DCA 기록 간 불일치 해결"""
        try:
            if not self.exchange:
                return {'synced': 0, 'error': 'Exchange not configured'}
            
            self.logger.info("🔄 포지션 동기화 시작...")
            
            # 거래소 실제 포지션 조회
            exchange_positions = self.exchange.fetch_positions()
            active_exchange_positions = {
                pos['symbol']: pos for pos in exchange_positions 
                if pos['size'] > 0 and pos['side'] == 'long'
            }
            
            # DCA 관리 포지션 조회
            active_dca_positions = {
                symbol: position for symbol, position in self.positions.items() 
                if position.is_active
            }
            
            sync_results = {
                'checked_positions': len(active_dca_positions),
                'missing_dca_orders': 0,
                'duplicate_orders_cleaned': 0,
                'orders_created': 0,
                'errors': []
            }
            
            # 각 DCA 포지션에 대해 주문 상태 확인
            for symbol, dca_position in active_dca_positions.items():
                try:
                    # 거래소 미체결 주문 조회
                    open_orders = self.exchange.fetch_open_orders(symbol)
                    dca_orders = [order for order in open_orders if order['side'] == 'buy']  # DCA는 매수 주문
                    
                    # DCA 단계별 주문 상태 분석
                    expected_orders = self._analyze_expected_dca_orders(dca_position)
                    actual_orders = {order['price']: order for order in dca_orders}
                    
                    # 누락된 DCA 주문 생성
                    for stage, order_info in expected_orders.items():
                        if order_info['should_exist'] and order_info['price'] not in actual_orders:
                            # 누락된 DCA 주문 생성
                            missing_result = self._create_missing_dca_order(
                                dca_position, stage, order_info, total_balance
                            )
                            if missing_result['success']:
                                sync_results['orders_created'] += 1
                                self.logger.info(f"✅ 누락 DCA 주문 생성: {symbol} {stage} @ ${order_info['price']:.4f}")
                            else:
                                sync_results['errors'].append(f"{symbol} {stage}: {missing_result['error']}")
                        
                    # 중복 주문 정리
                    duplicate_count = len(dca_orders) - len(expected_orders)
                    if duplicate_count > 0:
                        # 중복 주문 취소 로직 (가장 오래된 주문부터)
                        sorted_orders = sorted(dca_orders, key=lambda x: x['timestamp'])
                        for i in range(duplicate_count):
                            try:
                                self.exchange.cancel_order(sorted_orders[i]['id'], symbol)
                                sync_results['duplicate_orders_cleaned'] += 1
                                self.logger.info(f"🗑️ 중복 DCA 주문 취소: {symbol} {sorted_orders[i]['id']}")
                            except Exception as cancel_error:
                                sync_results['errors'].append(f"주문 취소 실패 {symbol}: {cancel_error}")
                    
                    sync_results['missing_dca_orders'] += len([
                        order for order in expected_orders.values() 
                        if order['should_exist'] and order['price'] not in actual_orders
                    ])
                    
                except Exception as pos_error:
                    self.logger.error(f"포지션 동기화 오류 {symbol}: {pos_error}")
                    sync_results['errors'].append(f"{symbol}: {str(pos_error)}")
            
            # 결과 요약
            self.logger.info(f"📊 동기화 완료: {sync_results['checked_positions']}개 포지션, "
                           f"{sync_results['orders_created']}개 주문 생성, "
                           f"{sync_results['duplicate_orders_cleaned']}개 중복 정리")
            
            if sync_results['errors']:
                self.logger.warning(f"⚠️ 동기화 오류 {len(sync_results['errors'])}건")
            
            return sync_results
            
        except Exception as e:
            self.logger.error(f"포지션 동기화 실패: {e}")
            return {'synced': 0, 'error': str(e)}
    
    def _analyze_expected_dca_orders(self, position: DCAPosition) -> Dict[str, Dict]:
        """DCA 포지션에서 예상되는 지정가 주문 분석"""
        try:
            expected = {}
            
            # 1차 DCA 주문 체크
            first_dca_price = position.initial_entry_price * (1 + self.config['first_dca_trigger'])
            first_dca_exists = any(
                entry.stage == 'first_dca' and entry.is_active and not entry.is_filled 
                for entry in position.entries
            )
            
            expected['first_dca'] = {
                'price': first_dca_price,
                'should_exist': position.current_stage == 'initial' and not first_dca_exists,
                'stage': 'first_dca'
            }
            
            # 2차 DCA 주문 체크
            second_dca_price = position.initial_entry_price * (1 + self.config['second_dca_trigger'])
            second_dca_exists = any(
                entry.stage == 'second_dca' and entry.is_active and not entry.is_filled 
                for entry in position.entries
            )
            
            expected['second_dca'] = {
                'price': second_dca_price,
                'should_exist': position.current_stage in ['initial', 'first_dca'] and not second_dca_exists,
                'stage': 'second_dca'
            }
            
            return expected
            
        except Exception as e:
            self.logger.error(f"예상 DCA 주문 분석 실패 {position.symbol}: {e}")
            return {}
    
    def _create_missing_dca_order(self, position: DCAPosition, stage: str, order_info: Dict, total_balance: float = None) -> Dict[str, Any]:
        """누락된 DCA 주문 생성"""
        try:
            if not total_balance:
                total_balance = 10000.0  # 기본값 사용
            
            price = order_info['price']
            
            # DCA 설정에 따른 주문 생성
            if stage == 'first_dca':
                amount = total_balance * self.config['first_dca_weight']
                leverage = self.config['first_dca_leverage']
            elif stage == 'second_dca':
                amount = total_balance * self.config['second_dca_weight']
                leverage = self.config['second_dca_leverage']
            else:
                return {'success': False, 'error': f'Unknown DCA stage: {stage}'}
            
            quantity = (amount * leverage) / price
            
            # 지정가 주문 실행
            order_result = self._execute_limit_order(position.symbol, quantity, "buy", price)
            
            if order_result['success']:
                # DCA 엔트리 추가
                dca_entry = DCAEntry(
                    stage=stage,
                    entry_price=price,
                    quantity=quantity,
                    notional=amount * leverage,
                    leverage=leverage,
                    timestamp=get_korea_time().isoformat(),
                    is_active=True,
                    order_type="limit",
                    order_id=order_result['order_id'],
                    is_filled=False
                )
                position.entries.append(dca_entry)
                position.last_update = get_korea_time().isoformat()
                self.save_data()
                
                return {'success': True, 'order_id': order_result['order_id']}
            else:
                return {'success': False, 'error': order_result.get('error', 'Order execution failed')}
                
        except Exception as e:
            self.logger.error(f"누락 DCA 주문 생성 실패 {position.symbol} {stage}: {e}")
            return {'success': False, 'error': str(e)}

# 모듈 테스트용 함수들
def test_dca_system():
    """DCA 시스템 테스트"""
    print("=== DCA 시스템 테스트 ===")
    
    # Mock exchange (테스트용)
    class MockExchange:
        def __init__(self):
            self.apiKey = "test_key"
        
        def fetch_positions(self):
            return []
        
        def fetch_ticker(self, symbol):
            return {'last': 50000.0}  # 테스트 가격
        
        def create_market_order(self, symbol, side, amount):
            return {
                'id': 'test_order_123',
                'filled': amount,
                'average': 50000.0
            }
    
    # DCA 시스템 초기화
    mock_exchange = MockExchange()
    dca_manager = ImprovedDCAPositionManager(exchange=mock_exchange)
    
    # 테스트 포지션 추가
    success = dca_manager.add_position(
        symbol="BTCUSDT",
        entry_price=50000.0,
        quantity=0.001,
        notional=500.0,
        leverage=10.0
    )
    
    print(f"포지션 추가 성공: {success}")
    
    # 포지션 요약
    summary = dca_manager.get_position_summary()
    print(f"포지션 요약: {summary}")
    
    # 시스템 상태
    health = dca_manager.get_system_health()
    print(f"시스템 상태: {health['status']}")
    
    print("=== 테스트 완료 ===")

if __name__ == "__main__":
    test_dca_system()