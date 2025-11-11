# -*- coding: utf-8 -*-
"""
📊 거래 신호 및 이력 로깅 시스템
대시보드 연동을 위한 실제 데이터 로깅 구현

주요 기능:
1. 거래 신호 로그 (trading_signals.log)
2. 거래 이력 JSON (trade_history.json)
3. 전략별 성과 추적
4. 실시간 통계 계산
5. 대시보드 API와 완전 호환

데이터 형식:
- 신호 로그: JSONL 형식 (한 줄에 하나의 JSON)
- 거래 이력: JSON 형식 (전체 거래 목록)
- 전략 통계: 실시간 계산
"""

import json
import time
import os
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import logging

def get_korea_time():
    """한국 표준시(KST) 현재 시간 반환"""
    return datetime.now(timezone(timedelta(hours=9)))

@dataclass
class TradingSignal:
    """거래 신호 데이터"""
    timestamp: str
    symbol: str
    strategy: str  # A, B, C
    action: str    # BUY, SELL, DCA_BUY, PARTIAL_SELL
    price: float
    quantity: float
    status: str    # 진입완료, 익절, 손절, DCA실행 등
    pnl: float = 0.0
    pnl_percent: float = 0.0
    entry_price: float = 0.0
    metadata: dict = None

@dataclass 
class TradeHistory:
    """완료된 거래 이력"""
    trade_id: str
    symbol: str
    strategy: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_percent: float
    duration_minutes: int
    trade_type: str  # NORMAL, DCA, PARTIAL
    metadata: dict = None

