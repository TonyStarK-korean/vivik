#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def find_ma_messages():
    file_path = "C:\\Project\\Alpha_Z\\workspace-251030\\one_minute_surge_entry_strategy.py"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print("MA 지표 부족 메시지를 생성하는 모든 위치:")
        print("=" * 60)
        
        # 1. "MA 지표 부족" 문자열을 포함한 모든 라인 찾기
        for i, line in enumerate(lines, 1):
            if "MA 지표 부족" in line:
                print(f"라인 {i}: {line.strip()}")
                # 앞뒤 몇 줄 컨텍스트 출력
                print("  컨텍스트:")
                for j in range(max(0, i-3), min(len(lines), i+3)):
                    marker = ">>> " if j+1 == i else "    "
                    print(f"  {marker}{j+1}: {lines[j].rstrip()}")
                print()
        
        # 2. "지표 부족" 또는 "조건 체크 불가능" 패턴 찾기
        patterns = [
            r"지표.*부족",
            r"조건.*체크.*불가능",
            r"조건체크불가능"
        ]
        
        for pattern in patterns:
            print(f"\n패턴 '{pattern}' 검색 결과:")
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    print(f"라인 {i}: {line.strip()}")
        
        # 3. return문에서 "부족" 키워드가 포함된 것들 찾기
        print(f"\nreturn문에서 '부족' 키워드 포함:")
        for i, line in enumerate(lines, 1):
            if "return" in line and "부족" in line:
                print(f"라인 {i}: {line.strip()}")
                # 앞뒤 몇 줄 컨텍스트 출력
                print("  컨텍스트:")
                for j in range(max(0, i-3), min(len(lines), i+3)):
                    marker = ">>> " if j+1 == i else "    "
                    print(f"  {marker}{j+1}: {lines[j].rstrip()}")
                print()
                
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    find_ma_messages()