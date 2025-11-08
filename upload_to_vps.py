#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VPS 업로드 스크립트
주요 파일들을 VPS 서버로 업로드
"""

import os
import sys
from pathlib import Path

# 업로드할 파일들
upload_files = [
    "one_minute_surge_entry_strategy.py",
    "binance_rate_limiter.py", 
    "binance_websocket_kline_manager.py",
    "telegram_bot.py",
    "binance_config.example.py",
    "telegram_config.example.py", 
    "requirements.txt",
    "README.md",
    "TRADING_SYSTEM_DOCUMENTATION.md",
    "strategy_conditions_comprehensive_guide.md",
    "dca_system_summary.md",
    "DCA_SYSTEM_IMPROVEMENTS.md"
]

vps_ip = "158.247.193.81"
vps_user = "root"
target_dir = "/root/vivik"

print("=== VPS 업로드 가이드 ===")
print(f"VPS IP: {vps_ip}")
print(f"사용자: {vps_user}")
print(f"대상 디렉토리: {target_dir}")
print()

print("다음 명령어들을 순서대로 실행하세요:")
print()

# 1. SSH 연결 및 디렉토리 생성
print("1. VPS에 SSH 연결 및 디렉토리 생성:")
print(f"   ssh {vps_user}@{vps_ip}")
print(f"   mkdir -p {target_dir}")
print(f"   cd {target_dir}")
print()

# 2. SCP 파일 업로드 명령어들
print("2. 파일 업로드 (로컬 터미널에서 실행):")
current_dir = str(Path.cwd())

for file in upload_files:
    file_path = Path(current_dir) / file
    if file_path.exists():
        print(f"   scp \"{file_path}\" {vps_user}@{vps_ip}:{target_dir}/")
    else:
        print(f"   # {file} - 파일 없음")

print()

# 3. VPS에서 실행할 설정 명령어들
print("3. VPS에서 실행할 설정:")
print("   # Python 및 필요 패키지 설치")
print("   apt update && apt install -y python3 python3-pip")
print("   pip3 install -r requirements.txt")
print()
print("   # 설정 파일 복사")
print("   cp binance_config.example.py binance_config.py")
print("   cp telegram_config.example.py telegram_config.py")
print()
print("   # 설정 파일 편집")
print("   nano binance_config.py  # API 키 입력")
print("   nano telegram_config.py  # 텔레그램 토큰 입력")
print()

# 4. 실행 명령어
print("4. 프로그램 실행:")
print("   python3 one_minute_surge_entry_strategy.py")
print()

# 5. 백그라운드 실행
print("5. 백그라운드 실행 (선택사항):")
print("   nohup python3 one_minute_surge_entry_strategy.py > trading.log 2>&1 &")
print("   # 로그 확인: tail -f trading.log")
print()

print("=== 업로드 완료 후 확인사항 ===")
print("1. API 키가 올바르게 설정되었는지 확인")
print("2. 네트워크 연결 상태 확인")
print("3. 프로그램이 정상 실행되는지 확인")
print("4. 텔레그램 알림이 오는지 확인")