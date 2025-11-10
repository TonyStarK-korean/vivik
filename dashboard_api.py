#!/usr/bin/env python3
"""
Alpha-Z Trading Dashboard API Server
실시간 계좌 정보 및 매매 데이터를 제공하는 REST API
"""

from flask import Flask, jsonify, send_file
from flask_cors import CORS
from binance.client import Client
from binance.exceptions import BinanceAPIException
import os
import json
from datetime import datetime
from dotenv import load_dotenv
import threading
import time

app = Flask(__name__)
CORS(app)  # CORS 활성화

# 환경 변수 로드
load_dotenv()

# Binance 클라이언트 초기화
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_SECRET_KEY')

if not api_key or not api_secret:
    print("⚠️ WARNING: BINANCE_API_KEY or BINANCE_SECRET_KEY not found in .env")
    print("API will run in DEMO mode with sample data")
    DEMO_MODE = True
else:
    try:
        client = Client(api_key, api_secret)
        # Futures 계정 확인
        client.futures_account()
        DEMO_MODE = False
        print("✅ Binance Futures API connected successfully")
    except Exception as e:
        print(f"⚠️ Binance API connection failed: {e}")
        print("API will run in DEMO mode with sample data")
        DEMO_MODE = True

# 캐시 데이터
cache = {
    'positions': [],
    'account_info': {},
    'recent_signals': [],
    'strategy_stats': {},
    'last_update': None
}

# 로그 파일 경로
LOG_FILE = 'trading_signals.log'


def get_account_balance():
    """계좌 잔고 정보 가져오기"""
    if DEMO_MODE:
        return {
            'totalWalletBalance': 12450.80,
            'totalUnrealizedProfit': 342.50,
            'availableBalance': 8200.30
        }

    try:
        account = client.futures_account()
        return {
            'totalWalletBalance': float(account['totalWalletBalance']),
            'totalUnrealizedProfit': float(account['totalUnrealizedProfit']),
            'availableBalance': float(account['availableBalance'])
        }
    except Exception as e:
        print(f"Error fetching account balance: {e}")
        return None


def get_open_positions():
    """현재 보유 중인 포지션 가져오기"""
    if DEMO_MODE:
        return [
            {
                'symbol': 'BTCUSDT',
                'positionAmt': 0.15,
                'entryPrice': 88250.0,
                'markPrice': 91295.0,
                'unRealizedProfit': 457.50,
                'leverage': 3,
                'positionSide': 'LONG'
            },
            {
                'symbol': 'ETHUSDT',
                'positionAmt': 2.5,
                'entryPrice': 3125.0,
                'markPrice': 3182.0,
                'unRealizedProfit': 142.50,
                'leverage': 3,
                'positionSide': 'LONG'
            },
            {
                'symbol': 'SOLUSDT',
                'positionAmt': 10.0,
                'entryPrice': 215.80,
                'markPrice': 218.50,
                'unRealizedProfit': 27.00,
                'leverage': 2,
                'positionSide': 'LONG'
            }
        ]

    try:
        positions = client.futures_position_information()
        open_positions = []

        for pos in positions:
            position_amt = float(pos['positionAmt'])
            if position_amt != 0:  # 포지션이 있는 것만
                entry_price = float(pos['entryPrice'])
                mark_price = float(pos['markPrice'])
                unrealized_pnl = float(pos['unRealizedProfit'])

                open_positions.append({
                    'symbol': pos['symbol'],
                    'positionAmt': position_amt,
                    'entryPrice': entry_price,
                    'markPrice': mark_price,
                    'unRealizedProfit': unrealized_pnl,
                    'leverage': int(pos['leverage']),
                    'positionSide': pos['positionSide']
                })

        return open_positions
    except Exception as e:
        print(f"Error fetching positions: {e}")
        return []


