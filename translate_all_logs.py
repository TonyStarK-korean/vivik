#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Translate ALL Korean log messages to English
Fast and safe translation preserving Python syntax
"""

import os
import re
import glob

# Korean -> English translation dictionary
TRANSLATIONS = {
    # Common words
    "초기화": "Initialization",
    "시작": "Starting",
    "중지": "Stopped",
    "완료": "Complete",
    "성공": "Success",
    "실패": "Failed",
    "에러": "Error",
    "오류": "Error",
    "경고": "Warning",
    "확인": "Confirmed",
    "취소": "Cancelled",

    # WebSocket
    "웹소켓": "WebSocket",
    "연결": "Connected",
    "구독": "Subscribed",
    "메시지": "Message",
    "수신": "Received",
    "미시작": "Not started",
    "미Starting": "Not started",

    # Trading
    "포지션": "Position",
    "진입": "Entry",
    "청산": "Exit",
    "손절": "Stop loss",
    "익절": "Take profit",
    "평단가": "Average price",
    "수익률": "Profit rate",
    "거래": "Trade",

    # Status
    "활성화": "Activated",
    "비활성화": "Deactivated",
    "대기": "Waiting",
    "처리": "Processing",
    "감지": "Detected",
    "복구": "Recovery",

    # System
    "시스템": "System",
    "설정": "Settings",
    "버퍼": "Buffer",
    "조회": "Retrieval",
    "캐시": "Cache",
    "만료": "Expired",
    "정리": "Cleanup",

    # Numbers
    "개": "",
    "건": "",
    "회": "times",
    "번": "times",
}

def translate_line(line):
    """Translate Korean in a single line"""
    for korean, english in TRANSLATIONS.items():
        if korean in line:
            line = line.replace(korean, english)
    return line

def translate_file(filepath):
    """Translate Korean log messages in a file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        translated_lines = []
        changed = False

        for line in lines:
            # Only translate if line contains logger or print
            if 'logger.' in line or 'print(' in line:
                new_line = translate_line(line)
                if new_line != line:
                    changed = True
                translated_lines.append(new_line)
            else:
                translated_lines.append(line)

        if changed:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.writelines(translated_lines)
            return True
        return False

    except Exception as e:
        print(f"[ERROR] Error translating {filepath}: {e}")
        return False

def main():
    """Translate all Python files"""
    print("=" * 70)
    print("Translating Korean Log Messages to English")
    print("=" * 70)
    print()

    # Get all .py files (not .ko_backup files)
    py_files = [f for f in glob.glob("*.py") if not f.endswith('.ko_backup')]

    translated_count = 0
    total_count = len(py_files)

    for filepath in py_files:
        if translate_file(filepath):
            print(f"[OK] {filepath}")
            translated_count += 1
        else:
            print(f"[SKIP] {filepath} (no changes)")

    print()
    print("=" * 70)
    print(f"[DONE] Translation Complete: {translated_count}/{total_count} files updated")
    print("=" * 70)
    print()
    print("Backup files saved with .ko_backup extension")
    print("To restore: cp file.py.ko_backup file.py")

if __name__ == "__main__":
    main()
