# -*- coding: utf-8 -*-
"""
현재 실행 중인 파이썬 거래 전략들 확인
"""

import psutil
import os
import sys

def find_running_trading_strategies():
    """실행 중인 파이썬 거래 전략 프로세스들 확인"""
    print("현재 실행 중인 파이썬 거래 전략들:")
    print("=" * 60)
    
    trading_processes = []
    strategy_keywords = [
        'alpha_z_triple_strategy',
        'one_minute_surge_entry',
        'fifteen_minute_mega',
        'bollinger_',
        'strategy',
        'trading',
        'binance_',
        'surge_',
        'crypto_'
    ]
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            if proc.info['name'].lower().startswith('python'):
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                
                # 거래 전략 관련 키워드 확인
                is_trading_strategy = any(keyword in cmdline.lower() for keyword in strategy_keywords)
                
                if is_trading_strategy:
                    trading_processes.append({
                        'pid': proc.info['pid'],
                        'cmdline': cmdline,
                        'create_time': proc.info['create_time']
                    })
                    
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    if trading_processes:
        print(f"발견된 거래 전략 프로세스: {len(trading_processes)}개\n")
        
        for i, proc in enumerate(trading_processes, 1):
            print(f"{i}. PID: {proc['pid']}")
            
            # 실행 파일 이름 추출
            cmdline = proc['cmdline']
            if '.py' in cmdline:
                try:
                    script_name = [part for part in cmdline.split() if '.py' in part][0]
                    script_name = os.path.basename(script_name)
                    print(f"   스크립트: {script_name}")
                except:
                    print(f"   명령행: {cmdline}")
            else:
                print(f"   명령행: {cmdline[:100]}{'...' if len(cmdline) > 100 else ''}")
                
            # 실행 시간
            import datetime
            create_time = datetime.datetime.fromtimestamp(proc['create_time'])
            print(f"   시작 시간: {create_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            
        # 20배 레버리지 설정 가능성 있는 프로세스 경고
        suspicious_processes = []
        for proc in trading_processes:
            cmdline = proc['cmdline'].lower()
            if any(keyword in cmdline for keyword in ['fifteen', 'mega', 'bollinger', 'surge']):
                suspicious_processes.append(proc)
        
        if suspicious_processes:
            print("🚨 20배 레버리지 설정 가능성 있는 프로세스:")
            print("-" * 50)
            for proc in suspicious_processes:
                print(f"PID {proc['pid']}: {proc['cmdline'][:80]}...")
            print()
            print("이 프로세스들이 다른 레버리지 설정을 사용할 수 있습니다!")
        
    else:
        print("현재 실행 중인 거래 전략이 없습니다.")
    
    return trading_processes

def check_multiple_strategy_conflicts():
    """여러 전략 실행으로 인한 충돌 가능성 체크"""
    processes = find_running_trading_strategies()
    
    if len(processes) > 1:
        print("\n⚠️ 여러 전략이 동시 실행 중입니다!")
        print("=" * 60)
        print("문제 가능성:")
        print("1. 각기 다른 레버리지 설정 (10배 vs 20배)")
        print("2. 동일 심볼에 중복 진입")
        print("3. 서로 다른 포지션 관리")
        print("4. API 레이트 리밋 초과")
        print("\n권장 사항:")
        print("- 하나의 전략만 실행하거나")
        print("- 전략별 심볼 분리하거나")
        print("- 레버리지 설정 통일")
        
    return len(processes) > 1

if __name__ == "__main__":
    try:
        has_conflicts = check_multiple_strategy_conflicts()
        
        if has_conflicts:
            print(f"\n🔍 해결 방법:")
            print("1. 불필요한 전략 프로세스 종료")
            print("2. 각 전략의 레버리지 설정 확인 및 통일")
            print("3. 전략별 진입 심볼 분리")
            
    except Exception as e:
        print(f"오류: {e}")
        import traceback
        traceback.print_exc()