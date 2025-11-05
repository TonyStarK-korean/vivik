# -*- coding: utf-8 -*-
"""
python-binance 라이브러리 테스트
ccxt 대신 사용 가능한 대안 라이브러리
"""

import sys
import os

# UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

print("="*60)
print("python-binance 라이브러리 연결 테스트")
print("="*60)

# 라이브러리 확인
try:
    from binance.client import Client
    from binance.exceptions import BinanceAPIException
    print("✓ python-binance 라이브러리 로드 성공")
except ImportError:
    print("✗ python-binance 설치 필요")
    print("\n설치 명령:")
    print("  pip install python-binance")
    sys.exit(1)

# 설정 로드
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from binance_config import BinanceConfig
    api_key = BinanceConfig.API_KEY
    secret_key = BinanceConfig.SECRET_KEY
    print(f"✓ API 키 로드: {api_key[:10]}...{api_key[-10:]}")
except ImportError:
    api_key = ""
    secret_key = ""
    print("! binance_config.py 없음 - 공개 API 테스트")

print("\n" + "-"*60)
print("연결 테스트 시작...")
print("-"*60)

try:
    # 클라이언트 생성
    if api_key and secret_key:
        client = Client(api_key, secret_key)
        print("✓ 인증 클라이언트 생성 성공")
    else:
        client = Client()
        print("✓ 공개 클라이언트 생성 성공")

    # 서버 시간 확인
    print("\n1. 서버 시간 확인...")
    server_time = client.get_server_time()
    from datetime import datetime
    time_str = datetime.fromtimestamp(server_time['serverTime']/1000)
    print(f"   ✓ 서버 시간: {time_str}")

    # 거래 정보 확인
    print("\n2. 거래 정보 확인...")
    exchange_info = client.futures_exchange_info()
    symbols = exchange_info.get('symbols', [])
    usdt_symbols = [s['symbol'] for s in symbols if s['symbol'].endswith('USDT')]
    print(f"   ✓ USDT 선물 심볼: {len(usdt_symbols)}개")

    # 계좌 정보 (API 키가 있는 경우)
    if api_key and secret_key:
        print("\n3. 계좌 정보 확인...")
        try:
            account = client.futures_account_balance()
            usdt_balance = next((float(b['balance']) for b in account if b['asset'] == 'USDT'), 0)
            print(f"   ✓ USDT 잔고: ${usdt_balance:.2f}")
        except BinanceAPIException as e:
            print(f"   ! 계좌 정보 조회 실패: {e}")

    print("\n" + "="*60)
    print("✓ 모든 테스트 성공!")
    print("="*60)
    print("\npython-binance 라이브러리가 정상 작동합니다.")
    print("이 라이브러리로 전략 스크립트를 수정할 수 있습니다.")

except BinanceAPIException as e:
    print(f"\n✗ Binance API 에러:")
    print(f"   코드: {e.code}")
    print(f"   메시지: {e.message}")

except Exception as e:
    print(f"\n✗ 연결 실패: {e}")
    print("\n상세 에러:")
    import traceback
    traceback.print_exc()

    print("\n" + "="*60)
    print("python-binance도 동일한 SSL 문제 발생")
    print("="*60)
    print("\n해결책: Python 64-bit로 업그레이드 필요")
    print("자세한 내용은 '해결방법_안내.md' 파일을 참고하세요.")
