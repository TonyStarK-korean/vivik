#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚨 시스템 긴급 일시정지 도구
Rate Limit 초과시 시스템을 안전하게 일시정지하고 복구하는 도구
"""

import os
import json
import time
import signal
import psutil
from datetime import datetime

class EmergencyPauseSystem:
    def __init__(self):
        self.pause_file = "emergency_pause.flag"
        self.system_processes = []
        
    def create_pause_flag(self):
        """일시정지 플래그 생성"""
        pause_info = {
            "paused_at": datetime.now().isoformat(),
            "reason": "Rate Limit 초과로 인한 긴급 정지",
            "resume_after": datetime.now().isoformat()
        }
        
        with open(self.pause_file, 'w') as f:
            json.dump(pause_info, f, indent=2)
            
        print(f"🚨 긴급 일시정지 플래그 생성: {self.pause_file}")
        
    def remove_pause_flag(self):
        """일시정지 플래그 제거"""
        if os.path.exists(self.pause_file):
            os.remove(self.pause_file)
            print("✅ 일시정지 플래그 제거됨")
        else:
            print("⚠️ 일시정지 플래그가 없습니다")
            
    def check_pause_status(self):
        """일시정지 상태 확인"""
        if os.path.exists(self.pause_file):
            try:
                with open(self.pause_file, 'r') as f:
                    pause_info = json.load(f)
                print("🚨 시스템이 일시정지 중입니다")
                print(f"정지 시간: {pause_info['paused_at']}")
                print(f"사유: {pause_info['reason']}")
                return True
            except:
                print("⚠️ 일시정지 플래그 파일이 손상되었습니다")
                return True
        else:
            print("✅ 시스템이 정상 운영 중입니다")
            return False
            
    def find_trading_processes(self):
        """실행 중인 거래 프로세스 찾기"""
        trading_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                
                # Alpha-Z 관련 프로세스 찾기
                if any(keyword in cmdline.lower() for keyword in [
                    'alpha_z_triple_strategy.py',
                    'improved_dca_position_manager.py',
                    'alpha-z',
                    'dca_manager'
                ]):
                    trading_processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmdline': cmdline[:100] + '...' if len(cmdline) > 100 else cmdline
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        return trading_processes
        
    def show_processes(self):
        """실행 중인 프로세스 표시"""
        processes = self.find_trading_processes()
        
        if processes:
            print(f"🔍 발견된 거래 관련 프로세스 ({len(processes)}개):")
            for i, proc in enumerate(processes, 1):
                print(f"  {i}. PID: {proc['pid']} | {proc['name']}")
                print(f"     명령어: {proc['cmdline']}")
        else:
            print("✅ 실행 중인 거래 관련 프로세스가 없습니다")
            
        return processes
        
    def pause_system(self):
        """시스템 일시정지"""
        print("🚨 시스템 긴급 일시정지를 시작합니다...")
        
        # 1. 일시정지 플래그 생성 (실행 중인 프로세스들이 감지할 수 있도록)
        self.create_pause_flag()
        
        # 2. 실행 중인 프로세스 확인
        processes = self.show_processes()
        
        if processes:
            print("\n⚠️ 실행 중인 프로세스가 있습니다.")
            print("⚠️ 이 프로세스들은 emergency_pause.flag 파일을 확인하여 자동으로 일시정지해야 합니다.")
            print("⚠️ 만약 자동으로 정지하지 않으면 수동으로 종료하세요.")
            
            choice = input("\n프로세스를 강제 종료하시겠습니까? (y/N): ").strip().lower()
            if choice == 'y':
                self.force_stop_processes(processes)
        
        print("\n✅ 시스템 일시정지 완료")
        print(f"📄 일시정지 플래그: {self.pause_file}")
        
    def force_stop_processes(self, processes):
        """프로세스 강제 종료"""
        print("🛑 프로세스 강제 종료 중...")
        
        for proc in processes:
            try:
                process = psutil.Process(proc['pid'])
                process.terminate()
                print(f"✅ PID {proc['pid']} 종료 요청")
                
                # 3초 대기 후 여전히 실행 중이면 강제 kill
                try:
                    process.wait(timeout=3)
                except psutil.TimeoutExpired:
                    process.kill()
                    print(f"💀 PID {proc['pid']} 강제 종료")
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                print(f"⚠️ PID {proc['pid']} 종료 실패: {e}")
        
    def resume_system(self):
        """시스템 재개"""
        print("🔄 시스템 재개를 시작합니다...")
        
        # Rate Limiter 상태 확인 추천
        print("⚠️ 시스템을 재개하기 전에 Rate Limiter 상태를 확인하세요:")
        print("   python rate_limiter_emergency_tool.py")
        
        confirm = input("Rate Limiter가 정상이고 시스템을 재개하시겠습니까? (y/N): ").strip().lower()
        if confirm != 'y':
            print("취소되었습니다.")
            return
            
        # 일시정지 플래그 제거
        self.remove_pause_flag()
        
        print("✅ 시스템 재개 완료")
        print("⚠️ Alpha-Z 거래 시스템을 다시 시작하세요:")
        print("   python alpha_z_triple_strategy.py")
        
    def monitor_mode(self):
        """모니터링 모드 - 5초마다 상태 확인"""
        print("📊 모니터링 모드 시작 (Ctrl+C로 종료)")
        
        try:
            while True:
                os.system('cls' if os.name == 'nt' else 'clear')
                print(f"🕐 모니터링 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("=" * 50)
                
                # 일시정지 상태 확인
                is_paused = self.check_pause_status()
                
                # 프로세스 상태 확인
                processes = self.show_processes()
                
                if is_paused and processes:
                    print("⚠️ 일시정지 중인데 프로세스가 여전히 실행 중입니다!")
                elif is_paused and not processes:
                    print("✅ 일시정지 중 - 프로세스 정상 정지됨")
                elif not is_paused and processes:
                    print("✅ 정상 운영 중 - 프로세스 실행 중")
                else:
                    print("ℹ️ 정상 상태 - 프로세스 없음")
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("\n📊 모니터링 종료")
            
    def show_help(self):
        """도움말 표시"""
        print("🚨 시스템 긴급 일시정지 도구")
        print("=" * 40)
        print("1. status   - 현재 상태 확인")
        print("2. pause    - 시스템 긴급 일시정지")
        print("3. resume   - 시스템 재개")
        print("4. processes- 실행 중인 프로세스 확인")
        print("5. monitor  - 모니터링 모드")
        print("6. help     - 이 도움말")
        print("7. exit     - 종료")

def main():
    tool = EmergencyPauseSystem()
    
    print("🚨 Alpha-Z 시스템 긴급 일시정지 도구")
    print("현재 시간:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print()
    
    # 초기 상태 확인
    tool.check_pause_status()
    
    while True:
        print("\n" + "=" * 50)
        command = input("명령어 입력 (help 입력시 도움말): ").strip().lower()
        
        if command == 'status':
            tool.check_pause_status()
        elif command == 'pause':
            tool.pause_system()
        elif command == 'resume':
            tool.resume_system()
        elif command == 'processes':
            tool.show_processes()
        elif command == 'monitor':
            tool.monitor_mode()
        elif command == 'help':
            tool.show_help()
        elif command in ['exit', 'quit', 'q']:
            print("👋 종료합니다.")
            break
        else:
            print("❌ 알 수 없는 명령어입니다. 'help'를 입력하세요.")

if __name__ == "__main__":
    main()