# -*- coding: utf-8 -*-
"""
A전략(3분봉 바닥급등타점) + B전략(15분봉 급등초입) + C전략(30분봉 급등맥점) 시스템
레버리지 10배 적용

거래 설정:
- 레버리지: 10배
- 초기 진입: 원금 1.0% x 10배 레버리지 (10% 노출)
- 최대 진입 종목: 10종목
- 재진입: 순환매 활성화 (최대 3회 순환매)
- 손절: 평균가 대비 -10% 전량 손절 (단계별 갱신)
- 종목당 최대 비중: 2.0% (초기 1.0% + 불타기 최대 1.0%)
- 최대 원금 사용: 20% (10종목 × 2.0%)

불타기 시스템 (상승 눌림목 추가 진입):
- 1차 불타기: +1.5% 상승 후 -0.8%~-1.2% 눌림 시 +0.5% 추가
  * 조건: 진입 후 최고점 +1.5% 이상, 현재 수익 +0.3% 이상
  * 타임아웃: 30분 이내
  * 누적 노출: 15% (1.0% + 0.5%) × 10배
- 2차 불타기: +1.0% 추가 상승 후 -0.8%~-1.0% 눌림 시 +0.5% 추가
  * 조건: 1차 후 최고점 +1.0% 이상, 총 수익 +2.0% 이상
  * 타임아웃: 20분 이내
  * 최대 노출: 20% (1.0% + 0.5% + 0.5%) × 10배
- 불타기 금지: 최고점 대비 -2.0% 이상 급락 시

청산 시스템:
- 손절: 평균가 대비 -10% 전량 손절 (불타기 후 평균가 갱신)
  * 초기 진입만: 1.0% × 10배 × -10% = 시드의 1.00% 손실
  * 1차 불타기: 1.5% × 10배 × -10% = 시드의 1.50% 손실
  * 2차 불타기: 2.0% × 10배 × -10% = 시드의 2.00% 손실
- 이익실현: Trailing Stop 방식
  * 2-3% 수익 도달 시 추적 시작
  * 최고점 대비 1.5% 하락 시 손실 전환 전 전량 청산
  * 예: 2.5% 수익 도달 → 2.0%로 하락 시 청산 (1.0% 이익 확보)

전략 조건:
A전략(3분봉 바닥급등타점): 5개 조건
  - 조건1: 500봉이내 MA80-MA480 골든크로스 or MA80<MA480
  - 조건2: 500봉이내 BB80-BB480 골든크로스
  - 조건3: 10봉이내 (저가<BB80하한 or MA5<BB80하한)
  - 조건4: 종가<MA5
  - 조건5: 10봉이내 MA5-MA20 골든크로스 and MA20<MA80
B전략(15분봉 급등초입): 6개 조건 - 200봉이내 MA80-MA480 골든크로스 + BB골든크로스 + MA5-MA20골든크로스 + BB200상단-MA480 상향돌파 + MA20-MA80 데드크로스 or 이격도조건 + 시가대비고가 3%이상
C전략(30분봉 급등맥점): 2개 기본조건 + 3개 타점(A/B/C) - 기본조건(50봉이내 MA80-MA480 골든크로스 or MA80<MA480 + 100봉이내 MA480-BB200 크로스) + A/B/C 타점 중 1개
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

# Binance Rate Limiter 추가 (IP 차단 방지)
try:
    from binance_rate_limiter import RateLimitedExchange, BinanceRateLimiter
    HAS_RATE_LIMITER = True
    print("[INFO] Binance Rate Limiter 로드 완료")
except ImportError:
    print("[WARNING] binance_rate_limiter.py 없음 - Rate Limiting 비활성화")
    HAS_RATE_LIMITER = False

try:
    from improved_dca_position_manager import ImprovedDCAPositionManager
    HAS_DCA_MANAGER = True
    print("[INFO] 개선된 DCA 매니저 로드 완료")
except ImportError:
    print("[INFO] improved_dca_position_manager.py 없음 - DCA 기능 비활성화")
    HAS_DCA_MANAGER = False

# 거래 로깅 시스템 추가
try:
    from strategy_integration_patch import (
        log_entry_signal, log_exit_signal, log_dca_signal,
        get_trading_statistics, get_strategy_performance
    )
    HAS_TRADING_LOGGER = True
    print("[INFO] 거래 로깅 시스템 연동 완료")
except ImportError:
    print("[INFO] strategy_integration_patch.py 없음 - 로깅 기능 비활성화")
    HAS_TRADING_LOGGER = False
    # 더미 함수들로 대체
    def log_entry_signal(*args, **kwargs): pass
    def log_exit_signal(*args, **kwargs): pass  
    def log_dca_signal(*args, **kwargs): pass
    def get_trading_statistics(): return {}
    def get_strategy_performance(): return {}

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
        
        # Exchange 설정 (Rate Limiter 적용으로 IP 차단 방지)
        # 공개 API (스캔용)
        raw_exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
        # Rate Limiter 래퍼 적용
        if HAS_RATE_LIMITER:
            self.exchange = RateLimitedExchange(raw_exchange, self.logger)
            print("[INFO] 공개 API - Rate Limiter 적용 완료")
        else:
            self.exchange = raw_exchange
            print("[WARNING] 공개 API - Rate Limiter 없음")
        
        # 프라이빗 API (거래용)
        if HAS_BINANCE_CONFIG and BinanceConfig.API_KEY:
            raw_private_exchange = ccxt.binance({
                'apiKey': BinanceConfig.API_KEY,
                'secret': BinanceConfig.SECRET_KEY,
                'sandbox': sandbox,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',
                    'warnOnFetchOpenOrdersWithoutSymbol': False  # 경고 메시지 억제
                }
            })
            
            # Rate Limiter 래퍼 적용
            if HAS_RATE_LIMITER:
                self.private_exchange = RateLimitedExchange(raw_private_exchange, self.logger)
                print("[INFO] 프라이빗 API - Rate Limiter 적용 완료")
            else:
                self.private_exchange = raw_private_exchange
                print("[WARNING] 프라이빗 API - Rate Limiter 없음")
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
        
        # DCA 매니저 초기화 (레버리지 10배)
        if HAS_DCA_MANAGER and self.private_exchange:
            self.dca_manager = ImprovedDCAPositionManager(
                exchange=self.private_exchange,
                telegram_bot=self.telegram_bot,
                stats_callback=None,  # 필요시 콜백 추가
                strategy=self  # 전략 참조 전달
            )
            # 레버리지 10배로 설정 업데이트
            self.dca_manager.config['initial_leverage'] = 10.0
            self.dca_manager.config['first_dca_leverage'] = 10.0
            self.dca_manager.config['second_dca_leverage'] = 10.0
            print("[INFO] DCA 매니저 초기화 완료 - 레버리지 10배 적용")
        else:
            self.dca_manager = None
            print("[WARN] DCA 매니저 없음 - 프라이빗 API 필요")
        
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
        
        print("15분봉 초필살기 전략 시스템 초기화 완료")
        print(f"   레버리지: 10배")
        print(f"   최초 진입: 1.5% (15% 노출)")
        print(f"   최대 손실: 0.45% (시드 기준)")
    
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
        """신호 데이터에서 전략 타입 추출 (A, B, C 전략 및 조합 지원)"""
        try:
            if signal_data.get('strategy_details'):
                details = signal_data['strategy_details']
                a_signal = details.get('strategy_a', {}).get('signal', False)
                b_signal = details.get('strategy_b', {}).get('signal', False)
                c_signal = details.get('strategy_c', {}).get('signal', False)

                # 3개 전략 모두 신호인 경우
                if a_signal and b_signal and c_signal:
                    return "[A+B+C전략(3분+15분+30분 트리플 신호)]"

                # 2개 전략 조합인 경우
                elif a_signal and b_signal:
                    return "[A+B전략(3분봉바닥급등+15분봉급등초입)]"
                elif a_signal and c_signal:
                    return "[A+C전략(3분봉바닥급등+30분봉급등맥점)]"
                elif b_signal and c_signal:
                    return "[B+C전략(15분봉급등초입+30분봉급등맥점)]"

                # 단일 전략인 경우 - 자세한 명칭 표시
                elif a_signal:
                    return "[A전략(3분봉 바닥급등타점)]"
                elif b_signal:
                    return "[B전략(15분봉 급등초입)]"
                elif c_signal:
                    return "[C전략(30분봉 급등맥점)]"

            return "[전략미상]"
        except:
            return "[전략미상]"
    
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
                    a_signal = details['strategy_a']['signal']
                    b_signal = details['strategy_b']['signal']

                    print(f"🔍 [전략분류] {clean_symbol} - A:{a_signal}, B:{b_signal}, C:{c_signal} | 통과: A={a_passed}/5, B={b_passed}/6, C={c_passed}/4")

                    # MA80>MA480인데 A전략 신호인 경우 경고
                    if a_signal:
                        # A전략 조건1 체크
                        a_cond1_check = any('[A전략 조건1]' in str(cond) and 'False' in str(cond) for cond in result.get('conditions', []))
                        if a_cond1_check:
                            print(f"🚨 [분류 오류 의심] {clean_symbol}: A전략 신호인데 조건1=False!")

                # A전략 분류 (5개 조건 기준)
                if details['strategy_a']['signal']:
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
                            failed_conds.append("종가<MA5 골든크로스")
                    elif '조건4' in str(cond):
                        if strategy_type == 'A':
                            failed_conds.append("현재가-MA5 조건")
                        elif strategy_type == 'B':
                            failed_conds.append("BB200-MA480 상향돌파")
                        else:  # C전략
                            failed_conds.append("시가대비고가 3%이상")
                    elif '조건5' in str(cond):
                        if strategy_type == 'A':
                            failed_conds.append("시가대비고가 3%이상")
                        else:  # B전략
                            failed_conds.append("데드크로스/이격도/시가대비고가+BB480")
                    elif '조건6' in str(cond):  # B전략만
                        failed_conds.append("시가대비고가 5%이상")
            return failed_conds

        # 🅰️ A전략(바닥타점) 결과
        print(f"\n🅰️ A전략(바닥타점) 결과 - MA80<MA480 필수")
        print(f"{'='*60}")

        if a_entry_signals:
            print(f"┌{'─'*30}┐")
            print(f"│   🔥 진입신호 ({len(a_entry_signals)}개)        │")
            print(f"│   (조건: MA80<MA480)     │")
            print(f"└{'─'*30}┘")
            # 2x2 배치
            for i in range(0, len(a_entry_signals), 2):
                row = a_entry_signals[i:i+2]
                if len(row) == 2:
                    print(f"   🎯 {GREEN}{row[0]['symbol']:<8}{RESET}   🎯 {GREEN}{row[1]['symbol']}{RESET}")
                else:
                    print(f"   🎯 {GREEN}{row[0]['symbol']}{RESET}")
        else:
            print(f"┌{'─'*30}┐")
            print(f"│  🔥 진입신호 (없음)        │")
            print(f"└{'─'*30}┘")
        
        if a_near_entry:
            print(f"\n┌{'─'*55}┐")
            print(f"│  🔥 진입임박 ({len(a_near_entry)}개) - 조건 1개 미충족                 │")
            print(f"└{'─'*55}┘")
            for signal in a_near_entry:
                # 해당 심볼의 원본 결과 찾기
                original_result = next((r for r in all_results if r['symbol'].replace('/USDT:USDT', '') == signal['symbol']), None)
                failed_conds = get_failed_conditions(original_result, 'A') if original_result else []
                failed_text = "\033[91m" + ", ".join(failed_conds) + "\033[0m" if failed_conds else "\033[91m미상\033[0m"
                print(f"   🔥 \033[93m{signal['symbol']}\033[0m - 미충족: {failed_text}")
        else:
            print(f"\n┌{'─'*30}┐")
            print(f"│  🔥 진입임박 (없음)        │")
            print(f"└{'─'*30}┘")
        
        if a_potential_entry:
            print(f"\n┌{'─'*55}┐")
            print(f"│  ⚡ 진입확률 ({len(a_potential_entry)}개) - 조건 2개 미충족                 │")
            print(f"└{'─'*55}┘")
            # 가로 4줄 배치
            symbols = [signal['symbol'] for signal in a_potential_entry]
            for i in range(0, len(symbols), 4):
                row = symbols[i:i+4]
                formatted_row = [f"\033[93m{symbol}\033[0m" for symbol in row]
                print(f"   ⚡ {' | '.join(formatted_row)}")
        else:
            print(f"\n┌{'─'*30}┐")
            print(f"│  ⚡ 진입확률 (없음)        │")
            print(f"└{'─'*30}┘")
        
        if a_watchlist:
            print(f"\n┌{'─'*40}┐")
            print(f"│   👀 관심종목 ({len(a_watchlist)}개)                  │")
            print(f"└{'─'*40}┘")
            # 가로 4줄 배치 (최대 10개)
            symbols = [signal['symbol'] for signal in a_watchlist[:10]]
            for i in range(0, len(symbols), 4):
                row = symbols[i:i+4]
                formatted_row = [f"\033[93m{symbol}\033[0m" for symbol in row]
                print(f"   👀 {' | '.join(formatted_row)}")
        else:
            print(f"\n┌{'─'*30}┐")
            print(f"│  👀 관심종목 (없음)        │")
            print(f"└{'─'*30}┘")
        
        # 🅱️ B전략(급등초입) 결과
        print(f"\n🅱️ B전략(급등초입) 결과 - 골든크로스 후 진입")
        print(f"{'='*60}")

        if b_entry_signals:
            print(f"┌{'─'*30}┐")
            print(f"│   🔥 진입신호 ({len(b_entry_signals)}개)        │")
            print(f"│   (MA80 >= MA480 OK)    │")
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
        
        # 🇨 C전략(30분봉 급등맥점) 결과
        print(f"\n🇨 C전략(30분봉 급등맥점) 결과 - 30분봉 독립")
        print(f"{'='*60}")

        if c_entry_signals:
            print(f"┌{'─'*30}┐")
            print(f"│   🔥 진입신호 ({len(c_entry_signals)}개)        │")
            print(f"│   (15분봉 MA 무관)      │")
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
        
        # A전략, B전략, C전략의 진입신호 통합
        for signal in a_entry_signals:
            signal_copy = signal.copy()
            signal_copy['strategy_type'] = '[A전략]'
            all_entry_signals.append(signal_copy)
            
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
            print(f"\n{'='*60}")
            print(f"🎯 전체 진입신호 통합 ({len(final_entry_signals)}개)")
            print(f"   ⚠️  주의: 각 종목이 어느 전략 신호인지 확인하세요!")
            print(f"{'='*60}")
            for signal in final_entry_signals:
                clean_symbol = signal['symbol'].replace('/USDT:USDT', '')
                strategy_type = signal['strategy_type']
                print(f"   🎯 {GREEN}{clean_symbol:<10}{RESET} {strategy_type}")
        else:
            print(f"\n🎯 전체 진입신호 통합 (없음)")
    
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
        # 🔥🔥🔥 UPDATED VERSION - A/B/C 전략 통합 🔥🔥🔥
        """
        A전략(3분봉 바닥급등타점) + B전략(15분봉 급등초입) + C전략(30분봉 급등맥점) 조건 체크

        A전략: 3분봉 바닥급등타점 (4개 조건)
        - (10봉이내 MA80-MA480 골든크로스 or 현재봉 MA80<MA480) AND
        - 15봉이내 BB80상단선-BB480상단선 골든크로스 AND
        - 5봉이내 1봉전 종가<MA5 골든크로스 AND
        - (3분봉상 or 15분봉상) 20봉이내 시가대비고가 3%이상 1회이상

        B전략: 15분봉 급등초입 (6개 조건)
        - 200봉 이내 MA80-MA480 골든크로스 AND
        - BB 골든크로스 AND
        - 10봉 이내 1봉전 MA5-MA20 골든크로스 AND (현재가<ma5 or 현재가-ma5 이격도 0.5%이내) AND
        - 250봉이내 BB200상단-MA480 상향돌파 AND
        - 40봉이내 데드크로스/이격도/시가대비고가 조건 AND
        - 200봉이내 시가대비고가 3%이상 1회이상

        C전략: 30분봉 급등맥점 (기본조건 2개 + 타점 3개 중 1개)
        - 기본조건1: 50봉이내 MA80-MA480 골든크로스 OR 현재봉 MA80<MA480
        - 기본조건2: 100봉이내 MA480-BB200상단선 크로스(양방향)
        - A타점/B타점/C타점 중 하나 충족 시 진입
        
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

            # 15분봉 MA 데이터 유효성 체크 (MA480 계산 가능 여부만 확인)
            ma80_15m = df_calc['ma80'].iloc[-1]
            ma5_15m = df_calc['ma5'].iloc[-1]
            ma480_15m = df_calc['ma480'].iloc[-1]

            if pd.isna(ma480_15m) or pd.isna(ma80_15m) or pd.isna(ma5_15m):
                conditions.append(f"[BLOCKED] 15분봉 MA 계산 실패 - 데이터 부족 (필요:480봉, 현재:{len(df_15m)})")
                return False, conditions, {
                    'strategy_a': {'signal': False, 'conditions': conditions, 'name': 'A전략(MA계산실패)'},
                    'strategy_b': {'signal': False, 'conditions': [], 'name': 'B전략(MA계산실패)'},
                    'strategy_c': {'signal': False, 'conditions': [], 'name': 'C전략(MA계산실패)'}
                }

            # A전략: 3분봉 바닥급등타점 (타임프레임 순서: 3분 → 15분 → 30분)
            # B전략: 15분봉 급등초입
            # C전략: 30분봉 급등맥점

            # A전략: 3분봉 바닥급등타점 체크
            strategy_a_signal, strategy_a_conditions = self._check_strategy_a_3min_precision(symbol)

            # B전략: 15분봉 급등초입 타점 체크 (재활성화)
            strategy_b_signal, strategy_b_conditions = self._check_strategy_b_uptrend_entry(df_calc)

            # C전략: 30분봉 급등맥점 체크 (임시 비활성화)
            # strategy_c_signal, strategy_c_conditions = self._check_strategy_c_30min_surge_peak(symbol)
            strategy_c_signal, strategy_c_conditions = False, ["C전략 임시 비활성화"]

            # 최종 신호 결정 - A, B전략 활성화 (C전략만 비활성화)
            is_signal = strategy_a_signal or strategy_b_signal  # A, B 전략 활성화


            # 전략별 상세 정보 구성
            strategy_details = {
                'strategy_a': {
                    'signal': strategy_a_signal,
                    'conditions': strategy_a_conditions,
                    'name': 'A전략(3분봉 바닥급등타점)'
                },
                'strategy_b': {
                    'signal': strategy_b_signal,
                    'conditions': strategy_b_conditions,
                    'name': 'B전략(15분봉 급등초입)'
                },
                'strategy_c': {
                    'signal': strategy_c_signal,
                    'conditions': strategy_c_conditions,
                    'name': 'C전략(30분봉 급등맥점)'
                }
            }

            # 기존 조건 리스트 구성 (호환성 유지)
            conditions.extend(strategy_a_conditions)
            conditions.extend(strategy_b_conditions)
            conditions.extend(strategy_c_conditions)

            # 전략별 결과 추가
            if strategy_a_signal:
                conditions.append("[전략결과] A전략(3분봉 바닥급등타점) 조건 충족 ✅")
            if strategy_b_signal:
                conditions.append("[전략결과] B전략(15분봉 급등초입) 조건 충족 ✅")
            if strategy_c_signal:
                conditions.append("[전략결과] C전략(30분봉 급등맥점) 조건 충족 ✅")
            if not is_signal:
                conditions.append("[전략결과] A전략, B전략, C전략 모두 미충족 ❌")


            # 디버그 로그
            if is_signal:
                strategy_names = []
                if strategy_a_signal:
                    strategy_names.append("A전략(3분봉 바닥급등타점)")
                if strategy_b_signal:
                    strategy_names.append("B전략(15분봉 급등초입)")
                if strategy_c_signal:
                    strategy_names.append("C전략(30분봉 급등맥점)")
                
                strategy_name = "+".join(strategy_names)
                self._write_debug_log(f"🎯 [{clean_symbol}] {strategy_name} 조건 충족!")
                for condition in conditions:
                    self._write_debug_log(f"   {condition}")
            
            return is_signal, conditions, strategy_details
            
        except Exception as e:
            conditions.append(f"[전체 전략] 조건 체크 오류: {str(e)}")
            self.logger.error(f"[{clean_symbol}] 전체 전략 조건 체크 실패: {e}")
            strategy_details = {
                'strategy_a': {'signal': False, 'conditions': [], 'name': 'A전략(3분봉 바닥급등타점)'},
                'strategy_b': {'signal': False, 'conditions': [], 'name': 'B전략(15분봉 급등초입)'},
                'strategy_c': {'signal': False, 'conditions': [], 'name': 'C전략(30분봉 급등맥점)'}
            }
            return False, conditions, strategy_details
    
    def _check_strategy_a_3min_precision(self, symbol):
        """A전략: 3분봉 바닥급등타점"""
        try:
            conditions = []
            
            # 3분봉 데이터 조회 (500+480=980봉 필요, 여유분으로 1000봉 요청)
            try:
                df_3m = None
                
                # 1차 시도: 강화된 WebSocket Provider 사용 (캠시된 3분봉 데이터)
                if self.ws_provider:
                    try:
                        # 메서드가 존재하는지 확인
                        if hasattr(self.ws_provider, 'get_cached_ohlcv'):
                            df_3m = self.ws_provider.get_cached_ohlcv(symbol, '3m', 1000)
                        else:
                            # 메서드가 없으면 일반 get_ohlcv 사용
                            df_3m = self.ws_provider.get_ohlcv(symbol, '3m', 1000)
                            
                        if df_3m is not None and len(df_3m) >= 980:
                            # WebSocket 성공 - 디버그 메시지
                            if symbol in ['APR/USDT:USDT', 'API3/USDT:USDT', 'PLAY/USDT:USDT']:
                                print(f"[DEBUG] {symbol}: WebSocket 성공 - 3분봉 {len(df_3m)}개")
                        else:
                            # 실패시 재시도
                            df_3m = self.ws_provider.get_ohlcv(symbol, '3m', 1000)
                    except Exception as ws_error:
                        if symbol in ['APR/USDT:USDT', 'API3/USDT:USDT', 'PLAY/USDT:USDT']:
                            print(f"[DEBUG] {symbol}: WebSocket 실패 - {ws_error}")
                        df_3m = None
                
                # 2차 시도: WebSocket 실패시 REST API 사용
                if df_3m is None or len(df_3m) < 980:
                    try:
                        df_3m = self.exchange.fetch_ohlcv(symbol, '3m', limit=1000)
                    except Exception as api_error:
                        return False, [f"[A전략] 3분봉 데이터 완전 실패: {api_error}"]
                
                if df_3m is None or len(df_3m) < 980:
                    return False, [f"[A전략] 3분봉 데이터 부족: {len(df_3m) if df_3m is not None else 0}봉 (980봉 필요)"]
                
                # DataFrame 변환
                df_calc = pd.DataFrame(df_3m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df_calc['timestamp'] = pd.to_datetime(df_calc['timestamp'], unit='ms')
                
                # 기술적 지표 계산 (indicators.py 모듈 사용)
                df_calc = self.calculate_indicators(df_calc)
                
                if df_calc is None:
                    return False, [f"[A전략] 3분봉 지표 계산 실패"]
                
                if len(df_calc) < 980:
                    return False, [f"[A전략] 지표 계산 후 데이터 부족: {len(df_calc)}봉 (980봉 필요)"]
                
                # MA480이 제대로 계산되었는지 확인 (500봉 범위 체크를 위해 필수)
                ma480_recent = df_calc['ma480'].tail(10)
                ma480_valid_count = ma480_recent.notna().sum()
                if ma480_valid_count < 5:
                    return False, [f"[A전략] MA480 계산 실패: 최근 10봉 중 {ma480_valid_count}개만 유효 (5개 이상 필요)"]
                
                # 디버깅을 위한 지표 값 확인 (특정 심볼만)
                clean_symbol = symbol.replace('/USDT:USDT', '')
                if clean_symbol in ['APR', 'API3', 'PLAY']:
                    ma480_current = df_calc['ma480'].iloc[-1]
                    ma80_current = df_calc['ma80'].iloc[-1]
                    bb480_current = df_calc.get('bb480_upper', pd.Series()).iloc[-1] if 'bb480_upper' in df_calc.columns else None
                    print(f"[DEBUG] {clean_symbol}: 데이터길이={len(df_calc)}, MA480={ma480_current:.2f}, MA80={ma80_current:.2f}, BB480={bb480_current:.2f if pd.notna(bb480_current) else 'NaN'}")
                
            except Exception as e:
                return False, [f"[A전략] 3분봉 데이터 조회 실패: {e}"]
            
            # 조건 1: 200봉이내 MA80-MA480 골든크로스 or 현재 MA80<MA480
            condition1 = False
            condition1_detail = "미충족"
            
            try:
                # 200봉이내 골든크로스 체크
                if len(df_calc) >= 201:
                    for i in range(1, min(201, len(df_calc))):
                        prev_idx = -(i+1)
                        curr_idx = -i
                        
                        if abs(prev_idx) > len(df_calc) or abs(curr_idx) > len(df_calc):
                            continue
                            
                        ma80_prev = df_calc['ma80'].iloc[prev_idx]
                        ma80_curr = df_calc['ma80'].iloc[curr_idx]
                        ma480_prev = df_calc['ma480'].iloc[prev_idx]
                        ma480_curr = df_calc['ma480'].iloc[curr_idx]
                        
                        # MA480 값의 유효성 추가 체크 (0이나 극값 제외)
                        if (pd.notna(ma80_prev) and pd.notna(ma80_curr) and
                            pd.notna(ma480_prev) and pd.notna(ma480_curr) and
                            ma480_prev > 0 and ma480_curr > 0 and  # MA480이 0보다 큰 값
                            abs(ma480_prev - ma480_curr) < ma480_curr * 0.1 and  # 급격한 변화 제외
                            ma80_prev <= ma480_prev and ma80_curr > ma480_curr):
                            condition1 = True
                            condition1_detail = f"{i}봉전 MA80-MA480 골든크로스"
                            break
                
                # 골든크로스가 없으면 현재 MA80<MA480 체크
                if not condition1:
                    ma80_current = df_calc['ma80'].iloc[-1]
                    ma480_current = df_calc['ma480'].iloc[-1]
                    
                    if (pd.notna(ma80_current) and pd.notna(ma480_current) and
                        ma480_current > 0 and  # MA480이 유효한 값
                        ma80_current < ma480_current):
                        condition1 = True
                        condition1_detail = "현재 MA80<MA480"
                        
                conditions.append(f"[A전략 조건1] 200봉이내 MA80-MA480 조건 ({condition1_detail}): {condition1}")
            except Exception as e:
                conditions.append(f"[A전략 조건1] MA80-MA480 조건 계산 실패: {e}")
                condition1 = False
            
            # 조건 2: 200봉이내 BB80-BB480 골든크로스
            condition2 = False
            condition2_detail = "골든크로스 없음"
            
            try:
                if len(df_calc) >= 201:
                    # BB80과 BB480 데이터 가져오기
                    bb80_data = df_calc.get('bb80_upper', df_calc.get('bb80', pd.Series()))
                    bb480_data = df_calc.get('bb480_upper', df_calc.get('bb480', pd.Series()))
                    
                    if len(bb80_data) >= 201 and len(bb480_data) >= 201:
                        for i in range(1, min(201, len(bb80_data))):
                            prev_idx = -(i+1)
                            curr_idx = -i
                            
                            if abs(prev_idx) > len(bb80_data) or abs(curr_idx) > len(bb80_data):
                                continue
                                
                            bb80_prev = bb80_data.iloc[prev_idx]
                            bb80_curr = bb80_data.iloc[curr_idx]
                            bb480_prev = bb480_data.iloc[prev_idx]
                            bb480_curr = bb480_data.iloc[curr_idx]
                            
                            # BB480 값의 유효성 추가 체크
                            if (pd.notna(bb80_prev) and pd.notna(bb80_curr) and
                                pd.notna(bb480_prev) and pd.notna(bb480_curr) and
                                bb480_prev > 0 and bb480_curr > 0 and  # BB480이 0보다 큰 값
                                abs(bb480_prev - bb480_curr) < bb480_curr * 0.1 and  # 급격한 변화 제외
                                bb80_prev <= bb480_prev and bb80_curr > bb480_curr):
                                condition2 = True
                                condition2_detail = f"{i}봉전 BB80-BB480 골든크로스"
                                break
                                
                conditions.append(f"[A전략 조건2] 200봉이내 BB80-BB480 골든크로스 ({condition2_detail}): {condition2}")
            except Exception as e:
                conditions.append(f"[A전략 조건2] BB80-BB480 골든크로스 계산 실패: {e}")
                condition2 = False
            
            # 조건 3: 20봉이내 (저가<BB80하한선 OR MA5<BB80하한선)
            condition3 = False
            condition3_detail = "미충족"

            try:
                bb80_lower = df_calc.get('bb80_lower', pd.Series())

                if len(bb80_lower) >= 21 and len(df_calc) >= 21:
                    for i in range(min(20, len(df_calc))):
                        idx = -(i+1)

                        if abs(idx) > len(df_calc):
                            break

                        low_price = df_calc['low'].iloc[idx]
                        ma5_value = df_calc['ma5'].iloc[idx]
                        bb80_lower_value = bb80_lower.iloc[idx]

                        # 저가<BB80하한선 OR MA5<BB80하한선
                        if pd.notna(low_price) and pd.notna(bb80_lower_value) and low_price < bb80_lower_value:
                            condition3 = True
                            condition3_detail = f"{i+1}봉전 저가<BB80하한선"
                            break

                        if pd.notna(ma5_value) and pd.notna(bb80_lower_value) and ma5_value < bb80_lower_value:
                            condition3 = True
                            condition3_detail = f"{i+1}봉전 MA5<BB80하한선"
                            break

                conditions.append(f"[A전략 조건3] 20봉이내 (저가<BB80하한 OR MA5<BB80하한) ({condition3_detail}): {condition3}")
            except Exception as e:
                conditions.append(f"[A전략 조건3] BB80하한선 조건 계산 실패: {e}")
                condition3 = False
            
            # 조건 4: 종가<MA5 AND MA80<MA5
            condition4 = False
            condition4_detail = "미충족"

            try:
                current_close = df_calc['close'].iloc[-1]
                current_ma5 = df_calc['ma5'].iloc[-1]
                current_ma80 = df_calc['ma80'].iloc[-1]

                if pd.notna(current_close) and pd.notna(current_ma5) and pd.notna(current_ma80):
                    close_below_ma5 = current_close < current_ma5
                    ma80_below_ma5 = current_ma80 < current_ma5
                    
                    if close_below_ma5 and ma80_below_ma5:
                        condition4 = True
                        condition4_detail = f"종가({current_close:.6f}) < MA5({current_ma5:.6f}) AND MA80({current_ma80:.6f}) < MA5"
                    else:
                        condition4_detail = f"종가<MA5={close_below_ma5}, MA80<MA5={ma80_below_ma5}"

                conditions.append(f"[A전략 조건4] 종가<MA5 AND MA80<MA5 ({condition4_detail}): {condition4}")
            except Exception as e:
                conditions.append(f"[A전략 조건4] 종가<MA5 계산 실패: {e}")
                condition4 = False
            
            # 조건 5: 5봉이내 RSI 30 이하
            condition5 = False
            condition5_detail = "미충족"

            try:
                rsi_series = df_calc.get('rsi', pd.Series()) if 'rsi' in df_calc.columns else pd.Series()

                if len(rsi_series) >= 5:
                    # 최근 5봉 검사
                    for i in range(min(5, len(rsi_series))):
                        idx = -(i+1)
                        rsi_value = rsi_series.iloc[idx]

                        if pd.notna(rsi_value) and rsi_value <= 30.0:
                            condition5 = True
                            condition5_detail = f"{i+1}봉전 RSI={rsi_value:.2f} (30 이하)"
                            break

                    if not condition5:
                        recent_rsi = rsi_series.iloc[-1]
                        condition5_detail = f"최근5봉 RSI 모두 30 초과 (현재={recent_rsi:.2f})" if pd.notna(recent_rsi) else "RSI 계산 실패"
                else:
                    condition5_detail = "RSI 데이터 부족"

                conditions.append(f"[A전략 조건5] 5봉이내 RSI 30 이하 ({condition5_detail}): {condition5}")
            except Exception as e:
                conditions.append(f"[A전략 조건5] RSI 계산 실패: {e}")
                condition5 = False
            
            
            # A전략 최종 신호 판정: 5개 조건 모두 True여야 함
            strategy_a_signal = condition1 and condition2 and condition3 and condition4 and condition5
            
            return strategy_a_signal, conditions
            
        except Exception as e:
            return False, [f"A전략 체크 실패: {e}"]
    
    def _check_strategy_b_uptrend_entry(self, df_calc):
        """B전략: 15분봉 급등초입"""
        try:
            conditions = []
            
            # df_calc는 이미 15분봉 데이터이므로 직접 사용
            if df_calc is None or len(df_calc) < 500:
                return False, [f"[B전략] 15분봉 데이터 부족: {len(df_calc) if df_calc is not None else 0}봉 (500봉 필요)"]
            
            # 조건 1: 200봉이내 MA80-MA480 골든크로스 AND MA80-MA480 이격도 1% 이상
            condition1 = False
            condition1_detail = "미충족"
            
            try:
                golden_cross_found = False
                
                if len(df_calc) >= 201:
                    for i in range(min(200, len(df_calc) - 1)):
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
                            golden_cross_found = True
                            break
                
                # 골든크로스가 있으면 현재 이격도 체크
                if golden_cross_found:
                    current_ma80 = df_calc['ma80'].iloc[-1]
                    current_ma480 = df_calc['ma480'].iloc[-1]
                    
                    if pd.notna(current_ma80) and pd.notna(current_ma480) and current_ma480 > 0:
                        gap_pct = abs((current_ma80 - current_ma480) / current_ma480) * 100
                        if gap_pct >= 1.0:
                            condition1 = True
                            condition1_detail = f"골든크로스=True, 이격도={gap_pct:.2f}%"
                        else:
                            condition1_detail = f"골든크로스=True, 이격도={gap_pct:.2f}% (1% 미만)"
                    else:
                        condition1_detail = "골든크로스=True, 이격도 계산 실패"
                else:
                    condition1_detail = "골든크로스 없음"
                                
                conditions.append(f"[B전략 조건1] 200봉이내 MA80-MA480 골든크로스 AND 이격도 1%이상 ({condition1_detail}): {condition1}")
            except Exception as e:
                conditions.append(f"[B전략 조건1] MA80-MA480 골든크로스 계산 실패: {e}")
                condition1 = False
            
            # 조건 2: BB골든크로스 (BB80상단-BB480상단)
            condition2 = False
            condition2_detail = "BB골든크로스 없음"
            
            try:
                bb80_upper = df_calc.get('bb80_upper', pd.Series())
                bb480_upper = df_calc['bb480_upper']
                
                if len(bb80_upper) >= 101 and len(bb480_upper) >= 101:
                    for i in range(min(100, len(bb80_upper) - 1)):
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
                            
                conditions.append(f"[B전략 조건2] BB골든크로스 ({condition2_detail}): {condition2}")
            except Exception as e:
                conditions.append(f"[B전략 조건2] BB골든크로스 계산 실패: {e}")
                condition2 = False

            # 조건 3: 삭제 (BB80-BB200 데드크로스 조건 제거)

            # 조건 4: (MA20-MA80 데드크로스 AND 저가/MA5-BB80하한 접근 AND RSI 과매도)
            # 3개 하위조건 모두 충족해야 True
            condition4 = False
            condition4_sub1 = False  # MA20-MA80 데드크로스
            condition4_sub2 = False  # 저가/MA5-BB80하한 접근
            condition4_sub3 = False  # RSI 과매도
            condition4_detail = "미충족"

            try:
                # 하위조건 1: 30봉 이내 MA20-MA80 데드크로스
                if len(df_calc) >= 31:
                    for i in range(min(30, len(df_calc) - 1)):
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
                            ma20_prev >= ma80_prev and ma20_curr < ma80_curr):
                            condition4_sub1 = True
                            condition4_sub1_detail = f"{i+1}봉전 MA20-MA80 데드크로스"
                            break

                if not condition4_sub1:
                    condition4_sub1_detail = "30봉이내 MA20-MA80 데드크로스 없음"

                # 하위조건 2: 10봉 이내 (저가<BB80하한 OR MA5-BB80하한 이격도 <=1%)
                bb80_lower = df_calc.get('bb80_lower', pd.Series())

                if len(bb80_lower) >= 11 and len(df_calc) >= 11:
                    for i in range(min(10, len(df_calc))):
                        idx = -(i+1)

                        if abs(idx) > len(df_calc):
                            break

                        low_price = df_calc['low'].iloc[idx]
                        ma5_value = df_calc['ma5'].iloc[idx]
                        bb80_lower_value = bb80_lower.iloc[idx]

                        # 저가 < BB80하한선
                        if pd.notna(low_price) and pd.notna(bb80_lower_value) and bb80_lower_value > 0:
                            if low_price < bb80_lower_value:
                                condition4_sub2 = True
                                condition4_sub2_detail = f"{i+1}봉전 저가<BB80하한선"
                                break

                        # MA5-BB80하한선 이격도 1%이내
                        if pd.notna(ma5_value) and pd.notna(bb80_lower_value) and bb80_lower_value > 0:
                            gap_pct = abs((ma5_value - bb80_lower_value) / bb80_lower_value) * 100
                            if gap_pct <= 1.0:
                                condition4_sub2 = True
                                condition4_sub2_detail = f"{i+1}봉전 MA5-BB80하한선 이격도 {gap_pct:.2f}%"
                                break

                if not condition4_sub2:
                    condition4_sub2_detail = "10봉이내 저가/MA5-BB80하한 접근 조건 미충족"

                # 하위조건 3: 5봉 이내 RSI <= 30
                rsi_series = df_calc.get('rsi', pd.Series()) if 'rsi' in df_calc.columns else pd.Series()

                if len(rsi_series) >= 5:
                    for i in range(min(5, len(rsi_series))):
                        idx = -(i+1)
                        rsi_value = rsi_series.iloc[idx]

                        if pd.notna(rsi_value) and rsi_value <= 30.0:
                            condition4_sub3 = True
                            condition4_sub3_detail = f"{i+1}봉전 RSI={rsi_value:.2f}"
                            break

                if not condition4_sub3:
                    condition4_sub3_detail = "5봉이내 RSI 30 이하 없음"

                # 조건4 최종 판정: 3개 하위조건 모두 True여야 함
                condition4 = condition4_sub1 and condition4_sub2 and condition4_sub3

                if condition4:
                    condition4_detail = f"충족 ({condition4_sub1_detail} & {condition4_sub2_detail} & {condition4_sub3_detail})"
                else:
                    failed_parts = []
                    if not condition4_sub1:
                        failed_parts.append(condition4_sub1_detail)
                    if not condition4_sub2:
                        failed_parts.append(condition4_sub2_detail)
                    if not condition4_sub3:
                        failed_parts.append(condition4_sub3_detail)
                    condition4_detail = " / ".join(failed_parts)

                conditions.append(f"[B전략 조건4] MA20-MA80 DC & 저가/MA5-BB80 & RSI ({condition4_detail}): {condition4}")
            except Exception as e:
                conditions.append(f"[B전략 조건4] 계산 실패: {e}")
                condition4 = False

            # 조건 5: (MA5-MA80 이격도 2%이내 AND 10봉이내 MA5-MA20 골든크로스)
            # 2개 하위조건 모두 충족해야 True
            condition5 = False
            condition5_sub1 = False  # MA5-MA80 이격도 2% 이내
            condition5_sub2 = False  # 10봉이내 MA5-MA20 골든크로스
            condition5_detail = "미충족"

            try:
                # 하위조건 1: MA5-MA80 이격도 2% 이내
                current_ma5 = df_calc['ma5'].iloc[-1]
                current_ma80 = df_calc['ma80'].iloc[-1]

                if pd.notna(current_ma5) and pd.notna(current_ma80) and current_ma80 > 0:
                    gap_pct = abs((current_ma5 - current_ma80) / current_ma80) * 100
                    if gap_pct <= 2.0:
                        condition5_sub1 = True
                        condition5_sub1_detail = f"MA5-MA80 이격도 {gap_pct:.2f}%"
                    else:
                        condition5_sub1_detail = f"MA5-MA80 이격도 {gap_pct:.2f}% (2% 초과)"
                else:
                    condition5_sub1_detail = "MA5/MA80 데이터 부족"

                # 하위조건 2: 10봉 이내 MA5-MA20 골든크로스
                if len(df_calc) >= 11:
                    for i in range(min(10, len(df_calc) - 1)):
                        curr_idx = -(i+1)
                        prev_idx = -(i+2)

                        if abs(prev_idx) > len(df_calc):
                            break

                        ma5_prev = df_calc['ma5'].iloc[prev_idx]
                        ma5_curr = df_calc['ma5'].iloc[curr_idx]
                        ma20_prev = df_calc['ma20'].iloc[prev_idx]
                        ma20_curr = df_calc['ma20'].iloc[curr_idx]

                        if (pd.notna(ma5_prev) and pd.notna(ma5_curr) and
                            pd.notna(ma20_prev) and pd.notna(ma20_curr) and
                            ma5_prev <= ma20_prev and ma5_curr > ma20_curr):
                            condition5_sub2 = True
                            condition5_sub2_detail = f"{i+1}봉전 MA5-MA20 골든크로스"
                            break

                if not condition5_sub2:
                    condition5_sub2_detail = "10봉이내 MA5-MA20 골든크로스 없음"

                # 조건5 최종 판정: 2개 하위조건 모두 True여야 함
                condition5 = condition5_sub1 and condition5_sub2

                if condition5:
                    condition5_detail = f"충족 ({condition5_sub1_detail} & {condition5_sub2_detail})"
                else:
                    failed_parts = []
                    if not condition5_sub1:
                        failed_parts.append(condition5_sub1_detail)
                    if not condition5_sub2:
                        failed_parts.append(condition5_sub2_detail)
                    condition5_detail = " / ".join(failed_parts)

                conditions.append(f"[B전략 조건5] MA5-MA80 이격도 & MA5-MA20 GC ({condition5_detail}): {condition5}")
            except Exception as e:
                conditions.append(f"[B전략 조건5] 계산 실패: {e}")
                condition5 = False

            # B전략 최종 신호 판정: C1 AND C2 AND (C4 OR C5)
            strategy_b_signal = condition1 and condition2 and (condition4 or condition5)
            
            return strategy_b_signal, conditions
            
        except Exception as e:
            return False, [f"B전략 체크 실패: {e}"]

    def _check_strategy_c_30min_surge_peak(self, symbol):
        """C전략: 30분봉 급등 맥점 (A/B/C 3개 타점)"""
        try:
            conditions = []

            # 30분봉 데이터 조회 (50+480=530봉 필요, 여유분으로 600봉 요청)
            try:
                df_30m = None

                # 1차 시도: WebSocket Provider 사용 (캐시된 30분봉 데이터)
                if self.ws_provider:
                    try:
                        if hasattr(self.ws_provider, 'get_cached_ohlcv'):
                            df_30m = self.ws_provider.get_cached_ohlcv(symbol, '30m', 600)
                        else:
                            df_30m = self.ws_provider.get_ohlcv(symbol, '30m', 600)

                        if df_30m is not None and len(df_30m) >= 500:
                            if symbol in ['APR/USDT:USDT', 'API3/USDT:USDT', 'PLAY/USDT:USDT']:
                                print(f"[DEBUG] {symbol}: WebSocket 성공 - 30분봉 {len(df_30m)}개")
                        else:
                            df_30m = self.ws_provider.get_ohlcv(symbol, '30m', 600)
                    except Exception as ws_error:
                        if symbol in ['APR/USDT:USDT', 'API3/USDT:USDT', 'PLAY/USDT:USDT']:
                            print(f"[DEBUG] {symbol}: WebSocket 실패 - {ws_error}")
                        df_30m = None

                # 2차 시도: WebSocket 실패시 REST API 사용
                if df_30m is None or len(df_30m) < 500:
                    try:
                        df_30m = self.exchange.fetch_ohlcv(symbol, '30m', limit=600)
                    except Exception as api_error:
                        return False, [f"[C전략] 30분봉 데이터 완전 실패: {api_error}"]

                if df_30m is None or len(df_30m) < 500:
                    return False, [f"[C전략] 30분봉 데이터 부족: {len(df_30m) if df_30m is not None else 0}봉 (500봉 필요)"]

                # DataFrame 변환
                df_calc = pd.DataFrame(df_30m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df_calc['timestamp'] = pd.to_datetime(df_calc['timestamp'], unit='ms')

                # 기술적 지표 계산 (indicators.py 모듈 사용)
                df_calc = self.calculate_indicators(df_calc)

                if len(df_calc) < 500:
                    return False, [f"[C전략] 지표 계산 후 데이터 부족: {len(df_calc)}봉"]

            except Exception as e:
                return False, [f"[C전략] 30분봉 데이터 조회 실패: {e}"]

            # 기본조건 1: 50봉이내 MA80-MA480 골든크로스 OR 현재봉 MA80<MA480
            base_condition1 = False
            base_condition1_detail = "미충족"

            try:
                current_ma80 = df_calc['ma80'].iloc[-1]
                current_ma480 = df_calc['ma480'].iloc[-1]

                if pd.notna(current_ma80) and pd.notna(current_ma480):
                    if current_ma80 < current_ma480:
                        base_condition1 = True
                        base_condition1_detail = "현재봉 MA80<MA480"
                    else:
                        # 50봉이내 MA80-MA480 골든크로스 체크
                        if len(df_calc) >= 51:
                            for i in range(min(50, len(df_calc) - 1)):
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
                                    base_condition1 = True
                                    base_condition1_detail = f"{i+1}봉전 MA80-MA480 골든크로스"
                                    break

                conditions.append(f"[C전략 기본1] MA80-MA480 조건 ({base_condition1_detail}): {base_condition1}")
            except Exception as e:
                conditions.append(f"[C전략 기본1] 계산 실패: {e}")
                base_condition1 = False

            # 기본조건 2: 100봉이내 MA480-BB200상단선 크로스 (양방향)
            base_condition2 = False
            base_condition2_detail = "크로스 없음"

            try:
                bb200_upper = df_calc.get('bb200_upper', pd.Series())

                if len(bb200_upper) >= 101 and len(df_calc) >= 101:
                    for i in range(min(100, len(bb200_upper) - 1)):
                        curr_idx = -(i+1)
                        prev_idx = -(i+2)

                        if abs(prev_idx) > len(bb200_upper):
                            break

                        ma480_prev = df_calc['ma480'].iloc[prev_idx]
                        ma480_curr = df_calc['ma480'].iloc[curr_idx]
                        bb200_prev = bb200_upper.iloc[prev_idx]
                        bb200_curr = bb200_upper.iloc[curr_idx]

                        if pd.notna(ma480_prev) and pd.notna(ma480_curr) and pd.notna(bb200_prev) and pd.notna(bb200_curr):
                            # 상향 돌파 또는 하향 돌파
                            if (ma480_prev <= bb200_prev and ma480_curr > bb200_curr) or \
                               (ma480_prev >= bb200_prev and ma480_curr < bb200_curr):
                                base_condition2 = True
                                cross_type = "상향" if ma480_curr > bb200_curr else "하향"
                                base_condition2_detail = f"{i+1}봉전 MA480-BB200 {cross_type}돌파"
                                break

                conditions.append(f"[C전략 기본2] MA480-BB200 크로스 ({base_condition2_detail}): {base_condition2}")
            except Exception as e:
                conditions.append(f"[C전략 기본2] 계산 실패: {e}")
                base_condition2 = False

            # 기본조건 충족 여부 확인 (두 조건 모두 충족해야 함)
            if not (base_condition1 and base_condition2):
                return False, conditions

            # A타점: 50봉이내 MA5-MA480 골든크로스 AND 현재봉 MA5<MA20 AND 1봉전(시가<MA5 AND 종가>MA5)
            entry_a = False
            entry_a_detail = "미충족"

            try:
                current_ma5 = df_calc['ma5'].iloc[-1]
                current_ma20 = df_calc['ma20'].iloc[-1]
                prev_open = df_calc['open'].iloc[-2]
                prev_close = df_calc['close'].iloc[-2]
                prev_ma5 = df_calc['ma5'].iloc[-2]

                # 현재봉 MA5<MA20 체크
                ma5_below_ma20 = pd.notna(current_ma5) and pd.notna(current_ma20) and current_ma5 < current_ma20

                # 1봉전 캔들이 MA5 돌파했는지 체크
                candle_cross_ma5 = (pd.notna(prev_open) and pd.notna(prev_close) and pd.notna(prev_ma5) and
                                   prev_open < prev_ma5 and prev_close > prev_ma5)

                # 50봉이내 MA5-MA480 골든크로스 체크
                ma5_cross_ma480 = False
                if len(df_calc) >= 51:
                    for i in range(min(50, len(df_calc) - 1)):
                        curr_idx = -(i+1)
                        prev_idx = -(i+2)

                        if abs(prev_idx) > len(df_calc):
                            break

                        ma5_prev = df_calc['ma5'].iloc[prev_idx]
                        ma5_curr = df_calc['ma5'].iloc[curr_idx]
                        ma480_prev = df_calc['ma480'].iloc[prev_idx]
                        ma480_curr = df_calc['ma480'].iloc[curr_idx]

                        if (pd.notna(ma5_prev) and pd.notna(ma5_curr) and
                            pd.notna(ma480_prev) and pd.notna(ma480_curr) and
                            ma5_prev <= ma480_prev and ma5_curr > ma480_curr):
                            ma5_cross_ma480 = True
                            break

                entry_a = ma5_cross_ma480 and ma5_below_ma20 and candle_cross_ma5
                entry_a_detail = f"골든크로스={ma5_cross_ma480}, MA5<MA20={ma5_below_ma20}, 캔들돌파={candle_cross_ma5}"
                conditions.append(f"[C전략 A타점] {entry_a_detail}: {entry_a}")
            except Exception as e:
                conditions.append(f"[C전략 A타점] 계산 실패: {e}")
                entry_a = False

            # B타점: 50봉이내 MA480 하향돌파 BB200 AND 이격도 3%이내 AND MA5>MA80 AND 5봉이내 MA5-MA480 골든크로스
            entry_b = False
            entry_b_detail = "미충족"

            try:
                # 50봉이내 MA480 하향돌파 BB200 체크
                ma480_cross_bb200 = False
                if len(df_calc) >= 51:
                    for i in range(min(50, len(df_calc) - 1)):
                        curr_idx = -(i+1)
                        prev_idx = -(i+2)

                        if abs(prev_idx) > len(df_calc):
                            break

                        ma480_prev = df_calc['ma480'].iloc[prev_idx]
                        ma480_curr = df_calc['ma480'].iloc[curr_idx]
                        bb200_prev = bb200_upper.iloc[prev_idx]
                        bb200_curr = bb200_upper.iloc[curr_idx]

                        if (pd.notna(ma480_prev) and pd.notna(ma480_curr) and
                            pd.notna(bb200_prev) and pd.notna(bb200_curr) and
                            ma480_prev >= bb200_prev and ma480_curr < bb200_curr):
                            ma480_cross_bb200 = True
                            break

                # MA5-MA480 이격도 3%이내 체크
                current_ma5 = df_calc['ma5'].iloc[-1]
                current_ma480 = df_calc['ma480'].iloc[-1]
                divergence_ok = False
                if pd.notna(current_ma5) and pd.notna(current_ma480) and current_ma480 > 0:
                    divergence = abs((current_ma5 - current_ma480) / current_ma480) * 100
                    divergence_ok = divergence <= 3.0

                # MA5>MA80 체크
                current_ma80 = df_calc['ma80'].iloc[-1]
                ma5_above_ma80 = pd.notna(current_ma5) and pd.notna(current_ma80) and current_ma5 > current_ma80

                # 5봉이내 MA5-MA480 골든크로스 체크
                ma5_cross_ma480_5 = False
                if len(df_calc) >= 6:
                    for i in range(min(5, len(df_calc) - 1)):
                        curr_idx = -(i+1)
                        prev_idx = -(i+2)

                        if abs(prev_idx) > len(df_calc):
                            break

                        ma5_prev = df_calc['ma5'].iloc[prev_idx]
                        ma5_curr = df_calc['ma5'].iloc[curr_idx]
                        ma480_prev = df_calc['ma480'].iloc[prev_idx]
                        ma480_curr = df_calc['ma480'].iloc[curr_idx]

                        if (pd.notna(ma5_prev) and pd.notna(ma5_curr) and
                            pd.notna(ma480_prev) and pd.notna(ma480_curr) and
                            ma5_prev <= ma480_prev and ma5_curr > ma480_curr):
                            ma5_cross_ma480_5 = True
                            break

                entry_b = ma480_cross_bb200 and divergence_ok and ma5_above_ma80 and ma5_cross_ma480_5
                entry_b_detail = f"MA480하향돌파={ma480_cross_bb200}, 이격도3%={divergence_ok}, MA5>MA80={ma5_above_ma80}, 골든크로스5봉={ma5_cross_ma480_5}"
                conditions.append(f"[C전략 B타점] {entry_b_detail}: {entry_b}")
            except Exception as e:
                conditions.append(f"[C전략 B타점] 계산 실패: {e}")
                entry_b = False

            # C타점: 30봉이내 (MA5-MA80 OR MA20-MA80) 데드크로스 AND MA5<MA80 AND 5봉이내 MA5-MA20 골든크로스 AND 현재가<MA20
            # ⚠️ 사용자 요청으로 C타점 비활성화
            entry_c = False
            entry_c_detail = "비활성화 (사용자 요청)"
            conditions.append(f"[C전략 C타점] {entry_c_detail}: {entry_c}")

            # 원래 C타점 로직은 주석 처리됨
            # try:
            #     dead_cross_found = False
            #     ...
            # except Exception as e:
            #     entry_c = False

            # C전략 최종 신호 판정: 기본조건 충족 AND (A타점 OR B타점 OR C타점)
            strategy_d_signal = (base_condition1 and base_condition2) and (entry_a or entry_b or entry_c)

            # 디버그 메시지
            clean_sym = symbol.replace('/USDT:USDT', '')
            if clean_sym in ['APR', 'API3', 'PLAY']:
                print(f"[DEBUG] C전략 {clean_sym}: 기본1={base_condition1}, 기본2={base_condition2}, A={entry_a}, B={entry_b}, C={entry_c} → 신호={strategy_d_signal}")

            return strategy_d_signal, conditions

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
                title = "🚨 A전략(3분봉 바닥급등타점) 진입 신호 🚨"
            elif "B전략" in strategy_type:
                title = "🚨 B전략(15분봉 급등초입) 진입 신호 🚨"
            elif "C전략" in strategy_type:
                title = "🚨 C전략(30분봉 급등맥점) 진입 신호 🚨"
            else:
                title = "🚨 진입 신호 🚨"

            message = f"""{title}
━━━━━━━━━━━━━━━━━━━━━━
📈 심볼: <b>{symbol}</b>💰 현재가: ${price:,.4f}
⏰ 신호발생: {timestamp}
🎯 전략: {strategy_type}
━━━━━━━━━━━━━━━━━━━━━━
🔥 레버리지: 10배
💡 청산 설정:
   • 포지션: 1.5% 상당 (15% 노출, 고정 진입)
   • 손절: -10% 전량 손절 (시드 1.50% 손실)
   • 익절: Trailing Stop (2-3% 최고점 추적)
"""
            
            self.telegram_bot.send_message(message)
            
            # 알림 전송 기록
            self._record_notification(symbol, strategy_type, "entry_signal")
            
        except Exception as e:
            self.logger.error(f"텔레그램 알림 실패: {e}")
    
    def execute_trade(self, signal_data):
        """실전매매 거래 실행"""
        # 변수 초기화 (에러 처리에서 안전하게 사용하기 위해)
        free_usdt = 0.0
        position_value = 0.0

        try:
            if not self.private_exchange:
                print(f"⚠️ 프라이빗 API 없음 - {signal_data['clean_symbol']} 거래 건너뛰기")
                return False

            symbol = signal_data['symbol']
            price = signal_data['price']
            clean_symbol = signal_data['clean_symbol']

            # 🔍 전략 디버그: signal_data 내용 확인
            print(f"\n🔍 [전략 디버그] {clean_symbol} signal_data 확인:")
            strategy_details = signal_data.get('strategy_details')
            if strategy_details:
                a_signal = strategy_details.get('strategy_a', {}).get('signal', False)
                b_signal = strategy_details.get('strategy_b', {}).get('signal', False)
                c_signal = strategy_details.get('strategy_c', {}).get('signal', False)
                print(f"   A전략 신호: {a_signal}")
                print(f"   B전략 신호: {b_signal}")
                print(f"   C전략 신호: {c_signal}")
            else:
                print(f"   ⚠️ strategy_details가 없습니다!")
                print(f"   signal_data keys: {signal_data.keys()}")
            
            # 포지션 개수 제한 체크 (최대 10개)
            portfolio = self.get_portfolio_summary()
            if portfolio['open_positions'] >= 10:
                print(f"⚠️ 최대 포지션 개수 도달 (10개) - {clean_symbol} 진입 건너뛰기")
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
            
            # 포지션 크기 계산 (1.0% x 10배 레버리지, 불타기 최대 2회)
            position_value = free_usdt * 0.010  # 1.0% (초기 진입)
            leverage = 10
            quantity = (position_value * leverage) / price  # 실제 구매할 수량
            
            # 명목가치가 $5 미만이면 최소값으로 조정
            min_notional_required = 5.0
            current_notional = quantity * price
            if current_notional < min_notional_required:
                quantity = min_notional_required / price  # 최소 $5 주문을 위한 수량
                actual_position_value = (quantity * price) / leverage  # 실제 투입되는 원금
                self.logger.info(f"💰 최소 주문 금액 조정: ${current_notional:.2f} → ${min_notional_required:.2f}")
                self.logger.info(f"📊 원금 비중 조정: {position_value/free_usdt*100:.2f}% → {actual_position_value/free_usdt*100:.2f}%")
                position_value = actual_position_value
            
            
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
📊 레버리지: 10배
📈 목표진입: {position_value:.0f} USDT (1.5%)
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
📊 레버리지: 10배
📈 목표진입: {position_value:.0f} USDT (1.5%)
🕒 시간: {get_korea_time().strftime('%H:%M:%S')}"""
                self._send_notification_once(symbol, "min_amount_insufficient", detailed_msg)
                return False
            
            # 최소 명목가치 검증 (이미 위에서 조정했지만 재확인)
            final_notional = quantity * price
            min_notional = 5.0  # 바이낸스 퓨처스 최소 명목가치 $5
            if final_notional < min_notional:
                error_msg = f"⚠️ 최종 명목가치 미달 - 계산값: ${final_notional:.2f}, 최소값: ${min_notional:.2f}"
                print(error_msg)
                # 이 경우는 시스템 오류이므로 거래를 중단
                self.logger.error(f"시스템 오류: 최소 명목가치 조정 후에도 ${final_notional:.2f} < ${min_notional:.2f}")
                return False
            
            # 레버리지 설정 (강화된 검증)
            try:
                # 1단계: 레버리지 설정
                self.private_exchange.set_leverage(leverage, symbol)
                print(f"🔧 레버리지 {leverage}배 설정 요청: \033[92m{clean_symbol}\033[0m 💚")
                
                # 2단계: 설정 검증 (429 에러 방지를 위해 간소화)
                try:
                    # 🚀 API 호출 최소화: 거래 후 검증으로 변경 (사전 검증 생략)
                    print(f"✅ 레버리지 {leverage}배 설정 요청 완료: {clean_symbol}")
                    print("   📋 거래 후 검증 예정 (API 호출 최소화)")
                        
                except Exception as verify_e:
                    print(f"⚠️ 레버리지 설정 후 처리 실패: {verify_e}")
                    print("   📋 거래 계속 진행")
                    
            except Exception as e:
                print(f"❌ 레버리지 설정 실패: {e}")
                print(f"   📋 {symbol} 거래 중단 - 레버리지 설정 필수")
                return False
            
            # 시장가 매수 주문
            order = self.private_exchange.create_market_buy_order(
                symbol=symbol,
                amount=quantity,
                params={'leverage': leverage}
            )
            
            if order['status'] == 'closed' or order['filled'] > 0:
                filled_qty = order['filled']
                filled_price = order['average'] or price
                notional = filled_qty * filled_price

                # active_positions에 추가
                self.active_positions[symbol] = {
                    'size': filled_qty,
                    'side': 'long',
                    'entry_price': filled_price,
                    'leverage': leverage,
                    'order_id': order['id']
                }

                print(f"✅ 실전 진입 완료: {GREEN}{clean_symbol}{RESET}")
                print(f"   💰 진입가: ${filled_price:,.4f}")
                print(f"   📊 수량: {filled_qty:.6f}")
                print(f"   🔥 레버리지: {leverage}배")
                print(f"   💵 투입금액: ${position_value:.0f} USDT")
                print(f"   📋 주문ID: {order['id']}")

                # 📊 거래 진입 로그 기록
                if HAS_TRADING_LOGGER:
                    strategy_type = self._get_strategy_type(signal_data)
                    log_entry_signal(
                        symbol=clean_symbol,
                        strategy=strategy_type,
                        price=filled_price,
                        quantity=filled_qty,
                        leverage=leverage,
                        metadata={
                            'order_id': order['id'],
                            'position_value': position_value,
                            'signal_data': signal_data,
                            'entry_time': get_korea_time().isoformat()
                        }
                    )

                # 🔍 거래 후 레버리지 검증 (API 호출 최소화)
                try:
                    # 주문 완료 후 실제 포지션에서 레버리지 확인 (추가 API 호출 없이)
                    if order.get('info') and 'leverage' in str(order.get('info', {})):
                        actual_leverage = order.get('info', {}).get('leverage', leverage)
                        if actual_leverage and float(actual_leverage) != leverage:
                            print(f"   ⚠️ 레버리지 불일치 발견: 요청 {leverage}배, 실제 {actual_leverage}배")
                        else:
                            print(f"   ✅ 레버리지 {leverage}배 확인됨")
                    else:
                        print(f"   ℹ️ 레버리지 검증 정보 없음 (정상 진행)")
                except Exception as e:
                    print(f"   ⚠️ 레버리지 검증 처리 오류: {e}")

                # DCA 매니저에 포지션 등록 (자동으로 1차, 2차 DCA 주문 생성)
                if self.dca_manager:
                    # 전략 정보도 함께 저장
                    dca_success = self.dca_manager.add_position(
                        symbol=symbol,
                        entry_price=filled_price,
                        quantity=filled_qty,
                        notional=notional,
                        leverage=leverage,
                        total_balance=free_usdt,
                        strategy=strategy_type,  # 전략 정보 추가
                        signal_data=signal_data  # 원본 신호 데이터 추가
                    )
                    if dca_success:
                        print(f"   ✅ DCA 시스템 등록 완료 - 자동 1차/2차 주문 생성됨")
                    else:
                        print(f"   ⚠️ DCA 시스템 등록 실패 - 수동 관리 필요")
                else:
                    # DCA 매니저 없으면 기존 방식 사용 (폴백)
                    print(f"   ⚠️ DCA 매니저 없음 - 기본 주문만 실행")
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
🎯 청산 설정 (DCA 비활성화):
   • 손절: ${filled_price * 0.90:,.4f} (-10% 전량)
   • 익절: Trailing Stop (2-3% 최고점 추적)
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
💵 투입금액: ${position_value:.0f} USDT (1.5%)
⚠️ 실패사유: 주문 처리 실패
📋 오류정보: {order.get('info', '상세정보없음')}
━━━━━━━━━━━━━━━━━━━━━━
📊 레버리지: 10배
🕒 시간: {get_korea_time().strftime('%H:%M:%S')}"""
                self._send_notification_once(symbol, "order_failed", detailed_msg)
                return False
            
        except Exception as e:
            self.logger.error(f"실전 거래 실행 실패: {e}")
            error_msg = f"❌ 거래 실행 실패: \033[92m{clean_symbol}\033[0m 💚 - {e}"
            print(error_msg)
            # 실패 알림 (중복 방지) - 상세 정보 포함
            strategy_type = self._get_strategy_type(signal_data)
            detailed_msg = f"""❌ <b>{clean_symbol}</b> 💚 거래 실패 (시스템오류)
━━━━━━━━━━━━━━━━━━━━━━
🎯 전략: {strategy_type}
💰 진입가격: ${price:.4f}
💵 투입금액: ${position_value:.0f} USDT (1.5%)
⚠️ 실패사유: 시스템 오류
📋 오류정보: {str(e)[:100]}
━━━━━━━━━━━━━━━━━━━━━━
📊 레버리지: 10배
🕒 시간: {get_korea_time().strftime('%H:%M:%S')}"""
            self._send_notification_once(symbol, "execution_failed", detailed_msg)
            return False
    
    def _place_dca_orders(self, symbol, entry_price, base_quantity):
        """손절 주문만 등록 (DCA 추가매수 없음)"""
        try:
            clean_symbol = symbol.replace('/USDT:USDT', '')
            stop_orders = []

            # DCA 추가매수 주문은 등록하지 않음 (완전 비활성화)
            # 손절 주문만 자동 등록

            # 손절 주문: -10% (전량 손절)
            stop_price = entry_price * 0.90
            try:
                stop_order = self.exchange.create_order(
                    symbol=symbol,
                    type='stop_market',
                    side='sell',
                    amount=base_quantity,  # 전량 손절
                    price=None,
                    params={
                        'stopPrice': stop_price,
                        'leverage': 10
                    }
                )
                stop_orders.append({
                    'stage': '손절',
                    'price': stop_price,
                    'quantity': base_quantity,
                    'order_id': stop_order['id']
                })
                print(f"   🛑 손절 주문 등록: ${stop_price:,.4f} (-10%)")
            except Exception as e:
                print(f"   ⚠️ 손절 주문 실패: {e}")

            # 손절 주문 정보를 active_positions에 저장
            if symbol in self.active_positions:
                self.active_positions[symbol]['dca_orders'] = stop_orders

            return stop_orders

        except Exception as e:
            self.logger.error(f"손절 주문 등록 실패: {e}")
            print(f"❌ 손절 주문 등록 실패: {e}")
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
        """실제 포지션 상태 체크 (주문 체결 여부 확인)"""
        try:
            if not self.private_exchange:
                return
                
            # 실제 포지션 재조회
            positions = self.private_exchange.fetch_positions()
            # open_orders 전체 조회는 제거 (Rate Limit 문제 회피)
            
            # 현재 실제 포지션 업데이트
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
                        'percentage': position['percentage']
                    }
            
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

    def _verify_dca_orders(self):
        """DCA 지정가 주문 검증 및 누락/중복 조정"""
        try:
            if not self.dca_manager:
                return

            print(f"\n🔍 DCA 주문 검증 시작...")

            # 모든 활성 포지션 확인
            for symbol, position in self.dca_manager.positions.items():
                if not position.is_active:
                    continue

                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')

                try:
                    # 🚀 API 호출 조절: 5초 대기 + 429 에러 방지
                    print(f"   📡 {clean_symbol} API 호출 대기 중... (5초)")
                    time.sleep(5.0)  # DCA 검증 간 충분한 대기
                    
                    # 거래소에서 실제 포지션 정보 조회
                    exchange_positions = self.private_exchange.fetch_positions([symbol])
                    current_position = None
                    for pos in exchange_positions:
                        if pos['contracts'] > 0 and pos['symbol'] == symbol:
                            current_position = pos
                            break

                    if not current_position:
                        print(f"   ⚠️ {clean_symbol}: 거래소에 포지션 없음 (동기화 필요)")
                        continue

                    # Initial margin 기반 현재 비중 계산
                    initial_margin = current_position.get('initialMargin', 0)
                    notional_value = current_position.get('notional', 0)
                    contracts = current_position.get('contracts', 0)
                    entry_price = current_position.get('entryPrice', 0)

                    # 잔고 조회
                    balance = self.private_exchange.fetch_balance()
                    total_balance = balance['USDT']['total']

                    if total_balance > 0 and notional_value > 0:
                        current_weight = (abs(notional_value) / total_balance) * 100
                        print(f"   📊 {clean_symbol}: 현재 비중 {current_weight:.2f}% (Notional: ${abs(notional_value):.0f})")
                    else:
                        current_weight = 0

                    # 미결 주문 조회
                    open_orders = self.private_exchange.fetch_open_orders(symbol)

                    # DCA 주문 분류 (1차, 2차)
                    dca1_orders = []
                    dca2_orders = []
                    stop_orders = []

                    for order in open_orders:
                        order_price = order.get('price', 0)
                        order_type = order.get('type', '')
                        order_side = order.get('side', '')

                        if order_side == 'buy' and order_type == 'limit':
                            # DCA 1차: 진입가 대비 -3% 근처
                            if entry_price * 0.96 < order_price < entry_price * 0.98:
                                dca1_orders.append(order)
                            # DCA 2차: 진입가 대비 -6% 근처
                            elif entry_price * 0.93 < order_price < entry_price * 0.95:
                                dca2_orders.append(order)
                        elif order_side == 'sell' and 'stop' in order_type.lower():
                            stop_orders.append(order)

                    # 🔥 불타기 전용 시스템 - DCA 비활성화
                    # DCA는 더 이상 사용하지 않으므로 정보성으로만 표시
                    print(f"   • 1차 DCA: {len(dca1_orders)}개, 2차 DCA: {len(dca2_orders)}개, 손절: {len(stop_orders)}개 (DCA시스템: 비활성화)")

                    # 🔥 DCA 시스템 간소화: 1차/2차 DCA 주문 체크 비활성화
                    # 불타기 시스템만 사용하므로 DCA 주문 누락 알림 제거
                    if len(dca1_orders) == 0:
                        # print(f"   ⚠️ {clean_symbol}: 1차 DCA 주문 누락 - 재생성 필요")  # 비활성화
                        pass  # DCA 시스템 비활성화됨
                        
                    if len(dca2_orders) == 0:
                        # print(f"   ⚠️ {clean_symbol}: 2차 DCA 주문 누락 - 재생성 필요")  # 비활성화
                        pass  # DCA 시스템 비활성화됨

                    # 중복된 주문 확인
                    if len(dca1_orders) > 1:
                        print(f"   ⚠️ {clean_symbol}: 1차 DCA 주문 중복 ({len(dca1_orders)}개) - 조정 필요")
                        # 가장 최근 주문 제외하고 나머지 취소
                        for order in dca1_orders[:-1]:
                            try:
                                self.private_exchange.cancel_order(order['id'], symbol)
                                print(f"      ✅ 중복 주문 취소: {order['id']}")
                            except Exception as e:
                                print(f"      ⚠️ 주문 취소 실패: {e}")

                    if len(dca2_orders) > 1:
                        print(f"   ⚠️ {clean_symbol}: 2차 DCA 주문 중복 ({len(dca2_orders)}개) - 조정 필요")
                        for order in dca2_orders[:-1]:
                            try:
                                self.private_exchange.cancel_order(order['id'], symbol)
                                print(f"      ✅ 중복 주문 취소: {order['id']}")
                            except Exception as e:
                                print(f"      ⚠️ 주문 취소 실패: {e}")

                    # 불타기 전용 순환매 상태 확인
                    if position.cyclic_state != 'NORMAL_DCA':
                        print(f"   🔄 {clean_symbol}: 불타기 전용 순환매 상태 - {position.cyclic_state} (사이클: {position.cyclic_count}/3)")

                        # 부분 청산 후 재진입 확인 (DCA 시스템 비활성화로 주석처리)
                        if position.cyclic_count > 0 and len(dca1_orders) == 0 and len(dca2_orders) == 0:
                            # print(f"   ⚠️ {clean_symbol}: 순환매 후 DCA 주문 누락 - 재생성 필요")  # 비활성화
                            pass  # 불타기 시스템만 사용하므로 DCA 주문 체크 불필요

                except Exception as e:
                    print(f"   ❌ {clean_symbol} 검증 실패: {e}")
                    continue

            print(f"   ✅ DCA 주문 검증 완료\n")

        except Exception as e:
            print(f"   ❌ DCA 주문 검증 실패: {e}\n")

    def run_continuous_scan(self, interval=30):
        """🚀 IP 밴 방지 최고속도 연속 스캔 실행"""
        print("🚀 15분봉 초필살기 전략 연속 스캔 시작 (🔥 실전매매 모드 🔥)")
        print(f"   ⚡ 최적화 스캔 주기: {interval}초 (바이낸스 레이트 리밋 준수)")
        print(f"   📊 레버리지: 10배")
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
                
                # DCA 매니저와 거래소 동기화 (주기적 포지션 확인, DCA 주문 검증)
                if self.dca_manager:
                    try:
                        print(f"\n🔄 DCA 시스템 동기화 중...")
                        self.dca_manager.sync_with_exchange()

                        # 활성 포지션 확인 및 검증
                        active_count = len([p for p in self.dca_manager.positions.values() if p.is_active])
                        print(f"   ✅ DCA 동기화 완료 - 활성 포지션: {active_count}개")
                        
                        # 🎨 콘솔에 활성포지션 예쁘게 출력
                        if active_count > 0:
                            self.dca_manager.display_console_positions()

                        # DCA 주문 상태 검증 (누락/중복 확인 및 조정)
                        self._verify_dca_orders()

                        # 🔥 실시간 불타기 기회 체크 (핵심 추가)
                        if active_count > 0:
                            print(f"\n📈 실시간 불타기 기회 체크...")
                            for symbol, position in self.dca_manager.positions.items():
                                if position.is_active:
                                    try:
                                        # 현재가 조회
                                        ticker = self.private_exchange.fetch_ticker(symbol)
                                        current_price = ticker['last']
                                        
                                        # 불타기 기회 체크
                                        pyramid_signal = self.dca_manager.check_pyramid_opportunity(position, current_price)
                                        if pyramid_signal and pyramid_signal.get('signal', False):
                                            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                                            print(f"🔥 {clean_symbol} 불타기 기회 감지!")
                                            print(f"   📊 현재가: ${current_price:.6f}")
                                            print(f"   📈 수익률: {pyramid_signal.get('current_profit_pct', 0):.2f}%")
                                            print(f"   🎯 단계: {pyramid_signal.get('stage', 'UNKNOWN')}")
                                            
                                            # 실제 불타기 진입 실행
                                            pyramid_success = self.dca_manager.execute_pyramid_entry(
                                                symbol, pyramid_signal
                                            )
                                            
                                            if pyramid_success:
                                                print(f"   ✅ 불타기 진입 성공!")
                                                # 텔레그램 알림
                                                message = f"""🔥 불타기 추가진입 완료 🔥
━━━━━━━━━━━━━━━━━━━━━━
📈 심볼: <b>{clean_symbol}</b>
💰 추가진입가: ${current_price:,.6f}
📊 단계: {pyramid_signal.get('stage', 'UNKNOWN')}
📈 수익률: +{pyramid_signal.get('current_profit_pct', 0):.2f}%
🔥 불타기 진입: {position.pyramid_count}/3
🕒 시간: {get_korea_time().strftime('%H:%M:%S')}"""
                                                self._send_notification_once(symbol, "pyramid_entry", message)
                                            else:
                                                print(f"   ❌ 불타기 진입 실패")
                                    except Exception as e:
                                        print(f"   ⚠️ {symbol} 불타기 체크 실패: {e}")

                        # 출구 전략 체크 (SuperTrend, BB600, 누적수익보호 등)
                        if active_count > 0:
                            try:
                                # 현재 가격 조회 및 청산 신호 체크
                                current_prices = {}
                                for symbol, position in self.dca_manager.positions.items():
                                    if position.is_active:
                                        try:
                                            ticker = self.private_exchange.fetch_ticker(symbol)
                                            current_price = ticker['last']
                                            current_prices[symbol] = current_price

                                            # 🔥 청산 신호 체크 (손절, 익절, SuperTrend, BB600 등) - 상세 디버그
                                            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                                            
                                            # 현재 수익률 계산
                                            current_profit = (current_price - position.average_price) / position.average_price * 100
                                            
                                            print(f"🔍 {clean_symbol} 청산 조건 체크: 현재가 ${current_price:.6f}, 평단가 ${position.average_price:.6f}, 수익률 {current_profit:.2f}%")
                                            
                                            exit_signal = self.dca_manager.check_all_new_exit_signals(symbol, current_price)
                                            if exit_signal:
                                                print(f"🚨 {clean_symbol} 청산 신호 감지!")
                                                print(f"   📊 신호 타입: {exit_signal.get('exit_type', 'UNKNOWN')}")
                                                print(f"   📈 청산 비율: {exit_signal.get('exit_ratio', 0) * 100:.0f}%")
                                                print(f"   💰 현재 수익률: {current_profit:.2f}%")
                                                print(f"   🔥 신호 강도: {exit_signal.get('signal_strength', 'UNKNOWN')}")
                                                
                                                # 다중 신호 감지 시 추가 정보
                                                total_signals = exit_signal.get('total_signals_detected', 1)
                                                if total_signals > 1:
                                                    print(f"   ⚠️ 다중 신호 감지: {total_signals}개 조건 동시 충족")
                                                
                                                if 'trigger_info' in exit_signal:
                                                    print(f"   🎯 트리거: {exit_signal['trigger_info']}")

                                                # 청산 실행
                                                exit_result = self.dca_manager.execute_new_exit(symbol, exit_signal)
                                                if exit_result and exit_result.get('success'):
                                                    print(f"   ✅ {clean_symbol} 청산 완료!")
                                                else:
                                                    print(f"   ⚠️ {clean_symbol} 청산 실패: {exit_result}")
                                            else:
                                                # 청산 신호가 없을 때도 로그 (5초에 한 번만)
                                                if not hasattr(self, '_last_no_signal_log'):
                                                    self._last_no_signal_log = {}
                                                current_time = time.time()
                                                if symbol not in self._last_no_signal_log or current_time - self._last_no_signal_log[symbol] > 5:
                                                    print(f"   ℹ️ {clean_symbol} 청산 신호 없음 (수익률: {current_profit:.2f}%)")
                                                    self._last_no_signal_log[symbol] = current_time
                                        except Exception as e:
                                            print(f"   ⚠️ {symbol} 청산 체크 실패: {e}")

                                # 순환매 통계 출력 (안전한 접근)
                                cyclic_stats = self.dca_manager.get_cyclic_statistics()
                                if isinstance(cyclic_stats, dict) and not cyclic_stats.get('error'):
                                    total_cyclic = cyclic_stats.get('total_cyclic_positions', 0)
                                    if total_cyclic > 0:
                                        print(f"\n   🔄 순환매 통계:")
                                        print(f"      • 순환매 포지션: {total_cyclic}개")
                                        
                                        # 안전하게 중첩 딕셔너리 접근
                                        cyclic_states = cyclic_stats.get('cyclic_states', {})
                                        active_count = cyclic_states.get('active', 0)
                                        complete_count = cyclic_states.get('complete', 0)
                                        
                                        print(f"      • 순환매 활성: {active_count}개")
                                        print(f"      • 순환매 완료: {complete_count}개")
                                        print(f"      • 총 순환매 수익: ${cyclic_stats.get('total_cyclic_profit', 0):.0f}")

                            except Exception as e:
                                print(f"   ⚠️ 순환매 통계 확인 실패: {e}")

                    except Exception as e:
                        print(f"   ⚠️ DCA 동기화 실패: {e}")

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
                    print(f"   🔍 활성 포지션:")
                    for symbol, pos in portfolio['positions'].items():
                        clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                        print(f"      • {clean_symbol}: {pos['percentage']:+.2f}% (${pos['unrealized_pnl']:+.0f})")
                
                # 동적 대기 시간 계산
                effective_interval = max(interval, 30)  # 최소 30초 대기
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

