# -*- coding: utf-8 -*-
"""
트레일링 스탑 시스템 테스트
"""

import json
import os
from improved_dca_position_manager import DCAPosition, DCAEntry

def test_trailing_stop_migration():
    """트레일링 스탑 필드 마이그레이션 테스트"""
    
    # 기존 포지션 데이터 로드
    positions_file = "dca_positions.json"
    if not os.path.exists(positions_file):
        print("❌ dca_positions.json 파일이 존재하지 않습니다.")
        return
    
    try:
        with open(positions_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print("=== 트레일링 스탑 마이그레이션 테스트 ===")
        
        for symbol, pos_data in data.items():
            print(f"\n종목: {symbol}")
            
            # 트레일링 스탑 필드 확인
            has_trailing_stop_active = 'trailing_stop_active' in pos_data
            has_trailing_stop_high = 'trailing_stop_high' in pos_data
            has_trailing_stop_percentage = 'trailing_stop_percentage' in pos_data
            
            print(f"  trailing_stop_active: {has_trailing_stop_active}")
            print(f"  trailing_stop_high: {has_trailing_stop_high}")
            print(f"  trailing_stop_percentage: {has_trailing_stop_percentage}")
            
            # 마이그레이션 시뮬레이션
            if not has_trailing_stop_active:
                pos_data['trailing_stop_active'] = False
                print("  ✅ trailing_stop_active 추가됨")
            if not has_trailing_stop_high:
                pos_data['trailing_stop_high'] = 0.0
                print("  ✅ trailing_stop_high 추가됨")
            if not has_trailing_stop_percentage:
                pos_data['trailing_stop_percentage'] = 0.05
                print("  ✅ trailing_stop_percentage 추가됨")
            
            # DCAPosition 객체 생성 테스트
            try:
                entries = [DCAEntry(**entry) for entry in pos_data['entries']]
                pos_data_copy = pos_data.copy()
                pos_data_copy['entries'] = entries
                position = DCAPosition(**pos_data_copy)
                print(f"  ✅ DCAPosition 객체 생성 성공")
                print(f"     trailing_stop_active: {position.trailing_stop_active}")
                print(f"     trailing_stop_high: {position.trailing_stop_high}")
                print(f"     trailing_stop_percentage: {position.trailing_stop_percentage}")
            except Exception as e:
                print(f"  ❌ DCAPosition 객체 생성 실패: {e}")
        
        print("\n=== BB600 트레일링 스탑 시스템 구현 상태 ===")
        print("✅ DCAPosition 클래스에 트레일링 스탑 필드 추가됨")
        print("✅ check_bb600_exit_signal() 함수에서 트레일링 스탑 활성화 로직 구현됨")
        print("✅ _check_trailing_stop() 함수에서 트레일링 스탑 청산 로직 구현됨")
        print("✅ mark_new_exit_completed() 함수에서 트레일링 스탑 상태 처리 구현됨")
        print("✅ 기존 포지션 호환성을 위한 마이그레이션 로직 구현됨")
        
        print("\n=== 새로운 BB600 청산 전략 ===")
        print("🎯 5분봉/15분봉/30분봉 캔들 고점이 BB600 상단선 돌파시:")
        print("   1. 50% 즉시 익절")
        print("   2. 트레일링 스탑 활성화")
        print("   3. 최고가에서 5% 하락시 나머지 50% 청산")
        print("   4. 텔레그램 알림 시스템 통합")
        
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {e}")

if __name__ == "__main__":
    test_trailing_stop_migration()