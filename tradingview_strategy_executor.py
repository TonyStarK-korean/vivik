# -*- coding: utf-8 -*-
"""
TradingView Webhook Strategy Executor
웹훅 신호를 받아 실제 매매 Execute
"""

import sys
import logging
from datetime import datetime
import threading
import time

# Legacy 전략 임포트
from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
import tradingview_webhook_server as webhook_server

# 로깅 Settings
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class TradingViewStrategyExecutor:
    """
    TradingView 웹훅 전략 Execute기
    웹훅 신호를 받아 Legacy 전략의 매매 로직 Execute
    """

    def __init__(self, strategy: OneMinuteSurgeEntryStrategy):
        """
        Initialize

        Args:
            strategy: Legacy 전략 인스턴스
        """
        self.strategy = strategy
        self.positions = {}  # Current Position 추적
        self.lock = threading.Lock()
        logger.info("✅ TradingView 전략 Execute기 Initialization complete")

    def execute_entry(self, symbol: str, strategy_info: str = None) -> bool:
        """
        Entry 신호 Execute

        Args:
            symbol: Symbol (BTC/USDT:USDT)
            strategy_info: 전략 Info

        Returns:
            Success 여부
        """
        with self.lock:
            try:
                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                logger.info(f"🎯 [Entry] {clean_symbol} - {strategy_info}")

                # 이미 Position이 있는지 Confirm
                if symbol in self.positions:
                    logger.warning(f"⚠️ {clean_symbol} Position already held - Entry Skip")
                    return False

                # Maximum positions 체크
                max_positions = webhook_server.webhook_config.get('trading', {}).get('max_positions', 5)
                if len(self.positions) >= max_positions:
                    logger.warning(f"⚠️ Maximum positions({max_positions}) Reached - Entry Skip")
                    return False

                # Entry 금액 계산 (DCA 고려)
                entry_amount = self.strategy.entry_amount
                if self.strategy.dca_manager:
                    entry_amount = self.strategy.dca_manager.initial_investment

                # Current price 조times
                try:
                    ticker = self.strategy.exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
                except Exception as e:
                    logger.error(f"❌ {clean_symbol} 가격 조times Failed: {e}")
                    return False

                # 매매 Execute (Legacy 전략의 execute_entry Usage)
                # DCA 시스템이 Active화되어 있으면 DCA로 Entry
                if self.strategy.dca_manager:
                    logger.info(f"🔄 {clean_symbol} DCA System으로 Entry Attempt")

                    # DCA Entry
                    result = self.strategy.dca_manager.enter_position(
                        symbol=symbol.replace('/USDT:USDT', '').replace('/', '') + 'USDT',
                        entry_price=current_price,
                        initial_amount=entry_amount
                    )

                    if result and 'success' in result and result['success']:
                        # Position 추적
                        self.positions[symbol] = {
                            'entry_price': result['entry_price'],
                            'quantity': result['quantity'],
                            'entry_time': datetime.now(),
                            'strategy': strategy_info or 'Strategy C: 3minute candles 시세 초입 포착',
                            'dca_enabled': True
                        }

                        # 텔레그램 Notification
                        self.strategy.send_unified_entry_alert(
                            symbol=symbol,
                            entry_price=result['entry_price'],
                            quantity=result['quantity'],
                            entry_amount=entry_amount,
                            is_dca=True,
                            strategy_info=strategy_info or 'Strategy C: 3minute candles 시세 초입 포착'
                        )

                        logger.info(f"✅ {clean_symbol} DCA Entry Success: ${result['entry_price']:.6f}")
                        return True
                    else:
                        logger.error(f"❌ {clean_symbol} DCA Entry Failed")
                        return False

                else:
                    # Legacy 방식 Entry
                    logger.info(f"🔄 {clean_symbol} Legacy 방식으로 Entry Attempt")

                    # Quantity 계산
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

                        # Position 추적
                        self.positions[symbol] = {
                            'entry_price': actual_price,
                            'quantity': actual_quantity,
                            'entry_time': datetime.now(),
                            'strategy': strategy_info or 'Strategy C: 3minute candles 시세 초입 포착',
                            'dca_enabled': False
                        }

                        # 텔레그램 Notification
                        self.strategy.send_unified_entry_alert(
                            symbol=symbol,
                            entry_price=actual_price,
                            quantity=actual_quantity,
                            entry_amount=entry_amount,
                            is_dca=False,
                            strategy_info=strategy_info or 'Strategy C: 3minute candles 시세 초입 포착'
                        )

                        logger.info(f"✅ {clean_symbol} Entry Success: ${actual_price:.6f}")
                        return True
                    else:
                        logger.error(f"❌ {clean_symbol} Order failed")
                        return False

            except Exception as e:
                logger.error(f"❌ {clean_symbol} Entry Execute Error: {e}", exc_info=True)
                return False

    def close_position(self, symbol: str, reason: str = "수동 Exit") -> bool:
        """
        Position Exit

        Args:
            symbol: Symbol
            reason: Exit Reason

        Returns:
            Success 여부
        """
        with self.lock:
            try:
                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                logger.info(f"🔻 [Exit] {clean_symbol} - {reason}")

                # Position Confirm
                if symbol not in self.positions:
                    logger.warning(f"⚠️ {clean_symbol} No position - Exit Skip")
                    return False

                position = self.positions[symbol]

                # DCA 시스템 Usage 중이면 DCA로 Exit
                if position.get('dca_enabled') and self.strategy.dca_manager:
                    logger.info(f"🔄 {clean_symbol} DCA System으로 Exit")

                    result = self.strategy.dca_manager.close_position(
                        symbol=symbol.replace('/USDT:USDT', '').replace('/', '') + 'USDT',
                        reason=reason
                    )

                    if result:
                        del self.positions[symbol]
                        logger.info(f"✅ {clean_symbol} DCA Exit Success")
                        return True
                    else:
                        logger.error(f"❌ {clean_symbol} DCA Exit Failed")
                        return False

                else:
                    # Legacy 방식 Exit
                    logger.info(f"🔄 {clean_symbol} Legacy 방식으로 Exit")

                    # 시장가 Exit
                    order = self.strategy.exchange.create_market_order(
                        symbol=symbol,
                        side='sell',
                        amount=position['quantity']
                    )

                    if order:
                        exit_price = order.get('average') or order.get('price')

                        # P&L 계산
                        pnl = (exit_price - position['entry_price']) * position['quantity']
                        pnl_pct = ((exit_price - position['entry_price']) / position['entry_price']) * 100

                        # 텔레그램 Notification
                        if self.strategy.telegram_bot:
                            message = f"🔻 [Exit] {clean_symbol}" + chr(10)
                            message += f"━━━━━━━━━━━━━━━━━━━━━━" + chr(10)
                            message += f"💰 Entry가: ${position['entry_price']:.6f}" + chr(10)
                            message += f"💰 Exit가: ${exit_price:.6f}" + chr(10)
                            message += f"📊 P&L: ${pnl:.2f} ({pnl_pct:+.2f}%)" + chr(10)
                            message += f"📝 Reason: {reason}" + chr(10)
                            message += f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}" + chr(10)

                            self.strategy.telegram_bot.send_message(message)

                        del self.positions[symbol]
                        logger.info(f"✅ {clean_symbol} Exit Success: P&L {pnl_pct:+.2f}%")
                        return True
                    else:
                        logger.error(f"❌ {clean_symbol} Exit Order failed")
                        return False

            except Exception as e:
                logger.error(f"❌ {clean_symbol} Exit Execute Error: {e}", exc_info=True)
                return False

    def get_positions(self):
        """Current Position 조times"""
        return self.positions.copy()

def main():
    """메인 함수"""
    print("=" * 60)
    print("🚀 TradingView Webhook Strategy System")
    print("=" * 60)

    # 1. Legacy 전략 Initialize
    print("\n📊 1Stage: Legacy 전략 System Initialize 중...")
    try:
        strategy = OneMinuteSurgeEntryStrategy()
        print("✅ 전략 System Initialization complete")
    except Exception as e:
        print(f"❌ 전략 System Initialization failed: {e}")
        sys.exit(1)

    # 2. 웹훅 Execute기 Initialize
    print("\n📡 2Stage: 웹훅 Execute기 Initialize 중...")
    executor = TradingViewStrategyExecutor(strategy)
    webhook_server.initialize_strategy_executor(executor)
    print("✅ 웹훅 Execute기 Initialization complete")

    # 3. 웹훅 서버 Starting
    print("\n🌐 3Stage: 웹훅 서버 Starting 중...")
    try:
        webhook_server.start_server()
    except KeyboardInterrupt:
        print("\n\n⏹️ 서버 Terminate 중...")
        print("👋 안녕히 가세요!")
    except Exception as e:
        print(f"❌ 서버 Starting Failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
