# -*- coding: utf-8 -*-
"""
🔗 전략 파일과 대시보드 연동 패치
메인 전략 파일에 거래 로깅 기능 통합

주요 기능:
1. 기존 전략 파일에 로깅 기능 추가
2. 진입/청산/DCA 신호 자동 로그
3. 실시간 대시보드 데이터 연동
4. 백워드 호환성 유지

사용법:
- 이 패치를 메인 전략 파일에서 import하여 사용
- 기존 코드 수정 최소화
"""

from typing import Optional, Dict, Any
import logging

# 거래 로거 초기화
try:
    from trading_signal_logger import get_trading_logger, TradingSignal
    TRADING_LOGGER_AVAILABLE = True
    trading_logger = get_trading_logger()
    print("✅ 거래 로깅 시스템 연동 완료")
except ImportError:
    TRADING_LOGGER_AVAILABLE = False
    trading_logger = None
    print("⚠️ 거래 로깅 시스템 없음 - 로깅 기능 비활성화")

def log_entry_signal(symbol: str, strategy: str, price: float, quantity: float, 
                    leverage: float = 10.0, metadata: Optional[Dict] = None):
    """진입 신호 로그"""
    if not TRADING_LOGGER_AVAILABLE:
        return
    
    try:
        # 메타데이터 보강
        enhanced_metadata = {
            'leverage': leverage,
            'position_value': quantity * price,
            'source': 'alpha_z_strategy',
            **(metadata or {})
        }
        
        trading_logger.log_entry_signal(
            symbol=symbol,
            strategy=strategy,
            price=price,
            quantity=quantity,
            metadata=enhanced_metadata
        )
        
        print(f"📊 진입 신호 로그: {symbol} {strategy}전략 @ ${price:,.4f}")
        
    except Exception as e:
        logging.error(f"진입 신호 로그 실패: {e}")

def log_exit_signal(symbol: str, price: float, entry_price: float, quantity: float,
                   exit_reason: str = "청산", leverage: float = 10.0, metadata: Optional[Dict] = None):
    """청산 신호 로그"""
    if not TRADING_LOGGER_AVAILABLE:
        return
    
    try:
        # PnL 계산
        position_value = quantity * entry_price * leverage
        pnl_raw = (price - entry_price) * quantity * leverage
        pnl_percent = ((price - entry_price) / entry_price) * 100 * leverage
        
        # 메타데이터 보강
        enhanced_metadata = {
            'leverage': leverage,
            'position_value': position_value,
            'exit_reason': exit_reason,
            'source': 'alpha_z_strategy',
            **(metadata or {})
        }
        
        # 상태 메시지 생성
        if pnl_percent > 0:
            status = f"익절 +{pnl_percent:.1f}%"
        else:
            status = f"손절 {pnl_percent:.1f}%"
        
        trading_logger.log_exit_signal(
            symbol=symbol,
            price=price,
            pnl=pnl_raw,
            pnl_percent=pnl_percent,
            status=status,
            metadata=enhanced_metadata
        )
        
        print(f"📊 청산 신호 로그: {symbol} @ ${price:,.4f} ({status})")
        
    except Exception as e:
        logging.error(f"청산 신호 로그 실패: {e}")

def log_dca_signal(symbol: str, price: float, quantity: float, stage: str = "DCA",
                  leverage: float = 10.0, metadata: Optional[Dict] = None):
    """DCA 추가매수 신호 로그"""
    if not TRADING_LOGGER_AVAILABLE:
        return
    
    try:
        # 메타데이터 보강
        enhanced_metadata = {
            'leverage': leverage,
            'dca_stage': stage,
            'position_value': quantity * price,
            'source': 'alpha_z_strategy',
            **(metadata or {})
        }
        
        trading_logger.log_dca_signal(
            symbol=symbol,
            price=price,
            quantity=quantity,
            metadata=enhanced_metadata
        )
        
        print(f"📊 DCA 신호 로그: {symbol} {stage} @ ${price:,.4f}")
        
    except Exception as e:
        logging.error(f"DCA 신호 로그 실패: {e}")

def log_custom_signal(symbol: str, strategy: str, action: str, price: float,
                     quantity: float = 0.0, status: str = "실행", 
                     metadata: Optional[Dict] = None):
    """커스텀 신호 로그"""
    if not TRADING_LOGGER_AVAILABLE:
        return
    
    try:
        from trading_signal_logger import TradingSignal
        from datetime import datetime, timezone, timedelta
        
        signal = TradingSignal(
            timestamp=datetime.now(timezone(timedelta(hours=9))).isoformat(),
            symbol=symbol,
            strategy=strategy,
            action=action,
            price=price,
            quantity=quantity,
            status=status,
            metadata=metadata or {}
        )
        
        trading_logger.log_signal(signal)
        print(f"📊 커스텀 신호 로그: {symbol} {action} @ ${price:,.4f}")
        
    except Exception as e:
        logging.error(f"커스텀 신호 로그 실패: {e}")

