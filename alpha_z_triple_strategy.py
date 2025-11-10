# -*- coding: utf-8 -*-
"""
A전략(15분봉 바닥타점) + B전략(15분봉 급등초입) + C전략(3분봉 바닥급등타점) 시스템
레버리지 20배 적용

거래 설정:
- 레버리지: 20배
- 포지션 크기: 원금 1.0% x 20배 레버리지 (20% 노출)
- 최대 진입 종목: 20종목
- 재진입: 순환매 활성화 (최초진입가 기준 청산모드 전환)
- 단계별 손절: 초기 -10% (시드 대비 6% 손실)
- 종목당 최대 비중: 3.0% (초기 1.0% + DCA 1.0% + 1.0%)
- 최대 원금 사용: 60% (20종목 × 3.0%)
- 손실 계산: 총 3% × 20배 × -10% = 시드의 6% 손실

DCA 시스템:
- 최초 진입: 1.0% x 20배 = 20% 노출 시장가 매수
- 1차 DCA: -3% 하락가에 1.0% x 20배 지정가 주문 (즉시 등록)
- 2차 DCA: -6% 하락가에 1.0% x 20배 지정가 주문 (즉시 등록)
- 전량 손절: -10% (시드 대비 6% 손실)

전략 조건:
A전략(15분봉 바닥타점): 임시 비활성화 - (ma80<ma480 and ma5<ma480) and BB복합조건 및 골든크로스 and 시가대비고가조건
B전략(15분봉 급등초입): 6개 조건 - 기존 급등초입 조건 + 시가대비고가조건 추가
C전략(3분봉 바닥급등타점): 3개 조건 - MA80-MA480 골든크로스(300봉이내) and BB80-BB480 골든크로스(300봉이내) and MA20-MA80 골든크로스(5봉이내)
"""

import os
import sys
import ccxt
import pandas as pd
import numpy as np
import time
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# 🔧 스크립트 디렉토리를 Python 경로에 추가 (import 문제 해결)
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# 기존 모듈들 import
try:
    from binance_config import BinanceConfig
    HAS_BINANCE_CONFIG = True
except ImportError:
    print("[INFO] binance_config.py 없음 - 공개 API만 사용")
    class BinanceConfig:
        API_KEY = ""
        SECRET_KEY = ""
    HAS_BINANCE_CONFIG = False

try:
    from telegram_bot import TelegramBot
    HAS_TELEGRAM = True
    print("[INFO] 텔레그램 봇 모듈 로드 완료")
except ImportError:
    print("[INFO] telegram_bot.py 없음 - 텔레그램 알림 비활성화")
    HAS_TELEGRAM = False
    class TelegramBot:
        def __init__(self):
            pass
        def send_message(self, message):
            pass

try:
    from improved_dca_position_manager import ImprovedDCAPositionManager
    HAS_DCA_MANAGER = True
    print("[INFO] 개선된 DCA 매니저 로드 완료")
except ImportError:
    print("[INFO] improved_dca_position_manager.py 없음 - DCA 기능 비활성화")
    HAS_DCA_MANAGER = False

# 가상매매 제거 - 실전매매로 변경
# try:
#     from virtual_trading_manager import VirtualTradingManager
#     HAS_VIRTUAL_TRADING = True
#     print("[INFO] 가상매매 매니저 로드 완료")
# except ImportError:
#     print("[INFO] virtual_trading_manager.py 없음 - 가상매매 기능 비활성화")
#     HAS_VIRTUAL_TRADING = False

HAS_VIRTUAL_TRADING = False  # 실전매매 모드

try:
    from websocket_ohlcv_provider import WebSocketOHLCVProvider
    HAS_WEBSOCKET_PROVIDER = True
    print("[INFO] WebSocket OHLCV 제공자 로드 완료")
except ImportError:
    print("[INFO] websocket_ohlcv_provider.py 없음 - WebSocket 최적화 비활성화")
    HAS_WEBSOCKET_PROVIDER = False

# 🎨 색상 코드 상수
GREEN = "\033[92m"      # 밝은 초록색
RESET = "\033[0m"       # 색상 초기화
GREEN_HEART = " 💚"     # 초록색 하트 이모지

def get_korea_time():
    """한국 시간 반환"""
    return datetime.now(timezone(timedelta(hours=9)))

