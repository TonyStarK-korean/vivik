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

# Windows 콘솔 UTF-8 설정
if os.name == 'nt':
    try:
        import locale
        import codecs
        # Windows 콘솔에서 UTF-8 출력 지원
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
        # 코드페이지를 UTF-8로 설정
        os.system('chcp 65001 > nul')
    except:
        pass

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
        """전략별 정보 반환 (Windows 호환)"""
        strategy_info = {
            'A': {'icon': 'A', 'name': '3분봉', 'color': Fore.RED + Style.BRIGHT},
            'B': {'icon': 'B', 'name': '15분봉', 'color': Fore.YELLOW + Style.BRIGHT},
            'C': {'icon': 'C', 'name': '30분봉', 'color': Fore.BLUE + Style.BRIGHT},
            'DCA': {'icon': 'D', 'name': 'DCA', 'color': Fore.MAGENTA + Style.BRIGHT}
        }
        return strategy_info.get(strategy, {'icon': 'X', 'name': '기타', 'color': Fore.WHITE})
    
    def format_percentage(self, percent: float, is_large: bool = True) -> str:
        """퍼센트 색상 포매팅 (상승=초록, 보합=노랑, 하락=빨강)"""
        # 색상 결정: 상승(초록), 보합부근(노랑), 하락(빨강)
        if percent > 0:  # 상승 (0% 초과)
            color = Fore.GREEN
        elif percent >= -1:  # 보합 부근 (-1% ~ 0%)
            color = Fore.YELLOW
        else:  # 하락 (-1% 미만)
            color = Fore.RED
            
        if is_large:
            # 레버리지 수익률 (크고 굵게)
            if percent >= 0:
                return f"{color}+{percent:.2f}%{Style.RESET_ALL}"
            else:
                return f"{color}{percent:.2f}%{Style.RESET_ALL}"
        else:
            # 원금 수익률 (작게)
            if percent >= 0:
                return f"{color}+ {percent:.2f}%{Style.RESET_ALL}"
            else:
                return f"{color}{percent:.2f}%{Style.RESET_ALL}"
    
    def safe_print_emoji(self, text):
        """Windows 콘솔에서 안전한 이모지 출력"""
        try:
            print(text, flush=True)
        except UnicodeEncodeError:
            # 이모지를 대체 문자로 변경
            safe_text = text.replace("🔥", "F").replace("✈️", "A").replace("✅", "+").replace("⚖️", "=").replace("🔻", "-")
            print(safe_text, flush=True)
    
    def get_trend_icon(self, percent: float) -> str:
        """트렌드 아이콘 반환 (단순화된 이모지)"""
        if percent > 0:  # 0% 초과 (모든 상승)
            return "✅"  # 체크 (상승)
        elif percent >= -1:  # -1% ~ 0% (보합 부근)
            return "⚖️"  # 저울 (보합)
        else:  # -1% 미만 (하락)
            return "🔻"  # 빨간 삼각형 (하락)
    
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
        """현재가 조회 (바이낸스 API 사용)"""
        try:
            import ccxt
            
            # 바이낸스 거래소 초기화
            exchange = ccxt.binance({
                'apiKey': '',  # 공개 데이터만 사용하므로 API 키 불필요
                'secret': '',
                'sandbox': False,
                'enableRateLimit': True,
            })
            
            current_prices = {}
            
            for symbol in symbols:
                try:
                    # ccxt 형식의 심볼로 변환 (예: BTC/USDT:USDT)
                    if '/USDT:USDT' not in symbol:
                        if '/' not in symbol:
                            ccxt_symbol = f"{symbol}/USDT:USDT"
                        else:
                            ccxt_symbol = symbol + ":USDT"
                    else:
                        ccxt_symbol = symbol
                    
                    ticker = exchange.fetch_ticker(ccxt_symbol)
                    current_prices[symbol] = ticker['last']
                    
                except Exception as e:
                    print(f"가격 조회 실패 {symbol}: {e}")
                    # 실패시 기본값 사용
                    current_prices[symbol] = 100.0
            
            return current_prices
            
        except ImportError:
            print("ccxt 모듈이 없습니다. pip install ccxt")
            # 샘플 데이터로 대체
            return {symbol: 100.0 for symbol in symbols}
            
        except Exception as e:
            print(f"현재가 조회 실패: {e}")
            # 오류시 기본값
            return {symbol: 100.0 for symbol in symbols}
    
    def display_positions(self):
        """활성포지션 예쁘게 출력"""
        positions = self.load_positions()
        
        if not positions:
            print(f"\n{Fore.CYAN}현재 활성 포지션이 없습니다{Style.RESET_ALL}")
            return
        
        # 현재가 조회
        symbols = [pos['symbol'] for pos in positions]
        current_prices = self.get_current_prices(symbols)
        
        # 헤더
        current_time = get_korea_time().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n{Fore.CYAN + Style.BRIGHT}{'='*50}")
        print(f" ALPHA-Z 활성포지션 현황 - {current_time}")
        print(f"{'='*50}{Style.RESET_ALL}")
        
        # 테이블 헤더 (요청된 형식)
        print(f"\n      {'심볼':<15} {'레버리지수익률':<15} {'원금'}")
        print(f"--------------------------------------------------")
        
        total_leveraged_pnl = 0
        total_original_pnl = 0
        total_positions = len(positions)
        profit_count = 0
        
        # 수익률 기준 내림차순 정렬
        positions_with_pnl = []
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
            
            positions_with_pnl.append((pos, leveraged_pnl))
        
        # 레버리지 수익률 기준 내림차순 정렬
        positions_with_pnl.sort(key=lambda x: x[1], reverse=True)
        
        for pos, leveraged_pnl in positions_with_pnl:
            symbol = pos['symbol']
            strategy = pos['strategy']
            avg_price = pos['average_price']
            quantity = pos['total_quantity']
            current_price = current_prices.get(symbol, avg_price)
            
            # 수익률 계산 (이미 계산됨)
            original_pnl = leveraged_pnl / 10  # 원금 수익률
            
            if leveraged_pnl > 0:
                profit_count += 1
            
            total_leveraged_pnl += leveraged_pnl
            total_original_pnl += original_pnl
            
            # 심볼 정리
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/', '')
            
            # 트렌드 아이콘
            trend_icon = self.get_trend_icon(leveraged_pnl)
            
            # 포매팅된 수익률 (레버리지와 원금 모두)
            formatted_leveraged = self.format_percentage(leveraged_pnl, is_large=True)
            formatted_original = self.format_percentage(original_pnl, is_large=False)
            
            # 요청된 형식으로 출력: 아이콘 심볼 레버리지수익률 원금수익률
            output_line = f"{trend_icon} {clean_symbol:<15} {formatted_leveraged:<15} {formatted_original:>10}"
            self.safe_print_emoji(output_line)
        
        # 요약 정보 (요청된 형식)
        print(f"--------------------------------------------------")
        avg_leveraged_pnl = total_leveraged_pnl / total_positions if total_positions > 0 else 0
        avg_original_pnl = total_original_pnl / total_positions if total_positions > 0 else 0
        
        # 합계 출력 (요청된 형식)
        trend_icon_total = self.get_trend_icon(avg_leveraged_pnl)
        formatted_total_leveraged = self.format_percentage(avg_leveraged_pnl, is_large=True)
        formatted_total_original = self.format_percentage(avg_original_pnl, is_large=False)
        
        total_line = f"{trend_icon_total} {'합계':<15} {formatted_total_leveraged:<15} {formatted_total_original:>10}"
        self.safe_print_emoji(total_line)
        print(f"--------------------------------------------------")
    
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