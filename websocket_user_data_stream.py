# -*- coding: utf-8 -*-
"""
Binance WebSocket User Data Stream
계좌 포지션 실시간 업데이트 (REST API 완전 대체)

기능:
- 실시간 포지션 변경 추적 (진입/청산)
- 실시간 잔고 업데이트
- 주문 체결/취소 알림
- Rate Limit 0% (WebSocket만 사용)

바이낸스 User Data Stream:
- Listen Key 기반 인증 (60분마다 갱신)
- 포지션/잔고/주문 실시간 이벤트
- REST API 대비 99% Rate Limit 절감
"""

import time
import logging
import threading
import json
from typing import Dict, Optional, Callable, List
from datetime import datetime
import requests


class BinanceUserDataStream:
    """바이낸스 WebSocket User Data Stream 매니저"""

    def __init__(self, exchange, logger=None):
        """
        Args:
            exchange: ccxt binance exchange 객체
            logger: 로거 인스턴스
        """
        self.exchange = exchange
        self.logger = logger or logging.getLogger(__name__)

        # API 키 설정
        self.api_key = exchange.apiKey
        self.api_secret = exchange.secret
        self.base_url = 'https://fapi.binance.com'  # Futures API

        # Listen Key 관리
        self.listen_key: Optional[str] = None
        self.listen_key_created_at = 0
        self.listen_key_refresh_interval = 30 * 60  # 30분마다 갱신 (60분 만료)

        # WebSocket 연결
        self.ws = None
        self.ws_thread: Optional[threading.Thread] = None
        self.running = False

        # 실시간 데이터 저장
        self.positions: Dict[str, Dict] = {}  # symbol -> position data
        self.balance: Dict = {}
        self.orders: Dict[str, Dict] = {}  # orderId -> order data

        # 콜백 함수
        self.position_callback: Optional[Callable] = None
        self.balance_callback: Optional[Callable] = None
        self.order_callback: Optional[Callable] = None

        # 통계
        self.stats = {
            'position_updates': 0,
            'balance_updates': 0,
            'order_updates': 0,
            'reconnections': 0
        }

        self.logger.info("🔐 WebSocket User Data Stream 초기화 완료")

    def _create_listen_key(self) -> Optional[str]:
        """Listen Key 생성 (60분 유효)"""
        try:
            url = f"{self.base_url}/fapi/v1/listenKey"
            headers = {'X-MBX-APIKEY': self.api_key}

            response = requests.post(url, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            listen_key = data.get('listenKey')

            self.logger.info(f"✅ Listen Key 생성 성공: {listen_key[:10]}...")
            return listen_key

        except Exception as e:
            self.logger.error(f"❌ Listen Key 생성 실패: {e}")
            return None

    def _refresh_listen_key(self):
        """Listen Key 갱신 (30분마다 자동 실행)"""
        try:
            if not self.listen_key:
                return

            url = f"{self.base_url}/fapi/v1/listenKey"
            headers = {'X-MBX-APIKEY': self.api_key}

            response = requests.put(url, headers=headers, timeout=10)
            response.raise_for_status()

            self.logger.info("✅ Listen Key 갱신 성공")
            self.listen_key_created_at = time.time()

        except Exception as e:
            self.logger.error(f"❌ Listen Key 갱신 실패: {e}")

    def _handle_account_update(self, data: Dict):
        """ACCOUNT_UPDATE 이벤트 처리 (포지션/잔고 변경)"""
        try:
            event_time = data.get('E', 0)
            update_data = data.get('a', {})

            # 1️⃣ 포지션 업데이트
            positions = update_data.get('P', [])
            for pos in positions:
                symbol = pos.get('s')  # BTCUSDT
                position_amount = float(pos.get('pa', 0))  # Position Amount
                entry_price = float(pos.get('ep', 0))  # Entry Price
                unrealized_pnl = float(pos.get('up', 0))  # Unrealized PnL

                # 포지션 데이터 업데이트
                self.positions[symbol] = {
                    'symbol': symbol,
                    'contracts': abs(position_amount),
                    'side': 'long' if position_amount > 0 else 'short' if position_amount < 0 else 'none',
                    'entryPrice': entry_price,
                    'markPrice': float(pos.get('mp', 0)),  # Mark Price
                    'unrealizedPnl': unrealized_pnl,
                    'leverage': int(pos.get('l', 1)),  # Leverage
                    'timestamp': event_time
                }

                self.stats['position_updates'] += 1
                self.logger.info(f"📊 [포지션] {symbol}: {position_amount:.4f} @ {entry_price:.2f} (PnL: {unrealized_pnl:.2f})")

                # 콜백 실행
                if self.position_callback:
                    self.position_callback(symbol, self.positions[symbol])

            # 2️⃣ 잔고 업데이트
            balances = update_data.get('B', [])
            for bal in balances:
                asset = bal.get('a')  # USDT
                wallet_balance = float(bal.get('wb', 0))  # Wallet Balance
                available_balance = float(bal.get('cw', 0))  # Available Balance

                self.balance[asset] = {
                    'asset': asset,
                    'wallet_balance': wallet_balance,
                    'available_balance': available_balance,
                    'timestamp': event_time
                }

                self.stats['balance_updates'] += 1
                self.logger.info(f"💰 [잔고] {asset}: {wallet_balance:.2f} (사용가능: {available_balance:.2f})")

                # 콜백 실행
                if self.balance_callback:
                    self.balance_callback(asset, self.balance[asset])

        except Exception as e:
            self.logger.error(f"❌ ACCOUNT_UPDATE 처리 실패: {e}")

    def _handle_order_update(self, data: Dict):
        """ORDER_TRADE_UPDATE 이벤트 처리 (주문 체결/취소)"""
        try:
            event_time = data.get('E', 0)
            order_data = data.get('o', {})

            symbol = order_data.get('s')  # BTCUSDT
            order_id = order_data.get('i')  # Order ID
            status = order_data.get('X')  # Order Status (NEW, FILLED, CANCELED, etc.)
            side = order_data.get('S')  # BUY/SELL
            order_type = order_data.get('o')  # MARKET/LIMIT
            price = float(order_data.get('p', 0))
            quantity = float(order_data.get('q', 0))
            filled_quantity = float(order_data.get('z', 0))
            avg_price = float(order_data.get('ap', 0))  # Average Price

            # 주문 데이터 저장
            self.orders[str(order_id)] = {
                'orderId': order_id,
                'symbol': symbol,
                'status': status,
                'side': side,
                'type': order_type,
                'price': price,
                'quantity': quantity,
                'filled_quantity': filled_quantity,
                'avg_price': avg_price,
                'timestamp': event_time
            }

            self.stats['order_updates'] += 1
            self.logger.info(f"📝 [주문] {symbol} {side} {status}: {filled_quantity}/{quantity} @ {avg_price:.2f}")

            # 콜백 실행
            if self.order_callback:
                self.order_callback(order_id, self.orders[str(order_id)])

        except Exception as e:
            self.logger.error(f"❌ ORDER_TRADE_UPDATE 처리 실패: {e}")

    def _on_message(self, ws, message):
        """WebSocket 메시지 수신 처리"""
        try:
            data = json.loads(message)
            event_type = data.get('e')

            if event_type == 'ACCOUNT_UPDATE':
                self._handle_account_update(data)

            elif event_type == 'ORDER_TRADE_UPDATE':
                self._handle_order_update(data)

        except Exception as e:
            self.logger.error(f"❌ WebSocket 메시지 처리 실패: {e}")

    def _on_error(self, ws, error):
        """WebSocket 에러 처리"""
        self.logger.error(f"❌ WebSocket 에러: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket 연결 종료"""
        self.logger.warning(f"⚠️ WebSocket 연결 종료: {close_status_code} - {close_msg}")

    def _on_open(self, ws):
        """WebSocket 연결 성공"""
        self.logger.info("✅ WebSocket User Data Stream 연결 성공")

    def start(self):
        """WebSocket User Data Stream 시작"""
        try:
            # 1. Listen Key 생성
            self.listen_key = self._create_listen_key()
            if not self.listen_key:
                self.logger.error("❌ Listen Key 생성 실패 - User Data Stream 시작 불가")
                return False

            self.listen_key_created_at = time.time()

            # 2. WebSocket 연결
            import websocket
            ws_url = f"wss://fstream.binance.com/ws/{self.listen_key}"

            self.ws = websocket.WebSocketApp(
                ws_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )

            self.running = True

            # 3. WebSocket 백그라운드 실행
            def run_ws():
                while self.running:
                    try:
                        self.ws.run_forever()
                    except Exception as e:
                        self.logger.error(f"WebSocket 실행 실패: {e}")
                        time.sleep(5)

            self.ws_thread = threading.Thread(target=run_ws, daemon=True)
            self.ws_thread.start()

            # 4. Listen Key 갱신 스레드
            def refresh_listen_key_loop():
                while self.running:
                    time.sleep(self.listen_key_refresh_interval)
                    self._refresh_listen_key()

            refresh_thread = threading.Thread(target=refresh_listen_key_loop, daemon=True)
            refresh_thread.start()

            self.logger.info("✅ User Data Stream 시작 완료")
            return True

        except Exception as e:
            self.logger.error(f"❌ User Data Stream 시작 실패: {e}")
            return False

    def stop(self):
        """WebSocket User Data Stream 종료"""
        try:
            self.running = False

            if self.ws:
                self.ws.close()

            # Listen Key 삭제
            if self.listen_key:
                url = f"{self.base_url}/fapi/v1/listenKey"
                headers = {'X-MBX-APIKEY': self.api_key}
                requests.delete(url, headers=headers, timeout=10)

            self.logger.info("✅ User Data Stream 종료 완료")

        except Exception as e:
            self.logger.error(f"❌ User Data Stream 종료 실패: {e}")

    def get_position(self, symbol: str) -> Optional[Dict]:
        """실시간 포지션 조회 (REST API 대체)"""
        return self.positions.get(symbol)

    def get_all_positions(self) -> List[Dict]:
        """모든 포지션 조회 (REST API 대체)"""
        return [pos for pos in self.positions.values() if pos.get('contracts', 0) > 0]

    def get_balance(self, asset: str = 'USDT') -> Optional[Dict]:
        """실시간 잔고 조회 (REST API 대체)"""
        return self.balance.get(asset)

    def get_stats(self) -> Dict:
        """통계 조회"""
        return {
            **self.stats,
            'total_positions': len(self.positions),
            'active_positions': len([p for p in self.positions.values() if p.get('contracts', 0) > 0]),
            'listen_key_age': int(time.time() - self.listen_key_created_at) if self.listen_key_created_at else 0
        }


# 사용 예시
if __name__ == "__main__":
    import ccxt
    from binance_config import API_KEY, API_SECRET

    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Exchange 초기화
    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': API_SECRET,
        'options': {'defaultType': 'future'}
    })

    # User Data Stream 시작
    user_stream = BinanceUserDataStream(exchange)

    # 콜백 함수 등록
    def on_position_update(symbol, position):
        print(f"[포지션 변경] {symbol}: {position}")

    def on_balance_update(asset, balance):
        print(f"[잔고 변경] {asset}: {balance}")

    user_stream.position_callback = on_position_update
    user_stream.balance_callback = on_balance_update

    # 시작
    if user_stream.start():
        print("✅ User Data Stream 실행 중...")
        print("종료하려면 Ctrl+C를 누르세요")

        try:
            while True:
                time.sleep(10)
                stats = user_stream.get_stats()
                print(f"\n📊 통계: {stats}")

        except KeyboardInterrupt:
            print("\n종료 중...")
            user_stream.stop()
