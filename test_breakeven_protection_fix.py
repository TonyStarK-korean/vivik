#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
본절청산 로직 수정 테스트
"""

def test_original_logic():
    """기존 로직 (문제 있음)"""
    print("=== 기존 로직 (문제 있음) ===")
    
    # 시나리오: 최대 수익 8%, 현재 손실 -2%
    max_profit_pct = 0.08  # 8% 최대 수익
    current_profit_pct = -0.02  # -2% 현재 손실
    half_drop_threshold = max_profit_pct * 0.5  # 4% 임계값
    
    print(f"최대 수익률: {max_profit_pct*100:.1f}%")
    print(f"현재 수익률: {current_profit_pct*100:.1f}%")
    print(f"절반 하락 임계값: {half_drop_threshold*100:.1f}%")
    
    # 기존 로직
    old_condition = current_profit_pct <= half_drop_threshold
    print(f"기존 조건 ({current_profit_pct:.3f} <= {half_drop_threshold:.3f}): {old_condition}")
    
    if old_condition:
        print("❌ 문제: 손실 상태에서도 본절청산 발동!")
    else:
        print("✅ 청산 안함")

def test_fixed_logic():
    """수정된 로직 (정상)"""
    print("\n=== 수정된 로직 (정상) ===")
    
    # 시나리오: 최대 수익 8%, 현재 손실 -2%
    max_profit_pct = 0.08  # 8% 최대 수익
    current_profit_pct = -0.02  # -2% 현재 손실
    half_drop_threshold = max_profit_pct * 0.5  # 4% 임계값
    
    print(f"최대 수익률: {max_profit_pct*100:.1f}%")
    print(f"현재 수익률: {current_profit_pct*100:.1f}%")
    print(f"절반 하락 임계값: {half_drop_threshold*100:.1f}%")
    
    # 수정된 로직: 양수 범위에서만 검사
    new_condition = current_profit_pct > 0 and current_profit_pct <= half_drop_threshold
    print(f"수정된 조건 ({current_profit_pct:.3f} > 0 and {current_profit_pct:.3f} <= {half_drop_threshold:.3f}): {new_condition}")
    
    if new_condition:
        print("✅ 청산 발동")
    else:
        print("✅ 정상: 손실 상태에서는 본절청산 안함")

def test_positive_scenarios():
    """양수 시나리오 테스트"""
    print("\n=== 양수 시나리오 테스트 ===")
    
    scenarios = [
        {"max": 0.08, "current": 0.06, "desc": "8% 최대 → 6% 현재 (정상 범위)"},
        {"max": 0.08, "current": 0.03, "desc": "8% 최대 → 3% 현재 (절반 하락 근처)"},
        {"max": 0.08, "current": 0.04, "desc": "8% 최대 → 4% 현재 (절반 하락 임계점)"},
        {"max": 0.08, "current": 0.039, "desc": "8% 최대 → 3.9% 현재 (절반 하락)"},
    ]
    
    for scenario in scenarios:
        max_profit = scenario["max"]
        current_profit = scenario["current"]
        half_threshold = max_profit * 0.5
        
        print(f"\n{scenario['desc']}:")
        print(f"  임계값: {half_threshold*100:.1f}%")
        
        # 수정된 조건
        should_exit = current_profit > 0 and current_profit <= half_threshold
        print(f"  청산 여부: {'✅ 청산' if should_exit else '❌ 유지'}")

def main():
    print("본절청산 로직 수정 테스트")
    print("=" * 50)
    
    test_original_logic()
    test_fixed_logic()
    test_positive_scenarios()
    
    print("\n" + "=" * 50)
    print("🎯 수정 완료:")
    print("  1. 메인 전략 파일: line 6259 수정")
    print("  2. DCA 매니저: line 3041, 3048 수정")
    print("  3. 조건: current_profit_pct > 0 조건 추가")
    print("  4. 효과: 손실시 본절청산 발동 방지")

if __name__ == "__main__":
    main()