def get_trading_statistics():
    """거래 통계 조회"""
    if not TRADING_LOGGER_AVAILABLE:
        return {}
    
    try:
        return trading_logger.get_trade_statistics()
    except Exception as e:
        logging.error(f"통계 조회 실패: {e}")
        return {}

def get_strategy_performance():
    """전략별 성과 조회"""
    if not TRADING_LOGGER_AVAILABLE:
        return {}
    
    try:
        return trading_logger.calculate_strategy_stats()
    except Exception as e:
        logging.error(f"전략 성과 조회 실패: {e}")
        return {}

# 백워드 호환성을 위한 래퍼 함수들
def write_signal_log(signal_data: Dict):
    """기존 신호 로그 함수와의 호환성"""
    if not signal_data:
        return
    
    symbol = signal_data.get('symbol', 'UNKNOWN')
    strategy = signal_data.get('strategy', 'UNKNOWN')
    action = signal_data.get('action', 'UNKNOWN')
    price = signal_data.get('price', 0.0)
    quantity = signal_data.get('quantity', 0.0)
    status = signal_data.get('status', '실행')
    
    log_custom_signal(
        symbol=symbol,
        strategy=strategy,
        action=action,
        price=price,
        quantity=quantity,
        status=status,
        metadata=signal_data
    )

def log_trade_complete(symbol: str, strategy: str, entry_price: float, exit_price: float,
                      quantity: float, leverage: float = 10.0):
    """완료된 거래 로그 (진입→청산 자동 처리)"""
    # 진입 로그
    log_entry_signal(
        symbol=symbol,
        strategy=strategy,
        price=entry_price,
        quantity=quantity,
        leverage=leverage,
        metadata={'trade_type': 'complete_trade'}
    )
    
    # 청산 로그
    log_exit_signal(
        symbol=symbol,
        price=exit_price,
        entry_price=entry_price,
        quantity=quantity,
        leverage=leverage,
        metadata={'trade_type': 'complete_trade'}
    )

# 사용 예시 및 테스트
if __name__ == "__main__":
    print("🧪 전략 연동 패치 테스트")
    
    # 진입 테스트
    log_entry_signal("BTCUSDT", "A", 91000.0, 0.1)
    
    # DCA 테스트  
    log_dca_signal("BTCUSDT", 89500.0, 0.05, "1차_DCA")
    
    # 청산 테스트
    log_exit_signal("BTCUSDT", 93500.0, 90250.0, 0.15, "익절")
    
    # 통계 조회 테스트
    stats = get_trading_statistics()
    print(f"거래 통계: {stats}")
    
    perf = get_strategy_performance()
    print(f"전략 성과: {perf}")
    
    print("✅ 테스트 완료")

"""
메인 전략 파일 적용 예시:

# alpha_z_triple_strategy.py 파일 상단에 추가
from strategy_integration_patch import (
    log_entry_signal, log_exit_signal, log_dca_signal,
    get_trading_statistics, get_strategy_performance
)

# 진입 시점에 추가
def execute_real_trade(self, signal_data):
    # ... 기존 거래 실행 코드 ...
    
    if order and order.get('filled'):
        # 진입 신호 로그 추가
        log_entry_signal(
            symbol=clean_symbol,
            strategy=self._get_strategy_type(signal_data),
            price=filled_price,
            quantity=filled_qty,
            leverage=leverage,
            metadata={
                'order_id': order['id'],
                'signal_data': signal_data
            }
        )

# DCA 실행 시점에 추가  
def add_dca_position(self, symbol, dca_price, dca_quantity):
    # ... 기존 DCA 코드 ...
    
    if success:
        # DCA 신호 로그 추가
        log_dca_signal(
            symbol=symbol,
            price=dca_price,
            quantity=dca_quantity,
            stage=dca_stage,
            metadata={'dca_info': dca_info}
        )

# 청산 시점에 추가
def close_position(self, symbol, exit_price, entry_price, quantity):
    # ... 기존 청산 코드 ...
    
    if success:
        # 청산 신호 로그 추가
        log_exit_signal(
            symbol=symbol,
            price=exit_price,
            entry_price=entry_price,
            quantity=quantity,
            exit_reason=exit_reason,
            metadata={'exit_info': exit_info}
        )
"""