#!/usr/bin/env python3
"""
Alpha-Z Trading Dashboard API Server
실시간 계좌 정보 및 매매 데이터를 제공하는 REST API
실제 DCA 포지션 및 거래 신호 로그 연동
"""

from flask import Flask, jsonify, send_file
from flask_cors import CORS
from binance.client import Client
from binance.exceptions import BinanceAPIException
import os
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Binance Rate Limiter 추가 (IP 차단 방지)
try:
    from binance_rate_limiter import BinanceRateLimiter
    HAS_RATE_LIMITER = True
    print("[INFO] 대시보드 API - Binance Rate Limiter 로드 완료")
except ImportError:
    print("[WARNING] 대시보드 API - binance_rate_limiter.py 없음, Rate Limiting 비활성화")
    HAS_RATE_LIMITER = False
import threading
import time
from collections import defaultdict

app = Flask(__name__)
CORS(app)  # CORS 활성화

# 환경 변수 로드
load_dotenv()

# Binance 클라이언트 초기화
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_SECRET_KEY')

if not api_key or not api_secret:
    print("[WARNING] BINANCE_API_KEY or BINANCE_SECRET_KEY not found in .env")
    print("API will run in DEMO mode with sample data")
    DEMO_MODE = True
    rate_limiter = None
else:
    try:
        client = Client(api_key, api_secret)
        # Futures 계정 확인
        client.futures_account()
        
        # Rate Limiter 초기화
        if HAS_RATE_LIMITER:
            rate_limiter = BinanceRateLimiter()
            print("[SUCCESS] Binance Rate Limiter 초기화 완료")
        else:
            rate_limiter = None
            print("[WARNING] Rate Limiter 없음 - IP 차단 위험")
        
        DEMO_MODE = False
        print("[SUCCESS] Binance Futures API connected successfully")
    except Exception as e:
        print(f"[WARNING] Binance API connection failed: {e}")
        print("API will run in DEMO mode with sample data")
        DEMO_MODE = True
        rate_limiter = None

# 캐시 데이터
cache = {
    'positions': [],
    'account_info': {},
    'recent_signals': [],
    'strategy_stats': {},
    'last_update': None,
    'dca_positions': {}  # DCA 포지션 데이터
}

# 파일 경로
LOG_FILE = 'trading_signals.log'
DCA_POSITIONS_FILE = 'dca_positions.json'
TRADE_HISTORY_FILE = 'trade_history.json'

def get_korea_time():
    """한국 표준시(KST) 현재 시간 반환"""
    return datetime.now(timezone(timedelta(hours=9)))

def _parse_strategy_info(strategy_str):
    """전략 정보 파싱 (중복 제거 및 정확한 분류)"""
    if not strategy_str or strategy_str == 'UNKNOWN':
        return 'UNKNOWN'
    
    # [A전략(3분봉 바닥급등타점)] 형태 파싱
    if isinstance(strategy_str, str):
        if 'A전략' in strategy_str:
            return 'A'
        elif 'B전략' in strategy_str:
            return 'B'
        elif 'C전략' in strategy_str:
            return 'C'
        elif strategy_str in ['A', 'B', 'C']:
            return strategy_str
    
    return 'UNKNOWN'


def get_account_balance():
    """계좌 잔고 정보 가져오기 (Rate Limiter 적용)"""
    if DEMO_MODE:
        return {
            'totalWalletBalance': 12450.80,
            'totalUnrealizedProfit': 342.50,
            'availableBalance': 8200.30
        }

    try:
        # Rate Limiting 체크
        if rate_limiter and not rate_limiter.wait_if_needed('/fapi/v2/account'):
            print("[ERROR] Rate limit exceeded - account balance request denied")
            return None
        
        account = client.futures_account()
        
        # Rate Limiting 기록
        if rate_limiter:
            rate_limiter.record_request('/fapi/v2/account')
        
        return {
            'totalWalletBalance': float(account['totalWalletBalance']),
            'totalUnrealizedProfit': float(account['totalUnrealizedProfit']),
            'availableBalance': float(account['availableBalance'])
        }
    except Exception as e:
        print(f"Error fetching account balance: {e}")
        # Rate Limiting 에러 기록
        if rate_limiter and hasattr(e, 'response'):
            status_code = getattr(e.response, 'status_code', 0) if e.response else 0
            if status_code:
                rate_limiter.record_error(status_code)
        return None


