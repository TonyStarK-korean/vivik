# -*- coding: utf-8 -*-
"""
TradingView Webhook Strategy Executor
웹훅 신호를 받아 실제 매매 실행
"""

import sys
import logging
from datetime import datetime
import threading
import time

# 기존 전략 임포트
from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
import tradingview_webhook_server as webhook_server

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class TradingViewStrategyExecutor:
    """
    TradingView 웹훅 전략 실행기
    웹훅 신호를 받아 기존 전략의 매매 로직 실행
    """

    def __init__(self, strategy: OneMinuteSurgeEntryStrategy):
        """
        초기화

        Args:
            strategy: 기존 전략 인스턴스
        """
        self.strategy = strategy
        self.positions = {}  # 현재 포지션 추적
        self.lock = threading.Lock()
        logger.info("✅ TradingView 전략 실행기 초기화 완료")

    def execute_entry(self, symbol: str, strategy_info: str = None) -> bool:
        """
        진입 신호 실행

        Args:
            symbol: 심볼 (BTC/USDT:USDT)
            strategy_info: 전략 정보

        Returns:
            성공 여부
        """
        with self.lock:
            try:
                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                logger.info(f"🎯 [진입] {clean_symbol} - {strategy_info}")

                # 이미 포지션이 있는지 확인
                if symbol in self.positions:
                    logger.warning(f"⚠️ {clean_symbol} 이미 포지션 보유 중 - 진입 스킵")
                    return False

                # 최대 포지션 수 체크
                max_positions = webhook_server.webhook_config.get('trading', {}).get('max_positions', 5)
                if len(self.positions) >= max_positions:
                    logger.warning(f"⚠️ 최대 포지션 수({max_positions}) 도달 - 진입 스킵")
                    return False

                # 진입 금액 계산 (DCA 고려)
                entry_amount = self.strategy.entry_amount
                if self.strategy.dca_manager:
                    entry_amount = self.strategy.dca_manager.initial_investment

                # 현재가 조회
                try:
                    ticker = self.strategy.exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
                except Exception as e:
                    logger.error(f"❌ {clean_symbol} 가격 조회 실패: {e}")
                    return False

                # 매매 실행 (기존 전략의 execute_entry 사용)
                # DCA 시스템이 활성화되어 있으면 DCA로 진입
                if self.strategy.dca_manager:
                    logger.info(f"🔄 {clean_symbol} DCA 시스템으로 진입 시도")

                    # DCA 진입
                    result = self.strategy.dca_manager.enter_position(
                        symbol=symbol.replace('/USDT:USDT', '').replace('/', '') + 'USDT',
                        entry_price=current_price,
                        initial_amount=entry_amount
                    )

                    if result and 'success' in result and result['success']:
                        # 포지션 추적
                        self.positions[symbol] = {
                            'entry_price': result['entry_price'],
                            'quantity': result['quantity'],
                            'entry_time': datetime.now(),
                            'strategy': strategy_info or '전략C: 3분봉 시세 초입 포착',
                            'dca_enabled': True
                        }

                        # 텔레그램 알림
                        self.strategy.send_unified_entry_alert(
                            symbol=symbol,
                            entry_price=result['entry_price'],
                            quantity=result['quantity'],
                            entry_amount=entry_amount,
                            is_dca=True,
                            strategy_info=strategy_info or '전략C: 3분봉 시세 초입 포착'
                        )

                        logger.info(f"✅ {clean_symbol} DCA 진입 성공: ${result['entry_price']:.6f}")
                        return True
                    else:
                        logger.error(f"❌ {clean_symbol} DCA 진입 실패")
                        return False

                else:
                    # 기존 방식 진입
                    logger.info(f"🔄 {clean_symbol} 기존 방식으로 진입 시도")

                    # 수량 계산
                    quantity = (entry_amount * self.strategy.leverage) / current_price

                    # 시장가 주문
                    order = self.strategy.exchange.create_market_order(
                        symbol=symbol,
                        side='buy',
                        amount=quantity
                    )

                    if order:
                        actual_price = order.get('average') or order.get('price') or current_price
                        actual_quantity = order.get('filled') or quantity

                        # 포지션 추적
                        self.positions[symbol] = {
                            'entry_price': actual_price,
                            'quantity': actual_quantity,
                            'entry_time': datetime.now(),
                            'strategy': strategy_info or '전략C: 3분봉 시세 초입 포착',
                            'dca_enabled': False
                        }

                        # 텔레그램 알림
                        self.strategy.send_unified_entry_alert(
                            symbol=symbol,
                            entry_price=actual_price,
                            quantity=actual_quantity,
                            entry_amount=entry_amount,
                            is_dca=False,
                            strategy_info=strategy_info or '전략C: 3분봉 시세 초입 포착'
                        )

                        logger.info(f"✅ {clean_symbol} 진입 성공: ${actual_price:.6f}")
                        return True
                    else:
                        logger.error(f"❌ {clean_symbol} 주문 실패")
                        return False

            except Exception as e:
                logger.error(f"❌ {clean_symbol} 진입 실행 오류: {e}", exc_info=True)
                return False

    def close_position(self, symbol: str, reason: str = "수동 청산") -> bool:
        """
        포지션 청산

        Args:
            symbol: 심볼
            reason: 청산 사유

        Returns:
            성공 여부
        """
        with self.lock:
            try:
                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                logger.info(f"🔻 [청산] {clean_symbol} - {reason}")

                # 포지션 확인
                if symbol not in self.positions:
                    logger.warning(f"⚠️ {clean_symbol} 포지션 없음 - 청산 스킵")
                    return False

                position = self.positions[symbol]

                # DCA 시스템 사용 중이면 DCA로 청산
                if position.get('dca_enabled') and self.strategy.dca_manager:
                    logger.info(f"🔄 {clean_symbol} DCA 시스템으로 청산")

                    result = self.strategy.dca_manager.close_position(
                        symbol=symbol.replace('/USDT:USDT', '').replace('/', '') + 'USDT',
                        reason=reason
                    )

                    if result:
                        del self.positions[symbol]
                        logger.info(f"✅ {clean_symbol} DCA 청산 성공")
                        return True
                    else:
                        logger.error(f"❌ {clean_symbol} DCA 청산 실패")
                        return False

                else:
                    # 기존 방식 청산
                    logger.info(f"🔄 {clean_symbol} 기존 방식으로 청산")

                    # 시장가 청산
                    order = self.strategy.exchange.create_market_order(
                        symbol=symbol,
                        side='sell',
                        amount=position['quantity']
                    )

                    if order:
                        exit_price = order.get('average') or order.get('price')

                        # 손익 계산
                        pnl = (exit_price - position['entry_price']) * position['quantity']
                        pnl_pct = ((exit_price - position['entry_price']) / position['entry_price']) * 100

                        # 텔레그램 알림
                        if self.strategy.telegram_bot:
                            message = f"🔻 [청산] {clean_symbol}" + chr(10)
                            message += f"━━━━━━━━━━━━━━━━━━━━━━" + chr(10)
                            message += f"💰 진입가: ${position['entry_price']:.6f}" + chr(10)
                            message += f"💰 청산가: ${exit_price:.6f}" + chr(10)
                            message += f"📊 손익: ${pnl:.2f} ({pnl_pct:+.2f}%)" + chr(10)
                            message += f"📝 사유: {reason}" + chr(10)
                            message += f"⏰ 시간: {datetime.now().strftime('%H:%M:%S')}" + chr(10)

                            self.strategy.telegram_bot.send_message(message)

                        del self.positions[symbol]
                        logger.info(f"✅ {clean_symbol} 청산 성공: 손익 {pnl_pct:+.2f}%")
                        return True
                    else:
                        logger.error(f"❌ {clean_symbol} 청산 주문 실패")
                        return False

            except Exception as e:
                logger.error(f"❌ {clean_symbol} 청산 실행 오류: {e}", exc_info=True)
                return False

    def get_positions(self):
        """현재 포지션 조회"""
        return self.positions.copy()

def main():
    """메인 함수"""
    print("=" * 60)
    print("🚀 TradingView Webhook Strategy System")
    print("=" * 60)

    # 1. 기존 전략 초기화
    print("\n📊 1단계: 기존 전략 시스템 초기화 중...")
    try:
        strategy = OneMinuteSurgeEntryStrategy()
        print("✅ 전략 시스템 초기화 완료")
    except Exception as e:
        print(f"❌ 전략 시스템 초기화 실패: {e}")
        sys.exit(1)

    # 2. 웹훅 실행기 초기화
    print("\n📡 2단계: 웹훅 실행기 초기화 중...")
    executor = TradingViewStrategyExecutor(strategy)
    webhook_server.initialize_strategy_executor(executor)
    print("✅ 웹훅 실행기 초기화 완료")

    # 3. 웹훅 서버 시작
    print("\n🌐 3단계: 웹훅 서버 시작 중...")
    try:
        webhook_server.start_server()
    except KeyboardInterrupt:
        print("\n\n⏹️ 서버 종료 중...")
        print("👋 안녕히 가세요!")
    except Exception as e:
        print(f"❌ 서버 시작 실패: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
