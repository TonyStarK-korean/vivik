# -*- coding: utf-8 -*-
"""
Binance 연결 테스트 스크립트
"""

import ccxt
import sys
import os

# UTF-8 출력 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 현재 디렉토리를 경로에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from binance_config import BinanceConfig
    print("✅ binance_config.py 로드 성공")
    print(f"   API_KEY: {BinanceConfig.API_KEY[:10]}...{BinanceConfig.API_KEY[-10:]}")
    print(f"   TESTNET: {BinanceConfig.TESTNET}")
except ImportError as e:
    print(f"❌ binance_config.py 로드 실패: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("Binance API 연결 테스트 시작")
print("="*60 + "\n")

# 테스트 1: 공개 API 연결 (인증 없이)
print("테스트 1: 공개 API 연결 (인증 없이)")
print("-" * 60)
try:
    exchange_public = ccxt.binance({
        'enableRateLimit': True,
        'timeout': 10000,
        'options': {
            'defaultType': 'future',
        }
    })

    print("서버 시간 확인 중...")
    server_time = exchange_public.fetch_time()
    print(f"✅ 서버 시간: {server_time}")

    print("\n마켓 로드 중...")
    markets = exchange_public.load_markets()
    usdt_futures = [s for s in markets.keys() if s.endswith('/USDT')]
    print(f"✅ USDT 선물 마켓 수: {len(usdt_futures)}개")

except Exception as e:
    print(f"❌ 공개 API 연결 실패:")
    print(f"   에러 타입: {type(e).__name__}")
    print(f"   에러 메시지: {str(e)}")
    import traceback
    print(f"   상세 정보:\n{traceback.format_exc()}")

# 테스트 2: 인증 API 연결
print("\n\n테스트 2: 인증 API 연결")
print("-" * 60)
try:
    exchange_auth = ccxt.binance({
        'apiKey': BinanceConfig.API_KEY,
        'secret': BinanceConfig.SECRET_KEY,
        'sandbox': BinanceConfig.TESTNET,
        'enableRateLimit': True,
        'timeout': 10000,
        'options': {
            'defaultType': 'future',
            'adjustForTimeDifference': True,
            'recvWindow': 60000
        }
    })

    print("마켓 로드 중...")
    markets = exchange_auth.load_markets()
    print(f"✅ 마켓 로드 성공: {len(markets)}개")

    print("\n계좌 정보 조회 중...")
    balance = exchange_auth.fetch_balance()
    total_usdt = balance.get('USDT', {}).get('total', 0)
    free_usdt = balance.get('USDT', {}).get('free', 0)
    print(f"✅ USDT 잔고:")
    print(f"   총계: ${total_usdt:.2f}")
    print(f"   사용가능: ${free_usdt:.2f}")

    print("\n✅ 모든 테스트 성공!")

except Exception as e:
    print(f"❌ 인증 API 연결 실패:")
    print(f"   에러 타입: {type(e).__name__}")
    print(f"   에러 메시지: {str(e)}")

    # 상세 에러 정보
    if hasattr(e, 'args') and len(e.args) > 0:
        print(f"   추가 정보: {e.args}")

    import traceback
    print(f"\n   상세 정보:\n{traceback.format_exc()}")

    # Rate limit 체크
    error_str = str(e)
    if "418" in error_str or "429" in error_str or "banned" in error_str.lower():
        print("\n⚠️ Rate Limit 또는 IP 밴 감지!")
        if "banned until" in error_str:
            import re
            ban_time_match = re.search(r'banned until (\d+)', error_str)
            if ban_time_match:
                ban_timestamp = int(ban_time_match.group(1))
                if ban_timestamp > 10**12:
                    ban_timestamp = ban_timestamp // 1000
                from datetime import datetime
                ban_time = datetime.fromtimestamp(ban_timestamp)
                print(f"   밴 해제 예정: {ban_time}")

print("\n" + "="*60)
print("테스트 완료")
print("="*60)
