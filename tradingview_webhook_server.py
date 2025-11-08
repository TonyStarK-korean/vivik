# -*- coding: utf-8 -*-
"""
TradingView Webhook Server
Strategy C+D 시그널을 TradingView에서 받아 자동 매매 Execute
"""

from flask import Flask, request, jsonify
import json
import logging
from datetime import datetime
import threading
import hmac
import hashlib
from typing import Dict, Optional
import os

# 로깅 Settings
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('tradingview_webhook.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 전역 변수
strategy_executor = None
webhook_config = {}

def load_config():
    """웹훅 Settings Load"""
    global webhook_config
    config_path = 'webhook_config.json'

    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            webhook_config = json.load(f)
            logger.info(f"✅ Settings Load Complete: {config_path}")
    else:
        # 기본 Settings Create
        webhook_config = {
            "security": {
                "enabled": True,
                "secret_key": "YOUR_SECRET_KEY_HERE_CHANGE_THIS"
            },
            "trading": {
                "enabled": True,
                "test_mode": False,
                "max_positions": 5
            },
            "telegram": {
                "enabled": True,
                "send_webhook_alerts": True
            },
            "server": {
                "host": "0.0.0.0",
                "port": 5000,
                "debug": False
            }
        }

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(webhook_config, f, indent=4, ensure_ascii=False)

        logger.warning(f"⚠️ Default config file created: {config_path}")
        logger.warning(f"⚠️ SECRET_KEY must be changed!")

def verify_signature(payload: str, signature: str) -> bool:
    """웹훅 서명 Verification (보안)"""
    if not webhook_config.get('security', {}).get('enabled', False):
        return True

    secret_key = webhook_config.get('security', {}).get('secret_key', '')

    if secret_key == "YOUR_SECRET_KEY_HERE_CHANGE_THIS":
        logger.warning("⚠️ SECRET_KEY is default value. Security risk!")
        return True  # count발 Stage에서는 허용

    # HMAC-SHA256 서명 Verification
    expected_signature = hmac.new(
        secret_key.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)

def parse_tradingview_alert(data: Dict) -> Optional[Dict]:
    """
    TradingView Notification 데이터 파싱

    Expected JSON 형식:
    {
        "symbol": "BTCUSDT",
        "action": "buy",
        "strategy": "strategy_c",
        "price": 50000.0,
        "timestamp": "2025-01-04T12:00:00Z"
    }
    """
    try:
        required_fields = ['symbol', 'action']

        # 필수 필드 Confirm
        for field in required_fields:
            if field not in data:
                logger.error(f"❌ 필수 필드 누락: {field}")
                return None

        # Symbol 형식 변환 (BTCUSDT → BTC/USDT:USDT)
        raw_symbol = data['symbol'].upper()
        if raw_symbol.endswith('USDT'):
            base = raw_symbol[:-4]
            formatted_symbol = f"{base}/USDT:USDT"
        else:
            formatted_symbol = raw_symbol

        # 액션 정규화
        action = data['action'].lower()
        if action not in ['buy', 'sell', 'close']:
            logger.error(f"❌ Unknown action: {action}")
            return None

        # 전략 Info
        strategy = data.get('strategy', 'strategy_c')
        strategy_name = {
            'strategy_c': 'Strategy C: 3minute candles 시세 초입 포착',
            'strategy_d': 'Strategy D: 5minute candles 초입 초강력 타점',
            'strategy_cd': 'Strategy C+D: 3minute candles+5minute candles 복합 Entry'
        }.get(strategy, 'Strategy C: 3minute candles 시세 초입 포착')

        parsed_data = {
            'symbol': formatted_symbol,
            'action': action,
            'strategy': strategy_name,
            'price': data.get('price'),
            'timestamp': data.get('timestamp', datetime.now().isoformat()),
            'raw_data': data
        }

        logger.info(f"✅ Notification 파싱 Complete: {formatted_symbol} {action.upper()} ({strategy})")
        return parsed_data

    except Exception as e:
        logger.error(f"❌ Notification 파싱 Failed: {e}")
        return None

def execute_trade(signal: Dict) -> Dict:
    """매매 Execute"""
    try:
        if not webhook_config.get('trading', {}).get('enabled', True):
            logger.warning("⚠️ 매매 비Active화됨 - Simulation mode")
            return {
                'success': True,
                'message': 'Simulation mode (Trade not executed)',
                'simulated': True
            }

        global strategy_executor
        if strategy_executor is None:
            logger.error("❌ Strategy executor not initialized")
            return {
                'success': False,
                'message': 'Strategy executor uninitialized'
            }

        symbol = signal['symbol']
        action = signal['action']
        strategy = signal['strategy']

        logger.info(f"🔄 매매 Execute Starting: {symbol} {action.upper()}")

        # BUY 신호
        if action == 'buy':
            result = strategy_executor.execute_entry(
                symbol=symbol,
                strategy_info=strategy
            )

            if result:
                return {
                    'success': True,
                    'message': f'{symbol} Entry Success',
                    'action': 'buy'
                }
            else:
                return {
                    'success': False,
                    'message': f'{symbol} Entry Failed'
                }

        # SELL/CLOSE 신호
        elif action in ['sell', 'close']:
            result = strategy_executor.close_position(
                symbol=symbol,
                reason='TradingView Exit 신호'
            )

            if result:
                return {
                    'success': True,
                    'message': f'{symbol} Exit Success',
                    'action': 'sell'
                }
            else:
                return {
                    'success': False,
                    'message': f'{symbol} Exit Failed (No position?)'
                }

    except Exception as e:
        logger.error(f"❌ 매매 Execute Error: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'매매 Execute Error: {str(e)}'
        }

@app.route('/webhook', methods=['POST'])
def webhook():
    """TradingView Webhook endpoint"""
    try:
        # 요청 로깅
        logger.info(f"📥 Webhook request received: {request.remote_addr}")

        # JSON 데이터 파싱
        if request.content_type == 'application/json':
            data = request.get_json()
        else:
            # TradingView는 때때로 form data로 전송
            data = json.loads(request.data.decode('utf-8'))

        logger.info(f"📦 Received data: {json.dumps(data, indent=2, ensure_ascii=False)}")

        # 보안 서명 Verification
        signature = request.headers.get('X-Webhook-Signature', '')
        payload = json.dumps(data)

        if not verify_signature(payload, signature):
            logger.warning(f"⚠️ 서명 Verification Failed: {request.remote_addr}")
            return jsonify({
                'success': False,
                'message': 'Invalid signature'
            }), 401

        # Notification 파싱
        signal = parse_tradingview_alert(data)
        if signal is None:
            return jsonify({
                'success': False,
                'message': 'Invalid alert format'
            }), 400

        # 매매 Execute (비동기)
        def async_execute():
            result = execute_trade(signal)
            logger.info(f"📊 매매 결과: {result}")

        thread = threading.Thread(target=async_execute, daemon=True)
        thread.start()

        # 즉시 Response (TradingView 타임아웃 방지)
        return jsonify({
            'success': True,
            'message': 'Signal received and processing',
            'symbol': signal['symbol'],
            'action': signal['action']
        }), 200

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON 파싱 Failed: {e}")
        return jsonify({
            'success': False,
            'message': 'Invalid JSON format'
        }), 400

    except Exception as e:
        logger.error(f"❌ 웹훅 Process Error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Internal error: {str(e)}'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """서버 Status 체크"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'trading_enabled': webhook_config.get('trading', {}).get('enabled', True),
        'version': '1.0.0'
    }), 200

