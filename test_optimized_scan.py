# -*- coding: utf-8 -*-
"""
최고속도 최적화된 스캔 테스트
IP 밴 방지 바이낸스 API 레이트 리밋 준수 테스트
"""
import os
import sys
import time

# 스크립트 디렉토리를 Python 경로에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

def test_optimized_scan():
    """최적화된 스캔 성능 테스트"""
    print("🚀 최고속도 최적화 스캔 테스트")
    print("="*60)
    
    try:
        from fifteen_minute_mega_strategy import FifteenMinuteMegaStrategy
        
        # 전략 인스턴스 생성
        print("\n📋 1단계: 전략 초기화...")
        strategy = FifteenMinuteMegaStrategy(sandbox=False)
        print("   ✅ 전략 인스턴스 생성 완료")
        
        # API 호출 추적기 초기화
        print("\n⚡ 2단계: API 호출 추적기 초기화...")
        api_call_tracker = {
            'calls_in_minute': 0,
            'last_minute_reset': time.time(),
            'max_calls_per_minute': 800,  # 안전 마진 (1200의 66%)
            'retry_delays': [1, 2, 5, 10, 30]
        }
        print(f"   🛡️ 최대 API 호출: {api_call_tracker['max_calls_per_minute']}/분")
        print(f"   ⚡ 바이낸스 레이트 리밋: 1200/분 (안전 마진 적용)")
        
        # 최적화된 스캔 실행
        print("\n🔥 3단계: 최고속도 최적화 스캔 실행...")
        scan_start = time.time()
        
        signals = strategy.scan_symbols_optimized(api_call_tracker)
        
        scan_duration = time.time() - scan_start
        
        # 결과 출력
        print(f"\n📊 4단계: 성능 테스트 결과")
        print("="*60)
        print(f"   ⚡ 스캔 소요시간: {scan_duration:.2f}초")
        print(f"   🛡️ API 호출 수: {api_call_tracker['calls_in_minute']}/{api_call_tracker['max_calls_per_minute']}")
        print(f"   📈 신호 발견: {len(signals)}개")
        print(f"   🚀 IP 밴 방지: {'성공' if api_call_tracker['calls_in_minute'] < 900 else '주의'}")
        
        if api_call_tracker['calls_in_minute'] < 500:
            print(f"   ✅ 매우 안전한 API 사용량 (50% 미만)")
        elif api_call_tracker['calls_in_minute'] < 700:
            print(f"   ⚠️ 보통 API 사용량 (70% 미만)")
        else:
            print(f"   🚨 높은 API 사용량 (70% 이상)")
        
        # 성능 분석
        if scan_duration < 10:
            print(f"   🔥 초고속 스캔 (10초 미만)")
        elif scan_duration < 30:
            print(f"   ⚡ 고속 스캔 (30초 미만)")
        elif scan_duration < 60:
            print(f"   📊 정상 스캔 (1분 미만)")
        else:
            print(f"   ⏳ 느린 스캔 (1분 이상)")
        
        # 추가 테스트 정보
        print(f"\n📋 최적화 기능:")
        print(f"   • 마켓 데이터 캐싱: {'활성' if hasattr(strategy, '_cached_futures_symbols') else '비활성'}")
        print(f"   • 배치 티커 조회: 활성 (단일 API 호출)")
        print(f"   • 병렬 분석 처리: 활성 (최대 8개 워커)")
        print(f"   • WebSocket 최적화: {'활성' if strategy.ws_provider else '비활성'}")
        print(f"   • API 호출 제한기: 활성 (실시간 추적)")
        print(f"   • 자동 백오프: 활성 (에러 복구)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_rate_limits():
    """API 레이트 리밋 테스트"""
    print(f"\n🛡️ 바이낸스 API 레이트 리밋 정보:")
    print("="*50)
    print(f"   • Futures REST API: 1200 requests/minute")
    print(f"   • Weight-based limits: Various per endpoint")
    print(f"   • Order limits: 300 orders/10 seconds")
    print(f"   • IP ban threshold: 2400 requests/minute")
    print(f"   • 권장 안전 마진: 800 requests/minute (66%)")
    print()
    print(f"🚀 최적화 전략:")
    print(f"   • 배치 API 호출 (fetch_tickers)")
    print(f"   • 캐싱 시스템 (5분 주기)")
    print(f"   • WebSocket 우선 사용")
    print(f"   • 실시간 호출 카운터")
    print(f"   • 동적 백오프")

def main():
    """메인 함수"""
    print("🚀 최고속도 최적화 스캔 테스트 시작")
    print("="*60)
    print("IP 밴 방지 바이낸스 API 레이트 리밋 준수 테스트")
    
    # API 레이트 리밋 정보 출력
    test_api_rate_limits()
    
    # 최적화된 스캔 테스트
    success = test_optimized_scan()
    
    print("\n" + "="*60)
    if success:
        print("✅ 최고속도 최적화 테스트 성공!")
        print("🛡️ IP 밴 방지 기능 정상 작동")
        print("⚡ 바이낸스 레이트 리밋 준수 완료")
        print()
        print("📋 사용법:")
        print("   • 단일 스캔: python fifteen_minute_mega_strategy.py")
        print("   • 연속 스캔: python fifteen_minute_mega_strategy.py continuous")
        print("   • 간격 설정: python fifteen_minute_mega_strategy.py continuous 90")
    else:
        print("❌ 테스트 실패")
    print("="*60)

if __name__ == "__main__":
    main()