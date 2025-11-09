# -*- coding: utf-8 -*-
"""
빠른 실행 테스트
"""
import subprocess
import time

def run_strategy():
    try:
        # 30초 제한으로 실행
        result = subprocess.run(
            ['python', 'alpha_z_triple_strategy.py'],
            timeout=30,
            capture_output=True,
            text=True,
            cwd=r'C:\Project\Alpha_Z\workspace-251106'
        )
        
        print("STDOUT:")
        print(result.stdout)
        print("\nSTDERR:")
        print(result.stderr)
        
    except subprocess.TimeoutExpired:
        print("30초 타임아웃")
    except Exception as e:
        print(f"실행 실패: {e}")

if __name__ == "__main__":
    run_strategy()