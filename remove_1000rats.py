#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1000RATS 완전 제거
"""

import json
import os

def main():
    print("=== 1000RATS 완전 제거 ===")
    
    try:
        # DCA 포지션에서 제거
        dca_file = "dca_positions.json"
        if os.path.exists(dca_file):
            with open(dca_file, 'r', encoding='utf-8') as f:
                dca_data = json.load(f)
            
            if "1000RATS/USDT:USDT" in dca_data:
                print("DCA 포지션에서 1000RATS 제거 중...")
                del dca_data["1000RATS/USDT:USDT"]
                
                with open(dca_file, 'w', encoding='utf-8') as f:
                    json.dump(dca_data, f, indent=2, ensure_ascii=False)
                
                print("DCA 포지션에서 1000RATS 제거 완료")
            else:
                print("DCA 포지션에 1000RATS 없음")
        
        # 백업 파일에서도 제거
        backup_file = "dca_positions_backup.json"
        if os.path.exists(backup_file):
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            if "1000RATS/USDT:USDT" in backup_data:
                print("백업 파일에서 1000RATS 제거 중...")
                del backup_data["1000RATS/USDT:USDT"]
                
                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, indent=2, ensure_ascii=False)
                
                print("백업 파일에서 1000RATS 제거 완료")
            else:
                print("백업 파일에 1000RATS 없음")
        
        # 활성 포지션에서도 제거
        active_file = "active_positions.json"
        if os.path.exists(active_file):
            with open(active_file, 'r', encoding='utf-8') as f:
                active_data = json.load(f)
            
            if "1000RATS/USDT:USDT" in active_data:
                print("활성 포지션에서 1000RATS 제거 중...")
                del active_data["1000RATS/USDT:USDT"]
                
                with open(active_file, 'w', encoding='utf-8') as f:
                    json.dump(active_data, f, indent=2, ensure_ascii=False)
                
                print("활성 포지션에서 1000RATS 제거 완료")
            else:
                print("활성 포지션에 1000RATS 없음")
        
        print("\n=== 제거 완료 ===")
        print("1000RATS 포지션이 모든 파일에서 제거되었습니다.")
        
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    main()