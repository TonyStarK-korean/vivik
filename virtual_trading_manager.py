# -*- coding: utf-8 -*-
"""
가상매매 관리 시스템
실제 거래 로직과 동일하지만 가상으로 실행
"""

import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import os

def get_korea_time():
    """한국 시간 반환"""
    return datetime.now(timezone(timedelta(hours=9)))

class VirtualPosition:
    """가상 포지션 클래스"""
    
    def __init__(self, symbol: str, entry_price: float, quantity: float, leverage: float, stage: str = "initial"):
        self.symbol = symbol
        self.entry_price = entry_price
        self.quantity = quantity
        self.leverage = leverage
        self.stage = stage  # "initial", "first_dca", "second_dca"
        self.entry_time = get_korea_time()
        
        # DCA 정보
        self.dca_orders = []
        self.total_quantity = quantity
        self.avg_price = entry_price
        
        # 수익률 추적
        self.max_profit = 0.0
        self.current_profit = 0.0
        
        # 청산 관련
        self.is_closed = False
        self.close_reason = None
        
    def add_dca(self, price: float, quantity: float, stage: str):
        """DCA 추가"""
        self.dca_orders.append({
            'price': price,
            'quantity': quantity,
            'stage': stage,
            'time': get_korea_time()
        })
        
        # 평균가 재계산
        total_cost = (self.total_quantity * self.avg_price) + (quantity * price)
        self.total_quantity += quantity
        self.avg_price = total_cost / self.total_quantity
        self.stage = stage
        
    def update_profit(self, current_price: float):
        """수익률 업데이트"""
        self.current_profit = ((current_price - self.avg_price) / self.avg_price) * 100
        if self.current_profit > self.max_profit:
            self.max_profit = self.current_profit
            
    def get_notional_value(self):
        """명목 가치 계산"""
        return self.total_quantity * self.avg_price
        
    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            'symbol': self.symbol,
            'entry_price': self.entry_price,
            'avg_price': self.avg_price,
            'quantity': self.quantity,
            'total_quantity': self.total_quantity,
            'leverage': self.leverage,
            'stage': self.stage,
            'entry_time': self.entry_time.isoformat(),
            'dca_orders': self.dca_orders,
            'max_profit': self.max_profit,
            'current_profit': self.current_profit,
            'is_closed': self.is_closed,
            'close_reason': self.close_reason
        }

