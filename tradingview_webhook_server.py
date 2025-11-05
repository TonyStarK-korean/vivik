# -*- coding: utf-8 -*-
"""
TradingView Webhook Server
전략C+D 시그널을 TradingView에서 받아 자동 매매 실행
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

# 로깅 설정
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
    """웹훅 설정 로드"""
    global webhook_config
    config_path = 'webhook_config.json'

    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            webhook_config = json.load(f)
            logger.info(f"✅ 설정 로드 완료: {config_path}")
    else:
        # 기본 설정 생성
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

        logger.warning(f"⚠️ 기본 설정 파일 생성됨: {config_path}")
        logger.warning(f"⚠️ SECRET_KEY를 반드시 변경하세요!")

def verify_signature(payload: str, signature: str) -> bool:
    """웹훅 서명 검증 (보안)"""
    if not webhook_config.get('security', {}).get('enabled', False):
        return True

    secret_key = webhook_config.get('security', {}).get('secret_key', '')

    if secret_key == "YOUR_SECRET_KEY_HERE_CHANGE_THIS":
        logger.warning("⚠️ SECRET_KEY가 기본값입니다. 보안 위험!")
        return True  # 개발 단계에서는 허용

    # HMAC-SHA256 서명 검증
    expected_signature = hmac.new(
        secret_key.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)

def parse_tradingview_alert(data: Dict) -> Optional[Dict]:
    """
    TradingView 알림 데이터 파싱

    예상 JSON 형식:
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

        # 필수 필드 확인
        for field in required_fields:
            if field not in data:
                logger.error(f"❌ 필수 필드 누락: {field}")
                return None

        # 심볼 형식 변환 (BTCUSDT → BTC/USDT:USDT)
        raw_symbol = data['symbol'].upper()
        if raw_symbol.endswith('USDT'):
            base = raw_symbol[:-4]
            formatted_symbol = f"{base}/USDT:USDT"
        else:
            formatted_symbol = raw_symbol

        # 액션 정규화
        action = data['action'].lower()
        if action not in ['buy', 'sell', 'close']:
            logger.error(f"❌ 알 수 없는 액션: {action}")
            return None

        # 전략 정보
        strategy = data.get('strategy', 'strategy_c')
        strategy_name = {
            'strategy_c': '전략C: 3분봉 시세 초입 포착',
            'strategy_d': '전략D: 5분봉 초입 초강력 타점',
            'strategy_cd': '전략C+D: 3분봉+5분봉 복합 진입'
        }.get(strategy, '전략C: 3분봉 시세 초입 포착')

        parsed_data = {
            'symbol': formatted_symbol,
            'action': action,
            'strategy': strategy_name,
            'price': data.get('price'),
            'timestamp': data.get('timestamp', datetime.now().isoformat()),
            'raw_data': data
        }

        logger.info(f"✅ 알림 파싱 완료: {formatted_symbol} {action.upper()} ({strategy})")
        return parsed_data

    except Exception as e:
        logger.error(f"❌ 알림 파싱 실패: {e}")
        return None

def execute_trade(signal: Dict) -> Dict:
    """매매 실행"""
    try:
        if not webhook_config.get('trading', {}).get('enabled', True):
            logger.warning("⚠️ 매매 비활성화됨 - 시뮬레이션 모드")
            return {
                'success': True,
                'message': '시뮬레이션 모드 (매매 미실행)',
                'simulated': True
            }

        global strategy_executor
        if strategy_executor is None:
            logger.error("❌ 전략 실행기가 초기화되지 않음")
            return {
                'success': False,
                'message': '전략 실행기 미초기화'
            }

        symbol = signal['symbol']
        action = signal['action']
        strategy = signal['strategy']

        logger.info(f"🔄 매매 실행 시작: {symbol} {action.upper()}")

        # BUY 신호
        if action == 'buy':
            result = strategy_executor.execute_entry(
                symbol=symbol,
                strategy_info=strategy
            )

            if result:
                return {
                    'success': True,
                    'message': f'{symbol} 진입 성공',
                    'action': 'buy'
                }
            else:
                return {
                    'success': False,
                    'message': f'{symbol} 진입 실패'
                }

        # SELL/CLOSE 신호
        elif action in ['sell', 'close']:
            result = strategy_executor.close_position(
                symbol=symbol,
                reason='TradingView 청산 신호'
            )

            if result:
                return {
                    'success': True,
                    'message': f'{symbol} 청산 성공',
                    'action': 'sell'
                }
            else:
                return {
                    'success': False,
                    'message': f'{symbol} 청산 실패 (포지션 없음?)'
                }

    except Exception as e:
        logger.error(f"❌ 매매 실행 오류: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'매매 실행 오류: {str(e)}'
        }

@app.route('/webhook', methods=['POST'])
def webhook():
    """TradingView 웹훅 엔드포인트"""
    try:
        # 요청 로깅
        logger.info(f"📥 웹훅 요청 수신: {request.remote_addr}")

        # JSON 데이터 파싱
        if request.content_type == 'application/json':
            data = request.get_json()
        else:
            # TradingView는 때때로 form data로 전송
            data = json.loads(request.data.decode('utf-8'))

        logger.info(f"📦 수신 데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")

        # 보안 서명 검증
        signature = request.headers.get('X-Webhook-Signature', '')
        payload = json.dumps(data)

        if not verify_signature(payload, signature):
            logger.warning(f"⚠️ 서명 검증 실패: {request.remote_addr}")
            return jsonify({
                'success': False,
                'message': 'Invalid signature'
            }), 401

        # 알림 파싱
        signal = parse_tradingview_alert(data)
        if signal is None:
            return jsonify({
                'success': False,
                'message': 'Invalid alert format'
            }), 400

        # 매매 실행 (비동기)
        def async_execute():
            result = execute_trade(signal)
            logger.info(f"📊 매매 결과: {result}")

        thread = threading.Thread(target=async_execute, daemon=True)
        thread.start()

        # 즉시 응답 (TradingView 타임아웃 방지)
        return jsonify({
            'success': True,
            'message': 'Signal received and processing',
            'symbol': signal['symbol'],
            'action': signal['action']
        }), 200

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON 파싱 실패: {e}")
        return jsonify({
            'success': False,
            'message': 'Invalid JSON format'
        }), 400

    except Exception as e:
        logger.error(f"❌ 웹훅 처리 오류: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Internal error: {str(e)}'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """서버 상태 체크"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'trading_enabled': webhook_config.get('trading', {}).get('enabled', True),
        'version': '1.0.0'
    }), 200

@app.route('/status', methods=['GET'])
def status():
    """상세 상태 정보"""
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
    """전략 실행기 초기화 (외부에서 호출)"""
    global strategy_executor
    strategy_executor = executor
    logger.info("✅ 전략 실행기 초기화 완료")

def start_server(host=None, port=None, debug=False):
    """웹훅 서버 시작"""
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
        logger.warning("⚠️ SECRET_KEY가 기본값입니다!")
        logger.warning("⚠️ webhook_config.json에서 SECRET_KEY를 변경하세요!")
        logger.warning("⚠️" * 20)

    app.run(host=host, port=port, debug=debug, threaded=True)

if __name__ == '__main__':
    # 단독 실행 시 (테스트용)
    print("⚠️ 테스트 모드: 전략 실행기 없이 서버만 시작")
    print("실제 사용 시에는 tradingview_strategy_executor.py를 실행하세요")
    start_server()
