#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VPS에 Config 파일 자동 업로드
"""

import os
import sys

def upload_configs():
    """Config 파일 업로드"""

    print("=" * 70)
    print("VPS Config 자동 업로드")
    print("=" * 70)
    print()

    # VPS 정보 입력
    print("VPS 접속 정보:")
    vps_user = input("VPS 사용자명 (예: root): ").strip()
    vps_ip = input("VPS IP 주소: ").strip()
    vps_path = input("프로젝트 경로 (기본: ~/vivik): ").strip() or "~/vivik"

    if not vps_user or not vps_ip:
        print("\n❌ 사용자명과 IP 주소를 입력해야 합니다!")
        return False

    # 현재 디렉토리
    script_dir = os.path.dirname(os.path.abspath(__file__))
    binance_config = os.path.join(script_dir, "binance_config.py")
    telegram_config = os.path.join(script_dir, "telegram_config.py")

    # 파일 존재 확인
    if not os.path.exists(binance_config):
        print(f"\n❌ binance_config.py 파일이 없습니다: {binance_config}")
        return False

    if not os.path.exists(telegram_config):
        print(f"\n❌ telegram_config.py 파일이 없습니다: {telegram_config}")
        return False

    print("\n✅ Config 파일 확인 완료")
    print(f"   - binance_config.py")
    print(f"   - telegram_config.py")
    print()

    # SCP 명령어 생성
    import subprocess

    print("📤 업로드 중...")
    print()

    try:
        # binance_config.py 업로드
        cmd1 = f'scp "{binance_config}" {vps_user}@{vps_ip}:{vps_path}/'
        print(f"실행: {cmd1}")
        result1 = subprocess.run(cmd1, shell=True, capture_output=True, text=True)

        if result1.returncode == 0:
            print("✅ binance_config.py 업로드 완료")
        else:
            print(f"❌ binance_config.py 업로드 실패: {result1.stderr}")
            return False

        # telegram_config.py 업로드
        cmd2 = f'scp "{telegram_config}" {vps_user}@{vps_ip}:{vps_path}/'
        print(f"실행: {cmd2}")
        result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True)

        if result2.returncode == 0:
            print("✅ telegram_config.py 업로드 완료")
        else:
            print(f"❌ telegram_config.py 업로드 실패: {result2.stderr}")
            return False

        print()
        print("=" * 70)
        print("✅ 모든 파일 업로드 완료!")
        print("=" * 70)
        print()

        # 다음 단계 안내
        print("📝 다음 단계:")
        print(f"   ssh {vps_user}@{vps_ip}")
        print(f"   cd {vps_path}")
        print("   pkill -f one_minute_surge_entry_strategy.py")
        print("   nohup python3 one_minute_surge_entry_strategy.py > trading_bot.log 2>&1 &")
        print("   tail -f trading_bot.log")
        print()

        # 자동으로 봇 재시작할지 묻기
        restart = input("VPS에서 봇을 자동으로 재시작하시겠습니까? (y/n): ").strip().lower()

        if restart == 'y':
            print("\n🚀 봇 재시작 중...")
            restart_cmd = f'ssh {vps_user}@{vps_ip} "cd {vps_path} && pkill -f one_minute_surge_entry_strategy.py; sleep 2; nohup python3 one_minute_surge_entry_strategy.py > trading_bot.log 2>&1 & echo \'봇 시작됨\'"'
            result = subprocess.run(restart_cmd, shell=True, capture_output=True, text=True)

            if result.returncode == 0:
                print("✅ 봇 재시작 완료")
                print(result.stdout)
            else:
                print(f"⚠️ 봇 재시작 실패: {result.stderr}")

        return True

    except Exception as e:
        print(f"\n❌ 업로드 중 오류 발생: {e}")
        return False

if __name__ == "__main__":
    try:
        upload_configs()
    except KeyboardInterrupt:
        print("\n\n❌ 사용자가 취소했습니다.")
        sys.exit(1)