@app.route('/status', methods=['GET'])
def status():
    """상세 Status Info"""
    global strategy_executor

    status_info = {
        'server': {
            'uptime': 'N/A',
            'timestamp': datetime.now().isoformat()
        },
        'strategy_executor': {
            'initialized': strategy_executor is not None,
            'positions': len(strategy_executor.positions) if strategy_executor else 0
        },
        'config': {
            'trading_enabled': webhook_config.get('trading', {}).get('enabled', True),
            'test_mode': webhook_config.get('trading', {}).get('test_mode', False),
            'security_enabled': webhook_config.get('security', {}).get('enabled', False)
        }
    }

    return jsonify(status_info), 200

def initialize_strategy_executor(executor):
    """전략 Execute기 Initialize (외부에서 호출)"""
    global strategy_executor
    strategy_executor = executor
    logger.info("✅ 전략 Execute기 Initialization complete")

def start_server(host=None, port=None, debug=False):
    """웹훅 서버 Starting"""
    load_config()

    server_config = webhook_config.get('server', {})
    host = host or server_config.get('host', '0.0.0.0')
    port = port or server_config.get('port', 5000)
    debug = debug or server_config.get('debug', False)

    logger.info("=" * 60)
    logger.info("🚀 TradingView Webhook Server Starting...")
    logger.info(f"📡 Listening on http://{host}:{port}/webhook")
    logger.info(f"💊 Health check: http://{host}:{port}/health")
    logger.info(f"📊 Status: http://{host}:{port}/status")
    logger.info("=" * 60)

    if webhook_config.get('security', {}).get('secret_key') == "YOUR_SECRET_KEY_HERE_CHANGE_THIS":
        logger.warning("⚠️" * 20)
        logger.warning("⚠️ SECRET_KEY is default value!")
        logger.warning("⚠️ webhook_config.json에서 SECRET_KEY를 Change하세요!")
        logger.warning("⚠️" * 20)

    app.run(host=host, port=port, debug=debug, threaded=True)

if __name__ == '__main__':
    # 단독 Execute 시 (Test용)
    print("⚠️ Test mode: 전략 Execute기 없이 서버만 Starting")
    print("실제 Usage 시에는 tradingview_strategy_executor.py를 Execute하세요")
    start_server()
