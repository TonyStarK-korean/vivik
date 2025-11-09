#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
바이낸스 IP 밴 상태 간단 확인
"""

import requests
import time
from datetime import datetime

def check_binance_access():
    """바이낸스 API 접근 가능 여부 확인"""
    try:
        print("바이낸스 API 상태 확인 중...")
        response = requests.get("https://fapi.binance.com/fapi/v1/ping", timeout=10)
        
        if response.status_code == 200:
            print("✅ 성공! IP 밴 없음 - 바로 트레이딩 가능!")
            return True
        elif response.status_code == 418:
            retry_after = response.headers.get('retry-after', 'unknown')
            print(f"❌ IP 밴 확인됨 (418)")
            if retry_after != 'unknown':
                wait_minutes = int(retry_after) // 60
                print(f"대기 시간: {retry_after}초 ({wait_minutes}분)")
            return False
        elif response.status_code == 429:
            print("⚠️ Rate Limit (429) - 잠시 후 해제됨")
            return False
        else:
            print(f"알 수 없는 상태: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"네트워크 오류: {e}")
        return False

def show_recovery_options():
    """복구 방법 안내"""
    print("\n=== 즉시 해결 방법 ===")
    print("1. 공유기 재부팅 (5분) - 가장 확실")
    print("2. VPN 사용")
    print("3. 모바일 핫스팟 사용") 
    print("4. 새 API 키 생성")
    print("5. 30분~2시간 대기")
    print("\n가장 빠른 방법: 공유기 재부팅!")

def main():
    print("=== 바이낸스 IP 밴 확인 도구 ===")
    print(f"확인 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("")
    
    is_ok = check_binance_access()
    
    if not is_ok:
        show_recovery_options()
        
        print("\n지속 모니터링을 원하면 'y'를 입력하세요:")
        choice = input("모니터링 시작? (y/n): ")
        
        if choice.lower() == 'y':
            print("\n30초마다 상태 확인합니다. Ctrl+C로 중단.")
            try:
                while True:
                    time.sleep(30)
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 재확인...")
                    if check_binance_access():
                        print("🎉 밴 해제! 트레이딩 재개 가능!")
                        break
            except KeyboardInterrupt:
                print("\n모니터링 중단.")

if __name__ == "__main__":
    main()