def get_recent_signals():
    """최근 신호 로그 읽기"""
    signals = []

    # 로그 파일이 있으면 읽기
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-50:]  # 최근 50개
                for line in lines:
                    try:
                        signal = json.loads(line.strip())
                        signals.append(signal)
                    except:
                        continue
        except Exception as e:
            print(f"Error reading signal log: {e}")

    # 로그가 없으면 샘플 데이터
    if not signals:
        signals = [
            {
                'timestamp': '2025-11-10 14:28:30',
                'symbol': 'SOLUSDT',
                'strategy': 'A',
                'action': 'BUY',
                'price': 215.80,
                'status': '진입완료'
            },
            {
                'timestamp': '2025-11-10 14:15:12',
                'symbol': 'BNBUSDT',
                'strategy': 'C',
                'action': 'SELL',
                'price': 645.30,
                'status': '익절 +4.2%'
            },
            {
                'timestamp': '2025-11-10 13:58:45',
                'symbol': 'ADAUSDT',
                'strategy': 'B',
                'action': 'BUY',
                'price': 1.082,
                'status': '진입완료'
            }
        ]

    return signals


def get_strategy_stats():
    """전략별 통계 (샘플)"""
    return {
        'strategy_a': {
            'win_count': 12,
            'loss_count': 4,
            'total_return': 18.5,
            'win_rate': 75.0
        },
        'strategy_b': {
            'win_count': 8,
            'loss_count': 4,
            'total_return': 12.3,
            'win_rate': 66.7
        },
        'strategy_c': {
            'win_count': 6,
            'loss_count': 4,
            'total_return': 9.8,
            'win_rate': 60.0
        }
    }


def update_cache():
    """캐시 업데이트"""
    while True:
        try:
            cache['account_info'] = get_account_balance()
            cache['positions'] = get_open_positions()
            cache['recent_signals'] = get_recent_signals()
            cache['strategy_stats'] = get_strategy_stats()
            cache['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            print(f"✅ Cache updated at {cache['last_update']}")
        except Exception as e:
            print(f"❌ Cache update error: {e}")

        time.sleep(10)  # 10초마다 업데이트


# API 엔드포인트

@app.route('/')
def index():
    """대시보드 HTML 제공"""
    return send_file('trading_dashboard.html')


@app.route('/api/account')
def api_account():
    """계좌 정보"""
    return jsonify(cache['account_info'])


@app.route('/api/positions')
def api_positions():
    """현재 포지션"""
    return jsonify(cache['positions'])


@app.route('/api/signals')
def api_signals():
    """최근 신호"""
    return jsonify(cache['recent_signals'])


@app.route('/api/strategy-stats')
def api_strategy_stats():
    """전략별 통계"""
    return jsonify(cache['strategy_stats'])


@app.route('/api/dashboard')
def api_dashboard():
    """모든 대시보드 데이터 한번에"""
    return jsonify({
        'account': cache['account_info'],
        'positions': cache['positions'],
        'signals': cache['recent_signals'],
        'strategy_stats': cache['strategy_stats'],
        'last_update': cache['last_update']
    })


@app.route('/api/health')
def api_health():
    """헬스체크"""
    return jsonify({
        'status': 'ok',
        'mode': 'DEMO' if DEMO_MODE else 'LIVE',
        'last_update': cache['last_update']
    })


if __name__ == '__main__':
    # 백그라운드에서 캐시 업데이트 시작
    cache_thread = threading.Thread(target=update_cache, daemon=True)
    cache_thread.start()

    print("\n" + "="*50)
    print("🚀 Alpha-Z Trading Dashboard API Server")
    print("="*50)
    print(f"Mode: {'DEMO' if DEMO_MODE else 'LIVE'}")
    print(f"Server: http://0.0.0.0:5000")
    print(f"Dashboard: http://0.0.0.0:5000")
    print("="*50 + "\n")

    # Flask 서버 시작
    app.run(host='0.0.0.0', port=5000, debug=False)
