#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

def find_ma_messages():
    file_path = "C:\\Project\\Alpha_Z\\workspace-251030\\one_minute_surge_entry_strategy.py"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        print("MA shortage messages found:")
        print("=" * 40)
        
        # Find "MA 지표 부족" messages
        for i, line in enumerate(lines, 1):
            if "MA 지표 부족" in line:
                print(f"Line {i}: {line.strip()}")
                print("Context:")
                for j in range(max(0, i-3), min(len(lines), i+3)):
                    marker = ">>>" if j+1 == i else "   "
                    print(f"  {marker}{j+1}: {lines[j]}")
                print()
        
        # Find return statements with "부족"
        print("Return statements with 부족:")
        for i, line in enumerate(lines, 1):
            if "return" in line and "부족" in line:
                print(f"Line {i}: {line.strip()}")
                
        # Find lines that generate the message
        print("\nLines that might generate the message:")
        for i, line in enumerate(lines, 1):
            if "지표" in line and "부족" in line and "조건" in line:
                print(f"Line {i}: {line.strip()}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_ma_messages()