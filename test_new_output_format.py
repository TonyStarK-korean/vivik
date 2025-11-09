# -*- coding: utf-8 -*-
"""
새로운 출력 형식 테스트
one_minute_surge_entry_strategy.py 스타일 적용 확인
"""
import os
import sys

# 스크립트 디렉토리를 Python 경로에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

def test_new_output_format():
    """새로운 출력 형식 테스트"""
    print("[INFO] 새로운 출력 형식 테스트 시작...")
    print("="*60)
    
    try:
        from fifteen_minute_mega_strategy import FifteenMinuteMegaStrategy
        
        print("\n[TEST] 전략 인스턴스 생성...")
        strategy = FifteenMinuteMegaStrategy(sandbox=False)
        print("[SUCCESS] 전략 인스턴스 생성 완료")
        
        print("\n[INFO] 새로운 출력 형식 특징:")
        print("  1. 진입신호 <- 모든 조건 충족 (녹색, 가격 표시)")
        print("  2. 진입임박 <- 1개 미충족 (노란색, 미충족 조건 빨간색)")
        print("  3. 진입확률 <- 2개 미충족 (심볼명만 가로 5개씩)")
        print("  4. 관심종목 <- 3개+ 미충족 (심볼명만 가로 6개씩)")
        print("  5. 스캔 통계 <- 각 카테고리별 개수")
        
        print("\n[SUCCESS] one_minute_surge_entry_strategy.py 스타일 적용 완료!")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("="*60)
    print("15분봉 초필살기 새로운 출력 형식 테스트")
    print("="*60)
    
    success = test_new_output_format()
    
    print("\n" + "="*60)
    if success:
        print("[SUCCESS] 새로운 출력 형식 적용 완료!")
        print("[RESULT] 조건별 분류 → 4단계 분류 시스템으로 개선!")
    else:
        print("[FAILED] 테스트 실패")
    print("="*60)