#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
메인 전략 active_positions에서 1000RATS 제거
"""

import sys
import os
import json

def main():
    print("=== 메인 전략 포지션에서 1000RATS 제거 ===")
    
    try:
        # active_positions.json 파일 확인
        positions_file = "active_positions.json"
        
        if os.path.exists(positions_file):
            with open(positions_file, 'r', encoding='utf-8') as f:
                positions = json.load(f)
            
            print(f"현재 활성 포지션: {len(positions)}개")
            for symbol in positions.keys():
                clean_symbol = symbol.replace('/USDT:USDT', '')
                print(f"  - {clean_symbol}")
            
            symbol_to_remove = "1000RATS/USDT:USDT"
            
            if symbol_to_remove in positions:
                print(f"\n🎯 {symbol_to_remove} 발견 - 제거 중...")
                del positions[symbol_to_remove]
                
                # 파일 저장
                with open(positions_file, 'w', encoding='utf-8') as f:
                    json.dump(positions, f, indent=2, ensure_ascii=False)
                
                print(f"✅ {symbol_to_remove} 제거 완료")
                print(f"남은 포지션: {len(positions)}개")
                
                for symbol in positions.keys():
                    clean_symbol = symbol.replace('/USDT:USDT', '')
                    print(f"  - {clean_symbol}")
                    
            else:
                print(f"❌ {symbol_to_remove}를 찾을 수 없습니다")
                
        else:
            print(f"❌ {positions_file} 파일을 찾을 수 없습니다")
            
        # 다른 포지션 파일들도 확인
        other_files = [
            "positions.json",
            "active_positions_backup.json"
        ]
        
        for file_name in other_files:
            if os.path.exists(file_name):
                print(f"\n📁 {file_name} 확인 중...")
                try:
                    with open(file_name, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if "1000RATS/USDT:USDT" in data:
                        print(f"  🎯 1000RATS 발견 - 제거 중...")
                        del data["1000RATS/USDT:USDT"]
                        
                        with open(file_name, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        
                        print(f"  ✅ {file_name}에서 1000RATS 제거 완료")
                    else:
                        print(f"  ✅ {file_name}에는 1000RATS 없음")
                        
                except json.JSONDecodeError:
                    print(f"  ❌ {file_name} JSON 파싱 오류")
                except Exception as e:
                    print(f"  ❌ {file_name} 처리 오류: {e}")
            else:
                print(f"📁 {file_name} 파일 없음")
                
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()