#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚨 바이낸스 IP 밴 복구 도구
실시간 밴 상태 확인 및 복구 시간 예측
"""

import time
import requests
import json
from datetime import datetime, timedelta

class BinanceIPBanRecovery:
    """바이낸스 IP 밴 상태 확인 및 복구 도구"""
    
    def __init__(self):
        self.test_url = "https://fapi.binance.com/fapi/v1/ping"  # 가장 가벼운 엔드포인트
        self.ban_detected_time = None
        self.last_success_time = None
        
    def check_ban_status(self):
        """현재 IP 밴 상태 확인"""
        try:
            response = requests.get(self.test_url, timeout=5)
            
            if response.status_code == 200:
                print("✅ API 접근 가능 - 밴 해제됨!")
                self.last_success_time = time.time()
                return False
            elif response.status_code == 418:
                retry_after = response.headers.get('retry-after', 'unknown')
                print(f"🔒 IP 밴 확인됨 (418) - Retry-After: {retry_after}초")
                if self.ban_detected_time is None:
                    self.ban_detected_time = time.time()
                return True
            elif response.status_code == 429:
                print("⚠️ Rate Limit (429) - 잠시 후 재시도 필요")
                return True
            else:
                print(f"❓ 알 수 없는 응답: {response.status_code}")
                return True
                
        except requests.exceptions.RequestException as e:
            print(f"🌐 네트워크 오류: {e}")
            return True
    
    def estimate_recovery_time(self):
        """밴 해제 시간 예측"""
        if self.ban_detected_time is None:
            return "밴 시작 시간 불명"
            
        elapsed = time.time() - self.ban_detected_time
        elapsed_minutes = elapsed / 60
        
        # 바이낸스 IP 밴 일반적인 패턴
        if elapsed_minutes < 10:
            return f"최소 10분 대기 필요 (현재 {elapsed_minutes:.1f}분 경과)"
        elif elapsed_minutes < 30:
            return f"보통 30분 내 해제 (현재 {elapsed_minutes:.1f}분 경과)"
        elif elapsed_minutes < 120:
            return f"최대 2시간 소요 가능 (현재 {elapsed_minutes:.1f}분 경과)"
        else:
            return f"심각한 밴 - 24시간 소요 가능 (현재 {elapsed_minutes:.1f}분 경과)"
    
    def get_alternative_solutions(self):
        """대안 해결책"""
        return """
🛠️ 즉시 해결 방법들:

1. 🔄 IP 변경 (가장 확실함)
   - 공유기 재부팅 (5분)
   - VPN 사용
   - 모바일 핫스팟 사용

2. 🔑 API 키 변경
   - 바이낸스에서 새 API 키 생성
   - 기존 키 삭제 후 새 키 적용

3. 🌐 프록시 사용
   - 프록시 서버 경유
   - CDN 서비스 이용

4. 📱 다른 네트워크
   - 모바일 데이터 사용
   - 다른 위치에서 접속

5. ⏰ 대기 (마지막 수단)
   - 최소 30분~2시간 대기
   - 심각한 경우 24시간
"""
    
    def continuous_monitoring(self):
        """지속적인 밴 상태 모니터링"""
        print("🔍 바이낸스 IP 밴 상태 모니터링 시작...")
        print("Ctrl+C로 중단")
        print("-" * 50)
        
        try:
            while True:
                current_time = datetime.now().strftime("%H:%M:%S")
                print(f"\n⏰ {current_time} - 밴 상태 확인 중...")
                
                is_banned = self.check_ban_status()
                
                if not is_banned:
                    print("🎉 밴 해제 완료! 트레이딩 재개 가능!")
                    break
                else:
                    estimate = self.estimate_recovery_time()
                    print(f"📊 예상 복구 시간: {estimate}")
                
                print("30초 후 재확인...")
                time.sleep(30)
                
        except KeyboardInterrupt:
            print("\n🛑 모니터링 중단됨")
    
    def quick_recovery_guide(self):
        """빠른 복구 가이드"""
        print("🚨 바이낸스 IP 밴 빠른 복구 가이드")
        print("=" * 50)
        
        # 현재 상태 확인
        is_banned = self.check_ban_status()
        
        if not is_banned:
            print("✅ 현재 밴 상태 아님 - 트레이딩 가능!")
            return
            
        print("\n🔴 IP 밴 확인됨")
        print(self.estimate_recovery_time())
        print(self.get_alternative_solutions())
        
        choice = input("\n⚡ 지속적으로 모니터링 하시겠습니까? (y/n): ")
        if choice.lower() == 'y':
            self.continuous_monitoring()

def main():
    """메인 실행 함수"""
    recovery_tool = BinanceIPBanRecovery()
    recovery_tool.quick_recovery_guide()

if __name__ == "__main__":
    main()