class VirtualTradingManager:
    """가상매매 관리자"""
    
    def __init__(self, initial_balance: float = 1000.0):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.positions: Dict[str, VirtualPosition] = {}
        self.closed_positions: List[VirtualPosition] = []
        self.trade_history = []
        
        # DCA 설정 (15분봉 초필살기 전략용)
        self.dca_config = {
            'initial_weight': 0.02,          # 2%
            'initial_leverage': 20.0,        # 20배
            'first_dca_trigger': -0.03,      # -3%
            'first_dca_weight': 0.02,        # 2%
            'second_dca_trigger': -0.06,     # -6%
            'second_dca_weight': 0.02,       # 2%
            'stop_loss': -0.10               # -10%
        }
        
        # 파일 경로
        self.data_file = 'virtual_positions.json'
        self.history_file = 'virtual_trade_history.json'
        
        # 기존 데이터 로드
        self.load_data()
        
    def save_data(self):
        """데이터 저장"""
        try:
            # 포지션 데이터 저장
            positions_data = {
                'current_balance': self.current_balance,
                'initial_balance': self.initial_balance,
                'positions': {symbol: pos.to_dict() for symbol, pos in self.positions.items()},
                'closed_positions': [pos.to_dict() for pos in self.closed_positions],
                'last_update': get_korea_time().isoformat()
            }
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(positions_data, f, ensure_ascii=False, indent=2)
                
            # 거래 기록 저장
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.trade_history, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"데이터 저장 실패: {e}")
            
    def load_data(self):
        """데이터 로드"""
        try:
            # 포지션 데이터 로드
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                self.current_balance = data.get('current_balance', self.initial_balance)
                self.initial_balance = data.get('initial_balance', 1000.0)
                
                # 포지션 복원
                for symbol, pos_data in data.get('positions', {}).items():
                    pos = VirtualPosition(
                        symbol=pos_data['symbol'],
                        entry_price=pos_data['entry_price'],
                        quantity=pos_data['quantity'],
                        leverage=pos_data['leverage'],
                        stage=pos_data['stage']
                    )
                    pos.avg_price = pos_data['avg_price']
                    pos.total_quantity = pos_data['total_quantity']
                    pos.dca_orders = pos_data.get('dca_orders', [])
                    pos.max_profit = pos_data.get('max_profit', 0.0)
                    pos.current_profit = pos_data.get('current_profit', 0.0)
                    self.positions[symbol] = pos
                    
            # 거래 기록 로드
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.trade_history = json.load(f)
                    
        except Exception as e:
            print(f"데이터 로드 실패: {e}")
            
    def open_position(self, symbol: str, price: float) -> Dict:
        """포지션 진입"""
        try:
            if symbol in self.positions:
                return {'success': False, 'error': '이미 포지션이 존재합니다'}
            
            # 포지션 크기 계산
            position_value = self.current_balance * self.dca_config['initial_weight']
            quantity = position_value / price
            leverage = self.dca_config['initial_leverage']
            
            # 잔고 확인
            required_margin = position_value  # 마진 = 포지션 가치 / 레버리지는 아니고 전체 투입금
            if self.current_balance < required_margin:
                return {'success': False, 'error': '잔고 부족'}
            
            # 포지션 생성
            position = VirtualPosition(symbol, price, quantity, leverage)
            self.positions[symbol] = position
            
            # 잔고 차감 (마진)
            self.current_balance -= required_margin
            
            # 거래 기록
            trade_record = {
                'type': 'open',
                'symbol': symbol,
                'price': price,
                'quantity': quantity,
                'leverage': leverage,
                'value': position_value,
                'time': get_korea_time().isoformat(),
                'stage': 'initial'
            }
            self.trade_history.append(trade_record)
            
            # 데이터 저장
            self.save_data()
            
            return {
                'success': True,
                'position': position,
                'used_balance': required_margin,
                'remaining_balance': self.current_balance
            }
            
        except Exception as e:
            return {'success': False, 'error': f'포지션 진입 실패: {e}'}
    
    def add_dca(self, symbol: str, price: float, stage: str) -> Dict:
        """DCA 추가"""
        try:
            if symbol not in self.positions:
                return {'success': False, 'error': '포지션이 존재하지 않습니다'}
            
            position = self.positions[symbol]
            
            # DCA 크기 계산
            if stage == 'first_dca':
                dca_weight = self.dca_config['first_dca_weight']
            elif stage == 'second_dca':
                dca_weight = self.dca_config['second_dca_weight']
            else:
                return {'success': False, 'error': '잘못된 DCA 단계'}
            
            dca_value = self.initial_balance * dca_weight  # 초기 잔고 기준
            dca_quantity = dca_value / price
            
            # 잔고 확인
            if self.current_balance < dca_value:
                return {'success': False, 'error': 'DCA 잔고 부족'}
            
            # DCA 추가
            position.add_dca(price, dca_quantity, stage)
            
            # 잔고 차감
            self.current_balance -= dca_value
            
            # 거래 기록
            trade_record = {
                'type': 'dca',
                'symbol': symbol,
                'price': price,
                'quantity': dca_quantity,
                'value': dca_value,
                'stage': stage,
                'new_avg_price': position.avg_price,
                'time': get_korea_time().isoformat()
            }
            self.trade_history.append(trade_record)
            
            # 데이터 저장
            self.save_data()
            
            return {
                'success': True,
                'position': position,
                'used_balance': dca_value,
                'remaining_balance': self.current_balance,
                'new_avg_price': position.avg_price
            }
            
        except Exception as e:
            return {'success': False, 'error': f'DCA 추가 실패: {e}'}
    
    def close_position(self, symbol: str, price: float, reason: str = "manual", partial_ratio: float = 1.0) -> Dict:
        """포지션 청산"""
        try:
            if symbol not in self.positions:
                return {'success': False, 'error': '포지션이 존재하지 않습니다'}
            
            position = self.positions[symbol]
            
            # 청산할 수량 계산
            close_quantity = position.total_quantity * partial_ratio
            close_value = close_quantity * price
            
            # 수익 계산
            cost_basis = close_quantity * position.avg_price
            pnl = close_value - cost_basis
            pnl_percent = (pnl / cost_basis) * 100
            
            # 레버리지 적용된 실제 수익
            leveraged_pnl = pnl * position.leverage
            
            # 잔고 업데이트
            returned_margin = cost_basis * partial_ratio  # 원래 투입된 마진
            self.current_balance += returned_margin + leveraged_pnl
            
            # 거래 기록
            trade_record = {
                'type': 'close',
                'symbol': symbol,
                'entry_price': position.avg_price,
                'close_price': price,
                'quantity': close_quantity,
                'pnl': leveraged_pnl,
                'pnl_percent': pnl_percent,
                'reason': reason,
                'partial_ratio': partial_ratio,
                'time': get_korea_time().isoformat(),
                'stage': position.stage
            }
            self.trade_history.append(trade_record)
            
            # 완전 청산인 경우
            if partial_ratio >= 1.0:
                position.is_closed = True
                position.close_reason = reason
                self.closed_positions.append(position)
                del self.positions[symbol]
            else:
                # 부분 청산인 경우 수량 조정
                position.total_quantity -= close_quantity
            
            # 데이터 저장
            self.save_data()
            
            return {
                'success': True,
                'pnl': leveraged_pnl,
                'pnl_percent': pnl_percent,
                'new_balance': self.current_balance,
                'close_value': close_value,
                'partial_ratio': partial_ratio
            }
            
        except Exception as e:
            return {'success': False, 'error': f'포지션 청산 실패: {e}'}
    
    def update_positions(self, price_data: Dict[str, float]):
        """포지션 업데이트 및 트리거 체크"""
        triggered_actions = []
        
        for symbol, position in list(self.positions.items()):
            if symbol in price_data:
                current_price = price_data[symbol]
                position.update_profit(current_price)
                
                # DCA 트리거 체크
                profit_from_entry = ((current_price - position.entry_price) / position.entry_price) * 100
                
                # 1차 DCA 트리거
                if (position.stage == "initial" and 
                    profit_from_entry <= self.dca_config['first_dca_trigger'] * 100):
                    triggered_actions.append({
                        'action': 'dca',
                        'symbol': symbol,
                        'price': current_price,
                        'stage': 'first_dca',
                        'trigger_percent': profit_from_entry
                    })
                
                # 2차 DCA 트리거
                elif (position.stage == "first_dca" and 
                      profit_from_entry <= self.dca_config['second_dca_trigger'] * 100):
                    triggered_actions.append({
                        'action': 'dca',
                        'symbol': symbol,
                        'price': current_price,
                        'stage': 'second_dca',
                        'trigger_percent': profit_from_entry
                    })
                
                # 손절 트리거
                if profit_from_entry <= self.dca_config['stop_loss'] * 100:
                    triggered_actions.append({
                        'action': 'stop_loss',
                        'symbol': symbol,
                        'price': current_price,
                        'profit_percent': profit_from_entry
                    })
        
        return triggered_actions
    
    def get_portfolio_summary(self) -> Dict:
        """포트폴리오 요약"""
        total_value = self.current_balance
        total_pnl = 0
        open_positions = len(self.positions)
        
        for position in self.positions.values():
            position_value = position.get_notional_value()
            total_value += position_value
            total_pnl += position_value * (position.current_profit / 100)
        
        total_trades = len(self.trade_history)
        win_trades = len([t for t in self.trade_history if t.get('type') == 'close' and t.get('pnl', 0) > 0])
        win_rate = (win_trades / max(1, len([t for t in self.trade_history if t.get('type') == 'close']))) * 100
        
        return {
            'initial_balance': self.initial_balance,
            'current_balance': self.current_balance,
            'total_value': total_value,
            'total_pnl': total_value - self.initial_balance,
            'total_pnl_percent': ((total_value - self.initial_balance) / self.initial_balance) * 100,
            'open_positions': open_positions,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'positions': {symbol: {
                'symbol': pos.symbol,
                'stage': pos.stage,
                'avg_price': pos.avg_price,
                'quantity': pos.total_quantity,
                'current_profit': pos.current_profit,
                'max_profit': pos.max_profit
            } for symbol, pos in self.positions.items()}
        }
    
    def reset_portfolio(self):
        """포트폴리오 리셋"""
        self.current_balance = self.initial_balance
        self.positions.clear()
        self.closed_positions.clear()
        self.trade_history.clear()
        
        # 파일 삭제
        if os.path.exists(self.data_file):
            os.remove(self.data_file)
        if os.path.exists(self.history_file):
            os.remove(self.history_file)
            
        print(f"포트폴리오가 초기값으로 리셋됨: ${self.initial_balance}")