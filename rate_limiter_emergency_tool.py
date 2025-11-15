#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚨 Rate Limiter 긴급 복구 도구
바이낸스 API Rate Limit 초과시 긴급 복구 및 상태 확인 도구
"""

import os
import json
import time
from datetime import datetime
from binance_rate_limiter import BinanceRateLimiter

class RateLimiterEmergencyTool:
    def __init__(self):
        self.rate_limiter = BinanceRateLimiter()
        
    def check_status(self):
        """현재 Rate Limiter 상태 확인"""
        print("🔍 Rate Limiter 상태 확인...")
        print("=" * 50)
        
        status = self.rate_limiter.get_status()
        
        # 기본 상태
        print(f"Rate Limited: {'🚨 예' if status['rate_limited'] else '✅ 아니오'}")
        print(f"현재 Weight: {status['current_weight']}/{status['max_weight']}")
        print(f"Weight 사용률: {status['weight_usage_pct']:.1f}%")
        print(f"분당 요청 수: {status['requests_per_minute']}")
        
        # 차단 상태
        print(f"\nIP 차단 상태: {status['ban_status']}")
        if status['ban_remaining_seconds'] > 0:
            print(f"차단 해제까지: {status['ban_remaining_seconds']}초")
            
        # 백오프 상태  
        if status['backoff_remaining_seconds'] > 0:
            print(f"429 백오프 남은 시간: {status['backoff_remaining_seconds']}초")
            
        print(f"연속 429 에러: {status['consecutive_429s']}회")
        print(f"백오프 배수: {status['backoff_multiplier']:.1f}x")
        
        # 에러 통계
        print(f"\n에러 통계:")
        for error_code, count in status['error_stats'].items():
            print(f"  {error_code}: {count}회")
            
        print(f"캐시 크기: {status['cache_size']}개")
        
        return status
        
    def emergency_reset(self):
        """긴급 리셋 (주의: 남용 금지)"""
        print("🚨 긴급 리셋을 진행하시겠습니까?")
        print("⚠️  주의: 이 작업은 Rate Limiter 상태를 완전히 초기화합니다.")
        print("⚠️  바이낸스 서버의 실제 Rate Limit은 리셋되지 않습니다!")
        
        confirm = input("정말로 리셋하시겠습니까? (yes/no): ")
        if confirm.lower() != 'yes':
            print("취소되었습니다.")
            return
            
        # 상태 파일 삭제
        state_file = 'binance_rate_limiter_state.json'
        if os.path.exists(state_file):
            os.remove(state_file)
            print(f"✅ {state_file} 삭제됨")
            
        # Rate Limiter 재초기화
        self.rate_limiter = BinanceRateLimiter()
        print("✅ Rate Limiter 재초기화 완료")
        
        # 통계 리셋
        self.rate_limiter.reset_stats()
        print("✅ 통계 리셋 완료")
        
        print("\n🎉 긴급 리셋 완료!")
        print("⚠️  주의: 실제 바이낸스 서버의 Rate Limit은 시간이 지나야 해제됩니다.")
        
    def wait_for_recovery(self):
        """복구까지 대기"""
        print("⏳ Rate Limit 복구까지 대기 중...")
        
        while True:
            status = self.rate_limiter.get_status()
            
            if not status['rate_limited']:
                print("✅ Rate Limit 해제됨!")
                break
                
            remaining_time = max(
                status.get('ban_remaining_seconds', 0),
                status.get('backoff_remaining_seconds', 0)
            )
            
            if remaining_time > 0:
                print(f"⏳ 남은 시간: {remaining_time}초...", end='\r')
            else:
                print("⏳ Weight 대기 중...", end='\r')
                
            time.sleep(5)
            
    def clear_cache(self):
        """캐시 모두 삭제"""
        print("🧹 캐시 정리 중...")
        self.rate_limiter._response_cache.clear()
        print("✅ 캐시 정리 완료")
        
    def set_conservative_mode(self):
        """보수적 모드 설정 (더 엄격한 제한)"""
        print("🛡️ 보수적 모드 설정 중...")
        self.rate_limiter._max_weight_per_minute = 800  # 더욱 보수적
        print("✅ 최대 weight을 800으로 설정 (기본 1000에서 감소)")
        
    def show_help(self):
        """도움말 표시"""
        print("🆘 Rate Limiter 긴급 복구 도구")
        print("=" * 40)
        print("1. status  - 현재 상태 확인")
        print("2. reset   - 긴급 리셋 (주의)")
        print("3. wait    - 복구까지 대기")
        print("4. cache   - 캐시 정리")
        print("5. safe    - 보수적 모드 설정")
        print("6. help    - 이 도움말")
        print("7. exit    - 종료")
        
def main():
    tool = RateLimiterEmergencyTool()
    
    print("🚨 Rate Limiter 긴급 복구 도구")
    print("현재 시간:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print()
    
    # 초기 상태 확인
    tool.check_status()
    
    while True:
        print("\n" + "=" * 50)
        command = input("명령어 입력 (help 입력시 도움말): ").strip().lower()
        
        if command == 'status':
            tool.check_status()
        elif command == 'reset':
            tool.emergency_reset()
        elif command == 'wait':
            tool.wait_for_recovery()
        elif command == 'cache':
            tool.clear_cache()
        elif command == 'safe':
            tool.set_conservative_mode()
        elif command == 'help':
            tool.show_help()
        elif command in ['exit', 'quit', 'q']:
            print("👋 종료합니다.")
            break
        else:
            print("❌ 알 수 없는 명령어입니다. 'help'를 입력하세요.")

if __name__ == "__main__":
    main()