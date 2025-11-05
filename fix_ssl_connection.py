# -*- coding: utf-8 -*-
"""
SSL 연결 문제 해결 패치
Binance API SSL 연결 실패 문제를 우회하는 스크립트
"""

import sys
import os

# UTF-8 출력 설정 (Windows 호환성)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import ssl
import urllib3
import warnings

# SSL 경고 무시 (임시 해결책)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# SSL 컨텍스트 생성 (레거시 모드)
def create_legacy_ssl_context():
    """레거시 SSL 컨텍스트 생성 (Python 32-bit 호환성)"""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
    return context

# ccxt 세션 패치
def patch_ccxt_session(exchange):
    """ccxt exchange 객체의 SSL 설정 패치"""
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.ssl_ import create_urllib3_context

    class SSLAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            ctx = create_legacy_ssl_context()
            kwargs['ssl_context'] = ctx
            return super().init_poolmanager(*args, **kwargs)

    exchange.session.mount('https://', SSLAdapter())
    return exchange

# Binance 안전 연결 함수
def create_safe_binance_connection(api_key=None, secret_key=None, sandbox=False):
    """SSL 문제 우회한 Binance 연결 생성"""
    import ccxt

    # 기본 설정
    config = {
        'enableRateLimit': True,
        'timeout': 30000,  # 타임아웃 증가
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True,
            'recvWindow': 60000
        }
    }

    # API 키 설정
    if api_key and secret_key:
        config['apiKey'] = api_key
        config['secret'] = secret_key
        config['sandbox'] = sandbox

    # Exchange 객체 생성
    exchange = ccxt.binance(config)

    # SSL 패치 적용
    exchange = patch_ccxt_session(exchange)

    # SSL 검증 비활성화 (임시)
    exchange.session.verify = False

    return exchange

if __name__ == '__main__':
    print("SSL 연결 패치 테스트")
    print("=" * 60)

    # 설정 로드
    try:
        from binance_config import BinanceConfig
        api_key = BinanceConfig.API_KEY
        secret_key = BinanceConfig.SECRET_KEY
        sandbox = BinanceConfig.TESTNET
        print("✓ binance_config.py 로드 성공")
    except ImportError:
        api_key = None
        secret_key = None
        sandbox = False
        print("! binance_config.py 없음 - 공개 API 사용")

    try:
        # 패치된 연결 생성
        print("\n패치된 Binance 연결 생성 중...")
        exchange = create_safe_binance_connection(api_key, secret_key, sandbox)

        # 마켓 로드
        print("마켓 로드 중...")
        markets = exchange.load_markets()
        usdt_futures = [s for s in markets.keys() if s.endswith('/USDT')]
        print(f"✓ 성공! USDT 선물: {len(usdt_futures)}개")

        # 잔고 확인 (API 키가 있는 경우)
        if api_key and secret_key:
            print("\n계좌 정보 조회 중...")
            balance = exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {}).get('total', 0)
            print(f"✓ USDT 잔고: ${usdt_balance:.2f}")

        print("\n✓ 모든 테스트 성공!")
        print("\n이 패치를 메인 스크립트에 적용하세요.")

    except Exception as e:
        print(f"\n✗ 연결 실패: {e}")
        print("\n다른 해결책을 시도해야 합니다.")
        import traceback
        traceback.print_exc()
