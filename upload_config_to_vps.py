#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VPS에 Config 파일 업로드 스크립트
binance_config.py와 telegram_config.py를 VPS로 전송
"""

import os
import sys

def create_scp_commands():
    """SCP 명령어 생성"""

    print("=" * 70)
    print("VPS Config 파일 업로드 가이드")
    print("=" * 70)
    print()

    # 현재 디렉토리 확인
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Config 파일 확인
    binance_config = os.path.join(script_dir, "binance_config.py")
    telegram_config = os.path.join(script_dir, "telegram_config.py")

    if not os.path.exists(binance_config):
        print(f"❌ binance_config.py 파일을 찾을 수 없습니다: {binance_config}")
        return False

    if not os.path.exists(telegram_config):
        print(f"❌ telegram_config.py 파일을 찾을 수 없습니다: {telegram_config}")
        return False

    print("✅ Config 파일 확인 완료")
    print(f"   - binance_config.py: {os.path.getsize(binance_config)} bytes")
    print(f"   - telegram_config.py: {os.path.getsize(telegram_config)} bytes")
    print()

    # VPS 정보 입력 받기
    print("VPS 접속 정보를 입력하세요:")
    print("-" * 70)

    vps_user = input("VPS 사용자명 (예: root): ").strip()
    if not vps_user:
        print("❌ 사용자명을 입력해야 합니다.")
        return False

    vps_ip = input("VPS IP 주소 (예: 123.456.789.0): ").strip()
    if not vps_ip:
        print("❌ IP 주소를 입력해야 합니다.")
        return False

    vps_path = input("VPS 프로젝트 경로 (기본: ~/vivik): ").strip()
    if not vps_path:
        vps_path = "~/vivik"

    print()
    print("=" * 70)
    print("📤 업로드 명령어")
    print("=" * 70)
    print()
    print("다음 명령어를 Windows PowerShell 또는 Git Bash에서 실행하세요:")
    print()

    # Windows 경로를 Unix 스타일로 변환
    binance_win = binance_config.replace("\\", "/")
    telegram_win = telegram_config.replace("\\", "/")

    # SCP 명령어 생성
    print("# 1. binance_config.py 업로드")
    print(f'scp "{binance_win}" {vps_user}@{vps_ip}:{vps_path}/')
    print()

    print("# 2. telegram_config.py 업로드")
    print(f'scp "{telegram_win}" {vps_user}@{vps_ip}:{vps_path}/')
    print()

    print("# 3. 두 파일을 한 번에 업로드")
    print(f'scp "{binance_win}" "{telegram_win}" {vps_user}@{vps_ip}:{vps_path}/')
    print()

    print("=" * 70)
    print("📝 업로드 후 VPS에서 확인")
    print("=" * 70)
    print()
    print(f"ssh {vps_user}@{vps_ip}")
    print(f"cd {vps_path}")
    print("ls -la binance_config.py telegram_config.py")
    print()

    print("=" * 70)
    print("🚀 봇 재시작")
    print("=" * 70)
    print()
    print("pkill -f one_minute_surge_entry_strategy.py")
    print("nohup python3 one_minute_surge_entry_strategy.py > trading_bot.log 2>&1 &")
    print("tail -f trading_bot.log")
    print()

    return True

def main():
    print()
    try:
        create_scp_commands()
    except KeyboardInterrupt:
        print("\n\n❌ 사용자가 취소했습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
