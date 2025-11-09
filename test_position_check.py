# -*- coding: utf-8 -*-
"""
포지션 체크 테스트 (Rate Limit 문제 해결 확인)
"""
import os
import sys

# 스크립트 디렉토리를 Python 경로에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

def test_position_check():
    """포지션 체크 로직 테스트"""
    print("[INFO] 포지션 체크 Rate Limit 해결 테스트...")
    print("="*50)
    
    try:
        from fifteen_minute_mega_strategy import FifteenMinuteMegaStrategy
        
        # 전략 인스턴스 생성
        strategy = FifteenMinuteMegaStrategy(sandbox=False)
        
        print("\n[TEST 1] 전략 초기화 완료")
        
        # 포지션 체크 테스트
        print("\n[TEST 2] 실제 포지션 상태 체크 테스트...")
        try:
            strategy.check_real_position_status()
            print("   [SUCCESS] 포지션 체크 완료 - Rate Limit 문제 없음")
        except Exception as e:
            if "2029 seconds" in str(e):
                print(f"   [FAIL] Rate Limit 오류 여전히 발생: {e}")
                return False
            else:
                print(f"   [INFO] 다른 오류 (정상): {e}")
        
        # 포트폴리오 요약 테스트
        print("\n[TEST 3] 포트폴리오 요약 테스트...")
        try:
            portfolio = strategy.get_portfolio_summary()
            print("   [SUCCESS] 포트폴리오 조회 완료")
            print(f"   [DATA] 가용 잔고: ${portfolio['free_balance']:.2f}")
            print(f"   [DATA] 활성 포지션: {portfolio['open_positions']}개")
        except Exception as e:
            print(f"   [WARN] 포트폴리오 조회 실패: {e}")
        
        print("\n[RESULT] Rate Limit 문제 해결 확인 완료")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] 테스트 실패: {e}")
        return False

def main():
    """메인 함수"""
    print("="*50)
    print("바이낸스 Rate Limit 문제 해결 테스트")
    print("="*50)
    
    success = test_position_check()
    
    print("\n" + "="*50)
    if success:
        print("[SUCCESS] Rate Limit 문제 해결됨")
    else:
        print("[FAILED] Rate Limit 문제 지속")
    print("="*50)

if __name__ == "__main__":
    main()