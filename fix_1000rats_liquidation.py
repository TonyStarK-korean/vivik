#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1000RATS 청산 동기화 수정
"""

import sys
import os

# 스크립트 디렉토리를 Python 경로에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from improved_dca_position_manager import ImprovedDCAPositionManager

def main():
    print("=== 1000RATS 청산 동기화 수정 ===")
    
    try:
        # DCA 매니저 초기화
        dca_manager = ImprovedDCAPositionManager()
        
        # 1000RATS 포지션 확인
        symbol = "1000RATS/USDT:USDT"
        
        if symbol in dca_manager.positions:
            position = dca_manager.positions[symbol]
            print(f"포지션 발견: {symbol}")
            print(f"  활성 상태: {position.is_active}")
            print(f"  평단가: ${position.average_price:.6f}")
            print(f"  수량: {position.total_quantity}")
            print(f"  최대 수익률: {position.max_profit_pct*100:.1f}%")
            
            # 청산 통지 실행
            print(f"\n청산 통지 실행...")
            result = dca_manager.notify_liquidation_from_strategy(
                symbol, 
                "manual_fix_breakeven_protection"
            )
            
            if result:
                print("✅ 청산 통지 완료 - DCA 포지션에서 제거됨")
            else:
                print("❌ 청산 통지 실패")
                
        else:
            print(f"❌ {symbol} 포지션을 찾을 수 없습니다")
            
        # 남은 활성 포지션 확인
        active_positions = dca_manager.get_active_positions()
        print(f"\n남은 활성 포지션: {len(active_positions)}개")
        for sym, pos in active_positions.items():
            clean_sym = sym.replace('/USDT:USDT', '')
            max_profit = pos.max_profit_pct * 100
            print(f"  {clean_sym}: 최대 {max_profit:.1f}%")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()