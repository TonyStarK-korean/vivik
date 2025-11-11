# -*- coding: utf-8 -*-
"""
🖥️ 콘솔 활성포지션 예쁜 출력기
스크린샷과 같은 스타일의 콘솔 출력
"""

import os
import sys
import time
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import threading

# Windows 콘솔 색상 지원
try:
    import colorama
    from colorama import Fore, Back, Style
    colorama.init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    print("colorama를 설치하면 더 예쁜 색상을 볼 수 있습니다: pip install colorama")
    HAS_COLORAMA = False
    # 더미 색상 클래스
    class Fore:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = ''
    class Style:
        BRIGHT = DIM = RESET_ALL = ''

def get_korea_time():
    """한국 표준시(KST) 현재 시간 반환"""
    return datetime.now(timezone(timedelta(hours=9)))

class ConsolePositionDisplay:
    """콘솔 활성포지션 예쁜 출력기"""
    
    def __init__(self):
        self.running = False
        self.display_thread = None
        self.update_interval = 3  # 3초마다 업데이트
        
    def clear_screen(self):
        """화면 클리어"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def get_strategy_info(self, strategy: str) -> Dict[str, str]:
        """전략별 정보 반환"""
        strategy_info = {
            'A': {'icon': '🔥', 'name': '3분봉', 'color': Fore.RED + Style.BRIGHT},
            'B': {'icon': '⚡', 'name': '15분봉', 'color': Fore.YELLOW + Style.BRIGHT},
            'C': {'icon': '🎯', 'name': '30분봉', 'color': Fore.BLUE + Style.BRIGHT},
            'DCA': {'icon': '🔄', 'name': 'DCA', 'color': Fore.MAGENTA + Style.BRIGHT}
        }
        return strategy_info.get(strategy, {'icon': '📊', 'name': '기타', 'color': Fore.WHITE})
    
    def format_percentage(self, percent: float) -> str:
        """퍼센트 색상 포매팅"""
        if percent >= 0:
            return f"{Fore.GREEN + Style.BRIGHT}+{percent:.2f}%{Style.RESET_ALL}"
        else:
            return f"{Fore.RED + Style.BRIGHT}{percent:.2f}%{Style.RESET_ALL}"
    
    def get_trend_icon(self, percent: float) -> str:
        """트렌드 아이콘 반환"""
        if percent >= 5:
            return f"{Fore.GREEN}🔺{Style.RESET_ALL}"  # 큰 상승
        elif percent >= 0:
            return f"{Fore.GREEN}✅{Style.RESET_ALL}"  # 수익
        elif percent >= -5:
            return f"{Fore.YELLOW}⚠️{Style.RESET_ALL}"  # 작은 손실
        else:
            return f"{Fore.RED}❌{Style.RESET_ALL}"   # 큰 손실
    
    def load_positions(self) -> List[Dict]:
        """활성 포지션 로드"""
        try:
            # DCA 포지션 파일에서 로드
            dca_file = 'dca_positions.json'
            if os.path.exists(dca_file):
                with open(dca_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        positions = []
                        for symbol, pos in data.items():
                            if pos.get('is_active', False):
                                positions.append({
                                    'symbol': symbol,
                                    'strategy': pos.get('strategy', 'UNKNOWN'),
                                    'entries': pos.get('entries', []),
                                    'average_price': pos.get('average_price', 0),
                                    'total_quantity': pos.get('total_quantity', 0),
                                    'current_stage': pos.get('current_stage', 'initial'),
                                    'cyclic_count': pos.get('cyclic_count', 0)
                                })
                        return positions
            
            return []
        except Exception as e:
            print(f"포지션 로드 실패: {e}")
            return []
    
    def get_current_prices(self, symbols: List[str]) -> Dict[str, float]:
        """현재가 조회 (임시 - 실제로는 바이낸스 API 사용)"""
        # 샘플 데이터 (실제로는 바이낸스 API에서 가져와야 함)
        sample_prices = {
            'BTCUSDT': 91250.50,
            'ETHUSDT': 3180.25,
            'SOLUSDT': 215.80,
            'ADAUSDT': 1.082,
            'DOTUSDT': 8.45,
            'LINKUSDT': 18.75,
            'AVAXUSDT': 42.30,
            'ATOMUSDT': 9.85,
            'MATICUSDT': 0.785,
            'FILUSDT': 6.25
        }
        
        current_prices = {}
        for symbol in symbols:
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/', '') + 'USDT'
            current_prices[symbol] = sample_prices.get(clean_symbol, 100.0)
        
        return current_prices
    
    def display_positions(self):
        """활성포지션 예쁘게 출력"""
        positions = self.load_positions()
        
        if not positions:
            print(f"\n{Fore.CYAN}📭 현재 활성 포지션이 없습니다{Style.RESET_ALL}")
            return
        
        # 현재가 조회
        symbols = [pos['symbol'] for pos in positions]
        current_prices = self.get_current_prices(symbols)
        
        # 헤더
        current_time = get_korea_time().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n{Fore.CYAN + Style.BRIGHT}{'='*80}")
        print(f"🚀 ALPHA-Z 활성포지션 현황 - {current_time}")
        print(f"{'='*80}{Style.RESET_ALL}")
        
        # 테이블 헤더
        print(f"\n{'아이콘':>4} {'심볼':<8} {'전략':>4} {'진입가':>12} {'현재가':>12} {'수익률':>12} {'상태':>8}")
        print(f"{'-'*70}")
        
        total_pnl = 0
        total_positions = len(positions)
        profit_count = 0
        
        for pos in positions:
            symbol = pos['symbol']
            strategy = pos['strategy']
            avg_price = pos['average_price']
            quantity = pos['total_quantity']
            current_price = current_prices.get(symbol, avg_price)
            
            # 수익률 계산
            if avg_price > 0:
                pnl_percent = ((current_price - avg_price) / avg_price) * 100
            else:
                pnl_percent = 0
            
            # 레버리지 적용 (10배 고정)
            leverage = 10
            leveraged_pnl = pnl_percent * leverage
            
            if leveraged_pnl > 0:
                profit_count += 1
            
            total_pnl += leveraged_pnl
            
            # 전략 정보
            strategy_info = self.get_strategy_info(strategy)
            
            # 심볼 정리
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/', '')
            
            # 트렌드 아이콘
            trend_icon = self.get_trend_icon(leveraged_pnl)
            
            # 포매팅된 수익률
            formatted_pnl = self.format_percentage(leveraged_pnl)
            
            # DCA 단계 표시
            stage_short = {
                'initial': 'INIT',
                'first_dca': '1DCA', 
                'second_dca': '2DCA',
                'closing': 'EXIT'
            }.get(pos['current_stage'], 'UNK')
            
            # 순환매 표시
            cyclic_display = f"R{pos['cyclic_count']}" if pos['cyclic_count'] > 0 else ""
            status = f"{stage_short}{cyclic_display}"
            
            print(f"{trend_icon:>4} {strategy_info['color']}{clean_symbol:<8}{Style.RESET_ALL} "
                  f"{strategy_info['icon']:>2}{strategy:>2} "
                  f"{Fore.CYAN}${avg_price:>10.2f}{Style.RESET_ALL} "
                  f"{Fore.WHITE}${current_price:>10.2f}{Style.RESET_ALL} "
                  f"{formatted_pnl:>18} "
                  f"{Fore.YELLOW}{status:>8}{Style.RESET_ALL}")
        
        # 요약 정보
        print(f"{'-'*70}")
        avg_pnl = total_pnl / total_positions if total_positions > 0 else 0
        win_rate = (profit_count / total_positions * 100) if total_positions > 0 else 0
        
        summary_color = Fore.GREEN if avg_pnl >= 0 else Fore.RED
        
        print(f"\n{Fore.CYAN + Style.BRIGHT}📊 포지션 요약:")
        print(f"   💰 총 포지션: {total_positions}개")
        print(f"   📈 수익 포지션: {profit_count}개 ({win_rate:.1f}%)")
        print(f"   📊 평균 수익률: {summary_color + Style.BRIGHT}{avg_pnl:+.2f}%{Style.RESET_ALL}")
        print(f"   🕐 업데이트: 매 {self.update_interval}초{Style.RESET_ALL}")
    
    def start_display(self):
        """실시간 콘솔 출력 시작"""
        self.running = True
        self.display_thread = threading.Thread(target=self._display_loop, daemon=True)
        self.display_thread.start()
        print(f"{Fore.GREEN}🚀 콘솔 활성포지션 출력 시작! (종료: Ctrl+C){Style.RESET_ALL}")
    
    def stop_display(self):
        """출력 중지"""
        self.running = False
        if self.display_thread:
            self.display_thread.join()
    
    def _display_loop(self):
        """출력 루프"""
        while self.running:
            try:
                self.clear_screen()
                self.display_positions()
                time.sleep(self.update_interval)
            except Exception as e:
                print(f"출력 오류: {e}")
                time.sleep(1)

def main():
    """메인 실행"""
    display = ConsolePositionDisplay()
    
    try:
        display.start_display()
        
        # 메인 스레드에서 대기
        while display.running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}👋 프로그램을 종료합니다...{Style.RESET_ALL}")
        display.stop_display()
    
    except Exception as e:
        print(f"{Fore.RED}오류 발생: {e}{Style.RESET_ALL}")
        display.stop_display()

if __name__ == "__main__":
    main()