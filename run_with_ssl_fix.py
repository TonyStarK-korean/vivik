#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSL 우회 버전 실행 스크립트
VPS에서 Binance API 연결 문제 해결
"""

import ssl
import warnings
import urllib3

# SSL 경고 무시
warnings.filterwarnings('ignore')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# SSL 검증 비활성화
ssl._create_default_https_context = ssl._create_unverified_context

print("🔓 SSL 검증 비활성화 완료")
print("🚀 메인 스크립트 실행 중...\n")

# 메인 스크립트 실행
import one_minute_surge_entry_strategy
