#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCA 관련 파일들을 vivik_clean 폴더로 복사
"""

import shutil
from pathlib import Path

# 현재 디렉토리와 대상 디렉토리
current_dir = Path("C:/Project/Alpha_Z/workspace-251106")
clean_dir = current_dir / "vivik_clean"

# 복사할 DCA 및 운영 관련 파일들
dca_files = [
    "dca_positions.json",
    "dca_limits.json", 
    "daily_stats.json",
    "half_profit_exit_config.json",
    "rate_limit_stats.json",
    "sent_notifications.json"
]

print("DCA 관련 파일 복사 Starting...")

copied_count = 0
for file_name in dca_files:
    src_file = current_dir / file_name
    dst_file = clean_dir / file_name
    
    if src_file.exists():
        try:
            shutil.copy2(src_file, dst_file)
            copied_count += 1
            print(f"[COPY] {file_name}")
        except Exception as e:
            print(f"[ERR] {file_name} 복사 Failed: {e}")
    else:
        print(f"[WARN] {file_name} 파일 없음")

print(f"\n[DONE] {copied_count} DCA 관련 파일 복사 Complete")

# vivik_clean 디렉토리의 파일 목록 확인
print(f"\n[CHECK] vivik_clean 폴더 내용:")
clean_files = []
for item in clean_dir.iterdir():
    if item.is_file():
        clean_files.append(item.name)

for file in sorted(clean_files):
    print(f"  - {file}")

print(f"\n총 {len(clean_files)} 파일")