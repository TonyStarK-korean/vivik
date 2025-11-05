#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCA 재주문 시스템 테스트
"""

import json
import sys
import os

# 스크립트 디렉토리를 Python 경로에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from improved_dca_position_manager import ImprovedDCAPositionManager, DCAPosition

def load_test_positions():
    """테스트용 DCA 포지션 로드"""
    try:
        with open('dca_positions.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"포지션 파일 로드 실패: {e}")
        return {}

def analyze_reorder_scenarios(positions_data):
    """DCA 재주문이 필요한 시나리오 분석"""
    scenarios = []
    
    for symbol, position_data in positions_data.items():
        # 각 포지션의 DCA 상태 분석
        stage_status = {}
        for entry in position_data.get('entries', []):
            stage_status[entry['stage']] = {
                'is_active': entry.get('is_active', False),
                'is_filled': entry.get('is_filled', False),
                'order_id': entry.get('order_id', '')
            }
        
        # 재주문이 필요한 단계 확인
        missing_stages = []
        
        # 1차 DCA 확인
        if ('first_dca' not in stage_status or 
            not stage_status['first_dca']['is_active'] or 
            stage_status['first_dca']['is_filled']):
            missing_stages.append('first_dca')
        
        # 2차 DCA 확인  
        if ('second_dca' not in stage_status or 
            not stage_status['second_dca']['is_active'] or 
            stage_status['second_dca']['is_filled']):
            missing_stages.append('second_dca')
        
        if missing_stages:
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            cyclic_count = position_data.get('cyclic_count', 0)
            max_cyclic_count = position_data.get('max_cyclic_count', 3)
            
            scenarios.append({
                'symbol': clean_symbol,
                'full_symbol': symbol,
                'missing_stages': missing_stages,
                'cyclic_count': cyclic_count,
                'max_cyclic_count': max_cyclic_count,
                'can_reorder': cyclic_count < max_cyclic_count,
                'stage_status': stage_status
            })
    
    return scenarios

def main():
    print("=== DCA 재주문 시스템 분석 ===\n")
    
    # 현재 포지션 로드
    positions = load_test_positions()
    print(f"로드된 포지션: {len(positions)}개\n")
    
    # 재주문 시나리오 분석
    scenarios = analyze_reorder_scenarios(positions)
    
    if not scenarios:
        print("[O] 재주문이 필요한 시나리오가 없습니다.")
        return
    
    print(f"[!] 재주문이 필요한 시나리오: {len(scenarios)}개\n")
    
    for i, scenario in enumerate(scenarios, 1):
        symbol = scenario['symbol']
        missing = scenario['missing_stages']
        cyclic = f"{scenario['cyclic_count']}/{scenario['max_cyclic_count']}"
        can_reorder = "[O]" if scenario['can_reorder'] else "[X]"
        
        print(f"{i:2d}. {symbol:12s} | 순환매: {cyclic} | 재주문가능: {can_reorder}")
        print(f"    빈 단계: {', '.join(missing)}")
        
        # 상세 상태 출력
        for stage, status in scenario['stage_status'].items():
            active = "[O]" if status['is_active'] else "[X]"
            filled = "[O]" if status['is_filled'] else "[X]"
            print(f"    {stage:12s}: 활성={active} 체결={filled}")
        print()
    
    # 실제 재주문 가능한 경우
    reorderable = [s for s in scenarios if s['can_reorder']]
    if reorderable:
        print(f"[!] 실제 재주문 실행 가능: {len(reorderable)}개")
        for scenario in reorderable[:3]:  # 상위 3개만 표시
            symbol = scenario['symbol']
            missing = len(scenario['missing_stages'])
            print(f"   - {symbol}: {missing}개 단계 재주문 필요")
    
    print(f"\n[*] 요약:")
    print(f"   전체 포지션: {len(positions)}개")
    print(f"   재주문 필요: {len(scenarios)}개")
    print(f"   재주문 가능: {len(reorderable)}개")
    
    # 메서드 존재 확인
    has_method = hasattr(ImprovedDCAPositionManager, 'place_missing_dca_orders_after_partial_exit')
    method_status = "[O] 존재" if has_method else "[X] 없음"
    print(f"   재주문 메서드: {method_status}")

if __name__ == "__main__":
    main()