class FifteenMinuteMegaStrategy:
    """15분봉 A전략(바닥타점) + B전략(급등초입) 시스템"""
    
    def __init__(self, sandbox=False):
        """초기화"""
        self.sandbox = sandbox
        self.logger = self._setup_logger()
        
        # Exchange 설정 (공개 API + 프라이빗 API 분리)
        # 공개 API (스캔용)
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
        # 프라이빗 API (거래용)
        if HAS_BINANCE_CONFIG and BinanceConfig.API_KEY:
            self.private_exchange = ccxt.binance({
                'apiKey': BinanceConfig.API_KEY,
                'secret': BinanceConfig.SECRET_KEY,
                'sandbox': sandbox,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'warnOnFetchOpenOrdersWithoutSymbol': False  # 경고 메시지 억제
                }
            })
            print("[INFO] 프라이빗 API 초기화 완료")
        else:
            self.private_exchange = None
            print("[WARN] 프라이빗 API 없음 - 거래 기능 비활성화")
        
        # 텔레그램 봇 초기화 (telegram_config.py에서 실제 설정 로드)
        try:
            from telegram_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
            self.telegram_bot = TelegramBot(bot_token=TELEGRAM_BOT_TOKEN, chat_id=TELEGRAM_CHAT_ID) if HAS_TELEGRAM else None
            if self.telegram_bot:
                print(f"[INFO] 텔레그램 봇 초기화 완료 - Chat ID: {TELEGRAM_CHAT_ID}")
        except ImportError:
            self.telegram_bot = TelegramBot() if HAS_TELEGRAM else None
            print("[WARN] telegram_config.py 없음 - 기본 설정 사용")
        
        # 실전매매 설정
        self.virtual_trader = None  # 가상매매 제거
        self.active_positions = {}  # 실제 포지션 추적 {symbol: position_info}
        print("[INFO] 실전매매 모드 - 실제 거래 활성화")
        
        # 텔레그램 중복 알림 방지 설정
        self.notification_file = "sent_notifications.json"
        self.sent_notifications = self._load_notification_history()
        print(f"[INFO] 텔레그램 알림 기록 로드: {len(self.sent_notifications)}개")
        
        # WebSocket OHLCV 제공자 초기화
        if HAS_WEBSOCKET_PROVIDER:
            self.ws_provider = WebSocketOHLCVProvider()
            print("[INFO] WebSocket OHLCV 제공자 초기화 완료")
        else:
            self.ws_provider = None
            print("[WARN] WebSocket OHLCV 제공자 없음")
        
        # DCA 매니저 초기화 (레버리지 20배) - Exchange 연결 안정성 강화
        if HAS_DCA_MANAGER:
            # 프라이빗 API 있을 때만 DCA 매니저 활성화
            if self.private_exchange and hasattr(self.private_exchange, 'apiKey') and self.private_exchange.apiKey:
                try:
                    self.dca_manager = ImprovedDCAPositionManager(
                        exchange=self.private_exchange,
                        telegram_bot=self.telegram_bot if hasattr(self, 'telegram_bot') else None,
                        strategy=self
                    )
                    # 레버리지 20배로 설정 업데이트
                    self.dca_manager.leverage = 20.0
                    
                    # 🔧 DCA 매니저 Exchange 연결 상태 검증
                    print(f"[INFO] DCA 매니저 초기화 완료 - 프라이빗 API, 레버리지 20배")
                    print(f"[INFO] API 키 설정 확인: {self.private_exchange.apiKey[:8]}...")
                    print(f"[INFO] DCA-Exchange 연결 상태: {type(self.dca_manager.exchange).__name__}")
                    print(f"[INFO] DCA-Exchange API 키 상태: {'OK' if self.dca_manager.exchange.apiKey else 'MISSING'}")
                    
                    # 🔧 Exchange 참조 안정성 확보 - 같은 객체 인스턴스 보장
                    if id(self.dca_manager.exchange) != id(self.private_exchange):
                        print(f"[WARN] DCA Exchange 객체 ID 불일치: DCA={id(self.dca_manager.exchange)} vs Main={id(self.private_exchange)}")
                    else:
                        print(f"[INFO] ✅ DCA-Main Exchange 객체 동일성 확인됨")
                        
                except Exception as dca_init_error:
                    print(f"[ERROR] DCA 매니저 초기화 실패: {dca_init_error}")
                    self.dca_manager = None
            else:
                self.dca_manager = None
                print("[WARN] DCA 매니저 비활성화 - 프라이빗 API 필요 (거래 실행용)")
        else:
            self.dca_manager = None
            print("[WARN] DCA 매니저 없음")
        
        # 캐시 시스템
        self._ohlcv_cache = {}
        self._ohlcv_cache_ttl = 1200  # 20분
        self._market_cache = None
        self._market_cache_time = 0
        self._market_cache_ttl = 3600  # 1시간
        
        # 실제 포지션을 조회해서 초기화
        self._load_active_positions()
        
        # 스캔 모드
        self._scan_mode = True
        
        # 디버그 로그 파일
        self.debug_log_file = "fifteen_minute_mega.log"
        
        # 중복 알림 방지 시스템 (심볼 + 사유별로 1회만 알림)
        self.notification_cache = {}  # {symbol_reason: timestamp}
        self.notification_cooldown = 3600  # 1시간 쿨다운
        
        # 🔧 DCA Exchange 재연결 요청 플래그
        self._request_exchange_reconnect = False
        
        print("15분봉 초필살기 전략 시스템 초기화 완료")
        print(f"   레버리지: 20배")
        print(f"   최초 진입: 1% (20% 노출)")
        print(f"   최대 손실: 6% (시드 기준)")
    
    def _setup_logger(self):
        """로거 설정"""
        import logging
        logger = logging.getLogger('FifteenMinuteMega')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _write_debug_log(self, message):
        """디버그 로그 작성"""
        try:
            timestamp = get_korea_time().strftime('%H:%M:%S')
            with open(self.debug_log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception:
            pass
    
    def _get_strategy_type(self, signal_data):
        """신호 데이터에서 전략 타입 추출"""
        try:
            if signal_data.get('strategy_details'):
                details = signal_data['strategy_details']
                
                # 각 전략 신호 확인
                a_signal = details.get('strategy_a', {}).get('signal', False)
                b_signal = details.get('strategy_b', {}).get('signal', False) 
                c_signal = details.get('strategy_c', {}).get('signal', False)
                
                # 복합 전략 우선 체크
                if a_signal and b_signal and c_signal:
                    return "[A+B+C전략]"
                elif a_signal and b_signal:
                    return "[A+B전략]"
                elif a_signal and c_signal:
                    return "[A+C전략]"
                elif b_signal and c_signal:
                    return "[B+C전략]"
                # 단일 전략 체크
                elif a_signal:
                    return "[A전략]"
                elif b_signal:
                    return "[B전략]"
                elif c_signal:
                    return "[C전략]"
                    
            # strategy_type 필드 직접 확인 (백업)
            strategy_type = signal_data.get('strategy_type', '')
            if strategy_type:
                return strategy_type
                
            return "[전략미상]"
        except Exception as e:
            return f"[전략오류:{e}]"
    
    def _send_notification_once(self, symbol, reason, message):
        """중복 방지 텔레그램 알림 (같은 심볼+사유로 1시간에 1회만)"""
        try:
            if not self.telegram_bot:
                return False
            
            # 텔레그램 설정이 기본값이면 알림 안보냄
            if hasattr(self.telegram_bot, 'bot_token') and "YOUR_BOT_TOKEN_HERE" in str(self.telegram_bot.bot_token):
                print(f"[INFO] 텔레그램 미설정으로 알림 건너뛰기: \033[92m{symbol.replace('/USDT:USDT', '')}\033[0m 💚 - {reason}")
                return False
            
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            cache_key = f"{clean_symbol}_{reason}"
            current_time = time.time()
            
            # 캐시 정리 (1시간 지난 항목 제거)
            expired_keys = []
            for key, timestamp in self.notification_cache.items():
                if current_time - timestamp > self.notification_cooldown:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.notification_cache[key]
            
            # 중복 알림 체크
            if cache_key in self.notification_cache:
                last_sent = self.notification_cache[cache_key]
                if current_time - last_sent < self.notification_cooldown:
                    print(f"   ⏭️ \033[92m{clean_symbol}\033[0m 💚 {reason} 알림 중복 방지 - 이미 전송함 ({int((current_time - last_sent)/60)}분 전)")
                    return False
            
            # 알림 전송
            self.telegram_bot.send_message(message)
            self.notification_cache[cache_key] = current_time
            print(f"[INFO] 텔레그램 알림 전송: {clean_symbol} - {reason}")
            return True
            
        except Exception as e:
            self.logger.error(f"텔레그램 알림 실패: {e}")
            return False
    
    def _count_strategy_conditions(self, conditions):
        """전략 조건 개수 계산"""
        count = 0
        for condition in conditions:
            if 'True' in condition or '충족' in condition:
                count += 1
        return count
    
    def _print_strategy_separated_results(self, all_results, entry_signals):
        """전략별 분리된 결과 출력"""
        print(f"\n🚀 A+B+C전략 통합 스캔 결과")
        print(f"{'='*60}")
        
        # 상태별 분류
        entry_signals_list = [r for r in all_results if r.get('status') == 'entry_signal']
        near_entry_list = [r for r in all_results if r.get('status') == 'near_entry']
        potential_entry_list = [r for r in all_results if r.get('status') == 'potential_entry']
        watchlist_list = [r for r in all_results if r.get('status') == 'watchlist']
        
        # A전략별 분류
        a_entry_signals = []
        a_near_entry = []
        a_potential_entry = []
        a_watchlist = []
        
        # B전략별 분류
        b_entry_signals = []
        b_near_entry = []
        b_potential_entry = []
        b_watchlist = []
        
        # C전략별 분류
        c_entry_signals = []
        c_near_entry = []
        c_potential_entry = []
        c_watchlist = []
        
        # 먼저 entry_signals의 모든 항목이 all_results에 있는지 확인하고 누락된 것 추가
        entry_signals_set = {r['symbol'] for r in entry_signals}
        all_results_set = {r['symbol'] for r in all_results}
        missing_in_all_results = entry_signals_set - all_results_set
        
        if missing_in_all_results:
            print(f"⚠️ DEBUG: entry_signals에 있지만 all_results에 없는 심볼들: {missing_in_all_results}")
            # entry_signals에 있는 항목들을 all_results에도 추가
            for signal in entry_signals:
                if signal['symbol'] not in all_results_set:
                    all_results.append(signal)
        
        for result in all_results:
            if result.get('strategy_details'):
                details = result['strategy_details']
                clean_symbol = result['symbol'].replace('/USDT:USDT', '')
                price = result['price']
                status = result.get('status', 'watchlist')
                failed_count = result.get('failed_count', 4)
                
                # A전략, B전략, C전략별 조건 통과 계산
                a_passed = 0
                b_passed = 0
                c_passed = 0
                
                for cond in result.get('conditions', []):
                    if '[A전략 조건' in str(cond) and 'True' in str(cond):
                        a_passed += 1
                    elif '[B전략 조건' in str(cond) and 'True' in str(cond):
                        b_passed += 1
                    elif '[C전략 조건' in str(cond) and 'True' in str(cond):
                        c_passed += 1
                
                # 전략별 진입확률 계산
                a_entry_probability = (a_passed / 5.0) * 100 if a_passed > 0 else 0  # A전략: 5개 조건
                b_entry_probability = (b_passed / 6.0) * 100 if b_passed > 0 else 0  # B전략: 6개 조건
                c_entry_probability = (c_passed / 4.0) * 100 if c_passed > 0 else 0  # C전략: 4개 조건
                
                a_result_data = {'symbol': clean_symbol, 'price': price, 'prob': a_entry_probability}
                b_result_data = {'symbol': clean_symbol, 'price': price, 'prob': b_entry_probability}
                c_result_data = {'symbol': clean_symbol, 'price': price, 'prob': c_entry_probability}
                
                # 디버그 출력
                if result.get('status') == 'entry_signal':
                    c_signal = details.get('strategy_c', {}).get('signal', False)
                    print(f"🔍 DEBUG: {clean_symbol} - A신호:{details['strategy_a']['signal']}, B신호:{details['strategy_b']['signal']}, C신호:{c_signal}, A통과:{a_passed}/5, B통과:{b_passed}/6, C통과:{c_passed}/4")
                
                # A전략 분류 (5개 조건 기준)
                if details['strategy_a']['signal']:
                    # BNT, GPS 같은 문제 심볼에 대한 디버깅
                    if clean_symbol in ['BNT', 'GPS', 'BARD', 'LINK']:
                        print(f"⚠️ 의심스러운 A전략 신호: {clean_symbol}")
                    a_entry_signals.append(a_result_data)
                elif a_passed == 4:  # 1개만 미충족
                    a_near_entry.append(a_result_data)
                elif a_passed == 3:  # 2개 미충족
                    a_potential_entry.append(a_result_data)
                elif a_passed >= 0:  # 1개 이상 미충족 (0개 포함)
                    a_watchlist.append(a_result_data)
                
                # B전략 분류 (6개 조건 기준)
                if details['strategy_b']['signal']:
                    b_entry_signals.append(b_result_data)
                elif b_passed == 5:  # 1개만 미충족
                    b_near_entry.append(b_result_data)
                elif b_passed == 4:  # 2개 미충족
                    b_potential_entry.append(b_result_data)
                elif b_passed >= 0:  # 1개 이상 미충족 (0개 포함)
                    b_watchlist.append(b_result_data)
                
                # C전략 분류 (4개 조건 기준)
                if details.get('strategy_c', {}).get('signal', False):
                    c_entry_signals.append(c_result_data)
                elif c_passed == 3:  # 1개만 미충족
                    c_near_entry.append(c_result_data)
                elif c_passed == 2:  # 2개 미충족
                    c_potential_entry.append(c_result_data)
                elif c_passed >= 0:  # 1개 이상 미충족 (0개 포함)
                    c_watchlist.append(c_result_data)
        
        # 미충족 조건 추출 함수
        def get_failed_conditions(result, strategy_type):
            failed_conds = []
            conditions = result.get('conditions', [])
            
            for cond in conditions:
                if f'[{strategy_type}전략 조건' in str(cond) and 'False' in str(cond):
                    if '조건1' in str(cond):
                        if strategy_type == 'A':
                            failed_conds.append("MA80<MA480 & MA5<MA480")
                        elif strategy_type == 'B':
                            failed_conds.append("MA80-MA480 골든크로스")
                        else:  # C전략
                            failed_conds.append("MA80-MA480 골든크로스/관계")
                    elif '조건2' in str(cond):
                        if strategy_type == 'C':
                            failed_conds.append("BB80-BB480 골든크로스")
                        else:  # A, B전략
                            failed_conds.append("BB 골든크로스")
                    elif '조건3' in str(cond):
                        if strategy_type == 'A':
                            failed_conds.append("MA 골든크로스")
                        elif strategy_type == 'B':
                            failed_conds.append("MA5-MA20 골든크로스+현재가")
                        else:  # C전략
                            failed_conds.append("MA5-MA20 골든크로스/복합조건")
                    elif '조건4' in str(cond):
                        if strategy_type == 'A':
                            failed_conds.append("현재가-MA5 조건")
                        elif strategy_type == 'B':
                            failed_conds.append("BB200-MA480 상향돌파")
                        else:  # C전략
                            failed_conds.append("1분봉 MA5-MA20 골든크로스")
                    elif '조건5' in str(cond):
                        if strategy_type == 'A':
                            failed_conds.append("시가대비고가 3%이상")
                        else:  # B전략
                            failed_conds.append("데드크로스/이격도/시가대비고가+BB480")
                    elif '조건6' in str(cond):  # B전략만
                        failed_conds.append("시가대비고가 5%이상")
            return failed_conds

        # 🅰️ A전략(바닥타점) 결과 - 임시 비활성화로 출력 생략
        # print(f"\n🅰️ A전략(바닥타점) 결과")
        # print(f"{'='*60}")
        # A전략 출력 코드 모두 주석 처리 (비활성화됨)
        
        # 🅱️ B전략(급등초입) 결과
        print(f"\n🅱️ B전략(급등초입) 결과")
        print(f"{'='*60}")
        
        if b_entry_signals:
            print(f"┌{'─'*30}┐")
            print(f"│   🔥 진입신호 ({len(b_entry_signals)}개)        │")
            print(f"└{'─'*30}┘")
            # 2x2 배치
            for i in range(0, len(b_entry_signals), 2):
                row = b_entry_signals[i:i+2]
                if len(row) == 2:
                    print(f"   🎯 {GREEN}{row[0]['symbol']:<8}{RESET}   🎯 {GREEN}{row[1]['symbol']}{RESET}")
                else:
                    print(f"   🎯 {GREEN}{row[0]['symbol']}{RESET}")
        else:
            print(f"┌{'─'*30}┐")
            print(f"│  🔥 진입신호 (없음)        │")
            print(f"└{'─'*30}┘")
        
        if b_near_entry:
            print(f"\n┌{'─'*55}┐")
            print(f"│  🔥 진입임박 ({len(b_near_entry)}개) - 조건 1개 미충족                 │")
            print(f"└{'─'*55}┘")
            for signal in b_near_entry:
                # 해당 심볼의 원본 결과 찾기
                original_result = next((r for r in all_results if r['symbol'].replace('/USDT:USDT', '') == signal['symbol']), None)
                failed_conds = get_failed_conditions(original_result, 'B') if original_result else []
                failed_text = "\033[91m" + ", ".join(failed_conds) + "\033[0m" if failed_conds else "\033[91m미상\033[0m"
                print(f"   🔥 \033[93m{signal['symbol']}\033[0m - 미충족: {failed_text}")
        else:
            print(f"\n┌{'─'*30}┐")
            print(f"│  🔥 진입임박 (없음)        │")
            print(f"└{'─'*30}┘")
        
        if b_potential_entry:
            print(f"\n┌{'─'*55}┐")
            print(f"│  ⚡ 진입확률 ({len(b_potential_entry)}개) - 조건 2개 미충족                 │")
            print(f"└{'─'*55}┘")
            # 가로 4줄 배치
            symbols = [signal['symbol'] for signal in b_potential_entry]
            for i in range(0, len(symbols), 4):
                row = symbols[i:i+4]
                formatted_row = [f"\033[93m{symbol}\033[0m" for symbol in row]
                print(f"   ⚡ {' | '.join(formatted_row)}")
        else:
            print(f"\n┌{'─'*30}┐")
            print(f"│  ⚡ 진입확률 (없음)        │")
            print(f"└{'─'*30}┘")
        
        if b_watchlist:
            print(f"\n┌{'─'*40}┐")
            print(f"│   👀 관심종목 ({len(b_watchlist)}개)                  │")
            print(f"└{'─'*40}┘")
            # 가로 4줄 배치 (최대 10개)
            symbols = [signal['symbol'] for signal in b_watchlist[:10]]
            for i in range(0, len(symbols), 4):
                row = symbols[i:i+4]
                formatted_row = [f"\033[93m{symbol}\033[0m" for symbol in row]
                print(f"   👀 {' | '.join(formatted_row)}")
        else:
            print(f"\n┌{'─'*30}┐")
            print(f"│  👀 관심종목 (없음)        │")
            print(f"└{'─'*30}┘")
        
        # 🇨 C전략(3분봉 바닥급등타점) 결과
        print(f"\n🇨 C전략(3분봉 바닥급등타점) 결과")
        print(f"{'='*60}")
        
        if c_entry_signals:
            print(f"┌{'─'*30}┐")
            print(f"│   🔥 진입신호 ({len(c_entry_signals)}개)        │")
            print(f"└{'─'*30}┘")
            # 2x2 배치
            for i in range(0, len(c_entry_signals), 2):
                row = c_entry_signals[i:i+2]
                if len(row) == 2:
                    print(f"   🎯 {GREEN}{row[0]['symbol']:<8}{RESET}   🎯 {GREEN}{row[1]['symbol']}{RESET}")
                else:
                    print(f"   🎯 {GREEN}{row[0]['symbol']}{RESET}")
        else:
            print(f"┌{'─'*30}┐")
            print(f"│  🔥 진입신호 (없음)        │")
            print(f"└{'─'*30}┘")
        
        if c_near_entry:
            print(f"\n┌{'─'*55}┐")
            print(f"│  🔥 진입임박 ({len(c_near_entry)}개) - 조건 1개 미충족                 │")
            print(f"└{'─'*55}┘")
            for signal in c_near_entry:
                # 해당 심볼의 원본 결과 찾기
                original_result = next((r for r in all_results if r['symbol'].replace('/USDT:USDT', '') == signal['symbol']), None)
                failed_conds = get_failed_conditions(original_result, 'C') if original_result else []
                failed_text = "\033[91m" + ", ".join(failed_conds) + "\033[0m" if failed_conds else "\033[91m미상\033[0m"
                print(f"   🔥 \033[93m{signal['symbol']}\033[0m - 미충족: {failed_text}")
        else:
            print(f"\n┌{'─'*30}┐")
            print(f"│  🔥 진입임박 (없음)        │")
            print(f"└{'─'*30}┘")
        
        if c_potential_entry:
            print(f"\n┌{'─'*55}┐")
            print(f"│  ⚡ 진입확률 ({len(c_potential_entry)}개) - 조건 2개 미충족                 │")
            print(f"└{'─'*55}┘")
            # 가로 4줄 배치
            symbols = [signal['symbol'] for signal in c_potential_entry]
            for i in range(0, len(symbols), 4):
                row = symbols[i:i+4]
                formatted_row = [f"\033[93m{symbol}\033[0m" for symbol in row]
                print(f"   ⚡ {' | '.join(formatted_row)}")
        else:
            print(f"\n┌{'─'*30}┐")
            print(f"│  ⚡ 진입확률 (없음)        │")
            print(f"└{'─'*30}┘")
        
        if c_watchlist:
            print(f"\n┌{'─'*40}┐")
            print(f"│   👀 관심종목 ({len(c_watchlist)}개)                  │")
            print(f"└{'─'*40}┘")
            # 가로 4줄 배치 (최대 10개)
            symbols = [signal['symbol'] for signal in c_watchlist[:10]]
            for i in range(0, len(symbols), 4):
                row = symbols[i:i+4]
                formatted_row = [f"\033[93m{symbol}\033[0m" for symbol in row]
                print(f"   👀 {' | '.join(formatted_row)}")
        else:
            print(f"\n┌{'─'*30}┐")
            print(f"│  👀 관심종목 (없음)        │")
            print(f"└{'─'*30}┘")
        
        # 📊 전체 진입신호 통합 (실제 거래 대상) - a_entry_signals, b_entry_signals, c_entry_signals 통합
        all_entry_signals = []
        
        # A전략, B전략, C전략의 진입신호 통합 (A전략 비활성화로 제외)
        # for signal in a_entry_signals:
        #     signal_copy = signal.copy()
        #     signal_copy['strategy_type'] = '[A전략]'
        #     all_entry_signals.append(signal_copy)
            
        for signal in b_entry_signals:
            signal_copy = signal.copy()
            signal_copy['strategy_type'] = '[B전략]'
            all_entry_signals.append(signal_copy)
            
        for signal in c_entry_signals:
            signal_copy = signal.copy()
            signal_copy['strategy_type'] = '[C전략]'
            all_entry_signals.append(signal_copy)
        
        # 중복 제거 (같은 심볼이 여러 전략에서 신호가 나온 경우)
        unique_signals = {}
        strategy_counts = {}
        
        for signal in all_entry_signals:
            symbol = signal['symbol']
            strategy = signal['strategy_type']
            
            if symbol not in unique_signals:
                unique_signals[symbol] = signal
                strategy_counts[symbol] = [strategy]
            else:
                strategy_counts[symbol].append(strategy)
        
        # 중복된 경우 전략 조합으로 표시
        for symbol, strategies in strategy_counts.items():
            if len(strategies) > 1:
                strategy_names = [s.replace('[', '').replace(']', '') for s in strategies]
                combined_strategy = f"[{'+'.join(sorted(strategy_names))}전략]"
                unique_signals[symbol]['strategy_type'] = combined_strategy
                
        final_entry_signals = list(unique_signals.values())
        
        if final_entry_signals:
            print(f"\n🎯 전체 진입신호 통합 ({len(final_entry_signals)}개) - B+C전략")
            print(f"{'─'*40}")
            for signal in final_entry_signals:
                clean_symbol = signal['symbol'].replace('/USDT:USDT', '')
                strategy_type = signal['strategy_type']
                print(f"   🎯 {GREEN}{clean_symbol}{RESET} {strategy_type}")
        else:
            print(f"\n🎯 전체 진입신호 통합 (없음) - B+C전략")
    
    def _load_notification_history(self):
        """텔레그램 알림 기록 로드"""
        try:
            if os.path.exists(self.notification_file):
                with open(self.notification_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 24시간 이전 기록은 삭제 (하루가 지나면 재알림 허용)
                    current_time = get_korea_time()
                    cutoff_time = current_time - timedelta(hours=24)
                    
                    filtered_data = {}
                    for symbol, record in data.items():
                        record_time = datetime.fromisoformat(record['timestamp'])
                        if record_time > cutoff_time:
                            filtered_data[symbol] = record
                    
                    return filtered_data
            return {}
        except Exception as e:
            print(f"[WARN] 알림 기록 로드 실패: {e}")
            return {}
    
    def _save_notification_history(self):
        """텔레그램 알림 기록 저장"""
        try:
            with open(self.notification_file, 'w', encoding='utf-8') as f:
                json.dump(self.sent_notifications, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"[WARN] 알림 기록 저장 실패: {e}")
    
    def _should_send_notification(self, symbol, strategy_type, reason="entry_signal"):
        """중복 알림 체크 - 같은 심볼의 같은 사유로는 24시간 내 재전송 안함"""
        clean_symbol = symbol.replace('/USDT:USDT', '')
        notification_key = f"{clean_symbol}_{strategy_type}_{reason}"
        
        if notification_key in self.sent_notifications:
            last_sent = datetime.fromisoformat(self.sent_notifications[notification_key]['timestamp'])
            current_time = get_korea_time()
            time_diff = current_time - last_sent
            
            if time_diff.total_seconds() < 24 * 3600:  # 24시간 이내
                hours_ago = time_diff.total_seconds() / 3600
                minutes_ago = time_diff.total_seconds() / 60
                
                if hours_ago >= 1:
                    time_str = f"{hours_ago:.1f}시간 전"
                else:
                    time_str = f"{minutes_ago:.0f}분 전"
                
                print(f"   ⏭️ \033[92m{clean_symbol}\033[0m 💚 {strategy_type} 알림 중복 방지 - 이미 전송함 ({time_str})")
                return False
        
        return True
    
    def _record_notification(self, symbol, strategy_type, reason="entry_signal"):
        """알림 전송 기록"""
        clean_symbol = symbol.replace('/USDT:USDT', '')
        notification_key = f"{clean_symbol}_{strategy_type}_{reason}"
        
        self.sent_notifications[notification_key] = {
            'symbol': clean_symbol,
            'strategy_type': strategy_type,
            'reason': reason,
            'timestamp': get_korea_time().isoformat()
        }
        
        # 즉시 저장
        self._save_notification_history()
        print(f"   📝 \033[92m{clean_symbol}\033[0m 💚 {strategy_type} 텔레그램 알림 전송 완료 및 기록 저장")
    
    def _load_active_positions(self):
        """실제 거래소에서 활성 포지션 로드"""
        try:
            if not self.private_exchange:
                print("⚠️ 프라이빗 API 없음 - 포지션 조회 건너뛰기")
                if not hasattr(self, 'active_positions'):
                    self.active_positions = {}
                return
                
            # 실제 포지션 조회
            positions = self.private_exchange.fetch_positions()
            
            # 실제 포지션이 있는 심볼들을 active_positions에 추가
            for position in positions:
                if position['contracts'] > 0:  # 포지션이 있는 경우
                    symbol = position['symbol']
                    self.active_positions[symbol] = {
                        'size': position['contracts'],
                        'side': position['side'],
                        'entry_price': position['entryPrice'],
                        'mark_price': position['markPrice'],
                        'unrealized_pnl': position['unrealizedPnl'],
                        'percentage': position['percentage']
                    }
            
            print(f"[INFO] 실제 포지션 로드 완료: {len(self.active_positions)}개")
            if self.active_positions:
                for symbol, pos in self.active_positions.items():
                    clean_symbol = symbol.replace('/USDT:USDT', '')
                    print(f"   • {clean_symbol}: {pos['percentage']:+.2f}% (${pos['size']:,.0f})")
                    
        except Exception as e:
            print(f"[WARN] 포지션 로드 실패: {e}")
            # 실패시 빈 딕셔너리로 초기화
            if not hasattr(self, 'active_positions'):
                self.active_positions = {}
    
    def get_portfolio_summary(self):
        """실제 포트폴리오 현황 조회"""
        try:
            if not self.private_exchange:
                return {
                    'free_balance': 0,
                    'total_balance': 0, 
                    'total_unrealized_pnl': 0,
                    'open_positions': 0,
                    'positions': {}
                }
                
            # 실제 잔고 조회
            balance = self.private_exchange.fetch_balance()
            
            # 포지션 재조회
            positions = self.private_exchange.fetch_positions()
            active_positions = [p for p in positions if p['contracts'] > 0]
            
            total_unrealized_pnl = sum(p.get('unrealizedPnl', 0) for p in active_positions)
            free_balance = balance['USDT']['free']
            total_balance = balance['USDT']['total']
            
            return {
                'free_balance': free_balance,
                'total_balance': total_balance,
                'total_unrealized_pnl': total_unrealized_pnl,
                'open_positions': len(active_positions),
                'positions': {p['symbol']: {
                    'symbol': p['symbol'],
                    'size': p['contracts'], 
                    'side': p['side'],
                    'entry_price': p['entryPrice'],
                    'mark_price': p['markPrice'],
                    'unrealized_pnl': p['unrealizedPnl'],
                    'percentage': p['percentage']
                } for p in active_positions}
            }
            
        except Exception as e:
            self.logger.error(f"포트폴리오 조회 실패: {e}")
            return {
                'free_balance': 0,
                'total_balance': 0, 
                'total_unrealized_pnl': 0,
                'open_positions': 0,
                'positions': {}
            }
    
    def get_ohlcv_data(self, symbol, timeframe, limit=1000):
        """OHLCV 데이터 조회 (캐싱 시스템 적용)"""
        try:
            # 캐시 체크
            cache_key = f"{symbol}_{timeframe}"
            current_time = time.time()
            
            if cache_key in self._ohlcv_cache:
                cached_data, cached_time = self._ohlcv_cache[cache_key]
                if current_time - cached_time < self._ohlcv_cache_ttl:
                    if len(cached_data) >= limit:
                        return cached_data.tail(limit)
                    return cached_data
            
            # API 호출
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if ohlcv and len(ohlcv) >= 10:
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # 캐시 저장
                self._ohlcv_cache[cache_key] = (df, current_time)
                return df
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"{symbol} {timeframe} 데이터 조회 실패: {e}")
            return None
    
    def calculate_indicators(self, df):
        """기술적 지표 계산"""
        try:
            if df is None or len(df) == 0:
                return None
            
            df = df.copy()
            
            # 기본 이동평균선
            df['ma5'] = df['close'].rolling(window=5).mean()
            df['ma20'] = df['close'].rolling(window=20).mean()
            df['ma80'] = df['close'].rolling(window=80).mean()
            df['ma480'] = df['close'].rolling(window=480).mean()
            
            # 볼린저 밴드
            # BB200 (기간 200, 표준편차 2.0)
            if len(df) >= 200:
                bb200_ma = df['close'].rolling(window=200).mean()
                bb200_std = df['close'].rolling(window=200).std()
                df['bb200_upper'] = bb200_ma + (bb200_std * 2.0)
                df['bb200_lower'] = bb200_ma - (bb200_std * 2.0)
                df['bb200_middle'] = bb200_ma
            
            # BB480 (기간 480, 표준편차 1.5)
            if len(df) >= 480:
                bb480_ma = df['close'].rolling(window=480).mean()
                bb480_std = df['close'].rolling(window=480).std()
                df['bb480_upper'] = bb480_ma + (bb480_std * 1.5)
                df['bb480_lower'] = bb480_ma - (bb480_std * 1.5)
                df['bb480_middle'] = bb480_ma
            
            # BB80 (기간 80, 표준편차 2.0) - B전략에서 필요
            if len(df) >= 80:
                bb80_ma = df['close'].rolling(window=80).mean()
                bb80_std = df['close'].rolling(window=80).std()
                df['bb80_upper'] = bb80_ma + (bb80_std * 2.0)
                df['bb80_lower'] = bb80_ma - (bb80_std * 2.0)
                df['bb80_middle'] = bb80_ma
            
            return df
            
        except Exception as e:
            self.logger.error(f"지표 계산 실패: {e}")
            return df
    
    def check_fifteen_minute_mega_conditions(self, symbol, df_15m):
        # 🔥🔥🔥 UPDATED VERSION - MA480 FIX 🔥🔥🔥
        """
        A전략(15분봉 바닥타점) + B전략(15분봉 급등초입) + C전략(3분봉 필살기 타점) 조건 체크
        
        A전략: 15분봉 바닥타점 (5개 조건)
        - (ma80<ma480 and ma5<ma480) AND
        - ((15분봉상 60봉이내 (bb80상단선-bb200상단선 이격도 1%이내 or bb80상단선-bb200상단선 골든크로스) or 
           (5분봉상 30봉이내 bb80상단선-bb200상단선 골든크로스)) AND
        - ((5봉이내 1봉전 ma5-ma80 골든크로스) or (5봉이내 ma5-ma20 골든크로스 ma5>ma20 and ma5우상향 2회이상)) AND
        - (현재가 ma5이격도 0.5%이내 or 현재가<ma5) AND
        - 15분봉상 10봉이내 시가대비고가 3%이상 1회이상 or 30분봉상 10봉이내 시가대비고가 3%이상 1회이상
        
        B전략: 15분봉 급등초입 (6개 조건)
        - 200봉 이내 MA80-MA480 골든크로스 AND
        - BB 골든크로스 AND
        - 10봉 이내 1봉전 MA5-MA20 골든크로스 AND (현재가<ma5 or 현재가-ma5 이격도 0.5%이내) AND
        - 250봉이내 BB200상단-MA480 상향돌파 AND
        - 40봉이내 데드크로스/이격도/시가대비고가 조건 AND
        - 200봉이내 시가대비고가 3%이상 1회이상
        
        C전략: 3분봉 바닥급등타점 (4개 조건)
        - (10봉이내 MA80-MA480 골든크로스 or 현재봉 MA80<MA480) AND
        - 15봉이내 BB80상단선-BB480상단선 골든크로스 AND
        - 5봉이내 1봉전 종가<MA5 골든크로스 AND
        - (3분봉상 or 15분봉상) 20봉이내 시가대비고가 3%이상 1회이상
        
        Args:
            symbol: 심볼명
            df_15m: 15분봉 데이터프레임
        
        Returns:
            tuple: (조건충족여부, 조건상세리스트, 전략상세정보)
        """
        conditions = []
        clean_symbol = symbol.replace('/USDT:USDT', '')
        
        if df_15m is None or len(df_15m) < 480:
            conditions.append("[전체 전략] 15분봉 데이터 부족 (480봉 필요)")
            return False, conditions, {}
        
        # 지표 계산 (BB80 포함)
        df_calc = self.calculate_indicators(df_15m)
        if df_calc is None:
            conditions.append("[전체 전략] 15분봉 지표 계산 실패")
            return False, conditions, {}
        
        try:
            clean_sym = symbol.replace('/USDT:USDT', '')
            # print(f"*** FIXED VERSION: {clean_sym} ***")  # 디버그용 주석처리
            
            # 🔥 CRITICAL FIX: 15분봉 MA80 < MA480 전제조건 체크
            ma80_15m = df_calc['ma80'].iloc[-1]  # 15분봉 MA80
            ma5_15m = df_calc['ma5'].iloc[-1]   # 15분봉 MA5
            ma480_15m = df_calc['ma480'].iloc[-1]  # 15분봉 MA480
            
            # 15분봉 MA480 데이터 유효성 체크
            if pd.isna(ma480_15m) or pd.isna(ma80_15m) or pd.isna(ma5_15m):
                conditions.append(f"[BLOCKED] 15분봉 MA480 계산 실패 - 데이터 부족 (필요:480봉, 현재:{len(df_15m)})")
                return False, conditions, {
                    'strategy_a': {'signal': False, 'conditions': conditions, 'name': 'A전략(MA계산실패)'},
                    'strategy_b': {'signal': False, 'conditions': [], 'name': 'B전략(MA계산실패)'},
                    'strategy_c': {'signal': False, 'conditions': [], 'name': 'C전략(MA계산실패)'}
                }
            
            # 전제조건 제거 - B전략에서 별도로 적용하지 않음
            # basic_ma_condition = (ma80_15m < ma480_15m and ma5_15m < ma480_15m)
            
            # 전제조건 체크 제거
            # if not basic_ma_condition:
            #     conditions.append(f"[BLOCKED] 15분봉MA80≥MA480 전제조건 차단 - MA80:{ma80_15m:.6f}, MA480:{ma480_15m:.6f}")
            #     return False, conditions, {
            #         'strategy_a': {'signal': False, 'conditions': conditions, 'name': 'A전략(차단됨)'},
            #         'strategy_b': {'signal': False, 'conditions': [], 'name': 'B전략(차단됨)'},
            #         'strategy_c': {'signal': False, 'conditions': [], 'name': 'C전략(차단됨)'}
            #     }
            
            # 전제조건 체크 없이 바로 전략 실행
            # 전제조건 통과한 심볼에 대한 로그는 제거 (너무 많음)
            
            # A전략: 15분봉 바닥 타점 체크 (임시 비활성화)
            # strategy_a_signal, strategy_a_conditions = self._check_strategy_a_bottom_entry(symbol, df_calc)
            strategy_a_signal = False  # A전략 임시 비활성화
            strategy_a_conditions = ["[A전략] 임시 비활성화됨"]
            
            # B전략: 15분봉 급등초입 타점 체크
            strategy_b_signal, strategy_b_conditions = self._check_strategy_b_uptrend_entry(df_calc)
            
            # C전략: 3분봉 필살기 타점 체크
            strategy_c_signal, strategy_c_conditions = self._check_strategy_c_3min_precision(symbol)
            
            # 최종 신호 결정 (A전략 제외)
            is_signal = strategy_b_signal or strategy_c_signal  # A전략 비활성화
            
            
            # 전략별 상세 정보 구성
            strategy_details = {
                'strategy_a': {
                    'signal': strategy_a_signal,
                    'conditions': strategy_a_conditions,
                    'name': 'A전략(바닥타점)'
                },
                'strategy_b': {
                    'signal': strategy_b_signal, 
                    'conditions': strategy_b_conditions,
                    'name': 'B전략(급등초입)'
                },
                'strategy_c': {
                    'signal': strategy_c_signal,
                    'conditions': strategy_c_conditions,
                    'name': 'C전략(3분봉 바닥급등타점)'
                }
            }
            
            # 기존 조건 리스트 구성 (호환성 유지)
            conditions.extend(strategy_a_conditions)
            conditions.extend(strategy_b_conditions)
            conditions.extend(strategy_c_conditions)
            
            # 전략별 결과 추가 (A전략 비활성화)
            if strategy_a_signal:
                conditions.append("[전략결과] A전략(바닥타점) 조건 충족 ✅ (비활성화됨)")
            if strategy_b_signal:
                conditions.append("[전략결과] B전략(급등초입) 조건 충족 ✅")
            if strategy_c_signal:
                conditions.append("[전략결과] C전략(3분봉 필살기) 조건 충족 ✅")
            if not is_signal:
                conditions.append("[전략결과] B전략, C전략 모두 미충족 ❌ (A전략 비활성화)")
            
            
            # 디버그 로그
            if is_signal:
                strategy_names = []
                # if strategy_a_signal:
                #     strategy_names.append("A전략(바닥타점)")  # A전략 비활성화
                if strategy_b_signal:
                    strategy_names.append("B전략(급등초입)")
                if strategy_c_signal:
                    strategy_names.append("C전략(3분봉 필살기)")
                
                strategy_name = "+".join(strategy_names)
                self._write_debug_log(f"🎯 [{clean_symbol}] {strategy_name} 조건 충족!")
                for condition in conditions:
                    self._write_debug_log(f"   {condition}")
            
            return is_signal, conditions, strategy_details
            
        except Exception as e:
            conditions.append(f"[전체 전략] 조건 체크 오류: {str(e)}")
            self.logger.error(f"[{clean_symbol}] 전체 전략 조건 체크 실패: {e}")
            strategy_details = {
                'strategy_a': {'signal': False, 'conditions': [], 'name': 'A전략(바닥타점)'},
                'strategy_b': {'signal': False, 'conditions': [], 'name': 'B전략(급등초입)'},
                'strategy_c': {'signal': False, 'conditions': [], 'name': 'C전략(3분봉 바닥급등타점)'}
            }
            return False, conditions, strategy_details
    
    def _check_strategy_a_bottom_entry(self, symbol, df_calc):
        """A전략: 15분봉 바닥 타점"""
        try:
            # print(f"🅰️ A전략 체크 시작: {symbol.replace('/USDT:USDT', '')}")  # 디버그용 주석처리
            conditions = []
            
            # 조건 1: ma80<ma480 and ma5<ma480
            ma80 = df_calc['ma80'].iloc[-1]
            ma480 = df_calc['ma480'].iloc[-1]
            ma5 = df_calc['ma5'].iloc[-1]
            
            condition1 = (pd.notna(ma80) and pd.notna(ma480) and pd.notna(ma5) and
                         ma80 < ma480 and ma5 < ma480)
            conditions.append(f"[A전략 조건1] MA80<MA480 AND MA5<MA480: {condition1} (MA80:{ma80:.4f}, MA480:{ma480:.4f}, MA5:{ma5:.4f})")
            
            # 조건 2: BB 이격도 및 골든크로스 체크
            condition2 = False
            try:
                # 15분봉상 60봉이내 BB80상단선-BB200상단선 이격도 1%이내 or 골든크로스
                bb80_upper = df_calc.get('bb80_upper', pd.Series())
                bb200_upper = df_calc['bb200_upper']
                
                # 15분봉 BB 체크
                bb_15m_check = False
                if len(bb80_upper) >= 60 and len(bb200_upper) >= 60:
                    for i in range(min(60, len(bb80_upper))):
                        bb80_val = bb80_upper.iloc[-(i+1)]
                        bb200_val = bb200_upper.iloc[-(i+1)]
                        
                        if pd.notna(bb80_val) and pd.notna(bb200_val) and bb200_val > 0:
                            # 이격도 1%이내 체크
                            gap_pct = abs(bb80_val - bb200_val) / bb200_val
                            if gap_pct <= 0.01:
                                bb_15m_check = True
                                break
                            
                            # 골든크로스 체크 (i>0일때만)
                            if i > 0:
                                bb80_prev = bb80_upper.iloc[-(i+2)]
                                bb200_prev = bb200_upper.iloc[-(i+2)]
                                if (pd.notna(bb80_prev) and pd.notna(bb200_prev) and
                                    bb80_prev <= bb200_prev and bb80_val > bb200_val):
                                    bb_15m_check = True
                                    break
                
                # 5분봉상 100봉이내 BB80상단선-BB200상단선 골든크로스
                bb_5m_check = False
                try:
                    # 5분봉 데이터 조회 (BB200 계산을 위해 충분한 데이터 확보)
                    df_5m = self.get_ohlcv_data(symbol, '5m', limit=500)
                    if df_5m is not None and len(df_5m) >= 200:
                        df_5m_calc = self.calculate_indicators(df_5m)
                        if df_5m_calc is not None and len(df_5m_calc) >= 200:
                            # BB80 계산
                            bb80_ma_5m = df_5m_calc['close'].rolling(window=80).mean()
                            bb80_std_5m = df_5m_calc['close'].rolling(window=80).std()
                            bb80_5m = bb80_ma_5m + (bb80_std_5m * 2.0)
                            bb200_5m = df_5m_calc['bb200_upper']
                            
                            if len(bb80_5m) >= 100 and len(bb200_5m) >= 100:
                                for i in range(1, min(101, len(bb80_5m))):
                                    bb80_prev = bb80_5m.iloc[-i-1]
                                    bb80_curr = bb80_5m.iloc[-i]
                                    bb200_prev = bb200_5m.iloc[-i-1]
                                    bb200_curr = bb200_5m.iloc[-i]
                                    
                                    if (pd.notna(bb80_prev) and pd.notna(bb80_curr) and
                                        pd.notna(bb200_prev) and pd.notna(bb200_curr) and
                                        bb80_prev <= bb200_prev and bb80_curr > bb200_curr):
                                        bb_5m_check = True
                                        break
                except:
                    pass
                
                condition2 = bb_15m_check or bb_5m_check
                bb_status = "15분봉" if bb_15m_check else "5분봉" if bb_5m_check else "미충족"
                conditions.append(f"[A전략 조건2] BB 이격도/골든크로스 ({bb_status}): {condition2}")
            except Exception as e:
                conditions.append(f"[A전략 조건2] BB 조건 계산 실패: {e}")
            
            # 조건 3: MA 골든크로스 조건
            condition3 = False
            try:
                ma5 = df_calc['ma5']
                ma20 = df_calc['ma20']
                ma80 = df_calc['ma80']
                
                # 10봉이내 1봉전 MA5-MA80 골든크로스
                ma5_ma80_cross = False
                if len(ma5) >= 11 and len(ma80) >= 11:
                    for i in range(1, min(11, len(ma5)-1)):  # 1봉전부터 체크
                        prev_idx = -(i+2)  # 1봉전
                        curr_idx = -(i+1)  # 현재
                        ma5_prev = ma5.iloc[prev_idx]
                        ma5_curr = ma5.iloc[curr_idx]
                        ma80_prev = ma80.iloc[prev_idx]
                        ma80_curr = ma80.iloc[curr_idx]
                        
                        if (pd.notna(ma5_prev) and pd.notna(ma5_curr) and 
                            pd.notna(ma80_prev) and pd.notna(ma80_curr) and
                            ma5_prev <= ma80_prev and ma5_curr > ma80_curr):
                            ma5_ma80_cross = True
                            break
                
                # 10봉이내 1봉전 MA5-MA20 골든크로스 with 조건
                ma5_ma20_cross = False
                if len(ma5) >= 11 and len(ma20) >= 11:
                    for i in range(1, min(11, len(ma5)-1)):  # 1봉전부터 체크
                        prev_idx = -(i+2)  # 1봉전
                        curr_idx = -(i+1)  # 현재
                        ma5_prev = ma5.iloc[prev_idx]
                        ma5_curr = ma5.iloc[curr_idx]
                        ma20_prev = ma20.iloc[prev_idx]
                        ma20_curr = ma20.iloc[curr_idx]
                        
                        if (pd.notna(ma5_prev) and pd.notna(ma5_curr) and
                            pd.notna(ma20_prev) and pd.notna(ma20_curr) and
                            ma5_prev <= ma20_prev and ma5_curr > ma20_curr):
                            # 0봉상 MA5>MA20 체크
                            current_ma5 = ma5.iloc[-1]
                            current_ma20 = ma20.iloc[-1]
                            
                            if pd.notna(current_ma5) and pd.notna(current_ma20) and current_ma5 > current_ma20:
                                ma5_ma20_cross = True
                                break
                
                condition3 = ma5_ma80_cross or ma5_ma20_cross
                cross_type = "MA5-MA80" if ma5_ma80_cross else "MA5-MA20" if ma5_ma20_cross else "미충족"
                conditions.append(f"[A전략 조건3] MA 골든크로스 ({cross_type}): {condition3}")
            except Exception as e:
                conditions.append(f"[A전략 조건3] MA 골든크로스 계산 실패: {e}")
            
            # 조건 4: (현재가-MA5 이격도0.5%이내 or 1봉전 종가<ma5)
            condition4 = False
            try:
                current_price = df_calc['close'].iloc[-1]
                ma5_current = df_calc['ma5'].iloc[-1]
                
                if pd.notna(current_price) and pd.notna(ma5_current) and ma5_current > 0:
                    # 현재가 MA5 이격도 0.5%이내 체크
                    ma5_distance = abs(current_price - ma5_current) / ma5_current
                    condition4_distance = ma5_distance <= 0.005
                    
                    # 1봉전 종가 < MA5 체크
                    condition4_prev_close = False
                    if len(df_calc) >= 2:
                        prev_close = df_calc['close'].iloc[-2]
                        prev_ma5 = df_calc['ma5'].iloc[-2]
                        if pd.notna(prev_close) and pd.notna(prev_ma5):
                            condition4_prev_close = prev_close < prev_ma5
                    
                    condition4 = condition4_distance or condition4_prev_close
                
                price_status = "이격도 0.5%이내" if condition4_distance else "1봉전종가<MA5" if condition4_prev_close else "미충족"
                conditions.append(f"[A전략 조건4] 현재가-MA5 이격도0.5%이내 OR 1봉전종가<MA5 ({price_status}): {condition4}")
            except Exception as e:
                conditions.append(f"[A전략 조건4] 현재가-MA5 조건 계산 실패: {e}")
            
            # 조건 5: 15분봉상 10봉이내 시가대비고가 3%이상 1회이상 or 30분봉상 10봉이내 시가대비고가 3%이상 1회이상
            condition5 = False
            try:
                # 15분봉 체크
                high_move_15m_count = 0
                high_move_15m_found = False
                if len(df_calc) >= 10:
                    for i in range(min(10, len(df_calc))):
                        candle = df_calc.iloc[-(i+1)]
                        if pd.notna(candle['open']) and pd.notna(candle['high']) and candle['open'] > 0:
                            high_move_pct = ((candle['high'] - candle['open']) / candle['open']) * 100
                            if high_move_pct >= 3.0:
                                high_move_15m_count += 1
                    high_move_15m_found = high_move_15m_count >= 1

                # 30분봉 체크
                high_move_30m_count = 0
                high_move_30m_found = False
                try:
                    df_30m = self.get_ohlcv_data(symbol, '30m', limit=50)
                    if df_30m is not None and len(df_30m) >= 10:
                        for i in range(min(10, len(df_30m))):
                            candle = df_30m.iloc[-(i+1)]
                            if pd.notna(candle['open']) and pd.notna(candle['high']) and candle['open'] > 0:
                                high_move_pct = ((candle['high'] - candle['open']) / candle['open']) * 100
                                if high_move_pct >= 3.0:
                                    high_move_30m_count += 1
                        high_move_30m_found = high_move_30m_count >= 1
                except Exception:
                    pass

                condition5 = high_move_15m_found or high_move_30m_found
                
                status_detail = f"15분봉:{high_move_15m_count}회" if high_move_15m_found else f"30분봉:{high_move_30m_count}회" if high_move_30m_found else "미충족"
                conditions.append(f"[A전략 조건5] 시가대비고가 3%이상 ({status_detail}): {condition5}")
            except Exception as e:
                conditions.append(f"[A전략 조건5] 시가대비고가 조건 계산 실패: {e}")
            
            # A전략 최종 판정: 모든 조건 충족
            strategy_a_signal = condition1 and condition2 and condition3 and condition4 and condition5
            
            
            
            return strategy_a_signal, conditions
            
        except Exception as e:
            return False, [f"A전략 체크 실패: {e}"]
    
    def _check_strategy_b_uptrend_entry(self, df_calc):
        """B전략: 15분봉 급등초입"""
        try:
            conditions = []
            
            # 조건 1: 200봉이내 MA80-MA480 골든크로스
            condition1 = False
            condition1_detail = "골든크로스 없음"
            
            if len(df_calc) >= 200:
                for i in range(len(df_calc) - 200, len(df_calc)):
                    if i <= 0:
                        continue
                    
                    prev_candle = df_calc.iloc[i-1]
                    curr_candle = df_calc.iloc[i]
                    
                    # 골든크로스: 이전봉에서 MA80 < MA480, 현재봉에서 MA80 >= MA480
                    if (pd.notna(prev_candle['ma80']) and pd.notna(prev_candle['ma480']) and
                        pd.notna(curr_candle['ma80']) and pd.notna(curr_candle['ma480']) and
                        prev_candle['ma80'] < prev_candle['ma480'] and
                        curr_candle['ma80'] >= curr_candle['ma480']):
                        condition1 = True
                        bars_ago = len(df_calc) - i - 1
                        condition1_detail = f"{bars_ago}봉전 골든크로스"
                        break
            
            conditions.append(f"[B전략 조건1] MA80-MA480 골든크로스 ({condition1_detail}): {condition1}")
            
            # 조건 2: BB 골든크로스 (200봉이내)
            condition2 = False
            condition2_detail = "골든크로스 없음"
            
            if len(df_calc) >= 200:
                # BB200상단선(표편2)-BB480상단선(표편1.5) 골든크로스 또는 이격도 1%이내 체크
                bb200_upper = df_calc['bb200_upper']
                bb480_upper = df_calc['bb480_upper']
                
                if len(bb200_upper) >= 200 and len(bb480_upper) >= 200:
                    for i in range(min(200, len(bb200_upper))):
                        bb200_val = bb200_upper.iloc[-(i+1)]
                        bb480_val = bb480_upper.iloc[-(i+1)]
                        
                        if pd.notna(bb200_val) and pd.notna(bb480_val) and bb480_val > 0:
                            # 이격도 1%이내 체크
                            gap_pct = abs(bb200_val - bb480_val) / bb480_val
                            if gap_pct <= 0.01:
                                condition2 = True
                                condition2_detail = f"BB200-BB480 이격도 1%이내 {i}봉전"
                                break
                            
                            # 골든크로스 체크 (i>0일때만)
                            if i > 0:
                                bb200_prev = bb200_upper.iloc[-(i+2)]
                                bb480_prev = bb480_upper.iloc[-(i+2)]
                                if (pd.notna(bb200_prev) and pd.notna(bb480_prev) and
                                    bb200_prev <= bb480_prev and bb200_val > bb480_val):
                                    condition2 = True
                                    condition2_detail = f"BB200-BB480 골든크로스 {i}봉전"
                                    break
                
                # BB80상단선(표편2)-BB480상단선(표편1.5) 골든크로스 또는 이격도 1%이내 체크 (위에서 못찾은 경우)
                if not condition2:
                    bb80_upper = df_calc.get('bb80_upper', pd.Series())
                    bb480_upper = df_calc['bb480_upper']
                    
                    if len(bb80_upper) >= 200 and len(bb480_upper) >= 200:
                        for i in range(min(200, len(bb80_upper))):
                            bb80_val = bb80_upper.iloc[-(i+1)]
                            bb480_val = bb480_upper.iloc[-(i+1)]
                            
                            if pd.notna(bb80_val) and pd.notna(bb480_val) and bb480_val > 0:
                                # 이격도 1%이내 체크
                                gap_pct = abs(bb80_val - bb480_val) / bb480_val
                                if gap_pct <= 0.01:
                                    condition2 = True
                                    condition2_detail = f"BB80-BB480 이격도 1%이내 {i}봉전"
                                    break
                                
                                # 골든크로스 체크 (i>0일때만)
                                if i > 0:
                                    bb80_prev = bb80_upper.iloc[-(i+2)]
                                    bb480_prev = bb480_upper.iloc[-(i+2)]
                                    if (pd.notna(bb80_prev) and pd.notna(bb480_prev) and
                                        bb80_prev <= bb480_prev and bb80_val > bb480_val):
                                        condition2 = True
                                        condition2_detail = f"BB80-BB480 골든크로스 {i}봉전"
                                        break
            
            conditions.append(f"[B전략 조건2] BB 골든크로스 ({condition2_detail}): {condition2}")
            
            # 조건 3: 10봉이내 1봉전 MA5-MA20 골든크로스 AND (현재가<MA5 or 현재가-MA5 이격도 0.5%이내)
            condition3 = False
            condition3_detail = "골든크로스 없음"
            
            # 10봉이내 1봉전 MA5-MA20 골든크로스 체크
            ma5_ma20_cross = False
            if len(df_calc) >= 10:
                for i in range(1, min(11, len(df_calc)-1)):  # 1봉전부터 10봉전까지
                    prev_idx = -(i+2)  # 골든크로스 이전봉
                    curr_idx = -(i+1)  # 골든크로스 봉
                    
                    if abs(prev_idx) > len(df_calc) or abs(curr_idx) > len(df_calc):
                        continue
                    
                    ma5_prev = df_calc['ma5'].iloc[prev_idx]
                    ma5_curr = df_calc['ma5'].iloc[curr_idx]
                    ma20_prev = df_calc['ma20'].iloc[prev_idx]
                    ma20_curr = df_calc['ma20'].iloc[curr_idx]
                    
                    # 골든크로스: 이전봉에서 MA5 < MA20, 현재봉에서 MA5 >= MA20
                    if (pd.notna(ma5_prev) and pd.notna(ma5_curr) and
                        pd.notna(ma20_prev) and pd.notna(ma20_curr) and
                        ma5_prev < ma20_prev and ma5_curr >= ma20_curr):
                        ma5_ma20_cross = True
                        condition3_detail = f"MA5-MA20 골든크로스 {i}봉전"
                        break
            
            # 현재가-MA5 조건 체크
            price_ma5_condition = False
            try:
                current_price = df_calc['close'].iloc[-1]
                ma5_current = df_calc['ma5'].iloc[-1]
                
                if pd.notna(current_price) and pd.notna(ma5_current) and ma5_current > 0:
                    # 현재가 < MA5 or 현재가-MA5 이격도 0.5%이내
                    ma5_distance = abs(current_price - ma5_current) / ma5_current
                    
                    if current_price < ma5_current or ma5_distance <= 0.005:
                        price_ma5_condition = True
                        
            except Exception:
                pass
            
            # 조건3 = 골든크로스 AND 현재가 조건
            condition3 = ma5_ma20_cross and price_ma5_condition
            
            if ma5_ma20_cross and price_ma5_condition:
                condition3_detail += " + 현재가 조건 충족"
            elif ma5_ma20_cross:
                condition3_detail += " (현재가 조건 미충족)"
            elif price_ma5_condition:
                condition3_detail = "골든크로스 없음 (현재가 조건만 충족)"
            
            conditions.append(f"[B전략 조건3] 10봉이내 1봉전 MA5-MA20 골든크로스+현재가조건 ({condition3_detail}): {condition3}")
            
            # 조건 4: 250봉이내 BB200상단선이 MA480 상향돌파
            condition4 = False
            condition4_detail = "상향돌파 없음"
            
            if len(df_calc) >= 250:
                for i in range(len(df_calc) - 250, len(df_calc)):
                    if i <= 0:
                        continue
                    
                    prev_candle = df_calc.iloc[i-1]
                    curr_candle = df_calc.iloc[i]
                    
                    # 상향돌파: 이전봉에서 BB200상단 <= MA480, 현재봉에서 BB200상단 > MA480
                    if (pd.notna(prev_candle['bb200_upper']) and pd.notna(prev_candle['ma480']) and
                        pd.notna(curr_candle['bb200_upper']) and pd.notna(curr_candle['ma480']) and
                        prev_candle['bb200_upper'] <= prev_candle['ma480'] and
                        curr_candle['bb200_upper'] > curr_candle['ma480']):
                        condition4 = True
                        bars_ago = len(df_calc) - i - 1
                        condition4_detail = f"BB200상단-MA480 상향돌파 {bars_ago}봉전"
                        break
            
            conditions.append(f"[B전략 조건4] BB200상단-MA480 상향돌파 ({condition4_detail}): {condition4}")
            
            # 조건 5: 40봉이내 MA20-MA80 데드크로스 or 이격도 조건
            condition5 = False
            try:
                ma5 = df_calc['ma5']
                ma20 = df_calc['ma20']
                ma80 = df_calc['ma80']
                
                # 40봉이내 MA20-MA80 데드크로스
                ma20_ma80_deadcross = False
                if len(ma20) >= 40 and len(ma80) >= 40:
                    for i in range(min(40, len(ma20))):
                        if i == 0:
                            continue
                        ma20_prev = ma20.iloc[-(i+1)]
                        ma20_curr = ma20.iloc[-i]
                        ma80_prev = ma80.iloc[-(i+1)]
                        ma80_curr = ma80.iloc[-i]
                        
                        if (pd.notna(ma20_prev) and pd.notna(ma20_curr) and 
                            pd.notna(ma80_prev) and pd.notna(ma80_curr) and
                            ma20_prev >= ma80_prev and ma20_curr < ma80_curr):
                            ma20_ma80_deadcross = True
                            break
                
                # 현재 이격도 조건 (MA5-MA80 이격도 1%이내 or MA20-MA80 이격도 2%이내)
                distance_condition = False
                if (pd.notna(ma5.iloc[-1]) and pd.notna(ma80.iloc[-1]) and ma80.iloc[-1] > 0):
                    ma5_ma80_distance = abs(ma5.iloc[-1] - ma80.iloc[-1]) / ma80.iloc[-1]
                    if ma5_ma80_distance <= 0.01:
                        distance_condition = True
                
                if not distance_condition and (pd.notna(ma20.iloc[-1]) and pd.notna(ma80.iloc[-1]) and ma80.iloc[-1] > 0):
                    ma20_ma80_distance = abs(ma20.iloc[-1] - ma80.iloc[-1]) / ma80.iloc[-1]
                    if ma20_ma80_distance <= 0.02:
                        distance_condition = True
                
                # 조건 5-3: 15분봉상 100봉이내 시가대비고가 15%이상 and (ma5<bb480상단 or ma5-bb480상단 이격도 2%이내)
                high_move_bb_condition = False
                try:
                    # 100봉이내 시가대비고가 15%이상 체크
                    high_move_15pct_found = False
                    if len(df_calc) >= 100:
                        for i in range(min(100, len(df_calc))):
                            candle = df_calc.iloc[-(i+1)]
                            if pd.notna(candle['open']) and pd.notna(candle['high']) and candle['open'] > 0:
                                high_move_pct = ((candle['high'] - candle['open']) / candle['open']) * 100
                                if high_move_pct >= 15.0:
                                    high_move_15pct_found = True
                                    break
                    
                    # MA5와 BB480상단 조건 체크
                    if high_move_15pct_found:
                        ma5_current = ma5.iloc[-1]
                        bb480_upper = df_calc['bb480_upper'].iloc[-1]
                        
                        if pd.notna(ma5_current) and pd.notna(bb480_upper) and bb480_upper > 0:
                            # MA5 < BB480상단 or MA5-BB480상단 이격도 2%이내
                            if ma5_current < bb480_upper:
                                high_move_bb_condition = True
                            else:
                                bb480_distance = abs(ma5_current - bb480_upper) / bb480_upper
                                if bb480_distance <= 0.02:
                                    high_move_bb_condition = True
                except Exception:
                    pass
                
                condition5 = ma20_ma80_deadcross or distance_condition or high_move_bb_condition
                
                status_detail = "MA20-MA80 데드크로스" if ma20_ma80_deadcross else "이격도 조건" if distance_condition else "시가대비고가15%+BB480조건" if high_move_bb_condition else "미충족"
                conditions.append(f"[B전략 조건5] 데드크로스/이격도/시가대비고가+BB480 ({status_detail}): {condition5}")
            except Exception as e:
                conditions.append(f"[B전략 조건5] 데드크로스/이격도 조건 계산 실패: {e}")
            
            # 조건 6: 15분봉상 200봉이내 시가대비고가 3%이상 1회이상
            condition6 = False
            try:
                if len(df_calc) >= 200:
                    high_move_count = 0
                    for i in range(min(200, len(df_calc))):
                        candle = df_calc.iloc[-(i+1)]
                        if pd.notna(candle['open']) and pd.notna(candle['high']) and candle['open'] > 0:
                            # 시가대비고가 상승률 계산
                            high_move_pct = ((candle['high'] - candle['open']) / candle['open']) * 100
                            if high_move_pct >= 3.0:
                                high_move_count += 1
                    
                    condition6 = high_move_count >= 1
                    
                conditions.append(f"[B전략 조건6] 200봉이내 시가대비고가 3%이상 ({high_move_count}회): {condition6}")
            except Exception as e:
                conditions.append(f"[B전략 조건6] 시가대비고가 조건 계산 실패: {e}")
            
            # B전략 최종 신호 판정: 모든 조건이 True여야 함
            strategy_b_signal = condition1 and condition2 and condition3 and condition4 and condition5 and condition6
            
            
            return strategy_b_signal, conditions
            
        except Exception as e:
            return False, [f"B전략 체크 실패: {e}"]
    
    def _check_strategy_c_3min_precision(self, symbol):
        """C전략: 3분봉 바닥급등타점 (3개 조건) - 개선된 버전
        조건1: 3분봉 300봉이내 MA80-MA480 골든크로스 OR 현재봉 MA80 < MA480
        조건2: 3분봉 300봉이내 BB80상단선(표준편차2)-BB480상단선(표준편차1.5) 골든크로스  
        조건3: 3분봉 5봉이내 1봉전 MA20-MA80 골든크로스
        """
        try:
            conditions = []
            
            # 3분봉 데이터 조회 (300+480=780봉 필요, 여유분으로 850봉 요청)
            try:
                df_3m = None
                
                # 1차 시도: 강화된 WebSocket Provider 사용 (캐시된 3분봉 데이터)
                if self.ws_provider:
                    try:
                        # 메서드가 존재하는지 확인
                        if hasattr(self.ws_provider, 'get_cached_ohlcv'):
                            df_3m = self.ws_provider.get_cached_ohlcv(symbol, '3m', 850)
                        else:
                            # 메서드가 없으면 일반 get_ohlcv 사용
                            df_3m = self.ws_provider.get_ohlcv(symbol, '3m', 850)
                            
                        if df_3m is not None and len(df_3m) >= 780:
                            # WebSocket 성공 - 디버그 메시지
                            if symbol in ['APR/USDT:USDT', 'API3/USDT:USDT', 'PLAY/USDT:USDT']:
                                print(f"[DEBUG] {symbol}: WebSocket 성공 - 3분봉 {len(df_3m)}개")
                            pass
                        else:
                            # 실패시 재시도
                            df_3m = self.ws_provider.get_ohlcv(symbol, '3m', 850)
                            if df_3m is not None and len(df_3m) >= 780:
                                if symbol in ['APR/USDT:USDT', 'API3/USDT:USDT', 'PLAY/USDT:USDT']:
                                    print(f"[DEBUG] {symbol}: 재시도 성공 - 3분봉 {len(df_3m)}개")
                            else:
                                if symbol in ['APR/USDT:USDT', 'API3/USDT:USDT', 'PLAY/USDT:USDT']:
                                    data_len = len(df_3m) if df_3m else 0
                                    print(f"[DEBUG] {symbol}: 데이터 부족 - 3분봉 {data_len}개")
                    except Exception as ws_error:
                        # WebSocket 완전 실패
                        if symbol in ['APR/USDT:USDT', 'API3/USDT:USDT', 'PLAY/USDT:USDT']:
                            print(f"[DEBUG] {symbol}: WebSocket 완전 실패 - {ws_error}")
                        df_3m = None
                
                # 2차 시도: WebSocket 실패시에만 REST API 시도 (API 제한 고려)
                if df_3m is None or len(df_3m) < 780:
                    try:
                        df_3m = self.exchange.fetch_ohlcv(symbol, '3m', limit=850)
                    except Exception as api_error:
                        return False, [f"[C전략] 3분봉 데이터 완전 실패: WebSocket 캐시 실패, REST API 제한 - {api_error}"]
                
                if df_3m is None or len(df_3m) < 780:
                    return False, [f"[C전략] 3분봉 데이터 부족: {len(df_3m) if df_3m is not None else 0}봉 (780봉 필요) - 모든 데이터 소스 실패"]
                
                # DataFrame 변환
                df_calc = pd.DataFrame(df_3m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df_calc['timestamp'] = pd.to_datetime(df_calc['timestamp'], unit='ms')
                
                # 기술적 지표 계산
                df_calc = self.calculate_indicators(df_calc)
                
                if len(df_calc) < 780:
                    return False, [f"[C전략] 지표 계산 후 데이터 부족: {len(df_calc)}봉"]
                    
            except Exception as e:
                return False, [f"[C전략] 3분봉 데이터 조회 실패: {e}"]
            
            # 조건 1: 300봉이내 MA80-MA480 골든크로스 or 현재봉 MA80 < MA480
            condition1 = False
            condition1_detail = "미충족"
            
            try:
                # 현재봉 MA80 < MA480 체크
                current_ma80 = df_calc['ma80'].iloc[-1]
                current_ma480 = df_calc['ma480'].iloc[-1]
                
                if pd.notna(current_ma80) and pd.notna(current_ma480):
                    if current_ma80 < current_ma480:
                        condition1 = True
                        condition1_detail = "현재봉 MA80<MA480"
                    else:
                        # 300봉이내 MA80-MA480 골든크로스 체크
                        if len(df_calc) >= 301:
                            for i in range(min(300, len(df_calc) - 1)):
                                curr_idx = -(i+1)
                                prev_idx = -(i+2)
                                
                                if abs(prev_idx) > len(df_calc):
                                    break
                                    
                                ma80_prev = df_calc['ma80'].iloc[prev_idx]
                                ma80_curr = df_calc['ma80'].iloc[curr_idx]
                                ma480_prev = df_calc['ma480'].iloc[prev_idx]
                                ma480_curr = df_calc['ma480'].iloc[curr_idx]
                                
                                if (pd.notna(ma80_prev) and pd.notna(ma80_curr) and
                                    pd.notna(ma480_prev) and pd.notna(ma480_curr) and
                                    ma80_prev <= ma480_prev and ma80_curr > ma480_curr):
                                    condition1 = True
                                    condition1_detail = f"{i+1}봉전 MA80-MA480 골든크로스"
                                    break
                                
                conditions.append(f"[C전략 조건1] MA80-MA480 조건 300봉이내 ({condition1_detail}): {condition1}")
            except Exception as e:
                conditions.append(f"[C전략 조건1] MA80-MA480 조건 계산 실패: {e}")
                condition1 = False
            
            # 조건 2: 300봉이내 BB80상단선(표편2)-BB480상단선(표편1.5) 골든크로스
            condition2 = False
            condition2_detail = "골든크로스 없음"
            
            try:
                bb80_upper = df_calc.get('bb80_upper', pd.Series())
                bb480_upper = df_calc['bb480_upper']
                
                if len(bb80_upper) >= 301 and len(bb480_upper) >= 301:
                    for i in range(min(300, len(bb80_upper) - 1)):
                        curr_idx = -(i+1)
                        prev_idx = -(i+2)
                        
                        if abs(prev_idx) > len(bb80_upper):
                            break
                            
                        bb80_prev = bb80_upper.iloc[prev_idx]
                        bb80_curr = bb80_upper.iloc[curr_idx]
                        bb480_prev = bb480_upper.iloc[prev_idx]
                        bb480_curr = bb480_upper.iloc[curr_idx]
                        
                        if (pd.notna(bb80_prev) and pd.notna(bb80_curr) and
                            pd.notna(bb480_prev) and pd.notna(bb480_curr) and
                            bb80_prev <= bb480_prev and bb80_curr > bb480_curr):
                            condition2 = True
                            condition2_detail = f"{i+1}봉전 BB80-BB480 골든크로스"
                            break
                            
                conditions.append(f"[C전략 조건2] BB80-BB480 골든크로스 300봉이내 ({condition2_detail}): {condition2}")
            except Exception as e:
                conditions.append(f"[C전략 조건2] BB80-BB480 골든크로스 계산 실패: {e}")
                condition2 = False
            
            # 조건 3: 5봉이내 1봉전 MA20-MA80 골든크로스
            condition3 = False
            condition3_detail = "골든크로스 없음"
            
            try:
                if len(df_calc) >= 6:  # 5봉이내 체크를 위해 6봉 필요
                    for i in range(1, min(6, len(df_calc))):  # 1봉전부터 5봉전까지
                        curr_idx = -(i+1)
                        prev_idx = -(i+2)
                        
                        if abs(prev_idx) > len(df_calc):
                            break
                            
                        ma20_prev = df_calc['ma20'].iloc[prev_idx]
                        ma20_curr = df_calc['ma20'].iloc[curr_idx]
                        ma80_prev = df_calc['ma80'].iloc[prev_idx]
                        ma80_curr = df_calc['ma80'].iloc[curr_idx]
                        
                        if (pd.notna(ma20_prev) and pd.notna(ma20_curr) and
                            pd.notna(ma80_prev) and pd.notna(ma80_curr) and
                            ma20_prev <= ma80_prev and ma20_curr > ma80_curr):
                            condition3 = True
                            condition3_detail = f"{i+1}봉전 MA20-MA80 골든크로스"
                            break
                            
                conditions.append(f"[C전략 조건3] 5봉이내 1봉전 MA20-MA80 골든크로스 ({condition3_detail}): {condition3}")
            except Exception as e:
                conditions.append(f"[C전략 조건3] MA20-MA80 골든크로스 계산 실패: {e}")
                condition3 = False
            
            # C전략 최종 신호 판정: 조건1, 조건2, 조건3만 체크 (3개 조건)
            strategy_c_signal = condition1 and condition2 and condition3
            
            # C전략 디버그 메시지 제거 (데이터 검증 완료)
                
            return strategy_c_signal, conditions
            
        except Exception as e:
            return False, [f"C전략 체크 실패: {e}"]
    
    def scan_symbols(self):
        """A전략+B전략+C전략 통합 스캔 (단계별 상세 출력)"""
        try:
            print(f"\n{'='*80}")
            print("🚀 A전략+B전략+C전략 통합 스캔 시작")
            print(f"{'='*80}")
            scan_start_time = time.time()
            
            # 공개 API를 사용한 실제 데이터 스캔 (API 키 불필요)
            try:
                print("🔍 공개 API 실시간 데이터 스캔 시작...")
                return self._detailed_scan_with_real_data()
            
            except Exception as scan_error:
                print(f"❌ 실시간 스캔 실패: {str(scan_error)[:100]}")
                print("⚠️ 스캔을 중단합니다. (가짜 신호 생성 방지)")
                return []
                
        except Exception as e:
            self.logger.error(f"스캔 실패: {e}")
            return []
    
    def _detailed_scan_with_real_data(self):
        """상세 실제 데이터 스캔 (단계별 출력)"""
        scan_start = time.time()
        
        try:
            # 1단계: 마켓 데이터 로드
            print("\n📋 1단계: 마켓 데이터 로드 중...")
            markets = self.exchange.load_markets()
            
            # USDT 선물 심볼 필터링
            usdt_futures = [symbol for symbol in markets.keys() 
                          if symbol.endswith('/USDT:USDT') and markets[symbol]['active']]
            
            print(f"   📊 전체 USDT 선물: {len(usdt_futures)}개")
            
            # 2단계: 24시간 상승률 상위 200개 → 4시간봉 필터링
            print("\n📈 2단계: 24시간 상승률 상위 200개 선별 중...")
            filter_start = time.time()
            
            try:
                tickers = self.exchange.fetch_tickers()
                
                # 24시간 상승률 + KST 상승률 상위 심볼 선별
                change_filtered = []
                kst_timezone = timezone(timedelta(hours=9))  # 한국 시간
                current_kst = datetime.now(kst_timezone)
                kst_start_today = current_kst.replace(hour=0, minute=0, second=0, microsecond=0)
                
                for symbol, ticker in tickers.items():
                    if symbol in usdt_futures:
                        volume = ticker.get('quoteVolume', 0)
                        change_24h = ticker.get('percentage', 0) or 0
                        current_price = ticker.get('last', 0)
                        
                        # 기본 필터링: 거래량 > 0, 24시간 변동률 > 0%
                        if volume > 0 and change_24h > 0 and current_price > 0:
                            try:
                                # KST 상승률 계산 (실제 데이터 사용)
                                try:
                                    ohlcv_1h = self.exchange.fetch_ohlcv(symbol, '1h', limit=24)
                                    
                                    if ohlcv_1h and len(ohlcv_1h) > 0:
                                        # 대략 KST 00:00 시간대의 가격을 찾기
                                        kst_open_price = None
                                        for candle in ohlcv_1h:
                                            candle_time = datetime.fromtimestamp(candle[0] / 1000, tz=kst_timezone)
                                            if candle_time.hour == 0:  # KST 00시대 봉
                                                kst_open_price = candle[1]  # 시가
                                                break
                                        
                                        # KST 00시 데이터가 없으면 가장 오래된 데이터 사용
                                        if not kst_open_price and ohlcv_1h:
                                            kst_open_price = ohlcv_1h[0][1]  # 첫 번째 봉의 시가
                                        
                                        # KST 상승률 계산
                                        if kst_open_price and kst_open_price > 0:
                                            kst_change_pct = ((current_price - kst_open_price) / kst_open_price) * 100
                                            
                                            # 현실적인 범위 체크 (-50% ~ +50%)
                                            if -50 <= kst_change_pct <= 50 and kst_change_pct > 0:
                                                change_filtered.append((symbol, ticker, change_24h, volume, kst_change_pct))
                                            elif change_24h > 0:
                                                # KST 데이터 비현실적이면 24h만 사용
                                                change_filtered.append((symbol, ticker, change_24h, volume, 0))
                                        elif change_24h > 0:
                                            # KST 계산 실패시 24h만 사용
                                            change_filtered.append((symbol, ticker, change_24h, volume, 0))
                                    elif change_24h > 0:
                                        # 1h 데이터 없으면 24h만 사용
                                        change_filtered.append((symbol, ticker, change_24h, volume, 0))
                                        
                                except:
                                    # API 오류시 24h만 사용
                                    if change_24h > 0:
                                        change_filtered.append((symbol, ticker, change_24h, volume, 0))
                                        
                            except Exception:
                                # 심볼별 처리 오류시 건너뛰기
                                continue
                
                # 24시간 상승률 순 정렬
                change_sorted = sorted(change_filtered, key=lambda x: x[2], reverse=True)
                
                # 실제 필터링된 개수 확인 후 상위 200개 선별
                total_filtered = len(change_filtered)
                top_200_symbols = change_sorted[:200]
                actual_selected = len(top_200_symbols)
                
                print(f"   ✅ 24h+KST 상승률 조건 통과: {total_filtered}개")
                print(f"   📊 상위 {actual_selected}개 선별 (최대 200개)")
                
                if actual_selected > 0:
                    avg_24h = sum(item[2] for item in top_200_symbols) / len(top_200_symbols)
                    print(f"   📊 평균 24h 상승률: {avg_24h:.2f}%")
                    
                    # KST 상승률이 있는 심볼들의 평균 표시
                    kst_positive_symbols = [item for item in top_200_symbols if len(item) > 4 and item[4] > 0]
                    if kst_positive_symbols:
                        avg_kst_change = sum(item[4] for item in kst_positive_symbols) / len(kst_positive_symbols)
                        print(f"   📊 평균 KST 상승률: {avg_kst_change:.2f}% ({len(kst_positive_symbols)}개 심볼)")
                    else:
                        print("   📊 KST 상승률 계산 성공한 심볼: 0개 (24h 데이터만 사용)")
                else:
                    print("   ⚠️ 조건을 만족하는 심볼이 없습니다")
                
                # 3단계: 4시간봉 시가대비고가 4%이상 필터링
                print("\n🔍 3단계: 4시간봉 급등 패턴 필터링 중...")
                pattern_filter_start = time.time()
                
                pattern_filtered = []
                for item in top_200_symbols:
                    symbol, ticker, change_24h, volume = item[:4]  # 처음 4개 값만 사용
                    try:
                        # 4시간봉 데이터 조회 (최근 4봉)
                        if self.ws_provider:
                            ohlcv_4h = self.ws_provider.get_ohlcv(symbol, '4h', 4)
                        else:
                            ohlcv_4h = self.exchange.fetch_ohlcv(symbol, '4h', limit=4)
                        
                        if not ohlcv_4h or len(ohlcv_4h) < 4:
                            continue
                            
                        # 조건1: 최근 4봉이내 시가대비고가 4%이상 1회이상 확인
                        surge_found = False
                        for candle in ohlcv_4h:
                            timestamp, open_price, high_price, low_price, close_price, volume = candle
                            
                            if open_price and open_price > 0:
                                surge_pct = ((high_price - open_price) / open_price) * 100
                                if surge_pct >= 4.0:
                                    surge_found = True
                                    break
                        
                        # 조건2: 4봉이전~0봉까지의 상승률 합계 > 0% 확인
                        total_gain = False
                        if len(ohlcv_4h) >= 4:
                            # 4봉 전 시가 (첫 번째 봉의 시가)
                            first_open = ohlcv_4h[0][1]
                            # 현재 봉 종가 (마지막 봉의 종가)
                            last_close = ohlcv_4h[-1][4]
                            
                            if first_open and first_open > 0 and last_close:
                                total_gain_pct = ((last_close - first_open) / first_open) * 100
                                if total_gain_pct > 0:
                                    total_gain = True
                        
                        # 두 조건 모두 만족해야 통과
                        if surge_found and total_gain:
                            pattern_filtered.append(symbol)
                            
                    except Exception:
                        # 개별 심볼 오류는 조용히 건너뛰기
                        continue
                
                filtered_symbols = pattern_filtered
                
                pattern_filter_elapsed = time.time() - pattern_filter_start
                filter_elapsed = time.time() - filter_start
                print(f"   ✅ 4시간봉 급등 패턴 필터링 완료: {len(filtered_symbols)}개 선별 ({pattern_filter_elapsed:.1f}초)")
                print(f"   📊 전체 필터링 소요시간: {filter_elapsed:.1f}초")
                
            except Exception as e:
                print(f"   ⚠️ 필터링 실패: {e}")
                filtered_symbols = usdt_futures[:100]
            
            # 3단계: 15분봉 초필살기 조건 스캔
            print(f"\n🔍 3단계: 15분봉 초필살기 조건 스캔 ({len(filtered_symbols)}개 심볼)")
            scan_stage_start = time.time()
            
            # 진행상황 추적 변수
            total_symbols = len(filtered_symbols)
            analyzed_count = 0
            entry_signals = []
            condition_stats = {
                'analyzed': 0,
                'data_insufficient': 0,
                'condition_1_fail': 0,
                'condition_2_fail': 0,
                'condition_3_fail': 0,
                'entry_fail': 0,
                'signals_found': 0
            }
            
            # 모든 분석 결과 수집용 리스트
            all_results = []
            entry_signals = []
            near_entry = []
            potential_entry = []
            watchlist = []
            
            # 병렬 분석 실행
            with ThreadPoolExecutor(max_workers=15) as executor:
                future_to_symbol = {
                    executor.submit(self.detailed_symbol_analysis, symbol): symbol 
                    for symbol in filtered_symbols
                }
                
                # 진행 상황 출력용 카운터
                progress_interval = max(1, total_symbols // 10)  # 10% 단위로 출력
                
                for i, future in enumerate(as_completed(future_to_symbol, timeout=90)):
                    symbol = future_to_symbol[future]
                    analyzed_count += 1
                    
                    try:
                        result = future.result(timeout=8)
                        
                        if result is None:
                            condition_stats['data_insufficient'] += 1
                            continue
                            
                        condition_stats['analyzed'] += 1
                        all_results.append(result)  # 모든 결과 저장
                        
                        # 결과 분류
                        status = result.get('status', 'watchlist')
                        if status == 'entry_signal':
                            entry_signals.append(result)
                            
                        # 디버그: 상태 확인 (모순 검사)
                        if result['symbol'] in ['APR/USDT:USDT', 'ARC/USDT:USDT', 'TRADOOR/USDT:USDT']:
                            clean_sym = result['symbol'].replace('/USDT:USDT', '')
                            details = result.get('strategy_details', {})
                            is_signal_value = (details.get('strategy_a', {}).get('signal', False) or 
                                             details.get('strategy_b', {}).get('signal', False) or 
                                             details.get('strategy_c', {}).get('signal', False))
                            print(f"🔍 STATUS DEBUG [{clean_sym}]: is_signal={is_signal_value}, status={status}, entry_signals추가={status=='entry_signal'}")
                            print(f"   A전략신호={details.get('strategy_a', {}).get('signal', 'N/A')}, B전략신호={details.get('strategy_b', {}).get('signal', 'N/A')}, C전략신호={details.get('strategy_c', {}).get('signal', 'N/A')}")
                            print(f"   분류된상태={status} ({'✅ 정상' if (is_signal_value and status == 'entry_signal') or (not is_signal_value and status != 'entry_signal') else '❌ 모순!!!'})")
                            
                            if status == 'entry_signal':
                                condition_stats['signals_found'] += 1
                                clean_symbol = result['clean_symbol']
                                price = result['price']
                                print(f"   🚨 진입 신호 발견: {clean_symbol} @ ${price:,.4f}")
                                
                                # 텔레그램 알림
                                self.send_entry_signal_notification(result)
                        elif status == 'near_entry':
                            near_entry.append(result)
                        elif status == 'potential_entry':
                            potential_entry.append(result)
                        elif status == 'watchlist':
                            watchlist.append(result)
                        
                        # 조건별 통계 업데이트 (기존 유지)
                        if 'failure_reason' in result:
                            reason = result['failure_reason']
                            if 'condition_1' in reason:
                                condition_stats['condition_1_fail'] += 1
                            elif 'condition_2' in reason:
                                condition_stats['condition_2_fail'] += 1
                            elif 'condition_3' in reason:
                                condition_stats['condition_3_fail'] += 1
                            elif 'condition_4' in reason:
                                condition_stats['condition_4_fail'] = condition_stats.get('condition_4_fail', 0) + 1
                            elif 'entry' in reason:
                                condition_stats['entry_fail'] += 1
                        
                        # 진행률 출력 (10% 단위)
                        if analyzed_count % progress_interval == 0:
                            progress_pct = (analyzed_count / total_symbols) * 100
                            signals_so_far = len(entry_signals)
                            print(f"   📊 진행률: {progress_pct:.0f}% ({analyzed_count}/{total_symbols}) - 신호: {signals_so_far}개")
                            
                    except Exception as e:
                        # 개별 심볼 분석 실패는 조용히 처리
                        condition_stats['data_insufficient'] += 1
            
            # 4단계: 스캔 결과 요약
            scan_elapsed = time.time() - scan_stage_start
            total_elapsed = time.time() - scan_start
            
            print(f"\n📊 4단계: 15분봉 초필살기 스캔 결과 요약")
            print(f"{'─'*60}")
            print(f"   📈 분석 대상: {total_symbols}개 심볼")
            print(f"   ✅ 분석 완료: {condition_stats['analyzed']}개")
            print(f"   ❌ 데이터 부족: {condition_stats['data_insufficient']}개")
            print(f"   🚨 진입 신호: {len(entry_signals)}개")
            print(f"   ⏱️ 스캔 소요시간: {scan_elapsed:.1f}초")
            print(f"   ⚡ 전체 소요시간: {total_elapsed:.1f}초")
            print(f"   🔥 분석 속도: {total_symbols/total_elapsed:.1f} 심볼/초")
            
            
            # 전략별 분리된 결과 출력
            self._print_strategy_separated_results(all_results, entry_signals)
            
            # 5. 통계 정보
            total_analyzed = len(all_results)
            if total_analyzed > 0:
                print(f"\n📊 스캔 통계")
                print(f"{'─'*40}")
                print(f"   📈 분석 완료: {total_analyzed}개")
                print(f"   🔥 진입신호: {len(entry_signals)}개")
                print(f"   ⚡ 진입임박: {len(near_entry)}개")
                print(f"   📈 진입확률: {len(potential_entry)}개")
                print(f"   👀 관심종목: {len(watchlist)}개")
                print(f"   📊 신호발견율: {(len(entry_signals)/total_analyzed*100):.1f}%")
            
            print(f"{'='*60}")
            return entry_signals
            
        except Exception as e:
            self.logger.error(f"상세 스캔 실패: {e}")
            return []
    
    def scan_symbols_optimized(self, api_call_tracker):
        """🚀 최고속도 최적화된 심볼 스캔 (IP 밴 방지)"""
        try:
            scan_start = time.time()
            # print(f"\n*** OPTIMIZED SCAN STARTING ***")  # 디버그용 주석처리
            print(f"\n🚀 최적화 15분봉 초필살기 스캔 시작")
            print(f"{'='*60}")
            
            # 1단계: 캐시된 마켓 데이터 사용 (API 호출 최소화)
            print("📋 1단계: 고속 마켓 데이터 로드...")
            if not hasattr(self, '_cached_futures_symbols') or \
               not hasattr(self, '_cache_time') or \
               time.time() - self._cache_time > 300:  # 5분마다 캐시 갱신
                
                # 마켓 데이터 캐시 갱신
                try:
                    markets = self.exchange.load_markets()
                    self._cached_futures_symbols = [
                        symbol for symbol, market in markets.items()
                        if symbol.endswith('/USDT:USDT') and market.get('active', False)
                    ]
                    self._cache_time = time.time()
                    api_call_tracker['calls_in_minute'] += 1
                    print(f"   🔄 마켓 데이터 캐시 갱신: {len(self._cached_futures_symbols)}개 심볼")
                except Exception as e:
                    print(f"   ⚠️ 마켓 데이터 로드 실패: {e}")
                    return []
            else:
                print(f"   ⚡ 캐시된 마켓 데이터 사용: {len(self._cached_futures_symbols)}개 심볼")
            
            # 2단계: 스마트 티커 배치 조회 (최적화)
            print("\n📈 2단계: 고속 티커 배치 조회...")
            batch_start = time.time()
            
            try:
                # 단일 배치 호출로 모든 티커 정보 가져오기
                tickers = self.exchange.fetch_tickers()
                api_call_tracker['calls_in_minute'] += 1
                batch_elapsed = time.time() - batch_start
                print(f"   ⚡ 배치 티커 조회 완료: {len(tickers)}개 ({batch_elapsed:.1f}초)")
            except Exception as e:
                print(f"   ❌ 배치 티커 조회 실패: {e}")
                return []
            
            # 3단계: 스마트 필터링 (메모리 기반)
            print("\n🔍 3단계: 고속 필터링 및 선별...")
            
            # 상승률만 기준으로 필터링 (거래량 필터 제거)
            filtered_symbols = []
            
            for symbol in self._cached_futures_symbols:
                if symbol in tickers:
                    ticker = tickers[symbol]
                    volume_24h = ticker.get('quoteVolume', 0) or 0
                    change_24h = ticker.get('percentage', 0) or 0
                    
                    # 상승률만 필터링 (거래량 필터 제거)
                    if change_24h > 0:
                        filtered_symbols.append((symbol, ticker, change_24h, volume_24h))
            
            # 상승률 기준 정렬 및 상위 150개 선별 (IP 밴 방지)
            filtered_symbols.sort(key=lambda x: x[2], reverse=True)
            top_symbols = filtered_symbols[:150]
            
            print(f"   ✅ 상승률 필터링: {len(filtered_symbols)}개 → {len(top_symbols)}개 선별")
            
            # 4단계: 병렬 조건 분석 (스마트 배치)
            print(f"\n🔥 4단계: 최고속도 병렬 조건 분석 (상위 {len(top_symbols)}개)...")
            analysis_start = time.time()
            
            entry_signals = []
            near_entry = []
            potential_entry = []
            watchlist = []
            all_results = []
            
            # 스마트 병렬 처리 (API 호출 최적화)
            max_workers = min(8, len(top_symbols))
            if max_workers > 0:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # 분석 태스크 생성
                    analysis_tasks = {}
                    
                    for symbol, ticker, change_24h, volume in top_symbols:
                        if api_call_tracker['calls_in_minute'] >= api_call_tracker['max_calls_per_minute'] - 100:
                            print(f"   ⚠️ API 호출 제한 임박 ({api_call_tracker['calls_in_minute']}/{api_call_tracker['max_calls_per_minute']}) - 분석 중단")
                            break
                            
                        future = executor.submit(self._optimized_symbol_analysis, symbol, ticker, api_call_tracker)
                        analysis_tasks[future] = symbol
                    
                    # 결과 수집
                    completed_count = 0
                    total_tasks = len(analysis_tasks)
                    
                    for future in as_completed(analysis_tasks):
                        try:
                            result = future.result(timeout=10)  # 10초 타임아웃
                            if result and result.get('analyzed'):
                                all_results.append(result)
                                
                                # 상태별 분류
                                status = result.get('status')
                                if status == 'entry_signal':
                                    entry_signals.append(result)
                                elif status == 'near_entry':
                                    near_entry.append(result)
                                elif status == 'potential_entry':
                                    potential_entry.append(result)
                                elif status == 'watchlist':
                                    watchlist.append(result)
                                
                                completed_count += 1
                                
                                # 진행률 출력 (25% 단위)
                                if total_tasks > 0 and completed_count % max(1, total_tasks // 4) == 0:
                                    progress_pct = (completed_count / total_tasks) * 100
                                    print(f"   📊 분석 진행: {progress_pct:.0f}% ({completed_count}/{total_tasks}) - 신호: {len(entry_signals)}개")
                        
                        except Exception as e:
                            # 개별 분석 실패는 조용히 처리
                            continue
            
            # 5단계: 결과 출력
            analysis_elapsed = time.time() - analysis_start
            total_elapsed = time.time() - scan_start
            
            print(f"\n⚡ 최고속도 스캔 완료!")
            print(f"{'─'*60}")
            print(f"   📈 대상 심볼: {len(top_symbols)}개")
            print(f"   ✅ 분석 완료: {len(all_results)}개")
            print(f"   🚨 진입 신호: {len(entry_signals)}개")
            print(f"   ⚡ 분석 시간: {analysis_elapsed:.1f}초")
            print(f"   🔥 전체 시간: {total_elapsed:.1f}초")
            print(f"   📊 분석 속도: {len(all_results)/total_elapsed:.1f} 심볼/초")
            print(f"   🛡️ API 호출: {api_call_tracker['calls_in_minute']}/{api_call_tracker['max_calls_per_minute']}")
            
            # 전략별 분리된 결과 출력
            self._print_strategy_separated_results(all_results, entry_signals)
            
            # 5. 통계 정보
            total_analyzed = len(all_results)
            if total_analyzed > 0:
                print(f"\n📊 최고속도 스캔 통계")
                print(f"{'─'*40}")
                print(f"   📈 분석 완료: {total_analyzed}개")
                print(f"   🔥 진입신호: {len(entry_signals)}개")
                print(f"   ⚡ 진입임박: {len(near_entry)}개")
                print(f"   📈 진입확률: {len(potential_entry)}개")
                print(f"   👀 관심종목: {len(watchlist)}개")
                print(f"   📊 신호발견율: {(len(entry_signals)/total_analyzed*100):.1f}%")
                print(f"   🚀 처리속도: {total_analyzed/total_elapsed:.1f} 심볼/초")
            
            print(f"{'='*60}")
            return entry_signals
            
        except Exception as e:
            self.logger.error(f"최적화 스캔 실패: {e}")
            print(f"❌ 최적화 스캔 실패: {e}")
            return []
    
    def _optimized_symbol_analysis(self, symbol, ticker, api_call_tracker):
        """최적화된 개별 심볼 분석 (API 호출 최소화)"""
        try:
            clean_symbol = symbol.replace('/USDT:USDT', '')
            
            # API 호출 제한 체크
            if api_call_tracker['calls_in_minute'] >= api_call_tracker['max_calls_per_minute'] - 10:
                return None
            
            # 기존 포지션 확인
            if symbol in self.active_positions:
                return None
            
            # 현재가 정보 (티커에서 직접 사용)
            current_price = ticker.get('last') or ticker.get('close')
            if not current_price or current_price <= 0:
                return None
            
            # 15분봉 데이터 조회 (WebSocket 우선, 단일 API 호출)
            df_15m = None
            
            # WebSocket 데이터 시도 (API 호출 없음)
            if self.ws_provider:
                try:
                    df_15m = self.ws_provider.get_ohlcv_dataframe(symbol, '15m', limit=1200)
                except:
                    pass
            
            # 폴백: REST API (필요시에만)
            if df_15m is None or len(df_15m) < 480:
                try:
                    df_15m = self.get_ohlcv_data(symbol, '15m', limit=1200)
                    api_call_tracker['calls_in_minute'] += 1
                    if df_15m is None or len(df_15m) < 480:
                        return None
                except:
                    return None
            
            # 15분봉 초필살기 조건 체크
            is_signal, conditions, strategy_details = self.check_fifteen_minute_mega_conditions(symbol, df_15m)
            
            # 결과 객체 생성
            result = {
                'symbol': symbol,
                'clean_symbol': clean_symbol,
                'price': current_price,
                'timestamp': get_korea_time().strftime('%Y-%m-%d %H:%M:%S'),
                'conditions': conditions,
                'strategy_details': strategy_details,
                'analyzed': True
            }
            
            if is_signal:
                result['status'] = 'entry_signal'
                return result
            else:
                # 조건별 통과 여부 확인 및 분류
                failed_conditions = []
                
                # A전략 조건 체크
                a_passed = 0
                for condition in conditions:
                    if '[A전략 조건' in condition and 'True' in condition:
                        a_passed += 1

                # B전략 조건 체크
                b_passed = 0
                for condition in conditions:
                    if '[B전략 조건' in condition and 'True' in condition:
                        b_passed += 1

                # 실패한 조건들 수집
                for condition in conditions:
                    if '[A전략 조건' in condition and 'False' in condition:
                        if '조건1' in condition:
                            failed_conditions.append("A전략-조건1")
                        elif '조건2' in condition:
                            failed_conditions.append("A전략-조건2")
                        elif '조건3' in condition:
                            failed_conditions.append("A전략-조건3")
                        elif '조건4' in condition:
                            failed_conditions.append("A전략-조건4")
                    elif '[B전략 조건' in condition and 'False' in condition:
                        if '조건1' in condition:
                            failed_conditions.append("B전략-조건1")
                        elif '조건2' in condition:
                            failed_conditions.append("B전략-조건2")
                        elif '조건3' in condition:
                            failed_conditions.append("B전략-조건3")
                        elif '조건4' in condition:
                            failed_conditions.append("B전략-조건4")
                        elif '조건5' in condition:
                            failed_conditions.append("B전략-조건5")
                
                # 전략별 상태 분류 (A전략: 5개 조건, B전략: 6개 조건)
                a_failed_count = 5 - a_passed
                b_failed_count = 6 - b_passed
                
                # CRITICAL: is_signal=False인 경우 절대 entry_signal이 될 수 없음 (최적화 버전)
                # A전략과 B전략 중 더 좋은 상태를 기준으로 분류 (하지만 is_signal=False이므로 entry_signal 제외)
                if a_failed_count == 1 or b_failed_count == 1:
                    result['status'] = 'near_entry'    # 1개 미충족 (진입임박)
                elif a_failed_count == 2 or b_failed_count == 2:
                    result['status'] = 'potential_entry'  # 2개 미충족 (진입확률)
                else:
                    result['status'] = 'watchlist'     # 0개 또는 3개 이상 미충족 (관심종목)
                
                # 더 나은 전략 정보 저장
                if a_failed_count <= b_failed_count:
                    result['failed_count'] = a_failed_count
                    result['passed_conditions'] = a_passed
                    result['strategy_focus'] = 'A'
                else:
                    result['failed_count'] = b_failed_count  
                    result['passed_conditions'] = b_passed
                    result['strategy_focus'] = 'B'
                result['failed_conditions'] = failed_conditions
                
                return result
                
        except Exception as e:
            # 개별 심볼 분석 실패는 조용히 처리
            return None
    
    def _detailed_fallback_scan(self):
        """상세 폴백 스캔 (API 키 문제시)"""
        print("\n🧪 가상 데이터 스캔 모드 (API 키 문제)")
        print(f"{'─'*60}")
        
        # 가상 스캔 시뮬레이션
        import random
        signals = []
        
        print("📋 1단계: 가상 마켓 데이터 로드...")
        print("   📊 가상 USDT 선물: 150개")
        
        print("\n📈 2단계: 가상 거래량 필터링...")
        print("   ✅ 거래량 필터링 완료: 150개 선별 (0.1초)")
        
        print("\n🔍 3단계: 가상 15분봉 초필살기 스캔...")
        
        # 20% 확률로 더미 진입 신호 생성
        if random.random() < 0.20:
            # 동적 심볼 로드
            try:
                # 실제 거래소에서 심볼 목록 가져오기 (퍼블릭 API)
                import ccxt
                public_exchange = ccxt.binance({'enableRateLimit': True})
                markets = public_exchange.load_markets()
                
                # USDT 선물 심볼 필터링 (상위 거래량 기준)
                usdt_futures = [symbol for symbol, market in markets.items() 
                              if symbol.endswith('/USDT:USDT') and market.get('active', False)]
                
                # 상위 거래량 심볼 선별 (최대 50개)
                dummy_symbols = usdt_futures[:50] if usdt_futures else []
                
                print(f"   📊 동적 로드된 심볼: {len(dummy_symbols)}개")
                
            except Exception as e:
                print(f"   ⚠️ 동적 심볼 로드 실패: {e}")
                # 폴백: 최소한의 주요 심볼
                dummy_symbols = [
                    'BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT', 'BNB/USDT:USDT',
                    'XRP/USDT:USDT', 'ADA/USDT:USDT', 'DOGE/USDT:USDT', 'MATIC/USDT:USDT'
                ]
            
            # 1-2개 신호 생성
            num_signals = random.randint(1, 2)
            selected_symbols = random.sample(dummy_symbols, min(num_signals, len(dummy_symbols)))
            
            for dummy_symbol in selected_symbols:
                # 동적 현재가 조회 시도
                dummy_price = None
                try:
                    # 실제 현재가 조회
                    ticker = public_exchange.fetch_ticker(dummy_symbol)
                    dummy_price = ticker.get('last') or ticker.get('close')
                    print(f"   📊 실시간 가격 조회: {dummy_symbol.replace('/USDT:USDT', '')} @ ${dummy_price:,.4f}")
                except:
                    # 폴백: 심볼별 현실적 가격 범위
                    if 'BTC' in dummy_symbol:
                        dummy_price = random.uniform(60000, 100000)
                    elif 'ETH' in dummy_symbol:
                        dummy_price = random.uniform(2000, 4000)
                    elif 'SOL' in dummy_symbol:
                        dummy_price = random.uniform(100, 300)
                    elif 'BNB' in dummy_symbol:
                        dummy_price = random.uniform(200, 600)
                    elif 'XRP' in dummy_symbol:
                        dummy_price = random.uniform(0.5, 2.0)
                    else:
                        dummy_price = random.uniform(0.1, 100)
                
                if dummy_price is None or dummy_price <= 0:
                    dummy_price = random.uniform(1, 100)
                
                clean_symbol = dummy_symbol.replace(':USDT', '').replace('/USDT', '')
                
                signal_data = {
                    'symbol': dummy_symbol,
                    'clean_symbol': clean_symbol,
                    'price': dummy_price,
                    'timestamp': get_korea_time().strftime('%Y-%m-%d %H:%M:%S'),
                    'status': 'entry_signal',
                    'conditions': ['[가상] 15분봉 초필살기 테스트 신호']
                }
                
                signals.append(signal_data)
                print(f"   🧪 가상 진입 신호: {clean_symbol} @ ${dummy_price:,.4f}")
                
                # 텔레그램 알림
                self.send_entry_signal_notification(signal_data)
        
        # 동적 가상 통계 출력
        total_analyzed = len(dummy_symbols) if 'dummy_symbols' in locals() else 150
        print(f"\n📊 4단계: 가상 스캔 결과 요약")
        print(f"{'─'*60}")
        print(f"   📈 분석 대상: {total_analyzed}개 심볼 (동적 로드)")
        print(f"   ✅ 분석 완료: {total_analyzed}개")
        print(f"   ❌ 데이터 부족: 0개")
        print(f"   🚨 진입 신호: {len(signals)}개")
        print(f"   ⏱️ 스캔 소요시간: 0.5초 (가상)")
        print(f"   ⚡ 전체 소요시간: 0.5초 (가상)")
        print(f"   🔥 분석 속도: {total_analyzed * 2} 심볼/초 (가상)")
        print(f"   ⚠️ 주의: 가상 데이터로 생성된 신호입니다")
        print(f"{'─'*60}")
        
        return signals
    
    def detailed_symbol_analysis(self, symbol):
        """상세 개별 심볼 분석 (통계 포함)"""
        try:
            clean_symbol = symbol.replace('/USDT:USDT', '')
            
            # 포지션 중복 체크
            if symbol in self.active_positions:
                return None
            
            # 15분봉 데이터 조회 (WebSocket 우선, REST 폴백)
            df_15m = None
            current_price = None
            
            # WebSocket 데이터 시도
            if self.ws_provider:
                try:
                    df_15m = self.ws_provider.get_ohlcv_dataframe(symbol, '15m', limit=1200)
                    if df_15m is not None and len(df_15m) > 0:
                        current_price = df_15m['close'].iloc[-1]
                except:
                    pass
            
            # 폴백: REST API
            if df_15m is None:
                df_15m = self.get_ohlcv_data(symbol, '15m', limit=1200)
                if df_15m is None or len(df_15m) < 500:
                    return None
            
            # 현재가 확보
            if current_price is None:
                try:
                    ticker = self.exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
                except:
                    if df_15m is not None and len(df_15m) > 0:
                        current_price = df_15m['close'].iloc[-1]
                    else:
                        return None
            
            # 15분봉 초필살기 조건 체크
            is_signal, conditions, strategy_details = self.check_fifteen_minute_mega_conditions(symbol, df_15m)
            
            # 결과 객체 생성
            result = {
                'symbol': symbol,
                'clean_symbol': clean_symbol,
                'price': current_price,
                'timestamp': get_korea_time().strftime('%Y-%m-%d %H:%M:%S'),
                'conditions': conditions,
                'strategy_details': strategy_details,
                'analyzed': True
            }
            
            if is_signal:
                result['status'] = 'entry_signal'
                return result
            else:
                # 조건별 통과 여부 확인 및 분류
                failed_conditions = []
                
                # A전략 조건 체크
                a_passed = 0
                for condition in conditions:
                    if '[A전략 조건' in condition and 'True' in condition:
                        a_passed += 1

                # B전략 조건 체크
                b_passed = 0
                for condition in conditions:
                    if '[B전략 조건' in condition and 'True' in condition:
                        b_passed += 1

                # 실패한 조건들 수집
                for condition in conditions:
                    if '[A전략 조건' in condition and 'False' in condition:
                        if '조건1' in condition:
                            failed_conditions.append("A전략-조건1")
                        elif '조건2' in condition:
                            failed_conditions.append("A전략-조건2")
                        elif '조건3' in condition:
                            failed_conditions.append("A전략-조건3")
                        elif '조건4' in condition:
                            failed_conditions.append("A전략-조건4")
                    elif '[B전략 조건' in condition and 'False' in condition:
                        if '조건1' in condition:
                            failed_conditions.append("B전략-조건1")
                        elif '조건2' in condition:
                            failed_conditions.append("B전략-조건2")
                        elif '조건3' in condition:
                            failed_conditions.append("B전략-조건3")
                        elif '조건4' in condition:
                            failed_conditions.append("B전략-조건4")
                        elif '조건5' in condition:
                            failed_conditions.append("B전략-조건5")
                
                # 전략별 상태 분류 (A전략: 5개 조건, B전략: 6개 조건)
                a_failed_count = 5 - a_passed
                b_failed_count = 6 - b_passed
                
                # CRITICAL: is_signal=False인 경우 절대 entry_signal이 될 수 없음
                # A전략과 B전략 중 더 좋은 상태를 기준으로 분류 (하지만 is_signal=False이므로 entry_signal 제외)
                if a_failed_count == 1 or b_failed_count == 1:
                    result['status'] = 'near_entry'    # 1개 미충족 (진입임박)
                elif a_failed_count == 2 or b_failed_count == 2:
                    result['status'] = 'potential_entry'  # 2개 미충족 (진입확률)
                else:
                    result['status'] = 'watchlist'     # 0개 또는 3개 이상 미충족 (관심종목)
                
                # 더 나은 전략 정보 저장
                if a_failed_count <= b_failed_count:
                    result['failed_count'] = a_failed_count
                    result['passed_conditions'] = a_passed
                    result['strategy_focus'] = 'A'
                else:
                    result['failed_count'] = b_failed_count  
                    result['passed_conditions'] = b_passed
                    result['strategy_focus'] = 'B'
                result['failed_conditions'] = failed_conditions
                
                # 기존 실패 이유 분석도 유지
                failure_reason = 'unknown'
                for condition in conditions:
                    if '[15분봉 조건1]' in condition and 'False' in condition:
                        failure_reason = 'condition_1_fail'
                        break
                    elif '[15분봉 조건2]' in condition and 'False' in condition:
                        failure_reason = 'condition_2_fail'
                        break
                    elif '[15분봉 조건3]' in condition and 'False' in condition:
                        failure_reason = 'condition_3_fail'
                        break
                    elif '[15분봉 조건4]' in condition and 'False' in condition:
                        failure_reason = 'condition_4_fail'
                        break
                    elif '[15분봉 최종]' in condition and 'False' in condition:
                        failure_reason = 'entry_fail'
                        break
                
                result['failure_reason'] = failure_reason
                return result
            
        except Exception as e:
            self.logger.debug(f"[{symbol}] 상세 분석 실패: {e}")
            return None
    
    def analyze_symbol_fast(self, symbol):
        """최적화된 개별 심볼 분석"""
        try:
            clean_symbol = symbol.replace('/USDT:USDT', '')
            
            # 포지션 중복 체크
            if symbol in self.active_positions:
                return None
            
            # WebSocket 우선 시도, 실패시 REST API 폴백
            df_15m = None
            current_price = None
            
            # WebSocket 데이터 시도
            if self.ws_provider:
                try:
                    df_15m = self.ws_provider.get_ohlcv_dataframe(symbol, '15m', limit=1200)
                    # WebSocket에서 현재가 가져오기 시도
                    if df_15m is not None and len(df_15m) > 0:
                        current_price = df_15m['close'].iloc[-1]
                except:
                    pass
            
            # 폴백: REST API
            if df_15m is None:
                df_15m = self.get_ohlcv_data(symbol, '15m', limit=1200)
                if df_15m is None or len(df_15m) < 500:
                    return None
            
            if current_price is None:
                try:
                    ticker = self.exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
                except:
                    if df_15m is not None and len(df_15m) > 0:
                        current_price = df_15m['close'].iloc[-1]
                    else:
                        return None
            
            # 15분봉 초필살기 조건 체크
            is_signal, conditions, strategy_details = self.check_fifteen_minute_mega_conditions(symbol, df_15m)
            
            if is_signal:
                return {
                    'symbol': symbol,
                    'clean_symbol': clean_symbol,
                    'price': current_price,
                    'timestamp': get_korea_time().strftime('%Y-%m-%d %H:%M:%S'),
                    'conditions': conditions,
                    'status': 'entry_signal'
                }
            
            return None
            
        except Exception as e:
            self.logger.debug(f"[{symbol}] 고속 분석 실패: {e}")
            return None
    
    def analyze_symbol(self, symbol):
        """개별 심볼 분석"""
        try:
            clean_symbol = symbol.replace('/USDT:USDT', '')
            
            # 포지션 중복 체크
            if symbol in self.active_positions:
                return None
            
            # 15분봉 데이터 조회
            df_15m = self.get_ohlcv_data(symbol, '15m', limit=1200)
            if df_15m is None or len(df_15m) < 500:
                return None
            
            # 15분봉 초필살기 조건 체크
            is_signal, conditions, strategy_details = self.check_fifteen_minute_mega_conditions(symbol, df_15m)
            
            if is_signal:
                # 현재가 조회
                current_price = df_15m.iloc[-1]['close']
                current_time = get_korea_time().strftime('%H:%M:%S')
                
                return {
                    'symbol': symbol,
                    'clean_symbol': clean_symbol,
                    'status': 'entry_signal',
                    'strategy_type': '15분봉 초필살기 전략',
                    'price': current_price,
                    'timestamp': current_time,
                    'conditions': conditions
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"{symbol} 분석 실패: {e}")
            return None
    
    def send_entry_signal_notification(self, signal_data):
        """진입 신호 텔레그램 알림 (중복 체크 포함)"""
        if not self.telegram_bot:
            return
        
        try:
            symbol = signal_data['clean_symbol']
            price = signal_data['price']
            timestamp = signal_data['timestamp']
            
            # 전략 타입 결정
            strategy_type = "Unknown"
            if signal_data.get('strategy_details'):
                details = signal_data['strategy_details']
                strategy_signals = []
                if details.get('strategy_a', {}).get('signal', False):
                    strategy_signals.append("A전략")
                if details.get('strategy_b', {}).get('signal', False):
                    strategy_signals.append("B전략")
                if details.get('strategy_c', {}).get('signal', False):
                    strategy_signals.append("C전략")
                
                if strategy_signals:
                    strategy_type = "+".join(strategy_signals)
                else:
                    strategy_type = "Unknown"
            
            # 중복 알림 체크
            if not self._should_send_notification(symbol, strategy_type, "entry_signal"):
                return
            
            # 전략별 제목 결정
            if "A전략" in strategy_type and "B전략" in strategy_type and "C전략" in strategy_type:
                title = "🚨 A+B+C전략 동시 진입 신호 🚨"
            elif "A전략" in strategy_type and "B전략" in strategy_type:
                title = "🚨 A+B전략 동시 진입 신호 🚨"
            elif "A전략" in strategy_type and "C전략" in strategy_type:
                title = "🚨 A+C전략 동시 진입 신호 🚨"
            elif "B전략" in strategy_type and "C전략" in strategy_type:
                title = "🚨 B+C전략 동시 진입 신호 🚨"
            elif "A전략" in strategy_type:
                title = "🚨 A전략(바닥타점) 진입 신호 🚨"
            elif "B전략" in strategy_type:
                title = "🚨 B전략(급등초입) 진입 신호 🚨"
            elif "C전략" in strategy_type:
                title = "🚨 C전략(3분봉 바닥급등타점) 진입 신호 🚨"
            else:
                title = "🚨 진입 신호 🚨"

            message = f"""{title}
━━━━━━━━━━━━━━━━━━━━━━
📈 심볼: <b>{symbol}</b>💰 현재가: ${price:,.4f}
⏰ 신호발생: {timestamp}
🎯 전략: {strategy_type}
━━━━━━━━━━━━━━━━━━━━━━
🔥 레버리지: 20배
💡 진입설정:
   • 포지션: 1% 상당 (20% 노출)
   • 1차 DCA: -3% (20% 노출)
   • 2차 DCA: -6% (20% 노출)
   • 손절: -10% (시드 6% 손실)
"""
            
            self.telegram_bot.send_message(message)
            
            # 알림 전송 기록
            self._record_notification(symbol, strategy_type, "entry_signal")
            
        except Exception as e:
            self.logger.error(f"텔레그램 알림 실패: {e}")
    
    def execute_trade(self, signal_data):
        """실전매매 거래 실행"""
        # 초기 변수 선언 (exception 처리용)
        position_value = 0
        free_usdt = 0
        
        try:
            if not self.private_exchange:
                print(f"⚠️ 프라이빗 API 없음 - {signal_data['clean_symbol']} 거래 건너뛰기")
                return False
                
            symbol = signal_data['symbol']
            price = signal_data['price']
            clean_symbol = signal_data['clean_symbol']
            
            # 포지션 개수 제한 체크 (최대 20개)
            portfolio = self.get_portfolio_summary()
            if portfolio['open_positions'] >= 20:
                print(f"⚠️ 최대 포지션 개수 도달 (20개) - {clean_symbol} 진입 건너뛰기")
                return False
            
            # 중복 포지션 체크
            if symbol in self.active_positions:
                print(f"⚠️ 이미 포지션 보유 중 - \033[92m{clean_symbol}\033[0m 💚 진입 건너뛰기")
                return False
            
            # 잔고 조회
            balance = self.private_exchange.fetch_balance()
            free_usdt = balance['USDT']['free']
            
            # 마켓 정보 조회 (최소 주문 수량 확인)
            market = self.private_exchange.market(symbol)
            min_amount = market['limits']['amount']['min'] if market['limits']['amount']['min'] else 0
            
            # 포지션 크기 계산 (1% x 20배 레버리지)
            position_value = free_usdt * 0.01  # 1%
            leverage = 20
            quantity = (position_value * leverage) / price  # 실제 구매할 수량
            
            
            
            if free_usdt < position_value:
                error_msg = f"⚠️ 잔고 부족 - 필요: ${position_value:.0f}, 보유: ${free_usdt:.0f}"
                print(error_msg)
                # 실패 알림 (중복 방지) - 상세 정보 포함
                strategy_type = self._get_strategy_type(signal_data)
                detailed_msg = f"""❌ <b>{clean_symbol}</b> 💚 거래 실패 (잔고부족)
━━━━━━━━━━━━━━━━━━━━━━
🎯 전략: {strategy_type}
💰 진입가격: ${price:.4f}
💵 필요금액: ${position_value:.0f} USDT
💳 보유잔고: ${free_usdt:.0f} USDT
⚠️ 실패사유: 잔고 부족
━━━━━━━━━━━━━━━━━━━━━━
📊 레버리지: 20배
📈 목표진입: {position_value:.0f} USDT (1.0%)
🕒 시간: {get_korea_time().strftime('%H:%M:%S')}"""
                self._send_notification_once(symbol, "balance_insufficient", detailed_msg)
                return False
            
            # 최소 주문 수량 검증
            if quantity < min_amount:
                error_msg = f"⚠️ 최소 주문 수량 미달 - 계산량: {quantity:.6f}, 최소량: {min_amount:.6f}"
                print(error_msg)
                # 실패 알림 (중복 방지) - 상세 정보 포함
                strategy_type = self._get_strategy_type(signal_data)
                detailed_msg = f"""❌ <b>{clean_symbol}</b> 💚 거래 실패 (최소수량미달)
━━━━━━━━━━━━━━━━━━━━━━
🎯 전략: {strategy_type}
💰 진입가격: ${price:.4f}
💵 필요금액: ${position_value:.0f} USDT
📊 계산수량: {quantity:.6f}
📏 최소수량: {min_amount:.6f}
⚠️ 실패사유: 최소 주문 수량 미달
━━━━━━━━━━━━━━━━━━━━━━
📊 레버리지: 20배
📈 목표진입: {position_value:.0f} USDT (1.0%)
🕒 시간: {get_korea_time().strftime('%H:%M:%S')}"""
                self._send_notification_once(symbol, "min_amount_insufficient", detailed_msg)
                return False
            
            # 레버리지 설정
            try:
                self.private_exchange.set_leverage(leverage, symbol)
                print(f"✅ 레버리지 {leverage}배 설정 완료: \033[92m{clean_symbol}\033[0m 💚")
            except Exception as e:
                print(f"⚠️ 레버리지 설정 실패: {e}")
            
            # 시장가 매수 주문
            order = self.private_exchange.create_market_buy_order(
                symbol=symbol,
                amount=quantity,
                params={'leverage': leverage}
            )
            
            if order['status'] == 'closed' or order['filled'] > 0:
                filled_qty = order['filled']
                filled_price = order['average'] or price
                
                # active_positions에 추가
                self.active_positions[symbol] = {
                    'size': filled_qty,
                    'side': 'long',
                    'entry_price': filled_price,
                    'leverage': leverage,
                    'order_id': order['id']
                }
                
                # 🔥 DCA 매니저에 포지션 등록 (신규 통합)
                if self.dca_manager and HAS_DCA_MANAGER:
                    try:
                        # 전체 잔고 조회 (DCA 매니저가 비중 계산에 필요)
                        current_balance = self.get_portfolio_summary().get('total_balance', 0)
                        
                        dca_success = self.dca_manager.add_position(
                            symbol=symbol,
                            entry_price=filled_price,
                            quantity=filled_qty,
                            notional=position_value * leverage,  # 실제 포지션 가치 (레버리지 적용)
                            leverage=float(leverage),
                            total_balance=current_balance
                        )
                        if dca_success:
                            print(f"✅ DCA 매니저 포지션 등록 완료: {clean_symbol}")
                        else:
                            print(f"⚠️ DCA 매니저 포지션 등록 실패: {clean_symbol}")
                    except Exception as e:
                        print(f"❌ DCA 매니저 등록 오류: {clean_symbol} - {e}")
                        self.logger.error(f"DCA 매니저 포지션 등록 실패 {symbol}: {e}")
                
                print(f"✅ 실전 진입 완료: {GREEN}{clean_symbol}{RESET}")
                print(f"   💰 진입가: ${filled_price:,.4f}")
                print(f"   📊 수량: {filled_qty:.6f}")
                print(f"   🔥 레버리지: {leverage}배")
                print(f"   💵 투입금액: ${position_value:.0f} USDT")
                print(f"   📋 주문ID: {order['id']}")
                
                # DCA 주문 등록 (기존 수동 방식 - 향후 DCA 매니저로 대체 예정)
                self._place_dca_orders(symbol, filled_price, quantity)
                
                # 텔레그램 성공 알림 (중복 방지) - 상세 정보 포함
                portfolio = self.get_portfolio_summary()
                strategy_type = self._get_strategy_type(signal_data)
                message = f"""🔥 실전 진입 완료 🔥
━━━━━━━━━━━━━━━━━━━━━━
🎯 전략: {strategy_type}
📈 심볼: <b>{clean_symbol}</b>💰 진입가: ${filled_price:,.4f}
📊 수량: {filled_qty:.6f}
🔥 레버리지: {leverage}배
💵 투입금액: ${position_value:.0f} USDT (1.0%)
📋 주문ID: {order['id']}
🕒 진입시간: {get_korea_time().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━
📊 포트폴리오 현황:
   • 잔고: ${portfolio['free_balance']:.0f} USDT
   • 포지션수: {portfolio['open_positions']}개
   • 총 PnL: ${portfolio['total_unrealized_pnl']:+.0f} USDT
━━━━━━━━━━━━━━━━━━━━━━
🎯 자동 DCA 설정:
   • 1차: ${filled_price * 0.97:,.4f} (-3%)
   • 2차: ${filled_price * 0.94:,.4f} (-6%)
   • 손절: ${filled_price * 0.90:,.4f} (-10%)
⚠️ 실제 거래 - 리스크 관리 필수!"""
                self._send_notification_once(symbol, "entry_success", message)
                
                return True
            else:
                error_msg = f"❌ 주문 실패: \033[92m{clean_symbol}\033[0m 💚 - {order.get('info', '')}"
                print(error_msg)
                # 실패 알림 (중복 방지) - 상세 정보 포함
                strategy_type = self._get_strategy_type(signal_data)
                detailed_msg = f"""❌ <b>{clean_symbol}</b> 💚 거래 실패 (주문실패)
━━━━━━━━━━━━━━━━━━━━━━
🎯 전략: {strategy_type}
💰 진입가격: ${price:.4f}
💵 투입금액: ${position_value:.0f} USDT (1.0%)
⚠️ 실패사유: 주문 처리 실패
📋 오류정보: {order.get('info', '상세정보없음')}
━━━━━━━━━━━━━━━━━━━━━━
📊 레버리지: 20배
🕒 시간: {get_korea_time().strftime('%H:%M:%S')}"""
                self._send_notification_once(symbol, "order_failed", detailed_msg)
                return False
            
        except Exception as e:
            self.logger.error(f"실전 거래 실행 실패: {e}")
            error_msg = f"❌ 거래 실행 실패: \033[92m{clean_symbol}\033[0m 💚 - {e}"
            print(error_msg)
            # 실패 알림 (중복 방지) - 상세 정보 포함
            strategy_type = self._get_strategy_type(signal_data)
            
            # position_value가 0인 경우 현재 잔고를 조회해서 다시 계산
            if position_value == 0:
                try:
                    if self.private_exchange:
                        balance = self.private_exchange.fetch_balance()
                        free_usdt = balance['USDT']['free']
                        position_value = free_usdt * 0.01
                except:
                    position_value = 0  # 잔고 조회도 실패한 경우
            
            detailed_msg = f"""❌ <b>{clean_symbol}</b> 💚 거래 실패 (시스템오류)
━━━━━━━━━━━━━━━━━━━━━━
🎯 전략: {strategy_type}
💰 진입가격: ${price:.4f}
💵 투입금액: ${position_value:.0f} USDT (1.0%)
⚠️ 실패사유: 시스템 오류
📋 오류정보: {str(e)[:100]}
━━━━━━━━━━━━━━━━━━━━━━
📊 레버리지: 20배
🕒 시간: {get_korea_time().strftime('%H:%M:%S')}"""
            self._send_notification_once(symbol, "execution_failed", detailed_msg)
            return False
    
    def _place_dca_orders(self, symbol, entry_price, base_quantity):
        """DCA 주문 등록 (-3%, -6%)"""
        try:
            clean_symbol = symbol.replace('/USDT:USDT', '')
            dca_orders = []
            
            # 1차 DCA: -3% 가격에 1% 추가 매수
            dca1_price = entry_price * 0.97
            balance = self.private_exchange.fetch_balance()
            free_usdt = balance['USDT']['free']
            dca1_value = free_usdt * 0.01  # 1%
            dca1_quantity = (dca1_value * 20) / dca1_price  # 20배 레버리지
            
            if free_usdt >= dca1_value:
                try:
                    dca1_order = self.exchange.create_limit_buy_order(
                        symbol=symbol,
                        amount=dca1_quantity,
                        price=dca1_price,
                        params={'leverage': 20}
                    )
                    dca_orders.append({
                        'stage': '1차_DCA',
                        'price': dca1_price,
                        'quantity': dca1_quantity,
                        'order_id': dca1_order['id']
                    })
                    print(f"   📋 1차 DCA 주문 등록: ${dca1_price:,.4f} ({dca1_quantity:.6f})")
                except Exception as e:
                    print(f"   ⚠️ 1차 DCA 주문 실패: {e}")
            
            # 2차 DCA: -6% 가격에 1% 추가 매수
            dca2_price = entry_price * 0.94
            dca2_value = free_usdt * 0.01  # 1%
            dca2_quantity = (dca2_value * 20) / dca2_price  # 20배 레버리지
            
            if free_usdt >= dca2_value:
                try:
                    dca2_order = self.exchange.create_limit_buy_order(
                        symbol=symbol,
                        amount=dca2_quantity,
                        price=dca2_price,
                        params={'leverage': 20}
                    )
                    dca_orders.append({
                        'stage': '2차_DCA',
                        'price': dca2_price,
                        'quantity': dca2_quantity,
                        'order_id': dca2_order['id']
                    })
                    print(f"   📋 2차 DCA 주문 등록: ${dca2_price:,.4f} ({dca2_quantity:.6f})")
                except Exception as e:
                    print(f"   ⚠️ 2차 DCA 주문 실패: {e}")
            
            # 손절 주문: -10%
            stop_price = entry_price * 0.90
            try:
                stop_order = self.exchange.create_order(
                    symbol=symbol,
                    type='stop_market',
                    side='sell',
                    amount=base_quantity,  # 기본 포지션만 손절
                    price=None,
                    params={
                        'stopPrice': stop_price,
                        'leverage': 20
                    }
                )
                dca_orders.append({
                    'stage': '손절',
                    'price': stop_price,
                    'quantity': base_quantity,
                    'order_id': stop_order['id']
                })
                print(f"   🛑 손절 주문 등록: ${stop_price:,.4f}")
            except Exception as e:
                print(f"   ⚠️ 손절 주문 실패: {e}")
            
            # DCA 주문 정보를 active_positions에 저장
            if symbol in self.active_positions:
                self.active_positions[symbol]['dca_orders'] = dca_orders
            
            return dca_orders
            
        except Exception as e:
            self.logger.error(f"DCA 주문 등록 실패: {e}")
            print(f"❌ DCA 주문 등록 실패: {e}")
            return []
    
    def get_total_balance(self):
        """총 잔고 조회"""
        try:
            if not self.private_exchange:
                return None
            balance = self.private_exchange.fetch_balance()
            return balance.get('USDT', {}).get('total', 0)
        except Exception as e:
            self.logger.error(f"잔고 조회 실패: {e}")
            return None
    
    def check_real_position_status(self):
        """실제 포지션 상태 체크 및 DCA 주문 자동 관리"""
        try:
            if not self.private_exchange:
                return
                
            # 실제 포지션 재조회
            positions = self.private_exchange.fetch_positions()
            
            # 현재 실제 포지션 업데이트 및 DCA 상태 분석
            current_positions = {}
            for position in positions:
                if position['contracts'] > 0:
                    symbol = position['symbol']
                    current_positions[symbol] = {
                        'size': position['contracts'],
                        'side': position['side'],
                        'entry_price': position['entryPrice'],
                        'mark_price': position['markPrice'],
                        'unrealized_pnl': position['unrealizedPnl'],
                        'percentage': position['percentage'],
                        'initial_margin': position.get('initialMargin', 0),
                        'notional': position.get('notional', 0)
                    }
                    
                    # 포지션 크기로 진입 단계 판별 및 DCA 관리 (안전한 처리)
                    try:
                        self._manage_dca_orders_by_margin(symbol, position)
                    except Exception as dca_err:
                        self.logger.debug(f"DCA 주문 관리 오류 {symbol}: {dca_err}")
                        continue
            
            # active_positions 업데이트
            self.active_positions = current_positions
            
            # DCA 주문 체결 확인
            for symbol, pos_info in self.active_positions.items():
                if 'dca_orders' not in pos_info:
                    continue
                
                clean_symbol = symbol.replace('/USDT:USDT', '')
                
                # 각 DCA 주문 상태 체크
                for dca_order in pos_info['dca_orders']:
                    order_id = dca_order['order_id']
                    stage = dca_order['stage']
                    
                    try:
                        # 주문 상태 조회
                        order_status = self.private_exchange.fetch_order(order_id, symbol)
                        
                        if order_status['status'] == 'closed' and order_status['filled'] > 0:
                            # DCA 주문이 체결됨
                            filled_price = order_status['average']
                            filled_qty = order_status['filled']
                            
                            print(f"🔥 실전 {stage} 체결: {clean_symbol}")
                            print(f"   💰 체결가: ${filled_price:,.4f}")
                            print(f"   📊 수량: {filled_qty:.6f}")
                            
                            # 텔레그램 DCA 체결 알림
                            if self.telegram_bot:
                                portfolio = self.get_portfolio_summary()
                                message = f"""🔥 실전 {stage} 체결 🔥
━━━━━━━━━━━━━━━━━━━━━━
📈 심볼: {clean_symbol}
💰 체결가: ${filled_price:,.4f}
📊 수량: {filled_qty:.6f}
📋 주문ID: {order_id}
━━━━━━━━━━━━━━━━━━━━━━
📊 포트폴리오 현황:
   • 잔고: ${portfolio['free_balance']:.0f} USDT
   • 포지션수: {portfolio['open_positions']}개
   • 총 PnL: ${portfolio['total_unrealized_pnl']:+.0f} USDT
⚠️ 실제 거래 체결"""
                                self.telegram_bot.send_message(message)
                            
                            # 체결된 주문 제거
                            dca_order['status'] = 'filled'
                            
                    except Exception as e:
                        # 주문이 취소되었거나 조회 실패
                        pass
            
            # active_positions 업데이트
            self.active_positions = current_positions
            
        except Exception as e:
            self.logger.error(f"실제 포지션 상태 체크 실패: {e}")
    
    def _manage_dca_orders_by_margin(self, symbol, position):
        """포지션 마진 분석으로 DCA 주문 자동 관리 (조용한 모드)"""
        try:
            # 포지션 데이터 타입 검증
            if not isinstance(position, dict):
                self.logger.debug(f"포지션 데이터 타입 오류 {symbol}: {type(position)}")
                return
                
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            initial_margin = position.get('initialMargin', 0)
            notional = position.get('notional', 0)
            entry_price = position.get('entryPrice', 0)
            size = position.get('contracts', 0)
            
            # None 값 및 유효성 체크 강화
            if (initial_margin is None or initial_margin <= 0 or 
                entry_price is None or entry_price <= 0 or
                notional is None or notional <= 0 or
                size is None or size <= 0):
                return
            
            # 원금 대비 마진 계산 (20배 레버리지 기준)
            leverage = 20
            expected_initial_margin = notional / leverage
            
            # 진입 단계 판별 (마진 크기로 추정)
            # 1% = 초기 진입, 2% = 1차 DCA 완료, 3% = 2차 DCA 완료
            margin_ratio = initial_margin / (expected_initial_margin * 0.01) if expected_initial_margin > 0 else 0
            
            # 비정상적인 마진비율 체크 (100 이상은 데이터 오류)
            if margin_ratio > 50:
                return
            
            # 현재 열린 주문 조회 (에러 방지)
            open_orders = self._get_open_orders_for_symbol(symbol)
            if not open_orders:
                open_orders = []
                
            # 주문 존재 여부 체크 (None 가격 방지)
            dca1_exists = False
            dca2_exists = False
            stop_exists = False
            
            for order in open_orders:
                if order.get('price') is None:
                    continue
                order_price = order['price']
                
                # 1차 DCA 주문 체크
                if abs(order_price - entry_price * 0.97) < entry_price * 0.001:
                    dca1_exists = True
                # 2차 DCA 주문 체크
                elif abs(order_price - entry_price * 0.94) < entry_price * 0.001:
                    dca2_exists = True
                # 손절 주문 체크
                elif order.get('type') == 'stop_market':
                    stop_exists = True
            
            # DCA 주문 관리 (강화된 모드 - 누락 주문 적극 재등록)
            actions_taken = []
            
            # 초기 진입 상태 - 무조건 1차, 2차 DCA 주문 있어야 함
            if margin_ratio < 1.5:  
                if not dca1_exists:
                    if self._place_single_dca_order(symbol, entry_price, 1, size):
                        actions_taken.append("1차DCA등록")
                if not dca2_exists:
                    if self._place_single_dca_order(symbol, entry_price, 2, size):
                        actions_taken.append("2차DCA등록")
                    
            # 1차 DCA 완료 상태 - 2차 DCA 주문만 있어야 함
            elif margin_ratio < 2.5:  
                if dca1_exists:
                    if self._cancel_dca_orders(symbol, entry_price * 0.97):
                        actions_taken.append("1차DCA취소")
                if not dca2_exists:
                    if self._place_single_dca_order(symbol, entry_price, 2, size):
                        actions_taken.append("2차DCA등록")
                    
            # 2차 DCA 완료 상태 - DCA 주문 모두 정리
            elif margin_ratio >= 2.5:  
                if dca1_exists:
                    if self._cancel_dca_orders(symbol, entry_price * 0.97):
                        actions_taken.append("1차DCA취소")
                if dca2_exists:
                    if self._cancel_dca_orders(symbol, entry_price * 0.94):
                        actions_taken.append("2차DCA취소")
            
            # 특별 케이스: DCA 주문이 전혀 없는 경우 강제 재등록
            if not dca1_exists and not dca2_exists and margin_ratio < 2.5:
                print(f"⚠️ {clean_symbol}: DCA 주문 전체 누락 감지 - 강제 재등록")
                if self._place_single_dca_order(symbol, entry_price, 1, size):
                    actions_taken.append("1차DCA강제등록")
                if self._place_single_dca_order(symbol, entry_price, 2, size):
                    actions_taken.append("2차DCA강제등록")
                    
            # 손절 주문 확인 - 항상 있어야 함
            if not stop_exists:
                if self._place_stop_order(symbol, entry_price, size):
                    actions_taken.append("손절등록")
            
            # 조용한 로그 - 액션이 있을 때만 출력
            if actions_taken:
                stage_name = "초기" if margin_ratio < 1.5 else "1차완료" if margin_ratio < 2.5 else "2차완료"
                print(f"🔧 {clean_symbol} DCA관리: {stage_name} ({'/'.join(actions_taken)})")
                
        except Exception as e:
            self.logger.error(f"DCA 주문 관리 실패 ({clean_symbol}): {e}")
            # 에러 메시지도 조용하게 - 로그에만 기록
    
    def _get_open_orders_for_symbol(self, symbol):
        """특정 심볼의 열린 주문 조회"""
        try:
            orders = self.private_exchange.fetch_open_orders(symbol)
            return orders if orders else []
        except Exception as e:
            self.logger.error(f"주문 조회 실패 ({symbol}): {e}")
            return []
    
    def _place_single_dca_order(self, symbol, entry_price, stage, base_quantity):
        """단일 DCA 주문 등록 (조용한 모드)"""
        try:
            if stage == 1:
                dca_price = entry_price * 0.97
                stage_name = "1차 DCA"
            elif stage == 2:
                dca_price = entry_price * 0.94
                stage_name = "2차 DCA"
            else:
                return False
                
            balance = self.private_exchange.fetch_balance()
            free_usdt = balance['USDT']['free']
            dca_value = free_usdt * 0.01  # 1%
            dca_quantity = (dca_value * 20) / dca_price  # 20배 레버리지
            
            if free_usdt >= dca_value:
                order = self.private_exchange.create_limit_buy_order(
                    symbol=symbol,
                    amount=dca_quantity,
                    price=dca_price,
                    params={'leverage': 20}
                )
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"DCA 주문 등록 실패: {e}")
            return False
    
    def _place_stop_order(self, symbol, entry_price, size):
        """손절 주문 등록 (조용한 모드)"""
        try:
            stop_price = entry_price * 0.90
            stop_order = self.private_exchange.create_order(
                symbol=symbol,
                type='stop_market',
                side='sell',
                amount=size,
                price=None,
                params={
                    'stopPrice': stop_price,
                    'leverage': 20
                }
            )
            return True
        except Exception as e:
            self.logger.error(f"손절 주문 등록 실패: {e}")
            return False
    
    def _cancel_dca_orders(self, symbol, target_price):
        """특정 가격대의 DCA 주문 취소 (조용한 모드)"""
        try:
            orders = self._get_open_orders_for_symbol(symbol)
            cancelled_count = 0
            
            for order in orders:
                if order.get('price') is None:
                    continue
                if abs(order['price'] - target_price) < target_price * 0.001:  # 0.1% 오차 허용
                    try:
                        self.private_exchange.cancel_order(order['id'], symbol)
                        cancelled_count += 1
                    except Exception as e:
                        self.logger.error(f"주문 취소 실패: {e}")
                        
            return cancelled_count > 0
        except Exception as e:
            self.logger.error(f"주문 취소 실패: {e}")
            return False
    
    def _print_dca_orders_summary(self):
        """DCA 주문 현황 요약 출력"""
        try:
            if not self.private_exchange:
                return
                
            # 모든 포지션의 DCA 주문 현황 분석
            positions = self.private_exchange.fetch_positions()
            active_positions = [p for p in positions if p['contracts'] > 0]
            
            if not active_positions:
                return
                
            print(f"\n🔧 DCA 주문 현황 요약:")
            print(f"   {'심볼':<8} {'진입단계':<8} {'1차DCA':<8} {'2차DCA':<8} {'손절':<8}")
            print(f"   {'─'*45}")
            
            missing_dca_count = 0
            total_positions = len(active_positions)
            
            for position in active_positions:
                symbol = position['symbol']
                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')[:6]
                
                # 마진으로 진입 단계 판별
                initial_margin = position.get('initialMargin', 0)
                notional = position.get('notional', 0)
                entry_price = position.get('entryPrice', 0)
                
                if initial_margin > 0 and notional > 0:
                    expected_initial_margin = notional / 20
                    margin_ratio = initial_margin / (expected_initial_margin * 0.01) if expected_initial_margin > 0 else 0
                    
                    if margin_ratio > 50:  # 비정상 데이터 스킵
                        continue
                        
                    stage = "초기" if margin_ratio < 1.5 else "1차완료" if margin_ratio < 2.5 else "2차완료"
                else:
                    stage = "불명"
                
                # 주문 현황 체크
                open_orders = self._get_open_orders_for_symbol(symbol)
                dca1_exists = False
                dca2_exists = False
                stop_exists = False
                
                for order in open_orders:
                    if order.get('price') is None:
                        continue
                    order_price = order['price']
                    
                    if abs(order_price - entry_price * 0.97) < entry_price * 0.001:
                        dca1_exists = True
                    elif abs(order_price - entry_price * 0.94) < entry_price * 0.001:
                        dca2_exists = True
                    elif order.get('type') == 'stop_market':
                        stop_exists = True
                
                # DCA 누락 체크
                expected_dca1 = stage in ["초기"]
                expected_dca2 = stage in ["초기", "1차완료"]
                
                if (expected_dca1 and not dca1_exists) or (expected_dca2 and not dca2_exists):
                    missing_dca_count += 1
                
                # 상태 표시
                dca1_status = "✅" if dca1_exists else ("⚠️" if expected_dca1 else "➖")
                dca2_status = "✅" if dca2_exists else ("⚠️" if expected_dca2 else "➖")
                stop_status = "✅" if stop_exists else "⚠️"
                
                print(f"   {clean_symbol:<8} {stage:<8} {dca1_status:<8} {dca2_status:<8} {stop_status:<8}")
            
            print(f"   {'─'*45}")
            if missing_dca_count > 0:
                print(f"   ⚠️  DCA 누락: {missing_dca_count}/{total_positions}개 포지션")
                print(f"   🔧 자동 재등록이 진행됩니다...")
            else:
                print(f"   ✅ 모든 DCA 주문 정상: {total_positions}개 포지션")
                
        except Exception as e:
            self.logger.error(f"DCA 주문 요약 출력 실패: {e}")
    
    def _print_portfolio_table(self, positions):
        """💎 아름다운 포지션 테이블 출력 (개선된 버전)"""
        print(f"   {'─'*95}")
        print(f"   {'순번':<4} {'💼 심볼':<8} {'수익률(x20/x1)':<20} {'수익금액':<12} {'진입가':<12} {'진입금액':<12}")
        print(f"   {'─'*95}")
        
        # 합계 계산을 위한 변수
        total_pnl = 0.0
        total_entry_amount = 0.0
        weighted_leverage_sum = 0.0
        weighted_original_sum = 0.0
        
        # 수익률별 정렬 (높은 수익률 -> 낮은 수익률 순)
        sorted_positions = sorted(positions.items(), key=lambda x: x[1]['percentage'], reverse=True)
        
        for idx, (symbol, pos) in enumerate(sorted_positions, 1):
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            
            # 기존 데이터
            leverage_percentage = pos['percentage']  # 레버리지 수익률
            pnl = pos['unrealized_pnl']
            entry_price = pos.get('entry_price', 0)
            size = pos.get('size', 0)
            
            # 원금 수익률 계산 (레버리지 20배 기준)
            leverage = 20
            original_percentage = leverage_percentage / leverage if leverage > 0 else 0
            
            # 진입금액 계산 (원금 기준)
            entry_amount = (entry_price * size) / leverage if leverage > 0 and entry_price > 0 and size > 0 else 0
            
            # 합계 누적
            total_pnl += pnl
            total_entry_amount += entry_amount
            weighted_leverage_sum += leverage_percentage * entry_amount
            weighted_original_sum += original_percentage * entry_amount
            
            # 수익률에 따른 색상 및 이모지
            if leverage_percentage >= 50.0:
                color = GREEN
                emoji = "🔥"
            elif leverage_percentage >= 20.0:
                color = GREEN
                emoji = "🚀"
            elif leverage_percentage >= 5.0:
                color = GREEN
                emoji = "✅"
            elif leverage_percentage >= 0.0:
                color = "\033[93m"  # 노란색
                emoji = "📈"
            elif leverage_percentage >= -10.0:
                color = "\033[91m"  # 빨간색
                emoji = "⚠️"
            else:
                color = "\033[91m"  # 빨간색
                emoji = "🔻"
            
            # PnL 색상 및 부호
            pnl_color = GREEN if pnl >= 0 else "\033[91m"
            pnl_sign = "+" if pnl >= 0 else ""
            
            # 원금 수익률 색상
            orig_color = GREEN if original_percentage >= 0 else "\033[91m"
            orig_sign = "+" if original_percentage >= 0 else ""
            
            # 심볼명 길이 조정 (최대 6자)
            display_symbol = clean_symbol[:6].ljust(6)
            
            # 테이블 출력 - 수익률 통합 포맷
            combined_return = f"{color}{leverage_percentage:+7.2f}%{RESET}({orig_color}{orig_sign}{original_percentage:5.2f}%{RESET})"
            print(f"   {idx:2d}   {emoji} {color}{display_symbol}{RESET} "
                  f"{combined_return:<31} "
                  f"{pnl_color}{pnl_sign}${pnl:8.2f}{RESET}   "
                  f"${entry_price:8.4f}   "
                  f"${entry_amount:8.2f}")
        
        # 합계 수익률 계산 (가중평균)
        avg_leverage_percentage = weighted_leverage_sum / total_entry_amount if total_entry_amount > 0 else 0
        avg_original_percentage = weighted_original_sum / total_entry_amount if total_entry_amount > 0 else 0
        
        # 합계 행 색상
        total_pnl_color = GREEN if total_pnl >= 0 else "\033[91m"
        total_pnl_sign = "+" if total_pnl >= 0 else ""
        
        avg_leverage_color = GREEN if avg_leverage_percentage >= 0 else "\033[91m"
        avg_leverage_sign = "+" if avg_leverage_percentage >= 0 else ""
        
        avg_original_color = GREEN if avg_original_percentage >= 0 else "\033[91m"
        avg_original_sign = "+" if avg_original_percentage >= 0 else ""
        
        # 합계 행 출력 - 수익률 통합 포맷
        print(f"   {'─'*95}")
        combined_avg_return = f"{avg_leverage_color}{avg_leverage_sign}{avg_leverage_percentage:7.2f}%{RESET}({avg_original_color}{avg_original_sign}{avg_original_percentage:5.2f}%{RESET})"
        print(f"   💰   {'합계':<6} "
              f"{combined_avg_return:<31} "
              f"{total_pnl_color}{total_pnl_sign}${total_pnl:8.2f}{RESET}   "
              f"{'─'*8}   "
              f"${total_entry_amount:8.2f}")
        print(f"   {'─'*95}")
    
    def run_continuous_scan(self, interval=15):
        """🚀 IP 밴 방지 최고속도 연속 스캔 실행"""
        print("🚀 15분봉 초필살기 전략 연속 스캔 시작 (🔥 실전매매 모드 🔥)")
        print(f"   ⚡ 최적화 스캔 주기: {interval}초 (바이낸스 레이트 리밋 준수)")
        print(f"   📊 레버리지: 20배")
        print(f"   🛡️ IP 밴 방지: 스마트 API 호출 제한 및 재사용 최적화")
        
        # 실제 잔고 조회
        try:
            portfolio = self.get_portfolio_summary()
            print(f"   💰 현재 잔고: ${portfolio['free_balance']:.0f} USDT")
            print(f"   📊 총 자산: ${portfolio['total_balance']:.0f} USDT")
            print(f"   🎯 활성 포지션: {portfolio['open_positions']}개")
        except:
            print(f"   ⚠️ 잔고 조회 실패")
        
        print(f"   💀 최대 손실: 6% (시드 기준)")
        print(f"   🔥 실제 거래 활성화 - 리스크 관리 필수!")
        print(f"\n🔥 바이낸스 API 레이트 리밋 최적화:")
        print(f"   • Futures: 1200 requests/min (20/sec)")
        print(f"   • 스마트 배치: 병렬 + 순차 하이브리드") 
        print(f"   • 캐시 활용: 티커 데이터 재사용")
        print(f"   • 에러 복구: 자동 백오프 및 재시도")
        
        # API 호출 제한 관리
        api_call_tracker = {
            'calls_in_minute': 0,
            'last_minute_reset': time.time(),
            'max_calls_per_minute': 600,  # 안전 마진 (1200의 50%) - IP 밴 방지 강화
            'retry_delays': [1, 2, 5, 10, 30]  # 백오프 딜레이 (초)
        }
        
        while True:
            try:
                # API 호출 수 리셋 (매분)
                current_time = time.time()
                if current_time - api_call_tracker['last_minute_reset'] >= 60:
                    api_call_tracker['calls_in_minute'] = 0
                    api_call_tracker['last_minute_reset'] = current_time
                
                print(f"\n{'='*60}")
                print(f"🔍 최적화 스캔 시작: {get_korea_time().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"📊 API 호출 현황: {api_call_tracker['calls_in_minute']}/{api_call_tracker['max_calls_per_minute']}/분")
                
                # API 호출 제한 체크
                if api_call_tracker['calls_in_minute'] >= api_call_tracker['max_calls_per_minute']:
                    wait_time = 60 - (current_time - api_call_tracker['last_minute_reset'])
                    if wait_time > 0:
                        print(f"⚠️ API 호출 제한 도달 - {wait_time:.0f}초 대기 (IP 밴 방지)")
                        time.sleep(wait_time)
                        api_call_tracker['calls_in_minute'] = 0
                        api_call_tracker['last_minute_reset'] = time.time()
                
                # 심볼 스캔 (최적화된 API 호출)
                scan_start = time.time()
                signals = self.scan_symbols_optimized(api_call_tracker)
                scan_duration = time.time() - scan_start
                
                print(f"⚡ 스캔 완료: {scan_duration:.1f}초, API 호출: {api_call_tracker['calls_in_minute']}/{api_call_tracker['max_calls_per_minute']}")
                
                # 진입 신호 처리 (entry_signal 상태만)
                for signal in signals:
                    # entry_signal 상태인 종목만 거래 실행
                    if signal.get('status') == 'entry_signal':
                        if self.execute_trade(signal):
                            print(f"✅ {signal['clean_symbol']} 진입 완료")
                    else:
                        print(f"⚠️ {signal['clean_symbol']} 거래 건너뛰기 (상태: {signal.get('status', 'unknown')})")
                
                # 🔥 DCA 매니저 포지션 모니터링 및 청산 체크 (7단계 청산 시스템 사용)
                if self.dca_manager and HAS_DCA_MANAGER:
                    try:
                        # DCA 매니저 상태 검증
                        if not hasattr(self.dca_manager, 'positions'):
                            self.logger.debug("DCA 매니저 positions 속성 없음")
                        elif not isinstance(self.dca_manager.positions, dict):
                            self.logger.debug(f"DCA 매니저 positions 타입 오류: {type(self.dca_manager.positions)}")
                        else:
                            # 신규 7단계 청산 시스템 사용
                            self._check_dca_positions_with_api()
                    except Exception as e:
                        # 상세한 오류 정보 로깅
                        import traceback
                        self.logger.error(f"DCA 매니저 트리거 체크 실패: {e}")
                        self.logger.debug(f"DCA 매니저 오류 상세: {traceback.format_exc()}")
                        print(f"⚠️ DCA 매니저 일시 오류 (다음 스캔에서 재시도)")
                
                # 실제 포지션 상태 체크 (DCA 주문 체결 확인)
                self.check_real_position_status()
                
                # 실제 포트폴리오 현황 출력
                portfolio = self.get_portfolio_summary()
                print(f"\n📊 실제 포트폴리오 현황:")
                print(f"   💰 현재잔고: ${portfolio['free_balance']:.0f} USDT")
                print(f"   📈 총 자산: ${portfolio['total_balance']:.0f} USDT")
                print(f"   📊 미실현 PnL: ${portfolio['total_unrealized_pnl']:+.0f} USDT")
                print(f"   🎯 포지션수: {portfolio['open_positions']}개")
                if portfolio['open_positions'] > 0:
                    self._print_portfolio_table(portfolio['positions'])
                
                # DCA 주문 현황 요약 출력
                self._print_dca_orders_summary()
                
                # 동적 대기 시간 계산
                effective_interval = interval  # 사용자 설정 간격 사용
                if api_call_tracker['calls_in_minute'] > 600:  # 75% 도달시 더 긴 대기
                    effective_interval = interval * 1.5
                
                print(f"⏳ {effective_interval:.0f}초 대기 중 (다음 스캔까지)...")
                time.sleep(effective_interval)
                
            except KeyboardInterrupt:
                print("\n👋 사용자에 의해 중단됨")
                break
            except Exception as e:
                self.logger.error(f"스캔 중 오류: {e}")
                print(f"❌ 스캔 오류: {e}")
                
                # 백오프 전략으로 재시도
                for delay in api_call_tracker['retry_delays']:
                    print(f"🔄 {delay}초 후 재시도...")
                    time.sleep(delay)
                    try:
                        # 간단한 연결 테스트
                        self.exchange.fetch_ticker('BTC/USDT')
                        print("✅ 연결 복구됨")
                        break
                    except:
                        continue
                else:
                    print("❌ 연결 복구 실패 - 60초 대기")
                    time.sleep(60)

    def run_websocket_enhanced_scan(self, strategy_interval=15, dca_interval=1):
        """🚀 웹소켓 기반 이중 스캔: 전략신호(15초) + DCA모니터링(1초)"""
        print("🚀 웹소켓 기반 이중 스캔 시스템 시작")
        print(f"   📊 전략 신호 탐지: {strategy_interval}초 주기 (API 사용)")
        print(f"   ⚡ DCA 포지션 모니터링: {dca_interval}초 주기 (WebSocket 사용)")
        print(f"   🛡️ IP 밴 방지: WebSocket 데이터로 API 호출 최소화")
        
        # WebSocket 데이터 제공자 확인
        if not (HAS_WEBSOCKET_PROVIDER and self.ws_provider):
            print("❌ WebSocket 제공자가 없습니다. 기본 스캔으로 전환합니다.")
            return self.run_continuous_scan(strategy_interval)
        
        # 초기 포트폴리오 상태
        try:
            portfolio = self.get_portfolio_summary()
            print(f"   💰 현재 잔고: ${portfolio['free_balance']:.0f} USDT")
            print(f"   📊 총 자산: ${portfolio['total_balance']:.0f} USDT")
            print(f"   🎯 활성 포지션: {portfolio['open_positions']}개")
        except Exception as e:
            print(f"⚠️ 포트폴리오 조회 실패: {e}")
        
        # API 호출 추적
        api_call_tracker = {
            'calls_in_minute': 0,
            'max_calls_per_minute': 800,
            'last_minute_reset': time.time()
        }
        
        # 마지막 전략 스캔 시간 추적
        last_strategy_scan = 0
        scan_count = 0
        
        print(f"\n{'='*80}")
        print("🔥 웹소켓 기반 이중 스캔 루프 시작 🔥")
        print(f"{'='*80}")
        
        while True:
            try:
                current_time = time.time()
                scan_count += 1
                
                # API 호출 수 리셋 (매분)
                if current_time - api_call_tracker['last_minute_reset'] >= 60:
                    api_call_tracker['calls_in_minute'] = 0
                    api_call_tracker['last_minute_reset'] = current_time
                
                # 1. 전략 신호 탐지 (15초마다 API 사용)
                if current_time - last_strategy_scan >= strategy_interval:
                    print(f"\n{'='*60}")
                    print(f"📈 전략 스캔 #{scan_count//strategy_interval}: {get_korea_time().strftime('%H:%M:%S')}")
                    
                    # API 호출 제한 체크
                    if api_call_tracker['calls_in_minute'] >= api_call_tracker['max_calls_per_minute']:
                        wait_time = 60 - (current_time - api_call_tracker['last_minute_reset'])
                        if wait_time > 0:
                            print(f"⚠️ API 제한 대기: {wait_time:.0f}초")
                            time.sleep(wait_time)
                            api_call_tracker['calls_in_minute'] = 0
                            api_call_tracker['last_minute_reset'] = time.time()
                    
                    # 전략 신호 스캔
                    signals = self.scan_symbols_optimized(api_call_tracker)
                    for signal in signals:
                        if signal.get('status') == 'entry_signal':
                            if self.execute_trade(signal):
                                print(f"✅ {signal['clean_symbol']} 진입 완료")
                    
                    last_strategy_scan = current_time
                
                # 🔧 DCA Exchange 재연결 요청 처리
                if hasattr(self, '_request_exchange_reconnect') and self._request_exchange_reconnect:
                    print(f"🔄 DCA Manager로부터 Exchange 재연결 요청 받음")
                    try:
                        if self.dca_manager and self.private_exchange:
                            reconnect_success = self.dca_manager.refresh_exchange_connection(self.private_exchange)
                            if reconnect_success:
                                print(f"✅ DCA Exchange 재연결 성공")
                            else:
                                print(f"❌ DCA Exchange 재연결 실패")
                        self._request_exchange_reconnect = False
                    except Exception as reconnect_error:
                        print(f"❌ Exchange 재연결 처리 실패: {reconnect_error}")
                        self._request_exchange_reconnect = False

                # 2. DCA 포지션 모니터링 (1초마다 WebSocket 사용)
                if self.dca_manager and HAS_DCA_MANAGER:
                    try:
                        # WebSocket 기반 실시간 가격으로 DCA 체크
                        self._check_dca_positions_websocket()
                    except Exception as dca_error:
                        if scan_count % 60 == 0:  # 1분마다 한 번만 로그
                            print(f"⚠️ DCA 모니터링 오류: {dca_error}")
                
                # 상태 출력 (10초마다)
                if scan_count % 10 == 0:
                    active_positions = len([p for p in (self.dca_manager.positions.values() if self.dca_manager else []) if getattr(p, 'is_active', False)])
                    print(f"⚡ 스캔 #{scan_count} | DCA 포지션: {active_positions}개 | API: {api_call_tracker['calls_in_minute']}/분")
                
                # 1초 대기
                time.sleep(dca_interval)
                
            except KeyboardInterrupt:
                print("\n👋 사용자에 의해 중단됨")
                break
            except Exception as e:
                self.logger.error(f"웹소켓 스캔 오류: {e}")
                print(f"❌ 오류: {e}")
                time.sleep(5)  # 오류 발생시 5초 대기
    
    def _check_dca_positions_websocket(self):
        """웹소켓 데이터 기반 DCA 포지션 실시간 모니터링"""
        try:
            if not self.dca_manager:
                return
            
            active_positions = {
                symbol: position for symbol, position in self.dca_manager.positions.items()
                if position.is_active
            }
            
            if not active_positions:
                return
            
            # 웹소켓에서 실시간 가격 조회 (API 호출 없음)
            for symbol, position in active_positions.items():
                try:
                    # 웹소켓 캐시에서 현재가 조회
                    ticker_data = self.ws_provider.get_ticker(symbol)
                    if not ticker_data or 'last' not in ticker_data:
                        continue
                    
                    current_price = float(ticker_data['last'])
                    
                    # DCA 청산 트리거 체크 (웹소켓 + BB80>BB600 수동청산 조건)
                    dca_result = self.dca_manager.check_dca_triggers(symbol, current_price)
                    
                    # dca_result가 유효한 딕셔너리인지 확인
                    if dca_result and isinstance(dca_result, dict) and dca_result.get('trigger_activated'):
                        action = dca_result.get('action', 'unknown')
                        trigger_info = dca_result.get('trigger_info', {})
                        manual_exit = dca_result.get('manual_exit', False)
                        
                        clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                        
                        # 수동청산 전환 신호 처리 (BB80 > BB600 조건)
                        if manual_exit and action == 'manual_exit_required':
                            profit_pct = trigger_info.get('profit_pct', 0)
                            bb80_upper = trigger_info.get('bb80_upper', 0)
                            bb600_upper = trigger_info.get('bb600_upper', 0)
                            reason = trigger_info.get('reason', '')
                            
                            print(f"\n🎯 {clean_symbol} 수동청산 전환 신호 (웹소켓):")
                            print(f"   💰 현재가: ${current_price:.6f}")
                            print(f"   📈 원금수익률: {profit_pct:.2f}% (≥5%)")
                            print(f"   📊 BB80 상단: ${bb80_upper:.6f}")
                            print(f"   📊 BB600 상단: ${bb600_upper:.6f}")
                            print(f"   🎯 조건: {reason}")
                            print(f"   ⚠️  수동 청산 권장 (자동청산 비활성화)")
                            
                            continue  # 수동청산 신호는 실제 청산하지 않고 알림만
                        
                        # 수익 보호 청산 신호 처리 (6-10% 구간 → 5% 보호)
                        if action == 'profit_protection_executed':
                            max_profit_pct = trigger_info.get('max_profit_pct', 0)
                            current_profit_pct = trigger_info.get('current_profit_pct', 0)
                            protection_line_pct = trigger_info.get('protection_line_pct', 5)
                            reason = trigger_info.get('reason', '')
                            
                            print(f"\n💰 {clean_symbol} 수익 보호 청산 실행 (웹소켓):")
                            print(f"   💰 현재가: ${current_price:.6f}")
                            print(f"   📈 최대 수익률: {max_profit_pct:.2f}% (≥6%)")
                            print(f"   📉 현재 수익률: {current_profit_pct:.2f}%")
                            print(f"   🛡️  보호선: {protection_line_pct:.0f}%")
                            print(f"   🎯 사유: {reason}")
                            print(f"   ✅ 전량 청산으로 5% 수익 보장")
                            
                            continue  # 보호 청산 완료됨
                        
                        # 기존 자동 청산 신호 처리
                        exit_type = dca_result.get('exit_type', 'unknown')
                        exit_ratio = dca_result.get('exit_ratio', 0)
                        current_price_from_signal = dca_result.get('current_price', current_price)
                        reason = dca_result.get('reason', 'unknown reason')
                        
                        print(f"\n🔥 DCA 청산 신호 (웹소켓): {clean_symbol}")
                        print(f"   📊 타입: {exit_type}")
                        print(f"   💰 현재가: ${current_price:.4f}")
                        print(f"   📉 청산비율: {exit_ratio*100:.0f}%")
                        print(f"   🎯 사유: {reason}")
                        if isinstance(trigger_info, dict):
                            for key, value in trigger_info.items():
                                print(f"   📋 {key}: {value}")
                        
                        # 실제 청산 실행 (수동청산 신호가 아닌 경우만)
                        try:
                            execute_result = self.dca_manager.execute_new_exit(symbol, dca_result)
                            if execute_result and execute_result.get('success'):
                                print(f"   ✅ 청산 실행 완료")
                            else:
                                print(f"   ❌ 청산 실행 실패: {execute_result.get('error', 'unknown error')}")
                        except Exception as exec_error:
                            if "apiKey" in str(exec_error):
                                print(f"   ❌ 청산 실행 실패: API 키가 설정되지 않았습니다")
                                print(f"   📋 해결방법: binance_config.py에서 API 키와 시크릿 키를 설정해주세요")
                            else:
                                print(f"   ❌ 청산 실행 오류: {exec_error}")
                        
                except Exception as pos_error:
                    # 개별 포지션 오류는 조용히 처리 (로그만)
                    self.logger.debug(f"포지션 체크 오류 {symbol}: {pos_error}")
                    continue
        
        except Exception as e:
            self.logger.error(f"웹소켓 DCA 체크 실패: {e}")
    
    def _check_dca_positions_with_api(self):
        """API 기반 DCA 포지션 실시간 모니터링 (일반 스캔용)"""
        try:
            if not self.dca_manager:
                return
            
            # 포지션 데이터 타입 검증 및 안전한 필터링
            active_positions = {}
            for symbol, position in self.dca_manager.positions.items():
                try:
                    # position이 딕셔너리 또는 DCAPosition 객체인지 확인
                    if hasattr(position, 'is_active'):
                        # DCAPosition 객체인 경우
                        if position.is_active:
                            active_positions[symbol] = position
                    elif isinstance(position, dict):
                        # 딕셔너리인 경우
                        if position.get('is_active', False):
                            active_positions[symbol] = position
                    # 문자열이나 다른 타입은 무시
                except Exception as pos_err:
                    self.logger.debug(f"포지션 데이터 타입 오류 {symbol}: {type(position)} - {pos_err}")
                    continue
            
            if not active_positions:
                return
            
            # API에서 실시간 가격 조회
            for symbol, position in active_positions.items():
                try:
                    # API에서 현재가 조회
                    ticker = self.exchange.fetch_ticker(symbol)
                    current_price = float(ticker['last'])
                    
                    # DCA 청산 트리거 체크 (7단계 청산 시스템 + BB80>BB600 수동청산 조건)
                    dca_result = self.dca_manager.check_dca_triggers(symbol, current_price)
                    
                    # dca_result가 유효한 딕셔너리인지 확인
                    if dca_result and isinstance(dca_result, dict) and dca_result.get('trigger_activated'):
                        action = dca_result.get('action', 'unknown')
                        trigger_info = dca_result.get('trigger_info', {})
                        manual_exit = dca_result.get('manual_exit', False)
                        
                        clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                        
                        # 수동청산 전환 신호 처리 (BB80 > BB600 조건)
                        if manual_exit and action == 'manual_exit_required':
                            profit_pct = trigger_info.get('profit_pct', 0)
                            bb80_upper = trigger_info.get('bb80_upper', 0)
                            bb600_upper = trigger_info.get('bb600_upper', 0)
                            reason = trigger_info.get('reason', '')
                            
                            print(f"\n🎯 {clean_symbol} 수동청산 전환 신호:")
                            print(f"   💰 현재가: ${current_price:.6f}")
                            print(f"   📈 원금수익률: {profit_pct:.2f}% (≥5%)")
                            print(f"   📊 BB80 상단: ${bb80_upper:.6f}")
                            print(f"   📊 BB600 상단: ${bb600_upper:.6f}")
                            print(f"   🎯 조건: {reason}")
                            print(f"   ⚠️  수동 청산 권장 (자동청산 비활성화)")
                            
                            # 텔레그램 알림
                            if hasattr(self, 'telegram_bot') and self.telegram_bot:
                                alert_message = f"""🎯 <b>{clean_symbol}</b> 수동청산 전환 신호
━━━━━━━━━━━━━━━━━━━━━━
💰 현재가: ${current_price:.6f}
📈 원금수익률: <b>{profit_pct:.2f}%</b> (≥5%)
📊 BB80 상단: ${bb80_upper:.6f}
📊 BB600 상단: ${bb600_upper:.6f}
━━━━━━━━━━━━━━━━━━━━━━
🎯 조건: {reason}
⚠️ <b>수동 청산 권장</b>
🚨 자동청산 일시 중단
🕒 시간: {get_korea_time().strftime('%H:%M:%S')}"""
                                self.telegram_bot.send_message(alert_message)
                            
                            continue  # 수동청산 신호는 실제 청산하지 않고 알림만
                        
                        # 수익 보호 청산 신호 처리 (6-10% 구간 → 5% 보호)
                        if action == 'profit_protection_executed':
                            max_profit_pct = trigger_info.get('max_profit_pct', 0)
                            current_profit_pct = trigger_info.get('current_profit_pct', 0)
                            protection_line_pct = trigger_info.get('protection_line_pct', 5)
                            reason = trigger_info.get('reason', '')
                            
                            print(f"\n💰 {clean_symbol} 수익 보호 청산 실행:")
                            print(f"   💰 현재가: ${current_price:.6f}")
                            print(f"   📈 최대 수익률: {max_profit_pct:.2f}% (≥6%)")
                            print(f"   📉 현재 수익률: {current_profit_pct:.2f}%")
                            print(f"   🛡️  보호선: {protection_line_pct:.0f}%")
                            print(f"   🎯 사유: {reason}")
                            print(f"   ✅ 전량 청산으로 5% 수익 보장")
                            
                            # 텔레그램 알림
                            if hasattr(self, 'telegram_bot') and self.telegram_bot:
                                alert_message = f"""💰 <b>{clean_symbol}</b> 수익 보호 청산 완료
━━━━━━━━━━━━━━━━━━━━━━
💰 현재가: ${current_price:.6f}
📈 최대 수익률: <b>{max_profit_pct:.2f}%</b>
📉 현재 수익률: {current_profit_pct:.2f}%
🛡️ 보호선: <b>{protection_line_pct:.0f}%</b>
━━━━━━━━━━━━━━━━━━━━━━
🎯 {reason}
✅ <b>전량 청산으로 5% 수익 확보</b>
🕒 시간: {get_korea_time().strftime('%H:%M:%S')}"""
                                self.telegram_bot.send_message(alert_message)
                            
                            continue  # 보호 청산 완료됨
                        
                        # 기존 자동 청산 신호 처리
                        exit_type = dca_result.get('exit_type', 'unknown')
                        exit_ratio = dca_result.get('exit_ratio', 0)
                        current_price_from_signal = dca_result.get('current_price', current_price)
                        reason = dca_result.get('reason', 'unknown reason')
                        
                        print(f"\n🔥 DCA 청산 신호: {clean_symbol}")
                        print(f"   📊 타입: {exit_type}")
                        print(f"   💰 현재가: ${current_price:.4f}")
                        print(f"   📉 청산비율: {exit_ratio*100:.0f}%")
                        print(f"   🎯 사유: {reason}")
                        if isinstance(trigger_info, dict):
                            for key, value in trigger_info.items():
                                print(f"   📋 {key}: {value}")
                        
                        # 실제 청산 실행 (수동청산 신호가 아닌 경우만)
                        try:
                            execute_result = self.dca_manager.execute_new_exit(symbol, dca_result)
                            if execute_result and execute_result.get('success'):
                                print(f"   ✅ 청산 실행 완료")
                            else:
                                print(f"   ❌ 청산 실행 실패: {execute_result.get('error', 'unknown error')}")
                        except Exception as exec_error:
                            if "apiKey" in str(exec_error):
                                print(f"   ❌ 청산 실행 실패: API 키가 설정되지 않았습니다")
                                print(f"   📋 해결방법: binance_config.py에서 API 키와 시크릿 키를 설정해주세요")
                            else:
                                print(f"   ❌ 청산 실행 오류: {exec_error}")
                        
                except Exception as pos_error:
                    # 개별 포지션 오류는 조용히 처리 (로그만)
                    self.logger.debug(f"포지션 체크 오류 {symbol}: {pos_error}")
                    continue
        
        except Exception as e:
            self.logger.error(f"API DCA 체크 실패: {e}")

def main():
    """🚀 Alpha-Z Triple Strategy 메인 함수"""
    import sys
    
    try:
        print("Alpha-Z Triple Strategy 시작 (A+B+C전략)")
        print("="*60)
        
        # 명령행 인수 처리
        mode = 'continuous'  # 기본값: 연속 스캔으로 변경
        interval = 15    # 기본값: 15초 간격 (최적화 - WebSocket 활용)
        
        if len(sys.argv) > 1:
            if sys.argv[1] in ['single', 'once', 's']:
                mode = 'single'
            elif sys.argv[1] in ['continuous', 'cont', 'c']:
                mode = 'continuous'
            elif sys.argv[1] in ['websocket', 'ws', 'w']:
                mode = 'websocket'  # 새로운 웹소켓 모드
            if len(sys.argv) > 2:
                try:
                    interval = int(sys.argv[2])
                    interval = max(10, min(600, interval))  # 10초~10분 제한 (WebSocket 최적화)
                except:
                    interval = 15
        
        # Alpha-Z Triple Strategy 초기화 (A전략+B전략+C전략, 실전매매 모드)
        strategy = FifteenMinuteMegaStrategy(sandbox=False)
        
        # 실제 포트폴리오 상태 출력
        portfolio = strategy.get_portfolio_summary()
        print(f"\n실전매매 포트폴리오 초기 상태:")
        print(f"   현재 잔고: ${portfolio['free_balance']:.0f} USDT")
        print(f"   총 자산: ${portfolio['total_balance']:.0f} USDT")
        print(f"   미실현 PnL: ${portfolio['total_unrealized_pnl']:+.0f} USDT")
        print(f"   활성 포지션: {portfolio['open_positions']}개")
        if portfolio['open_positions'] > 0:
            strategy._print_portfolio_table(portfolio['positions'])
        
        if mode == 'websocket':
            # 웹소켓 기반 이중 스캔 모드
            print(f"\n🚀 웹소켓 이중 스캔 모드 시작")
            print(f"   📊 전략 신호: {interval}초 주기 (API)")
            print(f"   ⚡ DCA 모니터링: 1초 주기 (WebSocket)")
            print(f"   🛡️ IP 밴 위험 최소화")
            print(f"   ⚠️ 중단: Ctrl+C")
            strategy.run_websocket_enhanced_scan(strategy_interval=interval, dca_interval=1)
        elif mode == 'continuous':
            # 연속 스캔 모드 (IP 밴 방지 최적화)
            print(f"\n연속 스캔 모드 시작 (IP 밴 방지 최적화)")
            print(f"   ⚡ 스캔 간격: {interval}초")
            print(f"   🛡️ 바이낸스 레이트 리밋 준수")
            print(f"   📊 단일 스캔: python alpha_z_triple_strategy.py single")
            print(f"   🚀 웹소켓 모드: python alpha_z_triple_strategy.py websocket")
            print(f"   ⚠️ 중단: Ctrl+C")
            strategy.run_continuous_scan(interval)
        else:
            # 단일 스캔 모드 (기본값)
            print(f"\n단일 스캔 모드 (최고속도 최적화)")
            print(f"   ⚡ IP 밴 방지 최적화 적용")
            print(f"   📊 기본값은 연속 모드입니다")
            
            # API 호출 추적기 초기화
            api_call_tracker = {
                'calls_in_minute': 0,
                'last_minute_reset': time.time(),
                'max_calls_per_minute': 800,
                'retry_delays': [1, 2, 5, 10, 30]
            }
            
            # 최적화된 단일 스캔 실행
            signals = strategy.scan_symbols_optimized(api_call_tracker)
            
            # 진입 신호 처리 (entry_signal 상태만)
            if signals:
                print(f"\n🔥 진입 신호 처리 중...")
                for signal in signals:
                    # entry_signal 상태인 종목만 거래 실행
                    if signal.get('status') == 'entry_signal':
                        if strategy.execute_trade(signal):
                            print(f"✅ {signal['clean_symbol']} 진입 완료")
                    else:
                        print(f"⚠️ {signal['clean_symbol']} 거래 건너뛰기 (상태: {signal.get('status', 'unknown')})")
            
            # 🔥 DCA 매니저 포지션 모니터링 및 청산 체크 (단일 스캔 모드 통합)
            if strategy.dca_manager and HAS_DCA_MANAGER:
                try:
                    # 현재 잔고 조회 (트리거 계산용)
                    temp_portfolio = strategy.get_portfolio_summary()
                    current_balance = temp_portfolio.get('free_balance', 0)
                    
                    # 모든 활성 DCA 포지션의 트리거 확인
                    dca_results = strategy.dca_manager.check_triggers(current_balance)
                    if dca_results:
                        for symbol, result in dca_results.items():
                            if result and result.get('trigger_activated'):
                                action = result.get('action', 'unknown')
                                trigger_type = result.get('trigger_info', {}).get('type', '알 수 없음')
                                print(f"🔄 DCA 트리거 활성: {symbol.replace('/USDT:USDT', '')} - {action} ({trigger_type})")
                                
                                # 청산 트리거인 경우 텔레그램 알림
                                if action in ['stop_loss_executed', 'supertrend_exit_executed', 'technical_exit_executed']:
                                    clean_sym = symbol.replace('/USDT:USDT', '')
                                    if hasattr(strategy, 'telegram_bot') and strategy.telegram_bot:
                                        strategy.telegram_bot.send_message(f"🚨 자동청산 실행: {clean_sym}\n유형: {trigger_type}\n액션: {action}")
                except Exception as e:
                    print(f"⚠️ DCA 매니저 단일 스캔 트리거 체크 실패: {e}")
            
            # 최종 포지션 상태 체크
            strategy.check_real_position_status()
            
            # 최종 포트폴리오 현황 출력
            final_portfolio = strategy.get_portfolio_summary()
            print(f"\n📊 최종 포트폴리오 현황:")
            print(f"   💰 잔고: ${final_portfolio['free_balance']:.0f} USDT")
            print(f"   📈 총 자산: ${final_portfolio['total_balance']:.0f} USDT") 
            print(f"   📊 미실현 PnL: ${final_portfolio['total_unrealized_pnl']:+.0f} USDT")
            print(f"   🎯 포지션수: {final_portfolio['open_positions']}개")
            
            print(f"\n⚡ 최고속도 스캔 완료!")
            print(f"   🛡️ API 호출: {api_call_tracker['calls_in_minute']}/{api_call_tracker['max_calls_per_minute']}")
            print(f"   📊 IP 밴 방지: 성공적으로 레이트 리밋 준수")
        
    except KeyboardInterrupt:
        print("\n👋 사용자에 의해 중단됨")
    except Exception as e:
        print(f"❌ 시스템 오류: {e}")
        import traceback
        traceback.print_exc()

def emergency_close_all_positions():
    """긴급 전체 포지션 청산 (비상용)"""
    try:
        strategy = FifteenMinuteMegaStrategy(sandbox=False)
        
        if not strategy.private_exchange:
            print("❌ 프라이빗 API 없음 - 청산 불가")
            return
        
        print("🚨 긴급 전체 포지션 청산 시작...")
        
        # 실제 포지션 조회
        positions = strategy.private_exchange.fetch_positions()
        open_positions = [p for p in positions if p['contracts'] > 0]
        
        if not open_positions:
            print("✅ 청산할 포지션이 없습니다.")
            return
        
        print(f"📊 청산할 포지션: {len(open_positions)}개")
        
        for position in open_positions:
            try:
                symbol = position['symbol']
                size = position['contracts']
                clean_symbol = symbol.replace('/USDT:USDT', '')
                
                # 시장가 매도 (전량 청산)
                order = strategy.private_exchange.create_market_sell_order(symbol, size)
                print(f"✅ {clean_symbol} 청산 완료: {size:.6f}")
                
            except Exception as e:
                print(f"❌ {symbol} 청산 실패: {e}")
        
        print("✅ 긴급 청산 완료")
        
    except Exception as e:
        print(f"❌ 긴급 청산 실패: {e}")

if __name__ == "__main__":
    main()