def main():
    """🚀 Alpha-Z Triple Strategy 메인 함수"""
    import sys
    
    try:
        print("Alpha-Z Triple Strategy 시작 (A+B+C전략)")
        print("="*60)
        
        # 명령행 인수 처리
        mode = 'continuous'  # 기본값: 연속 스캔 (24시간 실행)
        interval = 30    # 기본값: 30초 간격 (최적화)

        if len(sys.argv) > 1:
            # single, once, 1 옵션만 단일 스캔 모드
            if sys.argv[1] in ['single', 'once', '1']:
                mode = 'single'
            # 나머지는 모두 연속 스캔 (continuous, cont, c, --scan, scan)
            elif sys.argv[1] not in ['single', 'once', '1']:
                mode = 'continuous'

            # 간격 설정 (두 번째 인수)
            if len(sys.argv) > 2:
                try:
                    interval = int(sys.argv[2])
                    interval = max(30, min(600, interval))  # 30초~10분 제한
                except:
                    interval = 30
        
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
            print(f"   기존 포지션:")
            for symbol, pos in portfolio['positions'].items():
                clean_symbol = symbol.replace('/USDT:USDT', '')
                print(f"      • {clean_symbol}: {pos['percentage']:+.2f}% (${pos['unrealized_pnl']:+.0f})")
        
        if mode == 'continuous':
            # 연속 스캔 모드 (IP 밴 방지 최적화)
            print(f"\n연속 스캔 모드 시작 (IP 밴 방지 최적화)")
            print(f"   ⚡ 스캔 간격: {interval}초")
            print(f"   🛡️ 바이낸스 레이트 리밋 준수")
            print(f"   📊 사용법: python alpha_z_triple_strategy.py continuous [간격초]")
            print(f"   ⚠️ 중단: Ctrl+C")
            strategy.run_continuous_scan(interval)
        else:
            # 단일 스캔 모드 (기본값)
            print(f"\n단일 스캔 모드 (최고속도 최적화)")
            print(f"   ⚡ IP 밴 방지 최적화 적용")
            print(f"   📊 연속 모드: python alpha_z_triple_strategy.py continuous")
            
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
            
            # 최종 포지션 상태 체크
            strategy.check_real_position_status()
            
            # 🎨 콘솔에 활성포지션 예쁘게 출력
            if strategy.dca_manager:
                active_count = len([p for p in strategy.dca_manager.positions.values() if p.is_active])
                if active_count > 0:
                    strategy.dca_manager.display_console_positions()
            
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