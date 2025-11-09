#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def find_get_historical_data_method():
    with open('one_minute_surge_entry_strategy.py', 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')
        
    for i, line in enumerate(lines):
        if 'def _get_historical_data' in line:
            print(f"Found _get_historical_data method at line {i+1}")
            # Print method implementation
            start_line = i
            end_line = i + 1
            indent_level = len(line) - len(line.lstrip())
            
            # Find end of method
            for j in range(i+1, len(lines)):
                current_line = lines[j]
                if current_line.strip() == '':
                    continue
                current_indent = len(current_line) - len(current_line.lstrip())
                if current_indent <= indent_level and current_line.strip():
                    end_line = j
                    break
            else:
                end_line = len(lines)
            
            # Print method
            for j in range(start_line, min(end_line, start_line + 50)):  # Max 50 lines
                print(f'{j+1:4d}: {lines[j]}')
            return True
    
    print("_get_historical_data method not found")
    return False

if __name__ == "__main__":
    find_get_historical_data_method()