# -*- coding: utf-8 -*-
"""
완화된 조건으로 테스트
"""

def create_relaxed_test():
    """완화된 조건으로 테스트"""
    print("=== 완화된 조 테스트 ===")
    
    print("현재 문제:")
    print("1. MA480 유효 데이터 부족 (21/480)")
    print("2. 시장 변동률 매우 낮음 (BTC 0.35%, ETH 1.11%)")
    print("3. 4시간봉 급등 조 미충족 (2% 이상 급등 0)")
    
    print("\n임시 해결책:")
    print("1. MA480 조을 MA80으로 대체")
    print("2. 4시간봉 급등 기준을 2% → 1%로 완화")
    print("3. 변동률 필터 기준을 8% → 3%로 완화")
    print("4. 일봉 조 완화")
    
    print("\n추천 조치:")
    print("1. 시장이 Activated될 때까지 Waiting")
    print("2. 또는 조을 일시적으로 완화하여 테스트")
    print("3. 더 많은 기간의 데이터 수집 (480일 이상)")
    
    # 실제 완화 조건 제안
    print("\n=== 완화 조 제안 ===")
    print("변경 전:")
    print("- 4시간봉 급등: 2% 이상")
    print("- MA480 조 필수")
    print("- 변동률 필터: 8% 이상")
    print("- 일봉 15% 이상 캔들 필요")
    
    print("\n변경 후 (임시):")
    print("- 4시간봉 급등: 1% 이상")
    print("- MA80 조으로 대체")
    print("- 변동률 필터: 3% 이상")
    print("- 일봉 10% 이상 캔들 허용")
    
    return {
        'surge_threshold': 1.0,  # 2.0 → 1.0
        'change_pct_filter': 3.0,  # 8.0 → 3.0
        'daily_surge_threshold': 10.0,  # 15.0 → 10.0
        'use_ma80_instead_ma480': True
    }

if __name__ == "__main__":
    relaxed_params = create_relaxed_test()
    print(f"\n완화된 파라미터: {relaxed_params}")