def load_dca_positions():
    """DCA 포지션 파일에서 데이터 로드"""
    if not os.path.exists(DCA_POSITIONS_FILE):
        return {}

    try:
        with open(DCA_POSITIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"Error loading DCA positions: {e}")
        return {}


def get_open_positions():
    """현재 보유 중인 포지션 가져오기 (Binance API + DCA 데이터 결합)"""
    if DEMO_MODE:
        # DEMO 모드에서는 빈 배열 반환 - 샘플 데이터 제거
        print("[INFO] DEMO mode - returning empty positions array")
        return []

    try:
        # Rate Limiting 체크
        if rate_limiter and not rate_limiter.wait_if_needed('/fapi/v2/positionRisk'):
            print("[ERROR] Rate limit exceeded - position request denied")
            return []
        
        # Binance API에서 실제 포지션 가져오기
        positions = client.futures_position_information()
        
        # Rate Limiting 기록
        if rate_limiter:
            rate_limiter.record_request('/fapi/v2/positionRisk')
        
        open_positions = []

        # DCA 포지션 데이터 로드
        dca_data = load_dca_positions()

        for pos in positions:
            position_amt = float(pos['positionAmt'])
            if position_amt != 0:  # 포지션이 있는 것만
                symbol = pos['symbol']
                entry_price = float(pos['entryPrice'])
                mark_price = float(pos['markPrice'])
                unrealized_pnl = float(pos['unRealizedProfit'])

                # DCA 데이터와 결합 (심볼 형식 매칭)
                # Binance API: "BTCUSDT" vs DCA: "BTC/USDT:USDT" 형식 차이 해결
                dca_symbol_formats = [
                    symbol,  # 원본 형식 시도
                    f"{symbol[:-4]}/{symbol[-4:]}:USDT" if symbol.endswith('USDT') else symbol,  # BTC/USDT:USDT 형식
                    f"{symbol[:-4]}/{symbol[-4:]}" if symbol.endswith('USDT') else symbol  # BTC/USDT 형식
                ]
                
                dca_info = {}
                for fmt in dca_symbol_formats:
                    if fmt in dca_data:
                        dca_info = dca_data[fmt]
                        break

                position_data = {
                    'symbol': symbol,
                    'positionAmt': position_amt,
                    'entryPrice': entry_price,
                    'markPrice': mark_price,
                    'unRealizedProfit': unrealized_pnl,
                    'leverage': int(pos['leverage']),
                    'positionSide': pos['positionSide'],
                    # 전략 정보 개선
                    'strategy': _parse_strategy_info(dca_info.get('strategy', 'UNKNOWN')),
                    'dcaStage': dca_info.get('current_stage', 'UNKNOWN'),
                    'cyclicCount': dca_info.get('cyclic_count', 0),
                    'totalNotional': dca_info.get('total_notional', abs(position_amt * mark_price)),
                    'averagePrice': dca_info.get('average_price', entry_price),
                    'maxCyclicCount': dca_info.get('max_cyclic_count', 3),
                    'createdAt': dca_info.get('created_at', 'N/A')
                }

                open_positions.append(position_data)

        return open_positions
    except Exception as e:
        print(f"Error fetching positions: {e}")
        # Rate Limiting 에러 기록
        if rate_limiter and hasattr(e, 'response'):
            status_code = getattr(e.response, 'status_code', 0) if e.response else 0
            if status_code:
                rate_limiter.record_error(status_code)
        return []


