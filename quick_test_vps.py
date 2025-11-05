#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VPS 빠른 진단 스크립트"""

import sys
print("=" * 60)
print("🔍 VPS 환경 진단")
print("=" * 60)

# 1. Python 버전
print(f"\n1. Python 버전: {sys.version}")

# 2. 필수 패키지 확인
packages = ['ccxt', 'pandas', 'numpy', 'ta', 'requests']
print("\n2. 패키지 확인:")
for pkg in packages:
    try:
        __import__(pkg)
        print(f"  ✓ {pkg}")
    except ImportError:
        print(f"  ✗ {pkg} 없음 - pip3 install {pkg}")

# 3. 필수 파일 확인
import os
files = [
    'pattern_optimizations.py',
    'binance_config.py',
    'improved_dca_position_manager.py'
]
print("\n3. 필수 파일:")
for f in files:
    if os.path.exists(f):
        print(f"  ✓ {f}")
    else:
        print(f"  ✗ {f} 없음")

# 4. SSL 및 Binance 연결 테스트
print("\n4. Binance API 연결 테스트:")
try:
    import ssl
    import warnings
    import urllib3

    warnings.filterwarnings('ignore')
    urllib3.disable_warnings()
    ssl._create_default_https_context = ssl._create_unverified_context

    import ccxt
    exchange = ccxt.binance({'enableRateLimit': True})
    exchange.session.verify = False

    markets = exchange.load_markets()
    usdt_futures = [s for s in markets if s.endswith('/USDT')]
    print(f"  ✓ 연결 성공 - USDT 선물 {len(usdt_futures)}개")

except Exception as e:
    print(f"  ✗ 연결 실패: {e}")

print("\n" + "=" * 60)
print("진단 완료")
print("=" * 60)
