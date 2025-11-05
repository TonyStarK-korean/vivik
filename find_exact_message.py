#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def find_exact_message():
    file_path = "C:\\Project\\Alpha_Z\\workspace-251030\\one_minute_surge_entry_strategy.py"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        # 정확한 메시지 "MA 지표 부족 - 조건 체크 불가능" 찾기
        target_message = "MA 지표 부족 - 조건 체크 불가능"
        
        print(f"Looking for exact message: '{target_message}'")
        print("=" * 50)
        
        found_exact = False
        for i, line in enumerate(lines, 1):
            if target_message in line:
                print(f"EXACT MATCH at Line {i}: {line.strip()}")
                found_exact = True
                # 컨텍스트 출력
                print("Context:")
                for j in range(max(0, i-5), min(len(lines), i+5)):
                    marker = ">>>" if j+1 == i else "   "
                    print(f"  {marker}{j+1}: {lines[j]}")
                print()
        
        if not found_exact:
            print("Exact message not found. Looking for parts...")
            
            # 각 부분별로 찾기
            parts = ["MA", "지표", "부족", "조건", "체크", "불가능"]
            for part in parts:
                print(f"\nLines containing '{part}':")
                count = 0
                for i, line in enumerate(lines, 1):
                    if part in line and "return" in line:
                        count += 1
                        if count <= 3:  # 처음 3개만 출력
                            print(f"  Line {i}: {line.strip()}")
                        elif count == 4:
                            print(f"  ... (and {sum(1 for l in lines if part in l and 'return' in l) - 3} more)")
                            break
            
            # return문에서 "MA"와 "부족"이 함께 있는 경우
            print("\nReturn statements with both 'MA' and '부족':")
            for i, line in enumerate(lines, 1):
                if "return" in line and "MA" in line and "부족" in line:
                    print(f"  Line {i}: {line.strip()}")
                    # 앞뒤 컨텍스트
                    print("    Context:")
                    for j in range(max(0, i-2), min(len(lines), i+2)):
                        marker = "    >>>" if j+1 == i else "       "
                        print(f"{marker}{j+1}: {lines[j]}")
                    print()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_exact_message()