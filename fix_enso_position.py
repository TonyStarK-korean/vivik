# -*- coding: utf-8 -*-
"""
ENSO 포지션 데이터 수정 도구
DCA 중복 진입 문제 해결
"""

import json
import os
from datetime import datetime, timezone, timedelta

def fix_enso_position():
    """ENSO 포지션의 잘못된 DCA 데이터 수정"""
    
    positions_file = "dca_positions.json"
    backup_file = "dca_positions_backup_before_enso_fix.json"
    
    if not os.path.exists(positions_file):
        print("❌ dca_positions.json 파일이 존재하지 않습니다.")
        return
    
    try:
        # 백업 생성
        with open(positions_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ 백업 생성: {backup_file}")
        
        # ENSO 포지션 수정
        if "ENSO/USDT:USDT" in data:
            enso_position = data["ENSO/USDT:USDT"]
            
            print("=== ENSO 포지션 수정 전 상태 ===")
            print(f"Total quantity: {enso_position['total_quantity']}")
            print(f"Average price: {enso_position['average_price']}")
            print(f"Total notional: {enso_position['total_notional']}")
            print(f"Entries count: {len(enso_position['entries'])}")
            
            # 잘못된 DCA 진입 제거 - 초기 진입만 남김
            original_entries = enso_position['entries']
            initial_entry = None
            
            for entry in original_entries:
                if entry['stage'] == 'initial':
                    initial_entry = entry
                    break
            
            if initial_entry:
                # 초기 진입만 남기고 DCA 제거
                enso_position['entries'] = [initial_entry]
                enso_position['current_stage'] = 'initial'
                enso_position['average_price'] = initial_entry['entry_price']
                enso_position['total_quantity'] = initial_entry['quantity']
                enso_position['total_notional'] = initial_entry['notional']
                enso_position['last_update'] = datetime.now(timezone(timedelta(hours=9))).isoformat()
                
                print("\n=== ENSO 포지션 수정 후 상태 ===")
                print(f"Total quantity: {enso_position['total_quantity']}")
                print(f"Average price: {enso_position['average_price']}")
                print(f"Total notional: {enso_position['total_notional']}")
                print(f"Entries count: {len(enso_position['entries'])}")
                print(f"Entry price: {initial_entry['entry_price']}")
                
                # 수정된 데이터 저장
                with open(positions_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                print("✅ ENSO 포지션 수정 완료")
                
                # 현재 손실률 계산 (임시 - 실제 현재가 $1.32 기준)
                current_price = 1.32
                profit_pct = (current_price - initial_entry['entry_price']) / initial_entry['entry_price'] * 100
                print(f"\n현재가 ${current_price:.3f} 기준 손익률: {profit_pct:.2f}%")
                
            else:
                print("❌ 초기 진입 데이터를 찾을 수 없습니다.")
        else:
            print("❌ ENSO 포지션을 찾을 수 없습니다.")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    fix_enso_position()