class TradingSignalLogger:
    """거래 신호 및 이력 로깅 시스템"""
    
    def __init__(self, 
                 signals_file: str = "trading_signals.log",
                 history_file: str = "trade_history.json"):
        self.signals_file = signals_file
        self.history_file = history_file
        
        # 스레드 안전성을 위한 락
        self.file_lock = threading.Lock()
        
        # 로거 설정
        self.logger = self._setup_logger()
        
        # 활성 포지션 추적 (PnL 계산용)
        self.active_positions = {}
        
        # 전략별 통계 캐시
        self.strategy_stats_cache = {}
        self.last_stats_update = 0
        self.stats_cache_ttl = 30  # 30초 캐시
        
        # 거래 이력 로드
        self.trade_history = self._load_trade_history()
        
        self.logger.info(f"거래 신호 로거 초기화 완료")
        self.logger.info(f"  신호 파일: {self.signals_file}")
        self.logger.info(f"  이력 파일: {self.history_file}")
    
    def _setup_logger(self):
        """로거 설정"""
        logger = logging.getLogger('TradingSignalLogger')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def _load_trade_history(self) -> List[Dict]:
        """거래 이력 파일 로드"""
        if not os.path.exists(self.history_file):
            return []
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            self.logger.error(f"거래 이력 로드 실패: {e}")
            return []
    
    def _save_trade_history(self):
        """거래 이력 파일 저장"""
        with self.file_lock:
            try:
                with open(self.history_file, 'w', encoding='utf-8') as f:
                    json.dump(self.trade_history, f, ensure_ascii=False, indent=2)
                self.logger.debug("거래 이력 저장 완료")
            except Exception as e:
                self.logger.error(f"거래 이력 저장 실패: {e}")
    
    def log_signal(self, signal: TradingSignal):
        """거래 신호 로그 기록"""
        with self.file_lock:
            try:
                # JSONL 형식으로 추가 (한 줄에 하나의 JSON)
                signal_dict = asdict(signal)
                
                with open(self.signals_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(signal_dict, ensure_ascii=False) + '\n')
                
                # 활성 포지션 업데이트
                self._update_active_position(signal)
                
                self.logger.info(f"신호 기록: {signal.symbol} {signal.strategy} {signal.action} @ {signal.price}")
                
            except Exception as e:
                self.logger.error(f"신호 로그 실패: {e}")
    
    def _update_active_position(self, signal: TradingSignal):
        """활성 포지션 상태 업데이트"""
        symbol = signal.symbol
        
        if signal.action == 'BUY':
            # 새 포지션 생성
            self.active_positions[symbol] = {
                'entry_time': signal.timestamp,
                'entry_price': signal.price,
                'strategy': signal.strategy,
                'quantity': signal.quantity,
                'dca_entries': [],
                'partial_exits': []
            }
            
        elif signal.action == 'DCA_BUY':
            # DCA 추가매수
            if symbol in self.active_positions:
                pos = self.active_positions[symbol]
                pos['dca_entries'].append({
                    'time': signal.timestamp,
                    'price': signal.price,
                    'quantity': signal.quantity
                })
                
                # 평균가 재계산
                total_quantity = pos['quantity']
                total_value = pos['quantity'] * pos['entry_price']
                
                for dca in pos['dca_entries']:
                    total_quantity += dca['quantity']
                    total_value += dca['quantity'] * dca['price']
                
                pos['quantity'] = total_quantity
                pos['entry_price'] = total_value / total_quantity
        
        elif signal.action in ['SELL', 'PARTIAL_SELL']:
            if symbol in self.active_positions:
                pos = self.active_positions[symbol]
                
                if signal.action == 'PARTIAL_SELL':
                    # 부분 청산
                    pos['partial_exits'].append({
                        'time': signal.timestamp,
                        'price': signal.price,
                        'quantity': signal.quantity,
                        'pnl': signal.pnl,
                        'pnl_percent': signal.pnl_percent
                    })
                    pos['quantity'] -= signal.quantity
                    
                else:
                    # 전량 청산 - 거래 이력에 추가
                    trade = self._create_trade_history(symbol, signal)
                    if trade:
                        self.trade_history.append(asdict(trade))
                        self._save_trade_history()
                    
                    # 활성 포지션에서 제거
                    del self.active_positions[symbol]
    
    def _create_trade_history(self, symbol: str, exit_signal: TradingSignal) -> Optional[TradeHistory]:
        """거래 이력 생성"""
        if symbol not in self.active_positions:
            return None
        
        pos = self.active_positions[symbol]
        
        # 거래 기간 계산
        entry_time = datetime.fromisoformat(pos['entry_time'])
        exit_time = datetime.fromisoformat(exit_signal.timestamp)
        duration_minutes = int((exit_time - entry_time).total_seconds() / 60)
        
        # 거래 타입 결정
        trade_type = "NORMAL"
        if pos['dca_entries']:
            trade_type = "DCA"
        elif pos['partial_exits']:
            trade_type = "PARTIAL"
        
        # 고유 거래 ID 생성
        trade_id = f"{symbol}_{entry_time.strftime('%Y%m%d_%H%M%S')}"
        
        return TradeHistory(
            trade_id=trade_id,
            symbol=symbol,
            strategy=pos['strategy'],
            entry_time=pos['entry_time'],
            exit_time=exit_signal.timestamp,
            entry_price=pos['entry_price'],
            exit_price=exit_signal.price,
            quantity=pos['quantity'],
            pnl=exit_signal.pnl,
            pnl_percent=exit_signal.pnl_percent,
            duration_minutes=duration_minutes,
            trade_type=trade_type,
            metadata={
                'dca_count': len(pos['dca_entries']),
                'partial_exits': len(pos['partial_exits']),
                'status': exit_signal.status
            }
        )
    
    def calculate_strategy_stats(self, force_refresh: bool = False) -> Dict[str, Any]:
        """전략별 통계 계산 (캐시 적용)"""
        current_time = time.time()
        
        # 캐시 확인
        if not force_refresh and (current_time - self.last_stats_update) < self.stats_cache_ttl:
            return self.strategy_stats_cache
        
        stats = {
            'strategy_a': {'win_count': 0, 'loss_count': 0, 'total_return': 0.0, 'win_rate': 0.0, 'total_trades': 0},
            'strategy_b': {'win_count': 0, 'loss_count': 0, 'total_return': 0.0, 'win_rate': 0.0, 'total_trades': 0},
            'strategy_c': {'win_count': 0, 'loss_count': 0, 'total_return': 0.0, 'win_rate': 0.0, 'total_trades': 0}
        }
        
        # 거래 이력 분석
        for trade in self.trade_history:
            strategy_key = f"strategy_{trade['strategy'].lower()}"
            
            if strategy_key in stats:
                stats[strategy_key]['total_trades'] += 1
                
                if trade['pnl'] > 0:
                    stats[strategy_key]['win_count'] += 1
                else:
                    stats[strategy_key]['loss_count'] += 1
                
                stats[strategy_key]['total_return'] += trade['pnl_percent']
        
        # 승률 계산
        for strategy_key in stats:
            total = stats[strategy_key]['win_count'] + stats[strategy_key]['loss_count']
            if total > 0:
                stats[strategy_key]['win_rate'] = round((stats[strategy_key]['win_count'] / total) * 100, 1)
                stats[strategy_key]['total_return'] = round(stats[strategy_key]['total_return'], 1)
        
        # 캐시 업데이트
        self.strategy_stats_cache = stats
        self.last_stats_update = current_time
        
        return stats
    
    def get_recent_signals(self, limit: int = 50) -> List[Dict]:
        """최근 신호 로그 읽기"""
        if not os.path.exists(self.signals_file):
            return []
        
        signals = []
        try:
            with open(self.signals_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
                # 최근 limit개만 가져오기
                for line in lines[-limit:]:
                    try:
                        signal = json.loads(line.strip())
                        signals.append(signal)
                    except json.JSONDecodeError:
                        continue
                        
        except Exception as e:
            self.logger.error(f"신호 로그 읽기 실패: {e}")
        
        # 시간 순 정렬 (최신순)
        signals.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return signals
    
    def get_trade_statistics(self) -> Dict[str, Any]:
        """전체 거래 통계"""
        total_trades = len(self.trade_history)
        if total_trades == 0:
            return {
                'total_trades': 0,
                'win_count': 0,
                'loss_count': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_pnl_percent': 0,
                'profit_factor': 0,
                'avg_duration_minutes': 0
            }
        
        wins = [t for t in self.trade_history if t['pnl'] > 0]
        losses = [t for t in self.trade_history if t['pnl'] <= 0]
        
        total_profit = sum(t['pnl'] for t in wins) if wins else 0
        total_loss = abs(sum(t['pnl'] for t in losses)) if losses else 0
        profit_factor = round(total_profit / total_loss, 2) if total_loss > 0 else 0
        
        return {
            'total_trades': total_trades,
            'win_count': len(wins),
            'loss_count': len(losses),
            'win_rate': round((len(wins) / total_trades) * 100, 1),
            'total_pnl': round(sum(t['pnl'] for t in self.trade_history), 2),
            'avg_pnl_percent': round(sum(t['pnl_percent'] for t in self.trade_history) / total_trades, 2),
            'profit_factor': profit_factor,
            'avg_duration_minutes': round(sum(t['duration_minutes'] for t in self.trade_history) / total_trades, 1)
        }
    
    # 편의 메서드들
    def log_entry_signal(self, symbol: str, strategy: str, price: float, quantity: float, metadata: dict = None):
        """진입 신호 로그"""
        signal = TradingSignal(
            timestamp=get_korea_time().isoformat(),
            symbol=symbol,
            strategy=strategy,
            action='BUY',
            price=price,
            quantity=quantity,
            status='진입완료',
            metadata=metadata
        )
        self.log_signal(signal)
    
    def log_exit_signal(self, symbol: str, price: float, pnl: float, pnl_percent: float, 
                       status: str = '청산완료', metadata: dict = None):
        """청산 신호 로그"""
        if symbol in self.active_positions:
            pos = self.active_positions[symbol]
            
            signal = TradingSignal(
                timestamp=get_korea_time().isoformat(),
                symbol=symbol,
                strategy=pos['strategy'],
                action='SELL',
                price=price,
                quantity=pos['quantity'],
                status=status,
                pnl=pnl,
                pnl_percent=pnl_percent,
                entry_price=pos['entry_price'],
                metadata=metadata
            )
            self.log_signal(signal)
    
    def log_dca_signal(self, symbol: str, price: float, quantity: float, metadata: dict = None):
        """DCA 추가매수 신호 로그"""
        if symbol in self.active_positions:
            pos = self.active_positions[symbol]
            
            signal = TradingSignal(
                timestamp=get_korea_time().isoformat(),
                symbol=symbol,
                strategy=pos['strategy'],
                action='DCA_BUY',
                price=price,
                quantity=quantity,
                status='DCA실행',
                metadata=metadata
            )
            self.log_signal(signal)
    
    def clear_old_logs(self, days: int = 30):
        """오래된 로그 정리"""
        cutoff_time = get_korea_time() - timedelta(days=days)
        
        # 신호 로그 정리
        if os.path.exists(self.signals_file):
            try:
                recent_signals = []
                with open(self.signals_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            signal = json.loads(line.strip())
                            signal_time = datetime.fromisoformat(signal['timestamp'])
                            if signal_time > cutoff_time:
                                recent_signals.append(line)
                        except:
                            continue
                
                # 정리된 로그 다시 쓰기
                with open(self.signals_file, 'w', encoding='utf-8') as f:
                    f.writelines(recent_signals)
                    
                self.logger.info(f"신호 로그 정리 완료: {days}일 이전 데이터 삭제")
                
            except Exception as e:
                self.logger.error(f"로그 정리 실패: {e}")


# 글로벌 인스턴스 (싱글톤)
_logger_instance = None

def get_trading_logger() -> TradingSignalLogger:
    """글로벌 거래 로거 인스턴스 반환"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = TradingSignalLogger()
    return _logger_instance

# 사용 예시
if __name__ == "__main__":
    # 거래 로거 초기화
    logger = get_trading_logger()
    
    # 진입 신호 예시
    logger.log_entry_signal(
        symbol="BTCUSDT",
        strategy="A",
        price=91000.0,
        quantity=0.1,
        metadata={"source": "manual_test"}
    )
    
    # DCA 신호 예시
    time.sleep(1)
    logger.log_dca_signal(
        symbol="BTCUSDT",
        price=89500.0,
        quantity=0.05,
        metadata={"dca_stage": "first"}
    )
    
    # 청산 신호 예시
    time.sleep(1)
    logger.log_exit_signal(
        symbol="BTCUSDT",
        price=93000.0,
        pnl=450.0,
        pnl_percent=4.8,
        status="익절 +4.8%",
        metadata={"exit_reason": "profit_target"}
    )
    
    # 통계 확인
    stats = logger.calculate_strategy_stats()
    print("전략별 통계:", json.dumps(stats, indent=2))
    
    trade_stats = logger.get_trade_statistics()
    print("거래 통계:", json.dumps(trade_stats, indent=2))
    
    recent_signals = logger.get_recent_signals(10)
    print(f"최근 신호 {len(recent_signals)}개:", json.dumps(recent_signals, indent=2))