def get_recent_signals():
    """최근 신호 로그 읽기 (실제 데이터 연동 + 중복 제거)"""
    try:
        # 거래 로거 사용하여 실제 데이터 가져오기
        from trading_signal_logger import get_trading_logger
        logger = get_trading_logger()
        raw_signals = logger.get_recent_signals(50)
        
        # 시간 형식을 대시보드용으로 변환 및 중복 제거
        processed_signals = []
        seen_signals = set()  # 중복 체크용
        
        # 소스 우선순위 기반 중복 제거 (alpha_z_strategy > dca_manager > others)
        signal_priority_map = {}  # key -> (priority, signal)
        
        for signal in raw_signals:
            action = signal.get('action', '')
            strategy = signal.get('strategy', '')
            source = signal.get('metadata', {}).get('source', '')
            symbol = signal.get('symbol', '')
            
            # DCA 매니저에서 오는 중복 신호는 우선순위가 낮음
            if strategy == 'DCA' and source == 'dca_manager':
                continue  # DCA 전략은 완전히 제외
            
            # 전략 분류 정확히 파싱 
            original_strategy = strategy  # 원본 보존
            if strategy and strategy.startswith('[') and strategy.endswith(']'):
                # [A전략(3분봉 바닥급등타점)] 형태에서 A 추출
                if 'A전략' in strategy:
                    signal['strategy'] = 'A'
                elif 'B전략' in strategy:
                    signal['strategy'] = 'B'
                elif 'C전략' in strategy:
                    signal['strategy'] = 'C'
                else:
                    signal['strategy'] = 'A'  # 기본값
            elif strategy in ['A', 'B', 'C']:
                # 이미 올바른 형태면 그대로 유지
                pass
            else:
                # 기타 경우에는 A로 기본 설정
                signal['strategy'] = 'A'
            
            # 불타기 관련 액션 용어 변경
            if action == 'BUY' and source == 'dca_manager':
                signal['action'] = '불타기 진입'
                signal['status'] = '불타기 완료'
            
            # 중복 체크 키 생성 (심볼 + 전략 + 시간(분 단위))
            timestamp_key = signal.get('timestamp', '')
            if 'T' in timestamp_key and ':' in timestamp_key:
                try:
                    # YYYY-MM-DD HH:MM 형태로 변환 (분 단위 그룹핑)
                    time_part = timestamp_key.split('T')[1].split(':')
                    hour = time_part[0]
                    minute = time_part[1]
                    timestamp_key = f"{hour}:{minute}"
                except:
                    timestamp_key = timestamp_key[:16]  # YYYY-MM-DD HH:MM
            
            duplicate_key = f"{symbol}_{signal.get('strategy', '')}_{timestamp_key}_{action}"
            
            # 소스별 우선순위 설정 (높은 숫자가 높은 우선순위)
            if source == 'alpha_z_strategy':
                priority = 3  # 최고 우선순위
            elif source == 'telegram_signal':
                priority = 2
            elif source == 'dca_manager':
                priority = 1  # 최저 우선순위
            else:
                priority = 2  # 기본 우선순위
            
            # 중복 신호 우선순위 처리
            if duplicate_key not in signal_priority_map or signal_priority_map[duplicate_key][0] < priority:
                signal_priority_map[duplicate_key] = (priority, signal)
        
        # 우선순위가 높은 신호들만 선택
        for priority, signal in signal_priority_map.values():
            # ISO 형식을 일반 형식으로 변환
            if 'timestamp' in signal:
                try:
                    # ISO 형식에서 datetime으로 파싱 후 한국 시간 형식으로 변환
                    if 'T' in signal['timestamp'] and '+' in signal['timestamp']:
                        from dateutil.parser import parse
                        dt = parse(signal['timestamp'])
                        signal['timestamp'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass  # 파싱 실패시 원본 유지
                    
            processed_signals.append(signal)
        
        return processed_signals
        
    except ImportError:
        print("[WARNING] trading_signal_logger not available - using file reading")
        
        signals = []
        # 로그 파일이 있으면 읽기
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[-50:]  # 최근 50개
                    for line_num, line in enumerate(lines, 1):
                        try:
                            line = line.strip()
                            if line:  # 빈 줄 제외
                                signal = json.loads(line)
                                # 필수 필드 확인
                                if all(key in signal for key in ['timestamp', 'symbol', 'strategy']):
                                    signals.append(signal)
                        except json.JSONDecodeError as e:
                            print(f"[WARNING] JSON parse error at line {line_num}: {e}")
                            continue
                        except Exception as e:
                            print(f"[WARNING] Signal processing error at line {line_num}: {e}")
                            continue
                            
                print(f"[INFO] Successfully loaded {len(signals)} signals from log file")
            except Exception as e:
                print(f"[ERROR] Error reading signal log: {e}")

        # 실제 로그가 없으면 빈 배열 반환 - 샘플 데이터 제거
        if not signals:
            print("[INFO] No real signals found - returning empty array")
            signals = []

        return signals


def calculate_strategy_stats():
    """전략별 통계 실시간 계산 (실제 데이터 연동)"""
    try:
        # 거래 로거 사용하여 실제 통계 가져오기
        from trading_signal_logger import get_trading_logger
        logger = get_trading_logger()
        return logger.calculate_strategy_stats()
        
    except ImportError:
        print("[WARNING] trading_signal_logger not available - using file reading")
        
        stats = {
            'strategy_a': {'win_count': 0, 'loss_count': 0, 'total_return': 0.0, 'win_rate': 0.0, 'total_trades': 0},
            'strategy_b': {'win_count': 0, 'loss_count': 0, 'total_return': 0.0, 'win_rate': 0.0, 'total_trades': 0},
            'strategy_c': {'win_count': 0, 'loss_count': 0, 'total_return': 0.0, 'win_rate': 0.0, 'total_trades': 0}
        }

        # 거래 이력 파일이 있으면 로드
        if os.path.exists(TRADE_HISTORY_FILE):
            try:
                with open(TRADE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    trade_history = json.load(f)

                    for trade in trade_history:
                        strategy = trade.get('strategy', '').upper()
                        pnl = trade.get('pnl', 0.0)
                        pnl_percent = trade.get('pnl_percent', 0.0)

                        key = f'strategy_{strategy.lower()}'
                        if key in stats:
                            stats[key]['total_trades'] += 1
                            if pnl > 0:
                                stats[key]['win_count'] += 1
                            else:
                                stats[key]['loss_count'] += 1
                            stats[key]['total_return'] += pnl_percent
            except Exception as e:
                print(f"Error loading trade history: {e}")

        # 승률 계산
        for key in stats:
            total = stats[key]['win_count'] + stats[key]['loss_count']
            if total > 0:
                stats[key]['win_rate'] = round((stats[key]['win_count'] / total) * 100.0, 1)
                stats[key]['total_return'] = round(stats[key]['total_return'], 1)
            else:
                stats[key]['win_rate'] = 0.0

        # 실제 데이터만 사용 - 샘플 데이터 제거

        return stats


def get_strategy_stats():
    """전략별 통계 가져오기"""
    return calculate_strategy_stats()


def update_cache():
    """캐시 업데이트"""
    while True:
        try:
            cache['account_info'] = get_account_balance()
            cache['positions'] = get_open_positions()
            cache['dca_positions'] = load_dca_positions()
            cache['recent_signals'] = get_recent_signals()
            cache['strategy_stats'] = get_strategy_stats()
            cache['last_update'] = get_korea_time().strftime('%Y-%m-%d %H:%M:%S')

            # 포지션 수 출력
            position_count = len(cache['positions'])
            dca_count = len(cache['dca_positions'])
            signal_count = len(cache['recent_signals'])

            print(f"[CACHE] Updated at {cache['last_update']} | Positions: {position_count} | DCA: {dca_count} | Signals: {signal_count}")
        except Exception as e:
            print(f"[ERROR] Cache update error: {e}")

        time.sleep(3)  # 3초마다 업데이트 (실시간성 개선)


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
    print("Alpha-Z Trading Dashboard API Server")
    print("="*50)
    print(f"Mode: {'DEMO' if DEMO_MODE else 'LIVE'}")
    print(f"Server: http://0.0.0.0:5000")
    print(f"Dashboard: http://0.0.0.0:5000")
    print("="*50 + "\n")

    # Flask 서버 시작
    app.run(host='0.0.0.0', port=5000, debug=False)
