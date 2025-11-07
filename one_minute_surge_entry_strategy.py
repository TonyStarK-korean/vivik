# -*- coding: utf-8 -*-
"""
전략C + 전략D 조합 시스템 (OR 조합)
SuperClaude Expert Mode Implementation + 5분봉 SuperTrend(10-3) 진입 시그널

- 전략C: 3분봉 시세 초입 포착 (6개 조건 AND 5분봉 SuperTrend) - ✅ 활성화됨
- 전략D: 5분봉 초입 초강력 타점 (3개 조건 모두 충족 필요) - ✅ 활성화됨
- 기존 시스템 설정 및 DCA 체계 재사용
- 5분봉 SuperTrend(10-3): 트렌드 전환 시그널로 진입 정확도 향상

거래 설정: (현재 2% 진입 상태에 맞춘 조정)
- 레버리지: 10배
- 포지션 크기: 원금 2.0% x 10배 레버리지 (20% 노출)
- 최대 진입 종목: 15종목
- 재진입: 순환매 활성화 (최대 3회 순환매)
- 단계별 손절: 초기 -10%, 1차DCA 후 -7%, 2차DCA 후 -5%
- 종목당 최대 비중: 7.0% (초기 2.0% + DCA 2.5% + 2.5%)
- 최대 원금 사용: 105% (15종목 × 7.0%)
- 최대 손실률: 0.20% (초기), 0.308% (1차DCA), 0.350% (2차DCA)

전략 C: 3분봉 시세 초입 포착 (복합 논리 조건 + SuperTrend 모두 충족 필요) - ✅ 활성화됨:
------------------------------------------------------------------------
조건 1: 200봉이내 BB200상단선(표준편차2)-BB480상단선(표준편차1.5) 골든크로스
조건 2: (100봉이내 MA5-MA20 데드크로스 AND 10봉이내 MA1-MA5 골든크로스) and (ma5<ma20 or ma5-ma20 이격도 2%이내)
최종 논리 구조: 조건1 AND 조건2

AND

5분봉 SuperTrend(10-3) 진입 시그널: 하락 트렌드(-1)에서 상승 트렌드(1)로 전환 (최근 5봉 이내)

OR

전략 D: 5분봉 초입 초강력 타점 (5개 조건 모두 충족 필요) - ✅ 활성화됨:
----------------------------------------------------------------------
1. 15분봉 MA80<MA480
2. 5분봉 SuperTrend(10-3) 진입 시그널
3. 200봉이내 MA80-MA480 골든크로스 OR (MA80<MA480 and MA80-MA480 이격도 5%이내)
4. 700봉이내 (MA480이 5연속 이상 우하향 1회이상 AND BB200상단선이 MA480을 골든크로스)
5. 20봉이내 MA5-MA20 골든크로스

지정가 DCA 시스템: (현재 2% 진입 상태에 맞춘 조정)
- 최초 진입: 2.0% x 10배 = 20% 노출 시장가 매수
- 1차 DCA: -3% 하락가에 2.5% 지정가 주문 (즉시 등록)
- 2차 DCA: -6% 하락가에 2.5% 지정가 주문 (즉시 등록)
- 체결 관리: 매 스캔마다 지정가 주문 체결 상태 확인 및 평단가 자동 업데이트
- 청산: 미체결 지정가 주문 자동 취소 → 체결된 포지션만 시장가 청산

청산원칙 (5가지 청산 방식):
1. SuperTrend 전량청산: 5분봉 SuperTrend(10-3) 청산시그널시 전량청산
2. 본절청산: 수익률별 차등 보호 (3%~5%: 손실전환전, 5%~10%: 절반하락시, 10%+: 절반하락시)
3. 약상승후 급락 리스크 회피: 원금기준 최대수익률 3%이상 → 0.5%이하 손실부근 하락 + 5분봉 5봉이내 SuperTrend(10-2) 청산신호시 전량청산
4. BB600 트레일링 스탑: 3분봉/5분봉/15분봉/30분봉 캔들 고점이 BB600 상단선 돌파시 50% 익절 → 나머지 50%는 트레일링 스탑(5% 하락) 적용
5. DCA 순환매 일부청산: 기존 DCA 시스템 유지
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
    HAS_TELEGRAM_BOT = True
except ImportError:
    print("[INFO] telegram_bot.py 없음 - 텔레그램 알림 비활성화")
    TelegramBot = None
    HAS_TELEGRAM_BOT = False

try:
    from telegram_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    HAS_TELEGRAM_CONFIG = True
except ImportError:
    print("[INFO] telegram_config.py 없음 - 기본 텔레그램 설정 사용")
    TELEGRAM_BOT_TOKEN = None
    TELEGRAM_CHAT_ID = None
    HAS_TELEGRAM_CONFIG = False

from pattern_optimizations import (
    find_golden_cross_vectorized,
    find_dead_cross_vectorized,
    check_high_vs_open_vectorized,
    check_gap_within_threshold_vectorized,
    check_value_comparison_vectorized
)

# Add method alias for backward compatibility
def _find_golden_cross_vectorized_alias(self, df, fast_ma_col, slow_ma_col, recent_n=30):
    """Alias method to support any legacy calls to self.find_golden_cross_vectorized"""
    return find_golden_cross_vectorized(df, fast_ma_col, slow_ma_col, recent_n)

# 개선된 DCA 순환매수 시스템 import 추가
try:
    from improved_dca_position_manager import ImprovedDCAPositionManager
    HAS_DCA_SYSTEM = True
except ImportError:
    print("[ERROR] improved_dca_position_manager.py 없음 - DCA 시스템 비활성화")
    # 기존 시스템 폴백
    try:
        from dca_position_manager import DCAPositionManager as ImprovedDCAPositionManager
        HAS_DCA_SYSTEM = True
        print("[INFO] 기존 DCA 시스템 사용")
    except ImportError:
        ImprovedDCAPositionManager = None
        HAS_DCA_SYSTEM = False

# DCA 주문 복구 시스템 import (선택적)
try:
    from enhanced_dca_recovery_system import EnhancedDCARecoverySystem
    HAS_DCA_RECOVERY = True
except ImportError:
    EnhancedDCARecoverySystem = None
    HAS_DCA_RECOVERY = False

# 거래 내역 동기화 시스템 import (선택적)
try:
    from trade_history_sync import TradeHistorySync
    HAS_TRADE_HISTORY_SYNC = True
except ImportError:
    TradeHistorySync = None
    HAS_TRADE_HISTORY_SYNC = False

# 주문 기록 동기화 시스템 import (선택적)
try:
    from order_history_sync import OrderHistorySync
    HAS_ORDER_HISTORY_SYNC = True
except ImportError:
    OrderHistorySync = None
    HAS_ORDER_HISTORY_SYNC = False

# 전략 조건 상세 설명
STRATEGY_CONDITION_DETAILS = {
    # 전략 C 조건들
    'C1': {
        'name': '조건1',
        'description': 'BB200상단-BB480상단 골든크로스',
        'detail': '200봉이내 볼린저밴드 상단선 골든크로스 발생'
    },
    'C2A': {
        'name': '조건2A', 
        'description': 'MA5-MA20 데드크로스 확인',
        'detail': '100봉이내 MA5-MA20 데드크로스 발생'
    },
    'C2B': {
        'name': '조건2B',
        'description': 'MA1-MA5 골든크로스',
        'detail': '10봉이내 MA1-MA5 골든크로스 발생'
    },
    'C2C': {
        'name': '조건2C',
        'description': 'MA5<MA20 또는 이격도 2%이내',
        'detail': 'MA5가 MA20 아래 또는 MA5-MA20 이격도 2%이내'
    },
    'C_ST': {
        'name': 'SuperTrend',
        'description': '5분봉 SuperTrend 매수신호',
        'detail': '5분봉 SuperTrend(10-3) 하락→상승 전환'
    },
    
    # 전략 D 조건들
    'D1': {
        'name': '조건D1',
        'description': '15분봉 MA80<MA480',
        'detail': '15분봉에서 MA80이 MA480 아래 위치'
    },
    'D2': {
        'name': '조건D2', 
        'description': '5분봉 SuperTrend 매수신호',
        'detail': '5분봉 SuperTrend(10-3) 하락→상승 전환'
    },
    'D3': {
        'name': '조건D3',
        'description': 'MA80-MA480 골든크로스 OR 이격도<5%',
        'detail': '200봉이내 MA80-MA480 골든크로스 또는 이격도 5%이내'
    },
    'D4': {
        'name': '조건D4',
        'description': 'MA480 하락+BB200-MA480 골든',
        'detail': '700봉이내 MA480 5연속 하락 AND BB200상단-MA480 골든크로스'
    },
    'D5': {
        'name': '조건D5',
        'description': 'MA5-MA20 골든크로스',
        'detail': '20봉이내 MA5-MA20 골든크로스 발생'
    }
}

# 최적화된 WebSocket 스캐너 import (선택적)
try:
    from optimized_websocket_scanner import OptimizedWebSocketScanner
    HAS_OPTIMIZED_SCANNER = True
except ImportError:
    OptimizedWebSocketScanner = None
    HAS_OPTIMIZED_SCANNER = False

# 최적화된 2시간 필터 import (4시간봉 필터링용)
try:
    from optimized_2h_filter import Optimized2HFilter
    HAS_OPTIMIZED_FILTER = True
except ImportError:
    Optimized2HFilter = None
    HAS_OPTIMIZED_FILTER = False

import logging
import warnings

class RateLimitTracker:
    """바이낸스 Rate Limit 가중치 추적 시스템 + 통계 수집"""
    def __init__(self):
        self.weight_used = 0
        self.window_start = time.time()
        self.max_weight = 1200  # 분당 제한 (바이낸스 기준)
        self.warning_threshold = 0.60  # 60% 도달시 경고 (IP 밴 절대 방지!)

        # 📊 통계 수집 시스템
        self.stats = {
            'total_requests': 0,
            'total_weight_used': 0,
            'warning_count': 0,
            'wait_count': 0,
            'total_wait_time': 0.0,
            'peak_weight': 0,
            'peak_usage_pct': 0.0,
            'start_time': time.time(),
            'last_reset_time': time.time()
        }

        # 📈 시간대별 통계 (시간당 집계)
        self.hourly_stats = {}  # {hour: {requests, weight, warnings}}

        # 📁 통계 파일 경로
        self.stats_file = 'rate_limit_stats.json'
        self._load_stats()

    def _load_stats(self):
        """저장된 통계 불러오기"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    saved_stats = json.load(f)
                    # 오늘 날짜 통계만 로드
                    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                    if saved_stats.get('date') == today:
                        self.stats.update(saved_stats.get('stats', {}))
                        self.hourly_stats = saved_stats.get('hourly_stats', {})
        except Exception as e:
            print(f"⚠️ Rate Limit 통계 로드 실패: {e}")

    def _save_stats(self):
        """통계 저장"""
        try:
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            stats_data = {
                'date': today,
                'stats': self.stats,
                'hourly_stats': self.hourly_stats,
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Rate Limit 통계 저장 실패: {e}")

    def add_request(self, weight=1):
        """요청 가중치 추가"""
        current_time = time.time()

        # 1분 경과시 리셋
        if current_time - self.window_start >= 60:
            self.weight_used = 0
            self.window_start = current_time
            self.stats['last_reset_time'] = current_time

        self.weight_used += weight

        # 📊 통계 업데이트
        self.stats['total_requests'] += 1
        self.stats['total_weight_used'] += weight

        # 피크 사용량 기록
        current_usage_pct = (self.weight_used / self.max_weight) * 100
        if self.weight_used > self.stats['peak_weight']:
            self.stats['peak_weight'] = self.weight_used
            self.stats['peak_usage_pct'] = current_usage_pct

        # 시간대별 통계
        current_hour = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:00')
        if current_hour not in self.hourly_stats:
            self.hourly_stats[current_hour] = {'requests': 0, 'weight': 0, 'warnings': 0}
        self.hourly_stats[current_hour]['requests'] += 1
        self.hourly_stats[current_hour]['weight'] += weight

        # 80% 도달시 경고 및 대기
        if self.weight_used >= self.max_weight * self.warning_threshold:
            remaining_weight = self.max_weight - self.weight_used
            print(f"⚠️ Rate Limit {self.weight_used}/{self.max_weight} ({current_usage_pct:.1f}%) - 남은 가중치: {remaining_weight}")

            self.stats['warning_count'] += 1
            if current_hour in self.hourly_stats:
                self.hourly_stats[current_hour]['warnings'] += 1

            # 60% 이상이면 30초 대기 (IP 밴 절대 방지!)
            if self.weight_used >= self.max_weight * 0.6:
                print(f"🛑 Rate Limit 60% 초과 - 30초 대기 (안전 최우선)")
                self.stats['wait_count'] += 1
                self.stats['total_wait_time'] += 30.0
                time.sleep(30)
                # 대기 후 리셋
                self.weight_used = 0
                self.window_start = time.time()

        # 통계 저장 (100번 요청마다)
        if self.stats['total_requests'] % 100 == 0:
            self._save_stats()

    def can_request(self, weight=1):
        """요청 가능 여부 확인"""
        current_time = time.time()

        # 1분 경과시 리셋
        if current_time - self.window_start >= 60:
            self.weight_used = 0
            self.window_start = current_time

        # 요청 후 제한 초과 여부 확인
        return self.weight_used + weight < self.max_weight

    def wait_if_needed(self, weight=1):
        """필요시 대기"""
        if not self.can_request(weight):
            wait_time = 60 - (time.time() - self.window_start)
            if wait_time > 0:
                print(f"⏳ Rate Limit 대기: {wait_time:.1f}초")
                self.stats['wait_count'] += 1
                self.stats['total_wait_time'] += wait_time
                time.sleep(wait_time)
                # 대기 후 리셋
                self.weight_used = 0
                self.window_start = time.time()

    def get_stats_summary(self):
        """통계 요약 반환"""
        runtime = time.time() - self.stats['start_time']
        runtime_hours = runtime / 3600

        avg_weight_per_request = (self.stats['total_weight_used'] / self.stats['total_requests']
                                  if self.stats['total_requests'] > 0 else 0)

        return {
            '총 요청 수': self.stats['total_requests'],
            '총 가중치': self.stats['total_weight_used'],
            '평균 가중치/요청': f"{avg_weight_per_request:.2f}",
            '경고 횟수': self.stats['warning_count'],
            '대기 횟수': self.stats['wait_count'],
            '총 대기 시간': f"{self.stats['total_wait_time']:.1f}초",
            '피크 사용량': f"{self.stats['peak_weight']}/{self.max_weight} ({self.stats['peak_usage_pct']:.1f}%)",
            '실행 시간': f"{runtime_hours:.2f}시간",
            '시간당 요청': f"{self.stats['total_requests']/runtime_hours:.1f}회" if runtime_hours > 0 else "0회"
        }

    def generate_daily_report(self):
        """일일 리포트 생성"""
        summary = self.get_stats_summary()
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

        report = f"""
╔════════════════════════════════════════════════════════════╗
║          📊 Rate Limit 일일 리포트 - {today}          ║
╚════════════════════════════════════════════════════════════╝

📈 전체 통계:
  • 총 요청 수: {summary['총 요청 수']:,}회
  • 총 가중치 사용: {summary['총 가중치']:,}
  • 평균 가중치/요청: {summary['평균 가중치/요청']}
  • 시간당 평균 요청: {summary['시간당 요청']}

⚠️ 경고 및 대기:
  • Rate Limit 경고: {summary['경고 횟수']}회
  • 대기 발생: {summary['대기 횟수']}회
  • 총 대기 시간: {summary['총 대기 시간']}

🔥 피크 사용량:
  • 최대 가중치: {summary['피크 사용량']}

⏱️ 실행 시간:
  • 총 실행 시간: {summary['실행 시간']}

📊 시간대별 통계:
"""
        # 시간대별 통계 추가
        for hour, stats in sorted(self.hourly_stats.items()):
            report += f"  • {hour}: {stats['requests']}회 요청, {stats['weight']} 가중치"
            if stats['warnings'] > 0:
                report += f", ⚠️ {stats['warnings']}회 경고"
            report += "\n"

        report += "\n" + "═" * 60 + "\n"

        return report

    def print_stats(self):
        """통계 출력"""
        print(self.generate_daily_report())

def get_korea_time():
    """한국 표준시(KST) 현재 시간을 반환 (UTC +9시간)"""
    return datetime.now(timezone.utc) + timedelta(hours=9)

def setup_logging():
    """로깅 설정"""
    warnings.filterwarnings('ignore')

    # UTF-8 인코딩으로 콘솔 출력 설정
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

    # ⚡ WebSocket 관련 모든 로깅 완전 비활성화
    logging.getLogger('binance').setLevel(logging.CRITICAL)
    logging.getLogger('binance.ws').setLevel(logging.CRITICAL)
    logging.getLogger('binance.ws.threaded_stream').setLevel(logging.CRITICAL)
    logging.getLogger('binance.ws.reconnecting_websocket').setLevel(logging.CRITICAL)
    logging.getLogger('websockets').setLevel(logging.CRITICAL)
    logging.getLogger('websockets.client').setLevel(logging.CRITICAL)
    logging.getLogger('websockets.asyncio').setLevel(logging.CRITICAL)
    logging.getLogger('asyncio').setLevel(logging.CRITICAL)
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)

    # ⚡ asyncio 예외 핸들러 설정 (TimeoutError 무시)
    import asyncio
    def handle_exception(loop, context):
        # asyncio 예외를 조용히 무시 (TimeoutError 등)
        pass

    try:
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(handle_exception)
    except:
        pass

    # ⚡ 새 이벤트 루프 생성시에도 핸들러 적용
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except:
        pass

    # ⚡ sys.excepthook 오버라이드 (WebSocket TimeoutError traceback 숨기기)
    def custom_excepthook(exc_type, exc_value, exc_traceback):
        # TimeoutError와 WebSocket 관련 오류는 무시
        if exc_type.__name__ in ['TimeoutError', 'ConnectionError', 'OSError']:
            if 'websocket' in str(exc_value).lower() or 'handshake' in str(exc_value).lower():
                return  # 조용히 무시
        # 다른 오류는 기본 핸들러로 처리
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = custom_excepthook

    # ⚡ threading.excepthook 오버라이드 (스레드 내 예외도 숨기기)
    import threading
    def custom_thread_excepthook(args):
        # TimeoutError와 WebSocket 관련 오류는 무시
        if args.exc_type.__name__ in ['TimeoutError', 'ConnectionError', 'OSError']:
            if 'websocket' in str(args.exc_value).lower() or 'handshake' in str(args.exc_value).lower():
                return  # 조용히 무시
        # 다른 오류는 기본 핸들러로 처리
        if hasattr(threading, '__excepthook__'):
            threading.__excepthook__(args)

    threading.excepthook = custom_thread_excepthook

    logger = logging.getLogger('OneMinuteSurgeEntryStrategy')
    logger.setLevel(logging.INFO)

    if logger.handlers:
        logger.handlers.clear()

    # 파일 핸들러 - 모든 로그 기록
    file_handler = logging.FileHandler('strategy.log', encoding='utf-8')
    file_handler.setLevel(logging.INFO)

    # 콘솔 핸들러 - WARNING 이상만 출력
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # INFO는 콘솔에 출력 안함

    # 포맷터
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

class OneMinuteSurgeEntryStrategy:
    """1분봉 급등 초입 진입 전략"""
    
    def __init__(self, api_key=None, secret_key=None, sandbox=False):
        self.logger = setup_logging()
        
        # API 키가 None이면 BinanceConfig에서 가져오기
        if not api_key and HAS_BINANCE_CONFIG:
            api_key = BinanceConfig.API_KEY
        if not secret_key and HAS_BINANCE_CONFIG:
            secret_key = BinanceConfig.SECRET_KEY
        if sandbox is False and HAS_BINANCE_CONFIG:
            sandbox = BinanceConfig.TESTNET
        
        # 거래소 설정 - API 밴 상황 고려한 재시도 로직
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                self.exchange = ccxt.binance({
                    'apiKey': api_key if api_key else None,
                    'secret': secret_key if secret_key else None,
                    'sandbox': sandbox,
                    'enableRateLimit': True,
                    'rateLimit': 200,  # 50 → 200 (IP 밴 방지, 안전 우선)
                    'timeout': 5000,  # API 타임아웃 5초
                    'options': {
                        'defaultType': 'future',
                        'adjustForTimeDifference': True,
                        'recvWindow': 60000  # 60초 타임윈도우 (기본 10초 → 60초로 증가)
                    }
                })

                # ⚡ 연결 풀 크기 최적화: 병렬 처리 100개 워커 대응
                try:
                    from requests.adapters import HTTPAdapter
                    adapter = HTTPAdapter(
                        pool_connections=100,  # 연결 풀 개수 (200 → 100)
                        pool_maxsize=100,      # 각 풀의 최대 크기 (200 → 100)
                        max_retries=2          # 재시도 횟수 (3 → 2)
                    )
                    self.exchange.session.mount('https://', adapter)
                    self.exchange.session.mount('http://', adapter)
                except Exception as e:
                    self.logger.warning(f"연결 풀 설정 실패 (무시 가능): {e}")

                # 마켓 로드 (API 밴 가능 지점)
                self.exchange.load_markets()
                
                # 전체 USDT 선물 심볼 개수 확인
                usdt_symbols = [s for s in self.exchange.markets.keys() 
                              if s.endswith('/USDT') and self.exchange.markets[s]['active']]
                
                self.logger.info(f"바이낸스 연결 완료 - 전체 USDT 선물 심볼: {len(usdt_symbols)}개")
                
                if api_key and secret_key:
                    self.logger.info("인증 API 사용 - 거래 가능")
                else:
                    self.logger.info("공개 API 사용 - 스캔 전용")
                
                break  # 성공시 루프 종료
                    
            except Exception as e:
                retry_count += 1
                error_str = str(e)
                
                # Rate limit 또는 IP 밴 감지
                if ("418" in error_str or "429" in error_str or "banned" in error_str.lower() or 
                    "Too many requests" in error_str):
                    
                    self.logger.warning(f"🚨 API Rate Limit/IP 밴 감지 - WebSocket 전용 모드로 시작")
                    
                    # 밴 해제 시간 표시
                    if "banned until" in error_str:
                        import re
                        ban_time_match = re.search(r'banned until (\d+)', error_str)
                        if ban_time_match:
                            ban_timestamp = int(ban_time_match.group(1))
                            if ban_timestamp > 10**12:  # 밀리초 형태
                                ban_timestamp = ban_timestamp // 1000
                            import datetime
                            ban_time = datetime.datetime.fromtimestamp(ban_timestamp)
                            print(f"🚨 IP 밴 해제 예정: {ban_time}")
                    
                    # Rate limit 상태로 설정하고 WebSocket 전용 모드로 계속 진행
                    self._api_rate_limited = True
                    print("🔄 WebSocket 전용 모드로 계속 진행합니다 (REST API 차단)")
                    
                    # 최소한의 거래소 설정만 유지
                    try:
                        self.exchange = ccxt.binance(config)
                        # 심볼 목록만 하드코딩으로 설정
                        self.logger.info("⚠️ WebSocket 전용 모드 - 제한된 기능으로 시작")
                        break  # WebSocket 모드로 계속 진행
                    except:
                        pass
                else:
                    self.logger.error(f"거래소 초기화 실패: {e}")
                    if retry_count >= max_retries:
                        raise Exception("거래소 연결 실패")
        
        # 텔레그램 봇 설정
        self.telegram_bot = None
        if HAS_TELEGRAM_BOT and HAS_TELEGRAM_CONFIG and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            try:
                self.telegram_bot = TelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
            except Exception as e:
                self.logger.error(f"텔레그램 봇 초기화 실패: {e}")
        
        # 전략 설정 (옵션A: 보수적 안정 운영)
        self.max_positions = 15  # 최대 15종목 (확장된 포지션 관리)
        self.leverage = 10  # 10배 레버리지
        self.position_size_pct = 0.020  # 원금 2.0% × 10배 레버리지 (실제 진입 반영)
        self.min_balance = 1.0  # 최소 잔고 요구사항
        self.min_order_amount = 6.0  # 바이낸스 최소 주문 금액 ($5 + 안전마진 $1)
        
        # 💰 시드 설정 (전체 수익률 계산용)
        self.initial_seed = 100.0  # 초기 시드 $100 (실제 시드에 맞게 수정하세요)

        # OHLCV 데이터 캐시 (Rate Limit 회피용)
        # 🚀 글로벌 캐시 사용 (프로그램 재시작 전까지 유지)
        if not hasattr(self.__class__, '_global_ohlcv_cache'):
            self.__class__._global_ohlcv_cache = {}
        self._ohlcv_cache = self.__class__._global_ohlcv_cache  # 글로벌 캐시 참조
        self._ohlcv_cache_ttl = 300  # 5분 (빠른 갱신으로 실시간성 향상)

        # 🚀 마켓 정보 캐시 (고속화: 초기 스캔 시간 90% 단축)
        self._market_cache = None
        self._market_cache_time = 0
        self._market_cache_ttl = 3600  # 1시간 (마켓 정보는 거의 변하지 않음)

        # 중복 진입 방지 시스템
        self._processed_signals = set()
        
        # 중복 메시지 방지 시스템 (포지션 기반)
        self._sent_signals = set()  # 이미 진입 신호를 보낸 심볼들
        
        # 진입 실패 알림 중복 방지 (심볼별 마지막 실패 시간)
        self.last_failure_alerts = {}
        
        # 포지션 모니터링 시스템
        self.active_positions = {}
        
        # 청산 관리 시스템 (동기화 전에 초기화 필요)
        self.position_stats = {}  # 포지션별 통계 (최대수익률 등)
        
        # BB600 부분청산 1회 한정 추적 시스템
        self.bb600_partial_liquidations = {}  # {symbol: timestamp} 부분청산 실행 기록
        
        # 🔄 하이브리드 동기화 시스템
        self.last_exchange_sync_time = 0  # 마지막 거래소 동기화 시간
        self.exchange_sync_interval = 5  # 5초마다 거래소 동기화 (빠른 수익화)
        self.position_cache = {}  # 실시간 포지션 캐시
        self.sync_accuracy_threshold = 0.5  # 0.5% 이상 차이시 강제 동기화

        # DCA 순환매수 시스템 초기화 (동기화 전에 None으로 초기화 필요)
        self.dca_manager = None

        # 시작시 바이낸스 계좌와 동기화
        self.sync_positions_with_exchange()
        
        # DCA 시스템 초기화 조건 확인 및 초기화
        if HAS_DCA_SYSTEM and api_key and secret_key and not sandbox:
            try:
                self.dca_manager = ImprovedDCAPositionManager(
                    exchange=self.exchange,
                    telegram_bot=self.telegram_bot,
                    stats_callback=self.update_trade_stats,
                    strategy=self  # 전략 참조 전달 (active_positions 즉시 동기화용)
                )
                self.logger.info("🚀 개선된 DCA 시스템 초기화 완료")

                # 기존 포지션 처리 (개선된 시스템은 자동 동기화)
                try:
                    active_positions = self.dca_manager.get_active_positions()
                    if active_positions:
                        self.logger.info(f"🔄 {len(active_positions)}개 기존 포지션 감지 및 연동 완료")
                except Exception as e:
                    self.logger.error(f"기존 포지션 동기화 실패: {e}")
            except Exception as e:
                self.logger.error(f"개선된 DCA 시스템 초기화 실패: {e}")
                self.dca_manager = None
        else:
            # DCA 시스템 비활성화 상황들 처리 (조용히 처리)
            if not HAS_DCA_SYSTEM:
                self.logger.warning("⚠️ DCA 시스템 비활성화 - improved_dca_position_manager.py 필요")
            elif not (api_key and secret_key):
                # 공개 API 모드는 정상 작동이므로 warning 대신 info로 처리
                self.logger.info("ℹ️ DCA 시스템 비활성화 - 스캔 전용 모드")
            elif sandbox:
                self.logger.warning("⚠️ DCA 시스템 비활성화 - 샌드박스 모드")
            self.dca_manager = None
        
        # 🛡️ DCA 복구 시스템 초기화 (통합)
        self.dca_recovery = None
        if HAS_DCA_RECOVERY and self.dca_manager:
            try:
                self.dca_recovery = EnhancedDCARecoverySystem(
                    exchange=self.exchange,
                    dca_manager=self.dca_manager,
                    telegram_bot=self.telegram_bot
                )
                self.logger.info("🛡️ DCA 복구 시스템 초기화 완료")
            except Exception as e:
                self.logger.error(f"DCA 복구 시스템 초기화 실패: {e}")
                self.dca_recovery = None
        
        # 🔄 하이브리드 동기화 시스템 초기화 완료
        self.logger.info(f"🔄 하이브리드 동기화 시스템 활성화 - 동기화 간격: {self.exchange_sync_interval}초, 정확도 임계값: {self.sync_accuracy_threshold}%")
        
        # 🚨 긴급 청산 요청 시스템 (API 밴 대응)
        self._emergency_exit_requests = set()

        # 🚀 WebSocket 실시간 모니터링 시스템 초기화
        self.ws_kline_manager = None
        self.realtime_monitor = None

        # 🚀 WebSocket 메인 스캔용 활성화 (4시간봉 필터링은 REST API 사용)
        print("🚀 하이브리드 모드: WebSocket(메인 스캔) + REST API(4h 필터링)")

        # WebSocket은 스캔 성능 향상을 위해 DCA와 독립적으로 작동 (API 키 불필요)
        if not sandbox:
            try:
                # python-binance 라이브러리 기반 WebSocket 매니저 (공식 구현)
                from binance_websocket_kline_manager import BinanceWebSocketKlineManager

                # 🚀 스마트 하이브리드: WebSocket(실시간) + REST API(초기 데이터)
                print("🧠 스마트 하이브리드: WebSocket 실시간 + REST API 초기 데이터 (python-binance)")

                # WebSocket: 실시간 업데이트용 (python-binance)
                self.ws_kline_manager = BinanceWebSocketKlineManager(
                    callback=self.on_websocket_kline_update,
                    logger=self.logger
                )

                # WebSocket 시작 (오류 무시하고 계속 진행)
                try:
                    ws_started = self.ws_kline_manager.start(max_retries=2, retry_delay=5)
                except:
                    ws_started = False  # 모든 오류 무시

                if ws_started:
                    # REST API: 초기 히스토리 데이터 확보용 (병렬 처리)
                    self._use_smart_hybrid = True
                    self._initial_data_loaded = False

                    print("[WebSocket] ✅ kline 웹소켓 + 250ms 극한 스캔 모드 활성화!")

                    # 🎯 동적 심볼 구독 시스템 활성화 (필터링된 심볼만 구독)
                    self._dynamic_websocket_subscription = True
                    self._subscribed_symbols = set()  # 현재 구독 중인 심볼들 추적
                    print("🎯 동적 WebSocket 구독 시스템 활성화됨")
                    print("📡 필터링된 심볼만 동적으로 구독됩니다")
                else:
                    # WebSocket 시작 실패 - 메인 스캔도 REST API 사용
                    print("[WebSocket] ⚠️ 초기화 실패 - 메인 스캔도 REST API 사용")
                    self.ws_kline_manager = None  # WebSocket 비활성화

            except ImportError as e:
                self.logger.warning(f"⚠️ WebSocket 모듈 없음 - REST API 폴링 방식 사용: {e}")
                print("[WebSocket] ⚠️ WebSocket 모듈 미설치 - 기존 3초 폴링 방식 사용")
            except Exception as e:
                self.logger.error(f"❌ WebSocket 시스템 초기화 실패: {e}")
                print(f"[WebSocket] ❌ 초기화 실패 - 기존 방식으로 fallback: {e}")
        elif sandbox:
            self.logger.info("⚠️ 샌드박스 모드 - WebSocket 비활성화")
        else:
            # 공개 API 모드에서도 WebSocket 활성화 (시장 데이터는 공개)
            try:
                # WebSocket 모듈 동적 import (python-binance 기반)
                from binance_websocket_kline_manager import BinanceWebSocketKlineManager

                # WebSocket 매니저 생성 (공개 데이터, python-binance)
                self.ws_kline_manager = BinanceWebSocketKlineManager(
                    callback=self.on_websocket_kline_update,
                    logger=self.logger
                )

                # WebSocket 시작 (오류 무시하고 계속 진행)
                try:
                    ws_started = self.ws_kline_manager.start(max_retries=2, retry_delay=5)
                except:
                    ws_started = False  # 모든 오류 무시

                if ws_started:
                    print("🧠 공개 API 모드: WebSocket 시장 데이터 수신 활성화")

                    # 🎯 동적 심볼 구독 시스템 활성화
                    self._dynamic_websocket_subscription = True
                    self._subscribed_symbols = set()
                    print("🎯 동적 WebSocket 구독 시스템 활성화됨")
                    print("📡 필터링된 심볼만 동적으로 구독됩니다")
                else:
                    # WebSocket 시작 실패 - REST API 전용 모드
                    print("[WebSocket] ⚠️ 초기화 실패 - REST API 전용 모드 사용")
                    self.ws_kline_manager = None  # WebSocket 비활성화


            except ImportError as e:
                self.logger.warning(f"⚠️ WebSocket 모듈 없음 - REST API 방식 사용: {e}")
                print("[WebSocket] ⚠️ WebSocket 모듈 미설치")
            except Exception as e:
                self.logger.error(f"❌ WebSocket 시스템 초기화 실패: {e}")
                print(f"[WebSocket] ❌ 초기화 실패: {e}")


        # 📊 거래 내역 동기화 시스템 초기화
        self.trade_history_sync = None
        if HAS_TRADE_HISTORY_SYNC and self.exchange:
            try:
                self.trade_history_sync = TradeHistorySync(
                    exchange=self.exchange,
                    strategy=self
                )
                self.logger.info("📊 거래 내역 동기화 시스템 초기화 완료")
            except Exception as e:
                self.logger.error(f"거래 내역 동기화 시스템 초기화 실패: {e}")
                self.trade_history_sync = None
        
        # 🚀 최적화된 WebSocket 스캐너 초기화
        self.optimized_scanner = None
        if HAS_OPTIMIZED_SCANNER and self.ws_kline_manager:
            try:
                self.optimized_scanner = OptimizedWebSocketScanner(self)
                self.logger.info("🚀 최적화된 WebSocket 스캐너 초기화 완료")
                
                # WebSocket 스캔 모드 활성화 플래그
                self._use_websocket_scanner = True
                print("⚡ WebSocket 전용 스캔 모드 활성화됨")
                
            except Exception as e:
                self.logger.error(f"최적화된 WebSocket 스캐너 초기화 실패: {e}")
                self.optimized_scanner = None
                self._use_websocket_scanner = False
        else:
            self._use_websocket_scanner = False
            if not HAS_OPTIMIZED_SCANNER:
                self.logger.info("ℹ️ 최적화된 WebSocket 스캐너 비활성화 - optimized_websocket_scanner.py 필요")
            elif not self.ws_kline_manager:
                self.logger.info("ℹ️ 최적화된 WebSocket 스캐너 비활성화 - WebSocket 관리자 필요")
        
        # 🔧 최적화된 4시간봉 필터 초기화
        self.optimized_filter = None
        if HAS_OPTIMIZED_FILTER:
            try:
                self.optimized_filter = Optimized2HFilter()
                self.logger.info("🔧 최적화된 4시간봉 필터 초기화 완료")
            except Exception as e:
                self.logger.error(f"최적화된 4시간봉 필터 초기화 실패: {e}")
                self.optimized_filter = None
        else:
            self.logger.info("ℹ️ 최적화된 4시간봉 필터 비활성화 - optimized_2h_filter.py 필요")
        
        # 매매 통계 (한국시간 9시 기준 날짜 변경)
        trading_day = self._get_trading_day()
        self.today_stats = {
            'date': trading_day,
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0.0,
            'total_entry_amount': 0.0,  # 일일 사용된 총 원금 (Day ROE 계산용)
            'win_rate': 0.0,
            'trades_detail': []
        }

        # 📊 부분청산 누적 데이터 저장소 (포지션별로 부분청산 추적)
        # 구조: {symbol: {'partial_exits': [{...}], 'total_pnl': 0.0, 'exit_count': 0}}
        self.partial_exit_accumulator = {}

        # 기존 통계 파일 로드 (재시작 시 통계 복원)
        self._load_daily_stats()

        self.logger.info("1분봉 급등 초입 진입 전략 초기화 완료")
        
        # 디버깅 로그 파일 설정
        self._setup_debug_logging()

        # 데이터 캐시 시스템 초기화 (안정성 향상)
        self._data_cache = {}
        self._cache_ttl = 60  # 60초 캐시

        # ⚡ 고속 스캔 최적화 시스템
        self._ticker_cache = {}  # 티커 캐시 (1초 TTL)
        self._scan_mode = False  # 스캔 모드 플래그 (True시 디버그 로깅 최소화)

        # 🕐 4시간봉 필터링 타임스탬프 추적 (동적 증분 스캔용)
        self._last_full_scan_time = 0  # 마지막 전체 스캔 시간 (timestamp)

        # 🛡️ Rate Limit 가중치 추적 시스템 초기화
        self.rate_tracker = RateLimitTracker()
        self.logger.info("🛡️ Rate Limit 추적 시스템 초기화 완료 (분당 1200 가중치)")

        # 📊 주문 기록 동기화 시스템 초기화
        self.order_history_sync = None
        if HAS_ORDER_HISTORY_SYNC and self.exchange and hasattr(self.exchange, 'apiKey') and self.exchange.apiKey:
            try:
                self.order_history_sync = OrderHistorySync(self.exchange)
                self.logger.info("📊 주문 기록 동기화 시스템 초기화 완료")
            except Exception as e:
                self.logger.error(f"주문 기록 동기화 시스템 초기화 실패: {e}")
                self.order_history_sync = None
    
    def _setup_debug_logging(self):
        """디버깅 로그 파일 설정"""
        try:
            import os
            # 디버깅 로그 디렉토리 생성
            debug_dir = "strategy_debug"
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
            
            # 날짜별 디버깅 로그 파일
            today = get_korea_time().strftime('%Y%m%d')
            self.debug_log_file = os.path.join(debug_dir, f"one_minute_strategy_debug_{today}.log")
            
            # 로그 파일 초기화 (세션 시작 시)
            with open(self.debug_log_file, 'w', encoding='utf-8') as f:
                f.write(f"=== 1분봉 급등 초입 진입 전략 디버깅 로그 [{get_korea_time().strftime('%Y-%m-%d %H:%M:%S')}] ===\n\n")
                
        except Exception as e:
            self.logger.error(f"디버깅 로그 설정 실패: {e}")
            self.debug_log_file = None
        
        # 데이터 캐시 시스템 초기화 (안정성 향상)
        self._data_cache = {}
        self._cache_ttl = 60  # 60초 캐시
    
    def check_existing_position(self, symbol):
        """실제 바이낸스 계좌에서 해당 심볼의 포지션 확인 (실제 포지션 우선)"""
        try:
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')

            # 🔒 최우선: 로컬 캐시(active_positions) 확인 - 가장 빠르고 정확
            if symbol in self.active_positions:
                self.logger.debug(f"[포지션체크] 🔒 {clean_symbol} 로컬 캐시에 포지션 존재 - 중복 진입 차단")
                return True

            # 🚀 속도 테스트 모드: 포지션 체크 완전 건너뛰기
            if hasattr(self, '_speed_test_mode') and self._speed_test_mode:
                return clean_symbol in self._sent_signals  # 세션 캐시만 사용

            # API 키가 없는 경우 (공개 API 모드) - 세션 캐시만 사용
            if not hasattr(self.exchange, 'apiKey') or not self.exchange.apiKey:
                self.logger.debug(f"[포지션체크] {symbol} - API 키 없음, 세션 캐시만 사용")
                # 세션 내 신호 발송 기록으로만 체크
                if clean_symbol in self._sent_signals:
                    self.logger.debug(f"[포지션체크] ⚡ {clean_symbol} 세션 내 이미 신호 발송됨")
                    return True
                return False
            
            # 실제 API 호출로 정확한 포지션 상태 확인
            future_symbol = f"{clean_symbol}USDT"
            self.logger.debug(f"[포지션체크] {symbol} -> {future_symbol} 실시간 조회...")
            
            # 특정 심볼만 조회 (전체 조회 대신)
            try:
                # 특정 심볼 포지션만 조회 (더 빠름)
                position = self.exchange.fetch_position(future_symbol)
                position_size = position.get('size', 0) or position.get('contracts', 0)
                
                has_position = position_size > 0
                self.logger.debug(f"[포지션체크] {future_symbol} - 크기: {position_size}, 포지션: {has_position}")
                
                # 🔧 실제 포지션 상태와 세션 캐시 동기화
                if has_position:
                    # 실제로 포지션이 있으면 세션 캐시에 추가
                    self._sent_signals.add(clean_symbol)
                    self.logger.debug(f"[포지션체크] ✅ {clean_symbol} 세션 캐시 동기화 (포지션 존재)")
                else:
                    # 실제로 포지션이 없으면 세션 캐시에서 제거
                    if clean_symbol in self._sent_signals:
                        self._sent_signals.remove(clean_symbol)
                        self.logger.debug(f"[포지션체크] 🔄 {clean_symbol} 세션 캐시 정리 (포지션 없음)")
                
                return has_position
                
            except:
                # fetch_position 실패 시 전체 조회로 폴백
                positions = self.exchange.fetch_positions()
                for position in positions:
                    if position['symbol'] == future_symbol:
                        position_size = position.get('size', 0) or position.get('contracts', 0)
                        has_position = position_size > 0

                        # 🔧 실제 포지션 상태와 세션 캐시 동기화
                        if has_position:
                            self._sent_signals.add(clean_symbol)
                        elif clean_symbol in self._sent_signals:
                            self._sent_signals.remove(clean_symbol)

                        return has_position

                # 포지션 없음
                return False
            
        except Exception as e:
            # API 에러시에는 안전하게 True 반환 (중복 진입 차단)
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            self.logger.warning(f"[포지션체크] ❌ {clean_symbol} 확인 실패 (안전하게 진입 차단): {e}")
            return True  # 안전 우선: 포지션 확인 실패 시 진입 금지
    
    def _write_debug_log(self, message):
        """디버깅 메시지를 파일에 기록 (변경사항이 있을 때만)"""
        try:
            # ⚡ 스캔 모드시에도 DEBUG 메시지는 기록 (조건 분석용)
            if getattr(self, '_scan_mode', False) and "DEBUG" not in message:
                return

            if self.debug_log_file:
                # 변경사항 없는 정상 상황은 기록하지 않음
                no_change_patterns = [
                    "0개", "없음", "동기화 완료", "조회 성공",
                    "정상", "완료됨", "성공적"
                ]
                
                # 실제 변경사항이나 특별한 상황만 기록
                change_indicators = [
                    "실패", "에러", "ERROR", "경고", "WARNING",
                    "진입", "청산", "DCA", "추가매수", "신호",
                    "급등", "차이", "불일치", "누락", "추가", "제거",
                    "업데이트", "변경", "감지", "발견", "DEBUG"
                ]
                
                # 변경사항 없는 경우 스킵
                if any(pattern in message for pattern in no_change_patterns):
                    return
                    
                # 실제 변경사항이나 중요한 이벤트만 기록
                if any(indicator in message for indicator in change_indicators):
                    timestamp = get_korea_time().strftime('%H:%M:%S')
                    with open(self.debug_log_file, 'a', encoding='utf-8') as f:
                        f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            pass
    
    def _get_cached_data(self, cache_key):
        """캐시된 데이터 조회 (만료 시간 체크)"""
        try:
            if cache_key in self._data_cache:
                cached_data, timestamp = self._data_cache[cache_key]
                # TTL 체크
                if time.time() - timestamp < self._cache_ttl:
                    return cached_data
                else:
                    # 만료된 데이터 제거
                    del self._data_cache[cache_key]
            return None
        except Exception:
            return None
    
    def _set_cached_data(self, cache_key, data):
        """데이터 캐시에 저장"""
        try:
            self._data_cache[cache_key] = (data, time.time())
            # 캐시 크기 제한 (100개 이상이면 오래된 것부터 제거)
            if len(self._data_cache) > 100:
                oldest_key = min(self._data_cache.keys(),
                                key=lambda k: self._data_cache[k][1])
                del self._data_cache[oldest_key]
        except Exception:
            pass

    def format_condition_result(self, condition_code: str, result: bool, extra_info: str = "") -> str:
        """조건 체크 결과를 상세하게 포맷팅"""
        
        condition_info = STRATEGY_CONDITION_DETAILS.get(condition_code, {
            'name': condition_code,
            'description': '알 수 없는 조건',
            'detail': ''
        })
        
        status = "✅" if result else "❌"
        name = condition_info['name']
        description = condition_info['description']
        
        result_line = f"      {status} {name}: {description}"
        
        if extra_info:
            result_line += f" ({extra_info})"
        
        return result_line

    def _extract_condition_description(self, failed_condition: str) -> str:
        """실패 조건에서 구체적인 설명 추출"""
        # 조건 번호를 구체적인 설명으로 변경
        if '[3분봉 3번째-1]' in failed_condition:
            return "조건1: BB200상단-BB480상단 골든크로스"
        elif '[3분봉 3번째-2A]' in failed_condition:
            return "조건2A: MA5-MA20 데드크로스 확인"
        elif '[3분봉 3번째-2B]' in failed_condition:
            return "조건2B: MA1-MA5 골든크로스"
        elif '[3분봉 3번째-2C]' in failed_condition:
            return "조건2C: MA5<MA20 또는 이격도 2%이내"
        elif '[5분봉 D전략-1]' in failed_condition:
            return "D조건1: 15분봉 MA80<MA480"
        elif '[5분봉 D전략-2]' in failed_condition:
            return "D조건2: 5분봉 SuperTrend 매수신호"
        elif '[5분봉 D전략-3]' in failed_condition:
            return "D조건3: MA80-MA480 골든크로스 OR 이격도<5%"
        elif '[5분봉 D전략-4]' in failed_condition:
            return "D조건4: MA480 하락+BB200-MA480 골든"
        elif '[5분봉 D전략-5]' in failed_condition:
            return "D조건5: MA5-MA20 골든크로스"
        else:
            # 알 수 없는 조건은 원본에서 조건명만 추출
            condition_name = failed_condition.split(':')[0] if ':' in failed_condition else failed_condition
            return condition_name.strip()

    def _get_cached_markets(self):
        """🚀 캐시된 마켓 정보 조회 (초기 스캔 시간 90% 단축)

        마켓 정보는 거의 변하지 않으므로 1시간 캐싱:
        - 첫 조회: load_markets() API 호출 (2-5초 소요)
        - 이후 조회: 캐시에서 즉시 반환 (0ms)
        - 1시간 후: 자동 갱신
        """
        try:
            current_time = time.time()

            # 캐시가 유효한지 확인
            if (self._market_cache is not None and
                current_time - self._market_cache_time < self._market_cache_ttl):
                return self._market_cache

            # 캐시가 없거나 만료됨 → API 호출
            self._market_cache = self.exchange.load_markets()
            self._market_cache_time = current_time

            return self._market_cache

        except Exception as e:
            self.logger.error(f"마켓 캐시 조회 실패: {e}")
            # 실패시 기존 캐시라도 반환 (만료되었더라도)
            if self._market_cache is not None:
                return self._market_cache
            # 캐시도 없으면 직접 호출
            return self.exchange.load_markets()

    def _get_data_with_retry(self, symbol, timeframe, limit, max_retries=2):
        """모든 타임프레임용 재시도 로직 (일반화) - WebSocket 버퍼 우선 사용 - 고속 모드"""
        try:
            cache_key = f"{symbol}_{timeframe}_data"
            cached_data = self._get_cached_data(cache_key)
            if cached_data is not None:
                return cached_data

            # 🚀 1단계 최적화: WebSocket 버퍼 우선 사용 (REST API 완전 우회)
            # WebSocket 매니저가 활성화되어 있으면 버퍼에서 먼저 조회 시도
            if hasattr(self, 'ws_kline_manager') and self.ws_kline_manager:
                try:
                    ws_data = self.get_websocket_kline_data(symbol, timeframe, limit)
                    if ws_data is not None and len(ws_data) >= min(limit // 2, 200):  # 최소 50% 이상 데이터 있으면 사용
                        self._set_cached_data(cache_key, ws_data)
                        return ws_data
                except Exception as ws_error:
                    # WebSocket 조회 실패시 REST API fallback (무시하고 진행)
                    pass

            # WebSocket 버퍼에 없거나 부족하면 REST API 사용 (고속 모드: 재시도 2회로 감소)
            last_error = None
            for attempt in range(max_retries):
                try:
                    df = self.get_ohlcv_data(symbol, timeframe, limit=limit)
                    if df is not None and len(df) > 0:
                        self._set_cached_data(cache_key, df)
                        return df
                except Exception as e:
                    last_error = e
                    # Rate Limit 방지: 재시도 대기 시간 증가 (0.1초 → 0.5초)
                    if attempt < max_retries - 1:
                        time.sleep(0.5)  # 안전한 재시도

            # 실패 시 조용히 None 반환 (에러 로그 최소화)
            return None
        except Exception as e:
            return None
    
    def _get_daily_data_with_retry(self, symbol, max_retries=2):
        """일봉 데이터 조회 (재시도 로직 및 캐시 활용) - 고속 모드"""
        try:
            # 캐시 체크
            cache_key = f"{symbol}_1d_data"
            cached_data = self._get_cached_data(cache_key)
            if cached_data is not None:
                return cached_data

            # 재시도 로직 (고속 모드: 2회로 감소)
            last_error = None
            for attempt in range(max_retries):
                try:
                    df_1d = self.get_ohlcv_data(symbol, '1d', limit=150)
                    if df_1d is not None and len(df_1d) > 0:
                        # 성공시 캐시에 저장
                        self._set_cached_data(cache_key, df_1d)
                        return df_1d
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        # Rate Limit 방지: 재시도 대기 증가 (0.2초 → 0.7초)
                        time.sleep(0.7)

            # 실패 시 조용히 None 반환
            return None

        except Exception as e:
            return None
    
    def _analyze_hourly_surge_pattern(self, symbol_data):
        """1시간봉 상승 패턴 분석 (병렬 처리용) - 간소화 버전"""
        symbol, change_pct, volume_24h, ticker = symbol_data
        try:
            # 1시간봉 상승 패턴 분석
            pattern_matched = False
            surge_info = ""
            debug_info = []

            try:
                # 🚀 1시간봉 4개만 조회 (24→4: 83% 데이터 감소, 5배 속도 향상)
                df_1h = self.get_ohlcv_data(symbol, '1h', limit=4)
                if df_1h is not None and len(df_1h) >= 4:
                    # 최근 4봉 분석
                    recent_4 = df_1h
                    # 안전한 ticker 데이터 접근
                    if isinstance(ticker, dict) and 'last' in ticker:
                        current_price = ticker['last']
                    elif isinstance(ticker, (list, tuple)) and len(ticker) > 0:
                        current_price = float(ticker[0]) if ticker[0] is not None else None
                    else:
                        current_price = self.get_current_price(symbol)

                    if current_price is None:
                        return False, "", []

                    # 조건: 4봉 이내 상승 (4봉전 시가 → 현재가 상승률 > 0%)
                    first_candle_open = recent_4.iloc[0]['open']
                    overall_change = ((current_price - first_candle_open) / first_candle_open) * 100 if first_candle_open > 0 else 0

                    # 디버그 정보 수집
                    debug_info.append(f"24h:{change_pct:.1f}%")
                    debug_info.append(f"4h:{overall_change:.1f}%")

                    # 🚀 최종 조건: 4봉 이내 상승
                    if overall_change > 0:
                        pattern_matched = True
                        surge_info = f"4h{overall_change:+.1f}%"

            except:
                pass  # 1시간봉 분석 실패

            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')

            # 결과 반환
            if pattern_matched:
                return {
                    'symbol': symbol,
                    'clean_symbol': clean_symbol,
                    'change_pct': change_pct,
                    'volume_24h': volume_24h,
                    'surge_info': surge_info,
                    'matched': True,
                    'debug_info': debug_info
                }
            else:
                # 실패 원인 디버그 정보
                fail_reason = ' | '.join(debug_info) if debug_info else "분석실패"
                return {
                    'symbol': symbol,
                    'clean_symbol': clean_symbol,
                    'change_pct': change_pct,
                    'volume_24h': volume_24h,
                    'surge_info': fail_reason,
                    'matched': False,
                    'debug_info': debug_info
                }

        except Exception as e:
            # 분석 실패시 제외
            return {
                'symbol': symbol,
                'clean_symbol': symbol.replace('/USDT:USDT', '').replace('/USDT', ''),
                'change_pct': change_pct,
                'volume_24h': volume_24h,
                'surge_info': f'분석실패: {e}',
                'matched': False
            }  # 디버깅 로그 실패해도 전략 실행은 계속
    
    def get_ohlcv_data(self, symbol, timeframe, limit=1500):
        """OHLCV 데이터 조회 (캐싱 + WebSocket + API 폴백)"""
        try:
            # 🚀 캐싱 시스템: 먼저 캐시 체크 (limit 무시하여 캐시 효율 극대화)
            cache_key = f"{symbol}_{timeframe}"  # limit 제거하여 캐시 히트율 증가
            current_time = time.time()

            if hasattr(self, '_ohlcv_cache') and cache_key in self._ohlcv_cache:
                cached_data, cached_time = self._ohlcv_cache[cache_key]
                # 캐시 유효성 검증 (TTL 체크)
                if current_time - cached_time < self._ohlcv_cache_ttl:
                    # 캐시된 데이터가 요청된 limit보다 충분하면 슬라이싱하여 반환
                    if len(cached_data) >= limit:
                        return cached_data.tail(limit)
                    return cached_data

            # 🚨 Rate Limit 상황에서는 WebSocket만 사용하고 API 호출 절대 금지
            if hasattr(self, '_api_rate_limited') and self._api_rate_limited:
                # Rate limit 복구 체크 (10분마다로 늘림)
                if not hasattr(self, '_last_rate_limit_check'):
                    self._last_rate_limit_check = time.time()
                
                # 10분마다 복구 시도
                if time.time() - self._last_rate_limit_check > 600:  # 300 → 600 (10분)
                    self._last_rate_limit_check = time.time()
                    # Rate limit 플래그 리셋하여 복구 시도
                    self._api_rate_limited = False
                    self.logger.info("🔄 Rate limit 복구 시도 (10분 경과) - API 호출 재개")
                else:
                    # Rate Limit 상황에서는 WebSocket 데이터만 사용
                    ws_data = self.get_websocket_kline_data(symbol, timeframe, limit)
                    if ws_data is not None:
                        # 🚀 캐시에 저장
                        if not hasattr(self, '_ohlcv_cache'):
                            self._ohlcv_cache = {}
                        self._ohlcv_cache[cache_key] = (ws_data, current_time)
                        return ws_data
                    else:
                        self.logger.debug(f"🚨 Rate Limit 상태 - WebSocket 데이터 없음: {symbol} {timeframe}")
                        return None  # API 호출 절대 금지
            
            # WebSocket 매니저가 있는 경우 WebSocket 우선 사용
            if hasattr(self, 'ws_kline_manager') and self.ws_kline_manager:
                # WebSocket 버퍼에서 데이터 조회 시도
                ws_data = self.get_websocket_kline_data(symbol, timeframe, limit)
                if ws_data is not None and len(ws_data) >= 10:  # 최소 10개만 있어도 사용 (완화)
                    # 🚀 캐시에 저장
                    if not hasattr(self, '_ohlcv_cache'):
                        self._ohlcv_cache = {}
                    self._ohlcv_cache[cache_key] = (ws_data, current_time)
                    return ws_data
                
                # 🚀 성능 최적화: 프리로딩 스킵 (캐싱으로 대체)
                # 프리로딩은 너무 느리므로 바로 API 폴백으로 이동
                pass
            
            # 🚨 Rate Limit 체크 강화: 418, 429 에러 감지시 즉시 차단
            if hasattr(self, '_api_rate_limited') and self._api_rate_limited:
                return None
            
            # 🔄 하이브리드 모드: WebSocket 부족 시 REST API 폴백 (강력 제한!)
            # 40% 미만일 때만 REST API 사용 허용 (더욱 보수적)
            if hasattr(self, 'rate_tracker'):
                current_usage = (self.rate_tracker.weight_used / self.rate_tracker.max_weight) * 100
                if current_usage >= 40:  # 40% 넘으면 REST API 차단!
                    self.logger.debug(f"Rate Limit {current_usage:.1f}% - REST API 차단: {symbol} {timeframe}")
                    return None

            try:
                # Rate Limit 체크 및 대기
                if hasattr(self, 'rate_tracker'):
                    self.rate_tracker.wait_if_needed(weight=2)

                # REST API로 데이터 가져오기 (캐시 효율)
                self.logger.debug(f"WebSocket 데이터 부족 - REST API 폴백: {symbol} {timeframe}")
                fetch_limit = max(limit, 500)  # 2000 → 500 (더 적게)
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=fetch_limit)

                # Rate Limit 기록
                if hasattr(self, 'rate_tracker'):
                    self.rate_tracker.add_request(weight=2)

                if ohlcv and len(ohlcv) >= 10:
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

                    # 캐시 저장
                    if not hasattr(self, '_ohlcv_cache'):
                        self._ohlcv_cache = {}
                    self._ohlcv_cache[cache_key] = (df, current_time)
                    return df
                else:
                    return None
            except Exception as api_e:
                self.logger.debug(f"REST API 폴백 실패: {symbol} {timeframe} - {api_e}")
                return None

        except Exception as e:
            self.logger.error(f"{symbol} {timeframe} 데이터 조회 실패: {e}")
            return None
    
    
    def update_websocket_kline(self, symbol, timeframe, kline_data):
        """웹소켓에서 수신한 kline 데이터 업데이트"""
        try:
            if not hasattr(self, '_websocket_kline_buffer'):
                self._websocket_kline_buffer = {}
            
            buffer_key = f"{symbol}_{timeframe}"
            
            if buffer_key not in self._websocket_kline_buffer:
                self._websocket_kline_buffer[buffer_key] = []
            
            # 새로운 kline 데이터 추가
            timestamp = kline_data.get('t', 0)  # timestamp
            open_price = float(kline_data.get('o', 0))
            high_price = float(kline_data.get('h', 0))
            low_price = float(kline_data.get('l', 0))
            close_price = float(kline_data.get('c', 0))
            volume = float(kline_data.get('v', 0))
            
            new_kline = [timestamp, open_price, high_price, low_price, close_price, volume]
            
            # 버퍼에 추가 (최대 1500개 유지)
            self._websocket_kline_buffer[buffer_key].append(new_kline)
            
            # 조용한 데이터 수신 모니터링 (불필요한 출력 제거)
            if len(self._websocket_kline_buffer[buffer_key]) > 1500:
                self._websocket_kline_buffer[buffer_key] = self._websocket_kline_buffer[buffer_key][-1500:]
                
        except Exception as e:
            self.logger.error(f"웹소켓 kline 데이터 업데이트 실패 ({symbol}, {timeframe}): {e}")
    
    def _generate_higher_timeframes_from_1m(self, symbol):
        """1분봉 데이터로부터 다른 타임프레임 데이터 생성"""
        try:
            if not hasattr(self, '_websocket_kline_buffer'):
                return
                
            buffer_key_1m = f"{symbol}_1m"
            if buffer_key_1m not in self._websocket_kline_buffer:
                return
                
            kline_1m_data = self._websocket_kline_buffer[buffer_key_1m]
            if len(kline_1m_data) < 5:  # 최소 5개는 있어야 변환 가능
                return
            
            # 3분봉 생성 (3개씩 묶어서)
            if len(kline_1m_data) >= 3:
                self._create_timeframe_from_1m(symbol, '3m', 3, kline_1m_data)
            
            # 5분봉 생성 (5개씩 묶어서)  
            if len(kline_1m_data) >= 5:
                self._create_timeframe_from_1m(symbol, '5m', 5, kline_1m_data)
                
            # 15분봉 생성 (15개씩 묶어서)
            if len(kline_1m_data) >= 15:
                self._create_timeframe_from_1m(symbol, '15m', 15, kline_1m_data)
                
            # 1시간봉 생성 (60개씩 묶어서)
            if len(kline_1m_data) >= 60:
                self._create_timeframe_from_1m(symbol, '1h', 60, kline_1m_data)
                
            # 4시간봉 생성 (240개씩 묶어서) - 핵심 필터링용
            if len(kline_1m_data) >= 10:  # 테스트용: 최소 10개로 완화 (나중에 240으로 복구)
                self._create_timeframe_from_1m(symbol, '4h', 240, kline_1m_data)
                
            # 일봉 생성 (1440개씩 묶어서) - 부분적으로라도
            if len(kline_1m_data) >= 60:  # 최소 1시간치
                self._create_timeframe_from_1m(symbol, '1d', 1440, kline_1m_data)
                
        except Exception as e:
            self.logger.error(f"타임프레임 생성 실패 ({symbol}): {e}")
    
    def _create_timeframe_from_1m(self, symbol, target_timeframe, multiplier, kline_1m_data):
        """1분봉 데이터를 특정 타임프레임으로 변환"""
        try:
            buffer_key = f"{symbol}_{target_timeframe}"
            
            # 기존 버퍼가 없으면 생성
            if buffer_key not in self._websocket_kline_buffer:
                self._websocket_kline_buffer[buffer_key] = []
            
            # multiplier 단위로 묶어서 변환
            total_candles = len(kline_1m_data) // multiplier
            if total_candles == 0:
                return
                
            new_candles = []
            for i in range(total_candles):
                start_idx = i * multiplier
                end_idx = start_idx + multiplier
                candle_group = kline_1m_data[start_idx:end_idx]
                
                if len(candle_group) == multiplier:
                    # OHLCV 계산
                    timestamp = candle_group[0][0]  # 첫 번째 timestamp
                    open_price = candle_group[0][1]  # 첫 번째 시가
                    high_price = max(candle[2] for candle in candle_group)  # 최고가
                    low_price = min(candle[3] for candle in candle_group)   # 최저가  
                    close_price = candle_group[-1][4]  # 마지막 종가
                    volume = sum(candle[5] for candle in candle_group)  # 거래량 합
                    
                    new_candle = [timestamp, open_price, high_price, low_price, close_price, volume]
                    new_candles.append(new_candle)
            
            # 새로 생성된 캔들들로 버퍼 업데이트
            if new_candles:
                self._websocket_kline_buffer[buffer_key] = new_candles[-100:]  # 최근 100개만 유지
                
        except Exception as e:
            self.logger.error(f"타임프레임 변환 실패 ({symbol}, {target_timeframe}): {e}")
    
    def _fetch_all_timeframes_parallel(self, symbol, clean_symbol):
        """모든 타임프레임을 병렬로 한 번에 조회 (75x 속도 향상)"""
        try:
            timeframes = [
                ('1m', 600),   # MA480 계산 위해 증가
                ('3m', 300),   # MA80 계산 위해 증가
                ('5m', 100),   # SuperTrend 계산용
                ('15m', 500),  # MA480 계산 위해 증가
                ('1d', 100)    # 100봉 이내 조건용
            ]
            
            # 🚀 Rate Limit 대응: WebSocket 우선 + 에러 감지시 API 호출 차단
            results = {}
            with ThreadPoolExecutor(max_workers=5) as executor:
                # Rate Limit 상태에서는 WebSocket만 사용
                if hasattr(self, '_api_rate_limited') and self._api_rate_limited:
                    # WebSocket에서만 데이터 조회
                    for tf, limit in timeframes:
                        try:
                            ws_data = self.get_websocket_kline_data(symbol, tf, limit)
                            results[tf] = ws_data
                        except Exception as e:
                            self.logger.debug(f"🚨 Rate Limit 상태 - WebSocket 조회 실패: {symbol} {tf}")
                            results[tf] = None
                else:
                    # 정상 상태: get_ohlcv_data 메서드 사용 (WebSocket 우선 + API 폴백)
                    future_to_timeframe = {
                        executor.submit(self.get_ohlcv_data, symbol, tf, limit): tf
                        for tf, limit in timeframes
                    }
                    
                    for future in as_completed(future_to_timeframe):
                        timeframe = future_to_timeframe[future]
                        try:
                            df_result = future.result(timeout=5)  # 타임아웃 3→5초로 증가
                            results[timeframe] = df_result
                            
                            # Rate Limit 감지시 즉시 중단
                            if hasattr(self, '_api_rate_limited') and self._api_rate_limited:
                                self.logger.warning(f"🚨 Rate Limit 감지 - 병렬 조회 중단")
                                break
                                
                        except Exception as e:
                            # API 에러 감지 및 Rate Limit 플래그 설정
                            error_str = str(e).lower()
                            if ("418" in str(e) or "429" in str(e) or 
                                "too many requests" in error_str or "rate limit" in error_str):
                                self.logger.error(f"🚨 병렬 조회 중 Rate Limit 감지: {symbol} {timeframe} - {e}")
                                self._api_rate_limited = True
                                self._last_rate_limit_check = time.time()
                                results[timeframe] = None
                                break  # 즉시 중단
                            else:
                                # ⚡ 스캔 모드시 디버그 출력 스킵
                                if not self._scan_mode:
                                    self._write_debug_log(f"[ERROR] [{clean_symbol}] {timeframe} 조회 실패: {e}")
                                results[timeframe] = None
            
            # 결과 할당
            df_1m = results.get('1m')
            df_3m = results.get('3m') 
            df_5m = results.get('5m')
            df_15m = results.get('15m')
            df_1d = results.get('1d')
            
            # 최소 데이터 확인
            available_count = sum(1 for df in [df_1m, df_3m, df_5m, df_15m, df_1d] if df is not None and len(df) >= 3)
            if available_count < 3:  # 5개 중 3개 이상은 있어야 분석
                return None
                
            self.logger.debug(f"⚡ [{clean_symbol}] 병렬조회: {available_count}/5 성공")
            
            # 🔍 데이터 확보 후 바로 전략 분석 시도 (디버깅용)
            if available_count >= 3:
                try:
                    # MA 계산 가능 여부 사전 확인
                    if df_3m is not None and len(df_3m) >= 100:
                        result = self.check_surge_entry_conditions(symbol, df_1m, df_3m, df_1d, df_15m, df_5m, 0)
                        if isinstance(result, tuple) and len(result) == 2:
                            status, conditions = result
                            if status:
                                print(f"✅ [{clean_symbol}] 진입 조건 만족: {status}")
                            else:
                                # 조건 미충족 로그 제거 (성능 최적화)
                                # 250ms 목표 달성을 위해 불필요한 로그 출력 제거
                                pass
                    else:
                        print(f"⚠️ [{clean_symbol}] 데이터 부족 - 3분봉 {len(df_3m) if df_3m is not None else 0}개")
                except Exception as e:
                    if "'ma80'" in str(e):
                        # MA 계산 실패 메시지 조용히 처리 (화면 정리)
                        # print(f"⚠️ [{clean_symbol}] MA 계산 실패 - 기술지표 계산 불가")
                        pass
                    else:
                        print(f"❌ [{clean_symbol}] 전략 분석 실패: {e}")
            
            return df_1m, df_3m, df_5m, df_15m, df_1d
            
        except Exception as e:
            # ⚡ 스캔 모드시 디버그 출력 스킵
            if not self._scan_mode:
                self._write_debug_log(f"[ERROR] [{clean_symbol}] 병렬 조회 실패: {e}")
            return None
    
    def _smart_hybrid_data_fetch(self, symbol, clean_symbol):
        """스마트 하이브리드: WebSocket 전용 (1m 제거)"""
        try:
            # ⚡ WebSocket 버퍼 확인 (1m 제외)
            ws_3m = self.get_websocket_kline_data(symbol, '3m', 300)
            ws_5m = self.get_websocket_kline_data(symbol, '5m', 100)
            ws_15m = self.get_websocket_kline_data(symbol, '15m', 500)
            ws_1d = self.get_websocket_kline_data(symbol, '1d', 100)

            # WebSocket 데이터 충분도 확인 (MA480 계산 가능 여부)
            ws_sufficient = (
                ws_3m is not None and len(ws_3m) >= 100 and
                ws_15m is not None and len(ws_15m) >= 480
            )

            if ws_sufficient:
                # 🚀 WebSocket 데이터 충분 - 초고속 모드
                self.logger.debug(f"⚡ [{clean_symbol}] WebSocket 충분 - 0ms 응답")
                return None, ws_3m, ws_5m, ws_15m, ws_1d  # df_1m은 None
            else:
                # ⚡ WebSocket 전용 모드: 데이터 부족시 스킵
                self.logger.debug(f"⚠️ [{clean_symbol}] WebSocket 데이터 부족 - 스킵")
                return None
                
        except Exception as e:
            # ⚡ 스캔 모드시 디버그 출력 스킵
            if not self._scan_mode:
                self._write_debug_log(f"[ERROR] [{clean_symbol}] 스마트 하이브리드 실패: {e}")
            return None
    
    def on_websocket_kline_update(self, symbol, timeframe, kline_data):
        """WebSocket 스캔 전용 콜백 - kline 데이터를 버퍼에 저장"""
        try:
            # Kline 데이터 버퍼에 저장
            self.update_websocket_kline(symbol, timeframe, kline_data)
            
            # 🚀 다른 타임프레임 데이터 생성 (1분봉으로부터)
            self._generate_higher_timeframes_from_1m(symbol)
            
            # 2시간봉 최적화 필터 캐시 업데이트
            if hasattr(self, 'optimized_filter') and self.optimized_filter:
                # 매 2시간 정각마다 2시간봉 캐시 업데이트 (간소화된 로직)
                current_time = time.time()
                if not hasattr(self, '_last_2h_update'):
                    self._last_2h_update = 0
                
                # 10분마다 2시간봉 캐시 갱신 체크 (성능 최적화)
                if current_time - self._last_2h_update > 600:  # 10분
                    try:
                        # 2시간봉 추정 데이터 생성 (1분봉 120개로 근사)
                        if hasattr(self, '_websocket_kline_buffer'):
                            buffer_key = f"{symbol}_1m"
                            if buffer_key in self._websocket_kline_buffer:
                                kline_1m_data = self._websocket_kline_buffer[buffer_key]
                                if len(kline_1m_data) >= 120:  # 2시간치 1분봉
                                    # 2시간봉 데이터 근사 생성
                                    recent_120 = kline_1m_data[-120:]  # 최근 2시간
                                    estimated_2h = {
                                        't': recent_120[-1][0],  # 최신 timestamp
                                        'o': recent_120[0][1],   # 시가
                                        'h': max(candle[2] for candle in recent_120),  # 최고가
                                        'l': min(candle[3] for candle in recent_120),  # 최저가
                                        'c': recent_120[-1][4],  # 종가
                                        'v': sum(candle[5] for candle in recent_120)   # 거래량
                                    }
                                    
                                    # 2시간봉 캐시 업데이트
                                    self.optimized_filter.update_2h_cache_from_websocket(symbol, estimated_2h)
                                    
                        self._last_2h_update = current_time
                    except Exception as cache_error:
                        pass  # 캐시 업데이트 실패는 조용히 처리
            
            # 다른 타임프레임도 추론하여 업데이트 (성능 최적화)
            # 실제로는 각 타임프레임별로 별도 구독해야 하지만, 
            # 스캔 성능을 위해 1분봉에서 다른 타임프레임도 근사 생성
            
        except Exception as e:
            self.logger.error(f"WebSocket 스캔 콜백 실패 ({symbol}): {e}")
    
    def _force_preload_websocket_buffer(self, symbol, timeframe, limit=1000):
        """WebSocket 버퍼 강제 프리로딩 - Rate limit 감지시 API 호출 방지"""
        try:
            if not hasattr(self, '_websocket_kline_buffer'):
                self._websocket_kline_buffer = {}
            
            # Rate limit 감지 플래그 확인
            if not hasattr(self, '_api_rate_limited'):
                self._api_rate_limited = False
            
            # Rate limit 회복 체크 (2분마다)
            if not hasattr(self, '_last_rate_limit_check'):
                self._last_rate_limit_check = 0
            
            current_time = time.time()
            if self._api_rate_limited and (current_time - self._last_rate_limit_check) > 120:  # 2분
                self._last_rate_limit_check = current_time
                # Rate limit 회복 테스트
                try:
                    test_response = self.exchange.fetch_ticker('BTCUSDT')
                    if test_response:
                        self._api_rate_limited = False
                        self._write_debug_log("✅ Rate limit 회복 확인 - API 호출 재개")
                        print("✅ Rate limit 회복됨 - API 호출 재개")
                except:
                    self._write_debug_log("⚠️ Rate limit 여전히 활성 상태")
                    pass
            
            # 심볼 형식 통일 (BTC/USDT:USDT -> BTCUSDT)
            ws_symbol = symbol.replace('/USDT:USDT', '').replace('/', '')
            buffer_key = f"{symbol}_{timeframe}"
            
            # Rate limit 상태에서는 API 호출 건너뛰기
            if self._api_rate_limited:
                self._write_debug_log(f"[{symbol.replace('/USDT:USDT', '')}] Rate limit 감지 - API 호출 건너뛰기 ({timeframe})")
                
                # WebSocket 구독만 활성화 (API 호출 없이) - 배치 구독으로 변경
                # 전략에 필요한 타임프레임만 구독 (전략A 비활성화로 1m 제외, 4h는 REST API 필터링 전용)
                if self.ws_kline_manager:
                    # 배치 구독 (1개 심볼 × 4개 타임프레임)
                    self.ws_kline_manager.subscribe_batch(
                        symbols=[ws_symbol],
                        timeframes=['3m', '5m', '15m', '1d']
                    )
                return
            
            # ⚡ python-binance로 초기 데이터 로드 (Rate limit 없을 때만)
            try:
                if self.ws_kline_manager:
                    # WebSocket 구독 및 초기 히스토리 로드 (배치 구독) - 4h는 REST API 필터링 전용
                    self.ws_kline_manager.subscribe_batch(
                        symbols=[ws_symbol],
                        timeframes=['3m', '5m', '15m', '1d'],
                        load_history=True  # 하이브리드: 초기 히스토리 로드
                    )

                    self._write_debug_log(f"[{symbol.replace('/USDT:USDT', '')}] WebSocket 구독 및 초기 히스토리 로드 완료 ({timeframe})")
                        
                else:
                    self._write_debug_log(f"[{symbol.replace('/USDT:USDT', '')}] 프리로딩 실패: 데이터 없음 ({timeframe})")
                    
            except Exception as e:
                # Rate limit 에러 감지
                if "418" in str(e) or "too many requests" in str(e).lower():
                    self._api_rate_limited = True
                    self._write_debug_log(f"[{symbol.replace('/USDT:USDT', '')}] Rate limit 감지 - API 호출 중단 ({timeframe})")
                else:
                    self._write_debug_log(f"[{symbol.replace('/USDT:USDT', '')}] 프리로딩 실패: {e} ({timeframe})")
                
        except Exception as e:
            # Rate limit 에러 감지
            if "418" in str(e) or "too many requests" in str(e).lower():
                self._api_rate_limited = True
                self.logger.warning(f"Rate limit 감지 - API 호출 중단: {symbol}")
            else:
                self.logger.error(f"WebSocket 버퍼 프리로딩 실패 ({symbol}, {timeframe}): {e}")
    
    def update_websocket_subscriptions(self, filtered_symbols):
        """
        필터링된 심볼 추적 업데이트 (WebSocket 구독 없이)

        ⚡ 새로운 아키텍처:
        - WebSocket 구독 제거 (ConnectionResetError 방지)
        - REST API만 사용 (안정적이고 빠름)
        - scan_symbols()에서 각 심볼이 필요할 때 REST API로 데이터 로드
        - 병렬 처리로 200 symbols × 4 timeframes in ~30-60초
        """
        try:
            print(f"🔍 WebSocket 구독 업데이트 시작: {len(filtered_symbols)}개 필터링된 심볼")
            
            if not self.ws_kline_manager:
                print("❌ WebSocket 매니저가 없음 - 구독 불가")
                return
                
            if not hasattr(self, '_dynamic_websocket_subscription'):
                print("❌ 동적 구독 시스템이 비활성화됨")
                return
            
            print("✅ WebSocket 매니저와 동적 구독 시스템 확인됨")
            
            # 심볼 형식 변환 (BTC/USDT:USDT → BTCUSDT)
            target_symbols = set()
            for symbol in filtered_symbols:
                ws_symbol = symbol.replace('/USDT:USDT', '').replace('/', '')
                if not ws_symbol.endswith('USDT'):
                    ws_symbol += 'USDT'
                target_symbols.add(ws_symbol)
            
            print(f"🔄 심볼 형식 변환 완료: {len(target_symbols)}개 대상 심볼")
            print(f"📊 현재 구독 중인 심볼: {len(self._subscribed_symbols)}개")
            
            # 새로 구독할 심볼들
            to_subscribe = target_symbols - self._subscribed_symbols
            
            # 구독 해제할 심볼들 (현재 구독 중이지만 필터링에서 제외된 심볼들)
            to_unsubscribe = self._subscribed_symbols - target_symbols
            
            print(f"📡 새로 구독할 심볼: {len(to_subscribe)}개")
            print(f"🗑️ 구독 해제할 심볼: {len(to_unsubscribe)}개")
            
            # ⚡ WebSocket 구독 활성화 (배치 처리로 Rate Limit 방지)
            if to_subscribe:
                symbols_list = list(to_subscribe)
                total_symbols = len(symbols_list)

                print(f"📡 새로운 {total_symbols}개 심볼 WebSocket 구독 시작 (안정화 배치 처리)")

                # 배치 크기: 최대 75개씩 (75심볼 × 4타임프레임 = 300개 연결)
                # ⚡ 안정성 우선: 300개 이하 제한 + 충분한 딜레이
                batch_size = 75
                total_batches = (total_symbols + batch_size - 1) // batch_size

                print(f"   💡 고속 모드: 배치당 {batch_size}심볼 × 4타임프레임 = {batch_size*4}개 연결 (히스토리 병렬 로드)")
                print(f"   ⏱️ 총 {total_batches}개 배치 예상 소요 시간: 약 {total_batches * 0.5:.0f}초 (병렬 처리)")

                subscribed_count = 0
                failed_count = 0

                for batch_idx in range(total_batches):
                    start_idx = batch_idx * batch_size
                    end_idx = min(start_idx + batch_size, total_symbols)
                    batch_symbols = symbols_list[start_idx:end_idx]

                    try:
                        # 배치 구독 (4h 제외 - REST API 필터링 전용)
                        # ⚡ 안정화 모드: 300개 이하 제한 + 에러 무시 + 느린 속도
                        try:
                            self.ws_kline_manager.subscribe_batch(
                                symbols=batch_symbols,
                                timeframes=['3m', '5m', '15m', '1d'],
                                load_history=True,   # ✅ 하이브리드: 초기만 REST API
                                batch_size=25,       # 10 → 25 (속도 개선!)
                                delay=3.0,           # 10.0 → 3.0초 (3배 빠르게!)
                                max_workers=2        # 1 → 2 (2배 빠르게!)
                            )
                            subscribed_count += len(batch_symbols)
                            print(f"   ✅ 배치 {batch_idx + 1}/{total_batches} 완료 ({subscribed_count}/{total_symbols}개)")
                        except:
                            # WebSocket 오류는 완전히 무시하고 계속 진행
                            failed_count += len(batch_symbols)
                            print(f"   ⚠️ 배치 {batch_idx + 1} 구독 실패 (무시하고 계속)")

                        # 배치 간 안전 딜레이 (Rate Limit 방지)
                        if batch_idx < total_batches - 1:
                            import time
                            wait_time = 1.5  # 1.5초 대기 (Rate Limit 방지)
                            time.sleep(wait_time)

                    except:
                        # 최상위 예외 처리 - 모든 오류 무시
                        failed_count += len(batch_symbols)
                        print(f"   ⚠️ 배치 {batch_idx + 1} 완전 실패 (무시하고 계속)")

                # 구독 추적 업데이트
                self._subscribed_symbols.update(to_subscribe)

                print(f"✅ WebSocket 구독 완료: {subscribed_count}개 성공, {failed_count}개 실패")
                print(f"📊 총 구독 심볼: {len(self._subscribed_symbols)}개")
                self.logger.info(f"WebSocket 구독: {subscribed_count}/{total_symbols}개 성공")
            else:
                print("ℹ️ 새로 구독할 심볼이 없음")
            
            # 불필요한 심볼들 WebSocket 구독 해제 및 캐시 제거
            if to_unsubscribe:
                print(f"🗑️ {len(to_unsubscribe)}개 심볼 구독 해제 및 캐시 제거 중...")
                removed_cache_count = 0
                for symbol in to_unsubscribe:
                    # WebSocket 구독 해제 (4h 제외 - REST API 필터링 전용)
                    try:
                        for tf in ['3m', '5m', '15m', '1d']:
                            self.ws_kline_manager.unsubscribe_kline(symbol, tf)
                    except Exception as e:
                        self.logger.debug(f"구독 해제 실패 ({symbol}): {e}")

                    # 캐시 제거
                    ws_symbol = symbol.replace('/USDT:USDT', '').replace('/', '')
                    if not ws_symbol.endswith('USDT'):
                        ws_symbol += 'USDT'

                    for tf in ['3m', '5m', '15m', '1d']:
                        for limit in [500, 100, 700, 150]:  # 각 타임프레임별 limit (4h 제외)
                            cache_key = f"{symbol}_{tf}_{limit}"
                            if cache_key in self._ohlcv_cache:
                                del self._ohlcv_cache[cache_key]
                                removed_cache_count += 1

                    self._subscribed_symbols.discard(symbol)

                print(f"✅ WebSocket 구독 해제 및 캐시 제거 완료: {removed_cache_count}개 항목")
                self.logger.debug(f"구독 해제: {len(to_unsubscribe)}개 심볼, {removed_cache_count}개 캐시 항목")
            
            if to_subscribe or to_unsubscribe:
                total_subscribed = len(self._subscribed_symbols)
                cache_size = len(self._ohlcv_cache)
                print(f"🎯 심볼 추적 업데이트 완료: {total_subscribed}개 심볼, {cache_size}개 캐시")
            
        except Exception as e:
            self.logger.error(f"WebSocket 구독 업데이트 실패: {e}")
    
    def _subscribe_initial_major_symbols(self):
        """초기 심볼 구독 - 멀티 타임프레임 WebSocket 구독 (최적화)"""
        try:
            if not self.ws_kline_manager:
                print("❌ WebSocket 매니저가 없음 - 초기 구독 불가")
                return
            
            # 초기 고정 심볼 구독 제거 - 필터링된 심볼만 동적 구독
            initial_symbols = []  # 빈 목록으로 시작
            
            print(f"🚀 WebSocket 매니저 초기화 완료 - 필터링된 심볼만 동적 구독 방식")
            
            # WebSocket 버퍼 초기화
            if not hasattr(self, '_websocket_kline_buffer'):
                self._websocket_kline_buffer = {}
            
            print(f"✅ WebSocket 매니저 준비 완료:")
            print(f"   🎯 지원 타임프레임: 3m, 5m, 15m, 4h, 1d")
            print(f"   🔄 동적 구독 방식: 필터링 통과 심볼만 구독")
            print(f"   💾 버퍼 초기화 완료")
            
            # 5초 후 버퍼 상태 확인
            import threading
            def check_buffer_after_delay():
                import time
                time.sleep(5)  # Rate Limit 방지
                if hasattr(self, '_websocket_kline_buffer'):
                    buffer_count = len(self._websocket_kline_buffer)
                    print(f"🔍 5초 후 WebSocket 버퍼 상태: {buffer_count}개 심볼 버퍼링 중")
                    
                    # 데이터가 있는 버퍼만 카운트
                    data_buffers = 0
                    for key, data in self._websocket_kline_buffer.items():
                        if len(data) > 0:
                            data_buffers += 1
                    print(f"📊 데이터가 있는 버퍼: {data_buffers}개")
            
            threading.Thread(target=check_buffer_after_delay, daemon=True).start()
            
        except Exception as e:
            self.logger.error(f"초기 심볼 구독 실패: {e}")
            print(f"❌ 초기 심볼 구독 실패: {e}")
    
    def _subscribe_major_symbols_for_scan(self):
        """레거시 함수 - 동적 구독 시스템으로 대체됨"""
        # 이 함수는 더 이상 사용되지 않음
        # update_websocket_subscriptions()가 동적으로 처리
        pass
    
    def calculate_indicators(self, df):
        """기술적 지표 계산"""
        try:
            if df is None:
                return None

            # 완화된 데이터 요구사항 - WebSocket 실시간 데이터에 맞춰 조정
            # 데이터 길이에 따라 필요 최소 데이터 수 결정 (매우 완화된 기준)
            if len(df) >= 300:
                min_required = 100  # 기본 지표 계산 가능한 최소 수준
            elif len(df) >= 200:
                min_required = 80   # 더 완화된 기준
            elif len(df) >= 100:
                min_required = 50   # 최소 기준
            else:
                min_required = 30   # 극한 완화 - 기본 MA만이라도

            if len(df) < min_required:
                self._write_debug_log(f"지표 계산 실패: 데이터 부족 (길이:{len(df)}, 필요:{min_required})")
                # 임시: 극한 완화 - 최소 20개만 있어도 계산 시도
                if len(df) >= 20:
                    print(f"⚠️ 데이터 부족하지만 {len(df)}개로 지표 계산 시도")
                    # 계속 진행
                else:
                    return None

            # 이동평균 (길이에 따라 적응적 계산)
            df['ma5'] = df['close'].rolling(window=5).mean()
            df['ma20'] = df['close'].rolling(window=min(20, len(df))).mean()
            df['ma80'] = df['close'].rolling(window=min(80, len(df))).mean()
            
            # MA480은 데이터가 충분할 때만 계산
            if len(df) >= 480:
                df['ma480'] = df['close'].rolling(window=480).mean()
            else:
                # 데이터가 부족하면 MA200 또는 최대 가능한 길이로 대체
                ma_window = min(200, len(df) // 2) if len(df) > 20 else len(df) // 2
                if ma_window > 0:
                    df['ma480'] = df['close'].rolling(window=ma_window).mean()
                else:
                    df['ma480'] = df['close']

            # 볼린저 밴드 (적응적 계산)
            for period in [20, 80, 200]:
                actual_period = min(period, len(df))
                if actual_period >= 5:  # 최소 5개는 있어야 의미있음
                    rolling_mean = df['close'].rolling(window=actual_period).mean()
                    rolling_std = df['close'].rolling(window=actual_period).std()
                    df[f'bb{period}_upper'] = rolling_mean + (rolling_std * 2)
                    df[f'bb{period}_lower'] = rolling_mean - (rolling_std * 2)
                else:
                    df[f'bb{period}_upper'] = df['close']
                    df[f'bb{period}_lower'] = df['close']
            
            # BB480과 BB600은 충분한 데이터가 있을 때만 계산
            for period in [480, 600]:
                if len(df) >= period:
                    rolling_mean = df['close'].rolling(window=period).mean()
                    rolling_std = df['close'].rolling(window=period).std()
                    df[f'bb{period}_upper'] = rolling_mean + (rolling_std * 2)
                    df[f'bb{period}_lower'] = rolling_mean - (rolling_std * 2)
                else:
                    # 🚀 개선된 대체 계산: 가용 데이터로 최대한 계산
                    max_window = min(len(df) - 5, max(20, len(df) // 2))  # 최소 20, 최대 절반
                    if max_window >= 20:
                        # 가용한 최대 기간으로 볼린저 밴드 계산
                        rolling_mean = df['close'].rolling(window=max_window).mean()
                        rolling_std = df['close'].rolling(window=max_window).std()
                        # BB600은 더 넓은 밴드를 가지도록 조정 (표준편차 배수 증가)
                        std_multiplier = 2.5 if period == 600 else 2.2  # 600기간은 더 넓게
                        df[f'bb{period}_upper'] = rolling_mean + (rolling_std * std_multiplier)
                        df[f'bb{period}_lower'] = rolling_mean - (rolling_std * std_multiplier)
                    elif f'bb200_upper' in df.columns:
                        # BB200 기반 확장
                        expansion_factor = 1.3 if period == 600 else 1.2
                        df[f'bb{period}_upper'] = df['bb200_upper'] * expansion_factor
                        df[f'bb{period}_lower'] = df['bb200_lower'] * (2 - expansion_factor)
                    else:
                        # MA 기반 최후 대안
                        expansion_factor = 1.15 if period == 600 else 1.1
                        df[f'bb{period}_upper'] = df['ma480'] * expansion_factor
                        df[f'bb{period}_lower'] = df['ma480'] * (2 - expansion_factor)

            # 일목균형표
            # 기준선 (Kijun-sen) = (26일 최고가 + 26일 최저가) / 2
            df['ichimoku_base'] = (df['high'].rolling(window=26).max() + df['low'].rolling(window=26).min()) / 2
            # 전환선 (Tenkan-sen) = (9일 최고가 + 9일 최저가) / 2
            df['ichimoku_conversion'] = (df['high'].rolling(window=9).max() + df['low'].rolling(window=9).min()) / 2

            # SuperTrend 지표 추가 (누락된 중요 지표)
            if len(df) >= 20:  # SuperTrend 계산에 필요한 최소 데이터
                try:
                    # ATR 계산
                    df['tr'] = np.maximum(
                        df['high'] - df['low'],
                        np.maximum(
                            abs(df['high'] - df['close'].shift(1)),
                            abs(df['low'] - df['close'].shift(1))
                        )
                    )
                    df['atr'] = df['tr'].rolling(window=10).mean()
                    
                    # SuperTrend 계산 (10-3 설정)
                    hl2 = (df['high'] + df['low']) / 2
                    multiplier = 3.0
                    df['upper_band'] = hl2 + (multiplier * df['atr'])
                    df['lower_band'] = hl2 - (multiplier * df['atr'])
                    
                    # SuperTrend 라인과 방향 계산
                    df['supertrend'] = 0.0
                    df['supertrend_direction'] = 0  # 1: 상승, -1: 하락
                    df['supertrend_signal'] = 0    # 별칭 (호환성)
                    
                    for i in range(10, len(df)):
                        prev_close = df['close'].iloc[i-1]
                        curr_close = df['close'].iloc[i]
                        upper_band = df['upper_band'].iloc[i]
                        lower_band = df['lower_band'].iloc[i]
                        prev_supertrend = df['supertrend'].iloc[i-1] if i > 10 else upper_band
                        prev_direction = df['supertrend_direction'].iloc[i-1] if i > 10 else -1
                        
                        # SuperTrend 계산 로직
                        if prev_direction == 1:  # 이전이 상승 트렌드
                            if curr_close < lower_band:
                                df.loc[df.index[i], 'supertrend'] = upper_band
                                df.loc[df.index[i], 'supertrend_direction'] = -1
                                df.loc[df.index[i], 'supertrend_signal'] = -1
                            else:
                                df.loc[df.index[i], 'supertrend'] = max(lower_band, prev_supertrend)
                                df.loc[df.index[i], 'supertrend_direction'] = 1
                                df.loc[df.index[i], 'supertrend_signal'] = 1
                        else:  # 이전이 하락 트렌드
                            if curr_close > upper_band:
                                df.loc[df.index[i], 'supertrend'] = lower_band
                                df.loc[df.index[i], 'supertrend_direction'] = 1
                                df.loc[df.index[i], 'supertrend_signal'] = 1
                            else:
                                df.loc[df.index[i], 'supertrend'] = min(upper_band, prev_supertrend)
                                df.loc[df.index[i], 'supertrend_direction'] = -1
                                df.loc[df.index[i], 'supertrend_signal'] = -1
                    
                except Exception as st_error:
                    self.logger.warning(f"SuperTrend 계산 실패: {st_error}")
                    # SuperTrend 실패시 기본값 설정 (전략 우회를 위해)
                    df['supertrend'] = df['close']
                    df['supertrend_direction'] = 1  # 기본값을 상승으로 설정
                    df['supertrend_signal'] = 1

            # 최소 데이터 검증 (더 관대한 기준)
            recent_check = df.tail(10)
            
            # 기본 지표 검증
            ma20_valid = recent_check['ma20'].notna().sum()
            ma80_valid = recent_check['ma80'].notna().sum()
            
            if ma20_valid < 3 or ma80_valid < 3:
                self._write_debug_log(f"지표 계산 실패: 기본 MA 데이터 부족 (MA20:{ma20_valid}/10, MA80:{ma80_valid}/10)")
                return None
            
            # MA480은 조건부 검증 (충분한 데이터가 있을 때만)
            if len(df) >= 480:
                ma480_valid = recent_check['ma480'].notna().sum()
                if ma480_valid < 3:  # 5 -> 3으로 완화
                    self._write_debug_log(f"지표 계산 실패: MA480 데이터 부족 (유효:{ma480_valid}/10)")
                    return None

            # BB600 검증: 원래 계산 또는 대체 계산 모두 허용
            if 'bb600_upper' in df.columns:
                bb600_valid = recent_check['bb600_upper'].notna().sum()
                if bb600_valid < 1:  # 2 -> 1로 완화 (대체 계산도 허용)
                    self._write_debug_log(f"지표 계산 실패: BB600 데이터 부족 (유효:{bb600_valid}/1) - 대체계산 포함")
                    return None
                # 대체 계산 사용 시 디버그 정보
                if len(df) < 600:
                    self._write_debug_log(f"[INFO] BB600 대체계산 사용: 데이터{len(df)}개로 추정계산")

            return df
        except Exception as e:
            self.logger.error(f"지표 계산 실패: {e}")
            return None

    def calculate_supertrend(self, df, period=10, multiplier=3.0):
        """SuperTrend 지표 계산"""
        try:
            if df is None or len(df) < period:
                return None
            
            # ATR 계산
            df['tr'] = np.maximum(
                df['high'] - df['low'],
                np.maximum(
                    abs(df['high'] - df['close'].shift(1)),
                    abs(df['low'] - df['close'].shift(1))
                )
            )
            df['atr'] = df['tr'].rolling(window=period).mean()
            
            # SuperTrend 계산
            hl2 = (df['high'] + df['low']) / 2
            df['upper_band'] = hl2 + (multiplier * df['atr'])
            df['lower_band'] = hl2 - (multiplier * df['atr'])
            
            # SuperTrend 라인 계산
            df['supertrend'] = 0.0
            df['supertrend_direction'] = 0  # 1: 상승, -1: 하락
            
            for i in range(period, len(df)):
                prev_close = df['close'].iloc[i-1]
                curr_close = df['close'].iloc[i]
                upper_band = df['upper_band'].iloc[i]
                lower_band = df['lower_band'].iloc[i]
                prev_supertrend = df['supertrend'].iloc[i-1] if i > period else upper_band
                prev_direction = df['supertrend_direction'].iloc[i-1] if i > period else -1
                
                # SuperTrend 계산 로직
                if prev_direction == 1:  # 이전이 상승 트렌드
                    if curr_close < lower_band:
                        df.loc[df.index[i], 'supertrend'] = upper_band
                        df.loc[df.index[i], 'supertrend_direction'] = -1
                    else:
                        df.loc[df.index[i], 'supertrend'] = max(lower_band, prev_supertrend)
                        df.loc[df.index[i], 'supertrend_direction'] = 1
                else:  # 이전이 하락 트렌드
                    if curr_close > upper_band:
                        df.loc[df.index[i], 'supertrend'] = lower_band
                        df.loc[df.index[i], 'supertrend_direction'] = 1
                    else:
                        df.loc[df.index[i], 'supertrend'] = min(upper_band, prev_supertrend)
                        df.loc[df.index[i], 'supertrend_direction'] = -1
            
            return df
            
        except Exception as e:
            self._write_debug_log(f"SuperTrend 계산 실패: {e}", "ERROR")
            return None
    
    def check_5m_supertrend_entry_signal(self, symbol, df_5m):
        """5분봉 SuperTrend(10-3) 진입 시그널 체크"""
        try:
            if df_5m is None or len(df_5m) < 20:
                return False
            
            # SuperTrend 계산
            df_5m_calc = self.calculate_supertrend(df_5m, period=10, multiplier=3.0)
            if df_5m_calc is None:
                return False
            
            # 🚀 최근 5봉 이내에서 진입 시그널 찾기 (지연 최소화)
            recent_5 = df_5m_calc.tail(5)
            
            # 컬럼명 확인 및 대체
            direction_col = None
            if 'supertrend_direction' in df_5m_calc.columns:
                direction_col = 'supertrend_direction'
            elif 'supertrend_signal' in df_5m_calc.columns:
                direction_col = 'supertrend_signal'
            else:
                # 컬럼이 없으면 임시로 SuperTrend 조건 우회
                self.logger.debug(f"SuperTrend 컬럼 없음 - 조건 우회: {symbol}")
                return True
            
            # 진입 시그널 (완화된 조건): 
            # 1) 하락(-1)에서 상승(1)으로 전환 OR 2) 현재 상승추세(1) 상태
            
            # 최신 상태 확인
            latest_direction = recent_5.iloc[-1][direction_col]
            
            # 🔍 디버깅: SuperTrend 5봉 조건 로그
            clean_symbol = symbol.replace('/USDT:USDT', '')
            self.logger.debug(f"SuperTrend 5봉조건 체크 ({clean_symbol}): 현재방향={latest_direction}, 컬럼={direction_col}")
            
            # 최근 5봉의 모든 방향 값 로깅
            direction_values = recent_5[direction_col].tolist()
            self.logger.debug(f"SuperTrend 방향값들 ({clean_symbol}): {direction_values}")
            
            # 조건 1: 현재 상승추세(1)인 경우
            if latest_direction == 1:
                self.logger.debug(f"SuperTrend 5봉조건 통과 ({clean_symbol}): 현재 상승추세")
                return True
            
            # 조건 2: 최근 5봉 이내 하락→상승 전환 (지연 최소화)
            for i in range(1, len(recent_5)):
                prev_direction = recent_5.iloc[i-1][direction_col]
                curr_direction = recent_5.iloc[i][direction_col]
                
                # 하락(-1)에서 상승(1)으로 전환시 매수 시그널
                if prev_direction == -1 and curr_direction == 1:
                    self.logger.debug(f"SuperTrend 5봉조건 통과 ({symbol}): 전환신호 발견")
                    return True
            
            # 조건 3: 임시 완화 - 현재가가 SuperTrend 값보다 높으면 상승 신호로 간주
            if 'supertrend' in df_5m_calc.columns:
                latest_price = recent_5.iloc[-1]['close']
                latest_st_value = recent_5.iloc[-1]['supertrend']
                
                self.logger.debug(f"SuperTrend 조건3 체크 ({clean_symbol}): 현재가={latest_price:.6f}, ST값={latest_st_value:.6f}")
                
                if latest_price > latest_st_value:
                    self.logger.debug(f"SuperTrend 5봉조건 통과 ({clean_symbol}): 현재가({latest_price:.6f}) > ST값({latest_st_value:.6f})")
                    return True
            else:
                self.logger.debug(f"SuperTrend 조건3 스킵 ({clean_symbol}): supertrend 컬럼 없음")
            
            self.logger.debug(f"SuperTrend 5봉조건 실패 ({clean_symbol}): 모든 조건 미충족")
            return False
        except Exception as e:
            self.logger.error(f"5분봉 SuperTrend 진입 시그널 체크 실패 ({symbol}): {e}")
            return False
    
    def check_high_surge_conditions(self, symbol, df_1m, change_24h):
        """20% 이상 급등 종목을 위한 간소화된 조건 체크"""
        try:
            conditions = []
            failed_conditions = 0
            latest = df_1m.iloc[-1]
            
            conditions.append(f"[급등특별] 24h상승률: +{change_24h:.1f}%")
            
            # 1. 30봉 이내 ma80-ma480 골든크로스
            ma80_ma480_golden = find_golden_cross_vectorized(df_1m, 'ma80', 'ma480', recent_n=30)
            condition_1 = ma80_ma480_golden
            conditions.append(f"[급등-1] 30봉이내 MA80-MA480 골든크로스: {condition_1}")
            if not condition_1:
                failed_conditions += 1
            
            # 2. 골든크로스 이후 진입 조건
            condition_2 = False
            condition_2_details = ""
            
            if condition_1:  # 골든크로스가 있을 때만 체크
                # 30봉 내에서 MA80-MA480 골든크로스 발생 시점 찾기
                golden_cross_index = None
                recent_30 = df_1m.tail(30)
                
                if len(recent_30) >= 2 and 'ma80' in df_1m.columns and 'ma480' in df_1m.columns:
                    for i in range(len(recent_30) - 1):
                        prev_ma80 = recent_30.iloc[i]['ma80'] 
                        prev_ma480 = recent_30.iloc[i]['ma480']
                        curr_ma80 = recent_30.iloc[i+1]['ma80']
                        curr_ma480 = recent_30.iloc[i+1]['ma480']
                        
                        if (pd.notna(prev_ma80) and pd.notna(prev_ma480) and 
                            pd.notna(curr_ma80) and pd.notna(curr_ma480)):
                            if prev_ma80 <= prev_ma480 and curr_ma80 > curr_ma480:
                                golden_cross_index = i + 1
                                break
                
                if golden_cross_index is not None:
                    # 골든크로스 이후 데이터 추출 (최대 60봉 범위)
                    after_golden_cross = recent_30.iloc[golden_cross_index:]
                    lookback_period = min(60, len(after_golden_cross))
                    target_data = after_golden_cross.head(lookback_period)  # 골든크로스 이후 60봉 범위
                    
                    condition_2_details = f"골든크로스 후 {len(after_golden_cross)}봉 경과, 60봉 범위내 {lookback_period}봉 분석"
                    
                    if len(target_data) >= 2:
                        # MA5-일목전환선 데드크로스 찾기
                        ma5_conversion_dead_found = False
                        dead_cross_index = None
                        
                        if 'ichimoku_conversion' in df_1m.columns:
                            # 60봉 범위 내에서 20봉 이내 데드크로스 찾기
                            search_limit = min(20, len(target_data) - 1)
                            for i in range(search_limit):
                                prev_ma5 = target_data.iloc[i]['ma5']
                                prev_conversion = target_data.iloc[i]['ichimoku_conversion']
                                curr_ma5 = target_data.iloc[i+1]['ma5']
                                curr_conversion = target_data.iloc[i+1]['ichimoku_conversion']
                                
                                if (pd.notna(prev_ma5) and pd.notna(prev_conversion) and 
                                    pd.notna(curr_ma5) and pd.notna(curr_conversion)):
                                    if prev_ma5 >= prev_conversion and curr_ma5 < curr_conversion:
                                        ma5_conversion_dead_found = True
                                        dead_cross_index = i + 1
                                        break
                        
                        # 3봉이내 전환선 골든크로스와 MA20 골든크로스 동시 체크
                        recent_3 = df_1m.tail(3)
                        conversion_and_ma20_cross = False
                        
                        if len(recent_3) >= 1:
                            for _, row in recent_3.iterrows():
                                if (pd.notna(row['open']) and pd.notna(row['close']) and 
                                    pd.notna(row['ichimoku_conversion']) and pd.notna(row['ma20'])):
                                    # 시가<전환선 and 종가>전환선 and 시가<ma20 and 종가>ma20
                                    conversion_cross = (row['open'] < row['ichimoku_conversion'] and 
                                                      row['close'] > row['ichimoku_conversion'])
                                    ma20_cross = (row['open'] < row['ma20'] and row['close'] > row['ma20'])
                                    
                                    if conversion_cross and ma20_cross:
                                        conversion_and_ma20_cross = True
                                        break
                        
                        condition_2 = ma5_conversion_dead_found and conversion_and_ma20_cross
                        
                        if ma5_conversion_dead_found:
                            condition_2_details += f", MA5-전환선데드크로스발견(+{dead_cross_index}봉째)"
                        else:
                            condition_2_details += f", MA5-전환선데드크로스없음"
                        
                        if conversion_and_ma20_cross:
                            condition_2_details += f", 3봉이내 전환선&MA20 동시골든크로스:True"
                        else:
                            condition_2_details += f", 3봉이내 전환선&MA20 동시골든크로스:False"
                    else:
                        condition_2_details += ", 골든크로스 이후 데이터 부족"
                else:
                    condition_2_details = "30봉이내 MA80-MA480 골든크로스 없음"
            else:
                condition_2_details = "전제조건 미충족 (골든크로스 없음)"
            
            conditions.append(f"[급등-2] 골든크로스후 60봉범위내 20봉이내 진입조건: {condition_2}")
            conditions.append(f"  ㄴ {condition_2_details}")
            if not condition_2:
                failed_conditions += 1
            
            # 모든 조건 충족 여부
            is_signal = failed_conditions == 0
            
            return is_signal, conditions
            
        except Exception as e:
            self.logger.error(f"급등 조건 체크 실패 ({symbol}): {e}")
            return False, [f"[급등특별] 오류 발생: {str(e)}"]
    
    def check_surge_entry_conditions(self, symbol, df_1m, df_3m, df_1d, df_15m=None, df_5m=None, change_24h=0):
        """3분봉 1번째 전략 OR 3분봉 2번째 전략 조건 체크"""
        try:
            # 🔒 안전장치: 매개변수 초기화 확인
            if df_15m is None:
                df_15m = None  # 명시적 None 할당
            if df_5m is None:
                df_5m = None   # 명시적 None 할당
                
            # ⚡ 심볼 이름 정리 (디버깅 출력용)
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')

            conditions = []
            failed_conditions = 0

            # 24시간 상승률은 analyze_symbol에서 전달받음 (API 호출 제거)

            # === A전략(1분봉-15분봉 조합) 제거됨 - 사용자 요청에 따라 완전 삭제 ===

            # ⚡ 제외 조건: 3분봉 20봉 이내 시가대비 고가 30% 이상 급등 심볼 제외 (1분봉 제거)
            # 3분봉 20봉 = 60분 (1분봉 60봉과 동일한 시간)
            extreme_surge_60_candles = False
            if df_3m is not None and len(df_3m) >= 20:
                recent_20_3m = df_3m.tail(20)
                for _, row in recent_20_3m.iterrows():
                    if pd.notna(row['high']) and pd.notna(row['open']) and row['open'] > 0:
                        open_to_high_pct = ((row['high'] - row['open']) / row['open']) * 100
                        if open_to_high_pct >= 30.0:
                            extreme_surge_60_candles = True
                            break

            # 30% 이상 급등 심볼은 제외
            if extreme_surge_60_candles:
                conditions.append(f"[제외조건] 3분봉 20봉내 시가대비고가 30% 이상: True (심볼 제외)")
                self.logger.info(f"❌ {symbol} 제외: 3분봉 20봉내 시가대비고가 30% 이상 급등 감지")
                return False, conditions

            # A전략(1분봉-15분봉 조합) 조건들 제거됨 - 사용자 요청에 따라 완전 삭제

            # ========== [삭제됨] 기존 3분봉 전략 ==========
            # 기존 3분봉 전략 6개 조건 삭제됨 (사용자 요청에 따라 제거)
            passed_3m_new = False

            # ========== 3분봉 추가 조건 (비활성화) ==========
            # 3분봉 추가 조건: 200봉 이내 MA80-MA480 골든크로스 AND (조건A OR 조건B)
            strategy_3m_additional_enabled = False  # 🚫 비활성화 (전략C, D만 사용)
            strategy_3m_additional_met = False

            if strategy_3m_additional_enabled and df_3m is not None and len(df_3m) >= 40:  # 최소 40봉 필요 (BB80 돌파 조건용)
                # 3분봉 지표 계산
                df_3m_calc = self.calculate_indicators(df_3m)
                if df_3m_calc is not None:
                    # === 3분봉 통합 조건: (MA80<MA480 and 40봉이내 BB80상한선 돌파) OR 300봉이내 MA80-MA480 골든크로스 ===
                    condition_3m_unified = False
                    
                    # 🔍 상세 디버깅: 조건1 - MA80<MA480 and 40봉이내 BB80상한선 돌파
                    latest_3m = df_3m_calc.iloc[-1]
                    ma80_below_ma480 = False
                    
                    # 현재 MA80<MA480 체크
                    if ('ma80' in latest_3m.index and 'ma480' in latest_3m.index and
                        pd.notna(latest_3m['ma80']) and pd.notna(latest_3m['ma480'])):
                        ma80_below_ma480 = latest_3m['ma80'] < latest_3m['ma480']
                        
                    # 🔍 파일 디버깅 로그
                    ma80_val = f"{latest_3m['ma80']:.6f}" if pd.notna(latest_3m['ma80']) else "None"
                    ma480_val = f"{latest_3m['ma480']:.6f}" if pd.notna(latest_3m['ma480']) else "None"
                    debug_msg = f"[DEBUG-통합조건1] {symbol}: MA80<MA480={ma80_below_ma480}, MA80={ma80_val}, MA480={ma480_val}\n"
                    self._write_debug_log(debug_msg)
                    
                    # 🔍 상세 디버깅: 조건2 - 40봉이내 BB80 상한선 돌파
                    bb80_breakthrough_found = False
                    bb80_breakthrough_count = 0
                    if len(df_3m_calc) >= 40:
                        recent_40_3m = df_3m_calc.tail(40)
                        
                        # BB80 상한선 계산 필요 (기존에 bb80_upper 컬럼이 없을 수 있음)
                        if 'bb80_upper' not in df_3m_calc.columns:
                            # BB80 상한선을 임시로 계산
                            bb80_period = 80
                            bb80_std = 2.0
                            df_3m_calc['bb80_middle'] = df_3m_calc['close'].rolling(window=bb80_period).mean()
                            bb80_std_calc = df_3m_calc['close'].rolling(window=bb80_period).std()
                            df_3m_calc['bb80_upper'] = df_3m_calc['bb80_middle'] + (bb80_std_calc * bb80_std)
                        
                        for i, (_, row) in enumerate(recent_40_3m.iterrows()):
                            if (pd.notna(row['open']) and pd.notna(row['high']) and 
                                pd.notna(row['bb80_upper'])):
                                open_below_bb80 = row['open'] < row['bb80_upper']
                                high_above_bb80 = row['high'] > row['bb80_upper']
                                
                                if open_below_bb80 and high_above_bb80:
                                    bb80_breakthrough_count += 1
                                    if not bb80_breakthrough_found:
                                        bb80_breakthrough_found = True
                                        # 첫 번째 돌파 발견시 디버깅 로그
                                        debug_msg = f"[DEBUG-통합조건2] {symbol}: 첫번째 BB80돌파 발견! 인덱스={i}, 시가={row['open']:.6f}, 고가={row['high']:.6f}, BB80상한={row['bb80_upper']:.6f}\n"
                                        self._write_debug_log(debug_msg)
                        
                    # BB80 돌파 조건 디버깅 로그
                    debug_msg = f"[DEBUG-통합조건2] {symbol}: 40봉이내 BB80돌파={bb80_breakthrough_found}, 돌파횟수={bb80_breakthrough_count}, 검사대상봉수={len(recent_40_3m) if len(df_3m_calc) >= 40 else 0}\n"
                    self._write_debug_log(debug_msg)
                    
                    # 🔍 상세 디버깅: 조건2 - 300봉이내 MA80-MA480 골든크로스
                    ma80_ma480_golden_cross_300 = False
                    if len(df_3m_calc) >= 300:
                        ma80_ma480_golden_cross_300 = self._find_golden_cross(df_3m_calc, 'ma80', 'ma480', recent_n=300)
                    
                    debug_msg = f"[DEBUG-통합조건2] {symbol}: 300봉이내 MA80-MA480 골든크로스={ma80_ma480_golden_cross_300}\n"
                    self._write_debug_log(debug_msg)
                    
                    # 🔍 상세 디버깅: 최종 통합 조건 (OR 조건)
                    condition_1_with_bb80 = ma80_below_ma480 and bb80_breakthrough_found
                    condition_3m_unified = condition_1_with_bb80 or ma80_ma480_golden_cross_300
                    
                    # 통합 조건 결과 디버깅 로그
                    debug_msg = f"[DEBUG-통합조건최종] {symbol}: 통합조건={condition_3m_unified} (조건1={condition_1_with_bb80} [MA80<MA480={ma80_below_ma480} AND BB80돌파={bb80_breakthrough_found}] OR 조건2={ma80_ma480_golden_cross_300} [300봉골든크로스])\n"
                    self._write_debug_log(debug_msg)
                    
                    conditions.append(f"[3분봉 추가-조건1] MA80<MA480 AND BB80돌파: {condition_1_with_bb80}")
                    conditions.append(f"[3분봉 추가-조건2] 300봉이내 골든크로스: {ma80_ma480_golden_cross_300}")
                    
                    # 최종 3분봉 추가 조건
                    strategy_3m_additional_met = condition_3m_unified
                    conditions.append(f"[3분봉 추가] 최종: {strategy_3m_additional_met} (통합조건: {condition_3m_unified})")
                else:
                    strategy_3m_additional_met = False
                    conditions.append(f"[3분봉 추가] 3분봉 지표 계산 실패")
            elif not strategy_3m_additional_enabled:
                pass  # 비활성화됨 - 로그 출력 안 함
            else:
                strategy_3m_additional_met = False
                conditions.append(f"[3분봉 추가] 3분봉 데이터 부족 (300봉 미만)")

            # ========== 최적화된 스캔 순서: 전략C(3분봉) → 전략D(5분봉) ==========

            # 전략A, B 완전 제거됨 - 전략C, D만 사용
            strategy_15m_met = False  # 전략A 제거됨 (호환성 유지용)

            # 비활성화된 전략 로그는 출력하지 않음

            # ❌ 3분봉 2번째 전략 비활성화 (사용자 요청)
            strategy_3m_2nd_enabled = False  # 비활성화 플래그
            
            # 3분봉 2번째 전략 조건 체크 (OR 조건)
            strategy_3m_2nd_met = False
            conditions_3m_2nd = []

            if strategy_3m_2nd_enabled and df_3m is not None and df_1d is not None:
                try:
                    # 헤더 제거 - 실제 조건만 표시
                    
                    # 🚀 우선 체크: 5분봉 SuperTrend(10-3) 진입 시그널 (조기 종료)
                    supertrend_signal = False
                    if df_5m is not None:
                        supertrend_signal = self.check_5m_supertrend_entry_signal(symbol, df_5m)
                    
                    conditions_3m_2nd.append(f"[🚀 우선체크] 5분봉 SuperTrend(10-3): {supertrend_signal}")
                    
                    # 관심종목 분류를 위해 SuperTrend 실패해도 조건들 체크 진행
                    if supertrend_signal:
                        conditions_3m_2nd.append(f"[진행] SuperTrend 확인됨, 3분봉 조건 체크 진행")
                    else:
                        conditions_3m_2nd.append(f"[조건부 진행] SuperTrend 미충족이지만 관심종목 분류용 조건 체크")
                        
                        # 1. 일봉상 시가대비고가 50%이하
                        condition_3m_1 = False
                        if len(df_1d) > 0:
                            latest_daily = df_1d.iloc[-1]
                            if pd.notna(latest_daily['open']) and pd.notna(latest_daily['high']) and latest_daily['open'] > 0:
                                daily_open_to_high = ((latest_daily['high'] - latest_daily['open']) / latest_daily['open']) * 100
                                condition_3m_1 = daily_open_to_high <= 50.0
                        
                        conditions_3m_2nd.append(f"[3분봉 2번째-1] 일봉상 시가대비고가 50%이하: {condition_3m_1}")

                        # 2. 120봉이내 bb80상단선-bb600상단선 골든크로스 OR 이격도 3% 이내
                        df_3m_calc = self.calculate_indicators(df_3m)
                        condition_3m_2 = False
                        if df_3m_calc is not None and len(df_3m_calc) >= 120:
                            bb80_bb600_golden_3m = find_golden_cross_vectorized(df_3m_calc, 'bb80_upper', 'bb600_upper', recent_n=120)

                            # 골든크로스가 없어도 이격도 3% 이내면 통과
                            bb80_bb600_gap_ok = False
                            if len(df_3m_calc) > 0:
                                latest_3m = df_3m_calc.iloc[-1]
                                if pd.notna(latest_3m['bb80_upper']) and pd.notna(latest_3m['bb600_upper']) and latest_3m['bb600_upper'] > 0:
                                    gap_pct = abs(latest_3m['bb80_upper'] - latest_3m['bb600_upper']) / latest_3m['bb600_upper'] * 100
                                    bb80_bb600_gap_ok = gap_pct <= 3.0

                            condition_3m_2 = bb80_bb600_golden_3m or bb80_bb600_gap_ok

                        conditions_3m_2nd.append(f"[3분봉 2번째-2] 120봉이내 BB80-BB600 골든크로스 OR 이격도3%이내: {condition_3m_2}")

                    # 3. 60봉이내 ma20-bb600(표준편차 2.9)상단선 골든크로스 OR 현재 MA20 > BB600
                    condition_3m_3 = False
                    if df_3m_calc is not None and len(df_3m_calc) >= 60:
                        ma20_bb600_golden_3m = find_golden_cross_vectorized(df_3m_calc, 'ma20', 'bb600_upper', recent_n=60)
                        
                        # 골든크로스가 없어도 현재 MA20 > BB600면 통과 (완화)
                        ma20_above_bb600 = False
                        if len(df_3m_calc) > 0:
                            latest_3m = df_3m_calc.iloc[-1]
                            if pd.notna(latest_3m['ma20']) and pd.notna(latest_3m['bb600_upper']):
                                ma20_above_bb600 = latest_3m['ma20'] > latest_3m['bb600_upper']
                        
                        condition_3m_3 = ma20_bb600_golden_3m or ma20_above_bb600

                    conditions_3m_2nd.append(f"[3분봉 2번째-3] 60봉이내 MA20-BB600 골든크로스 OR 현재 MA20>BB600: {condition_3m_3}")

                    # 4. MA20>BB600 상단선 and MA20-BB600 이격도 2%이상
                    condition_3m_4 = False
                    if df_3m_calc is not None and len(df_3m_calc) > 0:
                        latest_3m = df_3m_calc.iloc[-1]
                        if pd.notna(latest_3m['ma20']) and pd.notna(latest_3m['bb600_upper']) and latest_3m['bb600_upper'] > 0:
                            # MA20이 BB600 상단선보다 위에 있는지 확인
                            ma20_above_bb600 = latest_3m['ma20'] > latest_3m['bb600_upper']
                            
                            # MA20-BB600 이격도 2% 이상인지 확인
                            gap_pct = ((latest_3m['ma20'] - latest_3m['bb600_upper']) / latest_3m['bb600_upper']) * 100
                            gap_sufficient = gap_pct >= 2.0
                            
                            # 두 조건 모두 충족해야 통과
                            condition_3m_4 = ma20_above_bb600 and gap_sufficient

                    conditions_3m_2nd.append(f"[3분봉 2번째-4] MA20>BB600 상단선 and MA20-BB600 이격도 2%이상: {condition_3m_4}")

                    # 5. 60봉이내 시가대비고가 3~20% 1회이상
                    condition_3m_5 = False
                    if df_3m is not None and len(df_3m) >= 60:
                        recent_60_3m = df_3m.tail(60)
                        surge_count = 0
                        for _, row in recent_60_3m.iterrows():
                            if pd.notna(row['open']) and pd.notna(row['high']) and row['open'] > 0:
                                open_to_high_pct = ((row['high'] - row['open']) / row['open']) * 100
                                if 3.0 <= open_to_high_pct <= 20.0:
                                    surge_count += 1
                        condition_3m_5 = surge_count >= 1

                    conditions_3m_2nd.append(f"[3분봉 2번째-5] 60봉이내 시가대비고가 3~20% 1회이상: {condition_3m_5}")

                    # 6. 30봉이내 3연속양봉 AND 30봉이내 (MA5우하향 AND 1봉전MA5돌파)
                    condition_3m_6 = False
                    if df_3m_calc is not None and len(df_3m_calc) >= 30:
                        recent_30_3m = df_3m_calc.tail(30)

                        # 6-1. 30봉 내 3연속 양봉 찾기
                        has_three_green = False
                        for i in range(len(recent_30_3m) - 2):
                            candle1 = recent_30_3m.iloc[i]
                            candle2 = recent_30_3m.iloc[i+1]
                            candle3 = recent_30_3m.iloc[i+2]

                            # 3연속 양봉 체크 (종가 > 시가)
                            if (pd.notna(candle1['open']) and pd.notna(candle1['close']) and candle1['close'] > candle1['open'] and
                                pd.notna(candle2['open']) and pd.notna(candle2['close']) and candle2['close'] > candle2['open'] and
                                pd.notna(candle3['open']) and pd.notna(candle3['close']) and candle3['close'] > candle3['open']):
                                has_three_green = True
                                break

                        # 6-2. 30봉 내에서 (MA5우하향 AND 1봉전MA5돌파) 패턴 찾기
                        ma5_pattern_found = False
                        for i in range(1, len(recent_30_3m)):  # 1부터 시작 (이전 봉과 비교 위해)
                            current_candle = recent_30_3m.iloc[i]
                            prev_candle = recent_30_3m.iloc[i-1]
                            
                            # 해당 시점에서 MA5 우하향 체크
                            if i >= 1 and i < len(recent_30_3m) - 1:
                                curr_ma5 = current_candle['ma5']
                                next_ma5 = recent_30_3m.iloc[i+1]['ma5'] if i+1 < len(recent_30_3m) else None
                                
                                # MA5 우하향: 현재 MA5 < 다음 MA5 (시간 순서상)
                                ma5_downtrend = False
                                if pd.notna(curr_ma5) and pd.notna(next_ma5):
                                    ma5_downtrend = curr_ma5 > next_ma5  # 시간이 지나면서 MA5가 하락

                                # 해당 시점에서 MA5 돌파 체크 (시가<MA5 and 종가>MA5)
                                ma5_cross = False
                                if (pd.notna(current_candle['open']) and pd.notna(current_candle['close']) and 
                                    pd.notna(current_candle['ma5'])):
                                    ma5_cross = (current_candle['open'] < current_candle['ma5'] and
                                               current_candle['close'] > current_candle['ma5'])

                                # 두 조건 모두 만족하면 패턴 발견
                                if ma5_downtrend and ma5_cross:
                                    ma5_pattern_found = True
                                    break

                    # 최종 조건: 3연속 양봉 AND 30봉 내 (MA5우하향 AND 1봉전MA5돌파) 패턴
                    condition_3m_6 = has_three_green and ma5_pattern_found

                    conditions_3m_2nd.append(f"[3분봉 2번째-6] 30봉이내 3연속양봉 AND 30봉이내 (MA5우하향 AND 1봉전MA5돌파): {condition_3m_6}")

                    # 3분봉 2번째 전략 평가 (SuperTrend + 6개 조건 모두 필요)
                    conditions_3m_2nd_list = [condition_3m_1, condition_3m_2, condition_3m_3, condition_3m_4,
                                             condition_3m_5, condition_3m_6]
                    passed_3m_2nd_count = sum(conditions_3m_2nd_list)
                    
                    # 최종 진입 조건: SuperTrend AND 6개 조건 모두 충족
                    strategy_3m_2nd_met = supertrend_signal and (passed_3m_2nd_count >= 6)
                    
                    # 관심종목 분류를 위한 상세 정보
                    missing_conditions = 6 - passed_3m_2nd_count
                    if not supertrend_signal:
                        missing_conditions += 1  # SuperTrend도 미충족으로 카운트
                    
                    conditions_3m_2nd.append(f"[3분봉 2번째 전략] SuperTrend: {supertrend_signal}, 조건: {passed_3m_2nd_count}/6개 → 미충족: {missing_conditions}개")
            
                    # 디버그 메시지 제거됨 (전략B 비활성화로 인해)
                    # if missing_conditions <= 4:  # 관심종목 범위
                    #     print(f"🔍 [DEBUG] {symbol.replace('/USDT:USDT', '')}: 3분봉2번째 미충족 {missing_conditions}개 (관심종목 후보!)")

                except Exception as e:
                    conditions_3m_2nd.append(f"[3분봉 2번째 전략] 오류 발생: {str(e)}")
                    strategy_3m_2nd_met = False
            else:
                if not strategy_3m_2nd_enabled:
                    pass  # 비활성화됨 - 로그 출력 안 함
                else:
                    conditions_3m_2nd.append("[3분봉 2번째 전략] 3분봉 또는 일봉 데이터 없음")
            
            # ✅ 3분봉 3번째 전략 활성화 (시세 초입 포착)
            strategy_3m_3rd_enabled = True  # 활성화 플래그

            # 3분봉 3번째 전략 조건 체크 (OR 조건)
            strategy_3m_3rd_met = False
            conditions_3m_3rd = []

            # 🔍 디버그: 전략C 진입 확인 (스캔 모드에서는 출력 안함)
            if not self._scan_mode:
                print(f"🔍 [전략C 시작] {symbol.replace('/USDT:USDT', '')}: df_3m={'있음' if df_3m is not None else '없음'}, len={len(df_3m) if df_3m is not None else 0}")

            if strategy_3m_3rd_enabled and df_3m is not None:
                try:
                    # 헤더 제거 - 실제 조건만 표시

                    # ⚡ 조기종료 최적화: 5분봉 SuperTrend 우선 체크
                    supertrend_signal = False
                    if df_5m is not None:
                        supertrend_signal = self.check_5m_supertrend_entry_signal(symbol, df_5m)

                    # 🚨 변수 초기화
                    condition_3m_c1 = False
                    condition_2 = False
                    final_condition = False
                    strategy_3m_3rd_met = False

                    # ⚡ SuperTrend 통과시에만 나머지 조건 체크 (조기 종료)
                    if supertrend_signal:
                        # 지표 계산 (SuperTrend 통과한 경우만)
                        df_3m_calc = self.calculate_indicators(df_3m)

                        # 1. 60봉이내 bb200상단선(표준편차2)-bb480상단선(표준편차1.5) 골든크로스
                        condition_3m_c1 = False
                        if df_3m_calc is not None and len(df_3m_calc) >= 60:
                            # BB200 (표준편차 2.0) 계산
                            if 'bb200_upper' not in df_3m_calc.columns:
                                df_3m_calc['bb200_middle'] = df_3m_calc['close'].rolling(window=200).mean()
                                df_3m_calc['bb200_std'] = df_3m_calc['close'].rolling(window=200).std()
                                df_3m_calc['bb200_upper'] = df_3m_calc['bb200_middle'] + (df_3m_calc['bb200_std'] * 2.0)
                            
                            # BB480 (표준편차 1.5) 계산  
                            if 'bb480_upper_std15' not in df_3m_calc.columns:
                                df_3m_calc['bb480_middle'] = df_3m_calc['close'].rolling(window=480).mean()
                                df_3m_calc['bb480_std'] = df_3m_calc['close'].rolling(window=480).std()
                                df_3m_calc['bb480_upper_std15'] = df_3m_calc['bb480_middle'] + (df_3m_calc['bb480_std'] * 1.5)
                            
                            condition_3m_c1 = self._find_golden_cross(df_3m_calc, 'bb200_upper', 'bb480_upper_std15', recent_n=200)

                        conditions_3m_3rd.append(f"[3분봉 3번째-1] 200봉이내 BB200상단선(표준편차2)-BB480상단선(표준편차1.5) 골든크로스: {condition_3m_c1}")

                        # 2A. 100봉이내 MA5-MA20 데드크로스
                        condition_3m_c2a = False
                        if df_3m_calc is not None and len(df_3m_calc) >= 100:
                            condition_3m_c2a = self._find_dead_cross(df_3m_calc, 'ma5', 'ma20', recent_n=100)

                        conditions_3m_3rd.append(f"[3분봉 3번째-2A] 100봉이내 MA5-MA20 데드크로스: {condition_3m_c2a}")

                        # 2B. 10봉이내 MA5-MA20 골든크로스
                        condition_3m_c2b = False
                        if df_3m_calc is not None and len(df_3m_calc) >= 10:
                            condition_3m_c2b = self._find_golden_cross(df_3m_calc, 'ma5', 'ma20', recent_n=10)

                        conditions_3m_3rd.append(f"[3분봉 3번째-2B] 10봉이내 MA5-MA20 골든크로스: {condition_3m_c2b}")

                        # 2C. MA5<MA20 or MA5-MA20 이격도 2%이내 조건
                        condition_3m_c2c = False
                        if df_3m_calc is not None and len(df_3m_calc) >= 1:
                            latest_row = df_3m_calc.iloc[-1]
                            ma5_val = latest_row.get('ma5', 0)
                            ma20_val = latest_row.get('ma20', 0)

                            if pd.notna(ma5_val) and pd.notna(ma20_val) and ma20_val > 0:
                                ma5_below_ma20 = ma5_val < ma20_val
                                gap_pct = abs(ma5_val - ma20_val) / ma20_val * 100
                                gap_within_2pct = gap_pct <= 2.0
                                condition_3m_c2c = ma5_below_ma20 or gap_within_2pct

                        conditions_3m_3rd.append(f"[3분봉 3번째-2C] MA5<MA20 or 이격도 2%이내: {condition_3m_c2c}")

                        # 조건 2 = 2A AND 2B AND 2C
                        condition_2 = condition_3m_c2a and condition_3m_c2b and condition_3m_c2c
                        conditions_3m_3rd.append(f"[3분봉 3번째-조건2] (2A AND 2B AND 2C): {condition_2}")

                        # condition_3 제거됨 - 전략C는 조건1 AND 조건2 AND SuperTrend만 사용

                        # 최종 조건: 1 AND 2 (원래대로 롤백)
                        final_condition = condition_3m_c1 and condition_2
                        conditions_3m_3rd.append(f"[3분봉 3번째-최종] 1 AND 2: {final_condition}")

                        # 3분봉 3번째 전략 평가 (SuperTrend + 논리조건 모두 필요) - 원래대로 롤백
                        strategy_3m_3rd_met = supertrend_signal and final_condition

                        # 통과 상태 계산 (디버깅용)
                        passed_conditions = []
                        if condition_3m_c1:
                            passed_conditions.append("조건1")
                        if condition_2:
                            passed_conditions.append("조건2")
                        # condition_3 제거됨
                        passed_status = ", ".join(passed_conditions) if passed_conditions else "없음"

                        # 미충족 조건 계산
                        missing_conditions = 0
                        if not condition_3m_c1:
                            missing_conditions += 1
                        if not condition_2:
                            missing_conditions += 1  # 조건2 미충족
                        if not supertrend_signal:
                            missing_conditions += 1

                        conditions_3m_3rd.append(f"[3분봉 3번째 전략] SuperTrend: {supertrend_signal}, 조건: {passed_status} → 미충족: {missing_conditions}개")

                        # 전략C 상세 디버그 출력
                        if missing_conditions > 0:
                            self._write_debug_log(f"[DEBUG-전략C] {symbol}: 조건1={condition_3m_c1}, 조건2={condition_2}, SuperTrend={supertrend_signal}")

                except Exception as e:
                    conditions_3m_3rd.append(f"[3분봉 3번째 전략] 오류 발생: {str(e)}")
                    strategy_3m_3rd_met = False
            else:
                if not strategy_3m_3rd_enabled:
                    conditions_3m_3rd.append("[3분봉 3번째 전략] 🚫 비활성화됨")
                else:
                    conditions_3m_3rd.append("[3분봉 3번째 전략] 3분봉 데이터 없음")
                    strategy_3m_3rd_met = False

            # ========== 전략D: 5분봉 초입 초강력 타점 ==========
            strategy_5m_4th_enabled = True  # 전략D 활성화
            strategy_5m_4th_met = False  # 항상 초기화하여 스코프 문제 방지
            conditions_5m_4th = []

            if strategy_5m_4th_enabled and df_5m is not None and len(df_5m) >= 30:  # 30봉 필요 (약 2.5시간)
                try:
                    # 5분봉 데이터에 지표 계산
                    df_5m_calc = self.calculate_indicators(df_5m)
                    
                    if df_5m_calc is not None and len(df_5m_calc) >= 30:  # 30봉 필요
                        # 초기화: 모든 조건 False로 시작
                        condition_5m_d1 = False
                        condition_5m_d2 = False
                        condition_5m_d3 = False
                        condition_5m_d4 = False
                        condition_5m_d5 = False

                        # ⚡ 성능 최적화: 실패율이 높은 조건들을 빠른 순서로 체크
                        
                        # 🚀 Step 1: 최고속 체크 - 현재가 기반 간단한 조건부터 (d1, d5)
                        
                        # 조건 1: 15분봉 MA80<MA480 (가장 빠른 체크)
                        if df_15m is not None and len(df_15m) >= 20:
                            df_15m_calc = self.calculate_indicators(df_15m)
                            if df_15m_calc is not None and len(df_15m_calc) > 0:
                                latest_15m = df_15m_calc.iloc[-1]
                                if (pd.notna(latest_15m['ma80']) and pd.notna(latest_15m['ma480'])):
                                    condition_5m_d1 = latest_15m['ma80'] < latest_15m['ma480']
                        
                        # 조건 1이 False면 즉시 종료
                        if not condition_5m_d1:
                            strategy_5m_4th_met = False
                            conditions_5m_4th.append(f"[5분봉 D전략-1] 15분봉 MA80<MA480: {condition_5m_d1}")
                            if condition_5m_d1 is False:
                                conditions_5m_4th.append("ㄴ 15분봉 MA80이 MA480보다 크거나 같음 (하락추세 아님)")
                        else:
                            # 조건 5: 10봉이내 MA5-MA20 골든크로스 (빠른 체크)
                            if len(df_5m_calc) >= 10:
                                condition_5m_d5 = find_golden_cross_vectorized(df_5m_calc, 'ma5', 'ma20', recent_n=10)
                            
                            # 조건 5가 False면 즉시 종료
                            if not condition_5m_d5:
                                strategy_5m_4th_met = False
                                conditions_5m_4th.append(f"[5분봉 D전략-5] MA5-MA20 골든크로스: {condition_5m_d5}")
                                if condition_5m_d5 is False:
                                    conditions_5m_4th.append("ㄴ 최근 10봉 내 MA5-MA20 골든크로스 없음")
                            else:
                                # 🚀 Step 2: 조건 3 체크 (중간 복잡도)
                                # 조건 3: 200봉이내 MA80-MA480 골든크로스 OR (MA80<MA480 and MA80-MA480 이격도 5%이내)
                                golden_cross_met = False
                                gap_condition_met = False

                                if len(df_5m_calc) >= 200:
                                    # 현재 MA80 < MA480 and 이격도 5% 이내 확인 (빠른 체크 먼저)
                                    latest = df_5m_calc.iloc[-1]
                                    if (pd.notna(latest['ma80']) and pd.notna(latest['ma480']) and
                                        latest['ma80'] < latest['ma480'] and latest['ma480'] > 0):
                                        gap_pct = ((latest['ma480'] - latest['ma80']) / latest['ma480']) * 100
                                        gap_condition_met = gap_pct <= 5.0
                                    
                                    # 이격도 조건이 안 되면 골든크로스 확인 (느린 체크)
                                    if not gap_condition_met:
                                        golden_cross_met = find_golden_cross_vectorized(df_5m_calc, 'ma80', 'ma480', recent_n=200)

                                    condition_5m_d3 = golden_cross_met or gap_condition_met

                                # 조건 3이 False면 즉시 종료
                                if not condition_5m_d3:
                                    strategy_5m_4th_met = False
                                    conditions_5m_4th.append(f"[5분봉 D전략-3] MA80-MA480 조건: {condition_5m_d3}")
                                    if not golden_cross_met and not gap_condition_met:
                                        conditions_5m_4th.append("ㄴ 골든크로스도 이격도 조건도 미충족")
                                else:
                                    # 🚀 Step 3: 조건 4 체크 (최고 복잡도 - 마지막에 체크)
                                    # 조건 4: 700봉이내 (MA480이 5연속 이상 우하향 1회이상 AND BB200상한선이 MA480을 골든크로스)
                                    ma480_downtrend_10 = False
                                    bb200_ma480_golden = False

                                    if len(df_5m_calc) >= 60:
                                        # MA480이 5연속 이상 우하향 확인 (최근 100봉 내에서)
                                        recent_data = df_5m_calc.tail(60)  # 100→60으로 완화

                                        # 연속 하락 구간 찾기
                                        max_consecutive_down = 0
                                        current_consecutive = 0

                                        for i in range(1, len(recent_data)):
                                            if (pd.notna(recent_data.iloc[i]['ma480']) and
                                                pd.notna(recent_data.iloc[i-1]['ma480']) and
                                                recent_data.iloc[i]['ma480'] < recent_data.iloc[i-1]['ma480']):
                                                current_consecutive += 1
                                                max_consecutive_down = max(max_consecutive_down, current_consecutive)
                                            else:
                                                current_consecutive = 0

                                        ma480_downtrend_10 = max_consecutive_down >= 5

                                        # BB200상한선이 MA480을 골든크로스 확인 - 700봉 전체를 대상으로 검사
                                        # "BB200상단선이 MA480을 골든크로스" = BB200 상단선이 MA480을 아래에서 위로 돌파
                                        bb200_ma480_debug_info = []
                                        total_cross_count = 0

                                        # 700봉 전체에서 골든크로스 검사 (df_5m_calc 사용)
                                        for i in range(1, len(df_5m_calc)):
                                            prev_candle = df_5m_calc.iloc[i-1]
                                            curr_candle = df_5m_calc.iloc[i]

                                            if (pd.notna(prev_candle['bb200_upper']) and pd.notna(prev_candle['ma480']) and
                                                pd.notna(curr_candle['bb200_upper']) and pd.notna(curr_candle['ma480'])):

                                                # "BB200상단선이 MA480을 골든크로스": BB200 상단선이 MA480을 아래에서 위로 돌파
                                                # 이전 봉: BB200 < MA480, 현재 봉: BB200 >= MA480
                                                bb200_golden_cross = (prev_candle['bb200_upper'] < prev_candle['ma480'] and
                                                                      curr_candle['bb200_upper'] >= curr_candle['ma480'])

                                                if bb200_golden_cross:
                                                    bb200_ma480_golden = True
                                                    total_cross_count += 1
                                                    cross_info = f"BB200→MA480골든크로스 발견! 인덱스={i}: 이전봉(BB200={prev_candle['bb200_upper']:.6f} < MA480={prev_candle['ma480']:.6f}) → 현재봉(BB200={curr_candle['bb200_upper']:.6f} >= MA480={curr_candle['ma480']:.6f})"
                                                    bb200_ma480_debug_info.append(cross_info)
                                                    # 첫 번째 골든크로스 발견 시 종료하지 않고 계속 검사하여 개수 세기
                                                    if total_cross_count >= 3:  # 최대 3개까지만 디버깅 정보 수집
                                                        break

                                        # 골든크로스가 발견되지 않은 경우, 최근 5봉만 디버깅 정보 수집
                                        if not bb200_ma480_golden and len(recent_data) >= 5:
                                            for i in range(len(recent_data) - 5, len(recent_data)):
                                                if i > 0:
                                                    prev_candle = recent_data.iloc[i-1]
                                                    curr_candle = recent_data.iloc[i]

                                                    if (pd.notna(prev_candle['bb200_upper']) and pd.notna(prev_candle['ma480']) and
                                                        pd.notna(curr_candle['bb200_upper']) and pd.notna(curr_candle['ma480'])):

                                                        prev_ma480 = prev_candle['ma480']
                                                        curr_ma480 = curr_candle['ma480']
                                                        prev_bb200 = prev_candle['bb200_upper']
                                                        curr_bb200 = curr_candle['bb200_upper']

                                                        # 관통 패턴 분석
                                                        cross_analysis = ""
                                                        if prev_ma480 < prev_bb200 and curr_ma480 >= curr_bb200:
                                                            cross_analysis = "→골든크로스1!"
                                                        elif prev_ma480 >= prev_bb200 and curr_ma480 < curr_bb200:
                                                            cross_analysis = "→골든크로스2!"
                                                        else:
                                                            cross_analysis = "→변화없음"

                                                        bb200_ma480_debug_info.append(f"봉{i}: MA480={curr_ma480:.6f}, BB200상한={curr_bb200:.6f} {cross_analysis}")

                                        # 디버깅 정보 출력 (MA480 5연속하락이 True인 경우 항상 출력)
                                        if ma480_downtrend_10:
                                            debug_msg = f"[BB200-MA480 DEBUG] {symbol}: 5연속하락감지(최대연속={max_consecutive_down})"
                                            debug_msg += f" | 검사범위={len(df_5m_calc)}봉(700봉)"

                                            if bb200_ma480_golden and len(bb200_ma480_debug_info) > 0:
                                                debug_msg += f" | {' | '.join(bb200_ma480_debug_info)}"
                                                debug_msg += f" | 총발견개수={total_cross_count}개"
                                            else:
                                                # 골든크로스가 없는 경우, 최근 5봉 정보 수집
                                                if len(recent_data) >= 5:
                                                    last_candle = recent_data.iloc[-1]
                                                    debug_msg += f" | 최근봉: MA480={last_candle.get('ma480', 'N/A'):.6f}, BB200상한={last_candle.get('bb200_upper', 'N/A'):.6f}"
                                                    # 가장 최근의 몇 개 값도 보여주기
                                                    recent_values = []
                                                    for j in range(max(0, len(recent_data)-3), len(recent_data)):
                                                        candle = recent_data.iloc[j]
                                                        if pd.notna(candle.get('ma480')) and pd.notna(candle.get('bb200_upper')):
                                                            ma480_val = candle['ma480']
                                                            bb200_val = candle['bb200_upper']
                                                            diff = bb200_val - ma480_val
                                                            recent_values.append(f"봉{j}(차이={diff:.6f})")
                                                    if recent_values:
                                                        debug_msg += f" | 최근차이: {', '.join(recent_values)}"

                                            debug_msg += f" | 골든크로스={bb200_ma480_golden}"
                                            self._write_debug_log(debug_msg)

                                        condition_5m_d4 = ma480_downtrend_10 and bb200_ma480_golden

                                        # 조건 4가 False면 즉시 종료  
                                        if not condition_5m_d4:
                                            strategy_5m_4th_met = False
                                            conditions_5m_4th.append(f"[5분봉 D전략-4] MA480하락+BB200골든: {condition_5m_d4}")
                                            if not ma480_downtrend_10:
                                                conditions_5m_4th.append("ㄴ MA480 5연속 하락 구간 없음")
                                            elif not bb200_ma480_golden:
                                                conditions_5m_4th.append("ㄴ BB200상단-MA480 골든크로스 없음")
                                        else:
                                            # 🚀 Step 4: 마지막 조건 2 체크 (SuperTrend)
                                            # 조건 2: 5분봉 SuperTrend(10-3) 진입 시그널
                                            supertrend_signal = self.check_5m_supertrend_entry_signal(symbol, df_5m_calc)
                                            condition_5m_d2 = supertrend_signal
                                            
                                            # 전략D 최종 평가: 5개 조건 모두 충족
                                            strategy_5m_4th_met = condition_5m_d1 and condition_5m_d2 and condition_5m_d3 and condition_5m_d4 and condition_5m_d5
                        
                        # 통과 상태 계산
                        passed_conditions_d = []
                        if condition_5m_d1:
                            passed_conditions_d.append("조건1")
                        if condition_5m_d2:
                            passed_conditions_d.append("조건2")
                        if condition_5m_d3:
                            passed_conditions_d.append("조건3")
                        if condition_5m_d4:
                            passed_conditions_d.append("조건4")
                        if condition_5m_d5:
                            passed_conditions_d.append("조건5")
                        passed_status_d = ", ".join(passed_conditions_d) if passed_conditions_d else "없음"
                        
                        # 미충족 조건 계산
                        missing_conditions_d = 0
                        if not condition_5m_d1:
                            missing_conditions_d += 1
                        if not condition_5m_d2:
                            missing_conditions_d += 1
                        if not condition_5m_d3:
                            missing_conditions_d += 1
                        if not condition_5m_d4:
                            missing_conditions_d += 1
                        if not condition_5m_d5:
                            missing_conditions_d += 1

                        # ✅ 각 조건의 상세 정보를 conditions_5m_4th에 추가 (진입임박 화면 출력용)
                        conditions_5m_4th.append(f"[5분봉 D전략-1] 15분봉 MA80<MA480: {condition_5m_d1}")
                        conditions_5m_4th.append(f"[5분봉 D전략-2] 5분봉 SuperTrend(10-3) 진입: {condition_5m_d2}")
                        conditions_5m_4th.append(f"[5분봉 D전략-3] 60봉이내 MA80-MA480 골든크로스: {condition_5m_d3}")
                        conditions_5m_4th.append(f"[5분봉 D전략-4] MA480 5연속하락 AND BB200-MA480 골든크로스: {condition_5m_d4}")
                        conditions_5m_4th.append(f"[5분봉 D전략-5] 20봉이내 MA5-MA20 골든크로스: {condition_5m_d5}")
                        conditions_5m_4th.append(f"[5분봉 D전략-최종] 1 AND 2 AND 3 AND 4 AND 5: {strategy_5m_4th_met}")
                        conditions_5m_4th.append(f"[5분봉 D전략] 조건 통과: {passed_status_d} → 미충족: {missing_conditions_d}개")

                        # 전략D 상세 디버그 출력 (모든 경우)
                        self._write_debug_log(f"[DEBUG-전략D] {symbol}: 조건1={condition_5m_d1}, 조건2={condition_5m_d2}, 조건3={condition_5m_d3}, 조건4={condition_5m_d4}, 조건5={condition_5m_d5}, 미충족={missing_conditions_d}개")

                except Exception as e:
                    conditions_5m_4th.append(f"[5분봉 D전략] 오류 발생: {str(e)}")
                    strategy_5m_4th_met = False
            else:
                if not strategy_5m_4th_enabled:
                    conditions_5m_4th.append("[5분봉 D전략] 🚫 비활성화됨")
                    strategy_5m_4th_met = False
                else:
                    conditions_5m_4th.append("[5분봉 D전략] 5분봉 데이터 부족 (30봉 필요)")
                    strategy_5m_4th_met = False

            # 최종 결과: 전략C OR 전략D만 활성화 (전략A, B는 임시 비활성화)
            all_conditions_met = strategy_3m_3rd_met or strategy_5m_4th_met

            # 조건 목록에 활성화된 전략 조건만 추가 (전략C, D만)
            conditions.extend(conditions_3m_3rd)
            conditions.extend(conditions_5m_4th)

            # 디버깅용 임시 완화: 일부 조건 통과한 심볼도 관심종목으로 분류
            if all_conditions_met:
                # 활성화된 전략 중 충족된 전략만 확인하여 로그 출력
                strategy_names = []
                strategy_types = []  # 충족된 모든 전략 타입 수집

                if strategy_3m_3rd_met:
                    strategy_names.append("전략C(3분봉 3번째)")
                    strategy_types.append("전략C: 3분봉 시세 초입 포착")

                strategy_5m_4th_met_check = locals().get('strategy_5m_4th_met', False)
                if strategy_5m_4th_met_check:
                    strategy_names.append("전략D(5분봉 초강력타점)")
                    strategy_types.append("전략D: 5분봉 초입 초강력 타점")

                # 텔레그램 알림용 전략 타입 결정
                if len(strategy_types) == 2:
                    # 둘 다 충족된 경우
                    strategy_type = "전략C+D: 3분봉+5분봉 복합 진입"
                elif len(strategy_types) == 1:
                    # 하나만 충족된 경우
                    strategy_type = strategy_types[0]
                else:
                    # 예외 상황 (발생하지 않아야 함)
                    strategy_type = "전략C: 3분봉 시세 초입 포착"
                
                strategy_text = " 및 ".join(strategy_names)
                self.logger.info(f"✅ {symbol} {strategy_text} 전략 조건 충족!")
                
                # 전략 타입 정보를 저장하여 텔레그램 알림에서 사용할 수 있도록 함
                if not hasattr(self, '_last_analysis_results'):
                    self._last_analysis_results = {}
                self._last_analysis_results[symbol] = {
                    'strategy_type': strategy_type,
                    'strategy_names': strategy_names,
                    'timestamp': time.time()
                }
                
                # 디버깅용 로그 추가
                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                self.logger.info(f"[전략저장] {clean_symbol} → {strategy_type} 저장 완료")

                return True, conditions
            
            # 진입 조건 미충족 시 - 새로운 개별 전략 로직으로 대체됨
            # 전략C와 전략D는 이제 개별적으로 조건 체크하고 상태 결정
            else:
                # ⚠️ 기존 통합 관심종목 분류 로직은 완전히 제거됨
                # 개별 전략 결과는 analyze_symbol 메서드에서 처리됨
                strategy_5m_4th_met_debug = locals().get('strategy_5m_4th_met', False)
                self._write_debug_log(f"❌ {symbol} 진입 조건 미충족 (전략C: {strategy_3m_3rd_met}, 전략D: {strategy_5m_4th_met_debug})")
                for condition in conditions:
                    self._write_debug_log(f"   {condition}")
                return False, conditions

        except KeyError as ke:
            # MA 컬럼 누락 특별 처리 (조용히 처리)
            if any(ma in str(ke) for ma in ['ma80', 'ma480', 'ma5', 'ma20', 'ma1']):
                # 로그 출력 제거 - 조용히 처리
                return False, []  # 빈 조건 목록으로 조용히 반환
            else:
                self.logger.error(f"{symbol} 데이터 컬럼 접근 오류: {ke}")
                return False, [f"데이터 구조 오류: {ke}"]
        except Exception as e:
            # Rate limit 에러 특별 처리
            if "418" in str(e) or "too many requests" in str(e).lower():
                if not hasattr(self, '_api_rate_limited'):
                    self._api_rate_limited = False
                if not self._api_rate_limited:
                    self._api_rate_limited = True
                    self.logger.warning(f"🚨 Rate limit 감지 - API 호출 중단 모드 활성화")
                
                # Rate limit 상황에서는 에러 로그 레벨을 낮춤
                self.logger.debug(f"{symbol} 진입 조건 체크 건너뛰기 (Rate limit)")
                return False, [f"Rate limit - 조건 체크 건너뛰기"]
            else:
                self.logger.error(f"{symbol} 전략C/D 진입 조건 체크 실패: {e}")
                return False, [f"조건 체크 실패: {e}"]

    def analyze_symbol(self, symbol, cached_ticker=None):
        """개별 심볼 분석 (invincible_surge_entry_strategy.py와 동일한 구조)"""
        # 디버그 제거 (성능 최적화)

        try:
            # 🛡️ 안전장치: 심볼 타입 검증 및 변환
            if isinstance(symbol, (list, tuple)):
                # 튜플/리스트가 전달된 경우 첫 번째 요소를 심볼로 사용
                if len(symbol) >= 1:
                    symbol = symbol[0]
                else:
                    self.logger.error(f"잘못된 심볼 데이터: {symbol}")
                    return None
            elif not isinstance(symbol, str):
                # 문자열이 아닌 경우 문자열로 변환 시도
                symbol = str(symbol)
            
            # ⚡ 심볼 이름 정리 (한 번만 생성)
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            
            # 🔍 AI16Z 디버깅용 로그
            # ⚡ 스캔 모드시 디버그 출력 스킵
            if not self._scan_mode:
                self._write_debug_log(f"[DEBUG] [{clean_symbol}] analyze_symbol 시작")

            # 포지션 체크 (순환매 고려)
            if symbol in self.active_positions:
                # ⚡ 스캔 모드시 디버그 출력 스킵
                if not self._scan_mode:
                    self._write_debug_log(f"[DEBUG] [{clean_symbol}] 활성 포지션 감지 - 분석 스킵")
                # DCA 매니저가 있으면 순환매 상태 체크
                if self.dca_manager and hasattr(self.dca_manager, 'positions'):
                    if symbol in self.dca_manager.positions:
                        position = self.dca_manager.positions[symbol]
                        # 순환매 재진입 가능 상태인지 체크
                        if (position.cyclic_state == "cyclic_paused" and 
                            position.cyclic_count < position.max_cyclic_count):
                            # 순환매 재진입 허용 (이는 DCA 매니저에서 처리됨)
                            pass
                        else:
                            # 일반 포지션 또는 순환매 완료된 상태
                            return None
                else:
                    # DCA 매니저가 없으면 기존 로직 유지
                    return None
            
            # 🚀 성능 최적화: WebSocket 프리로딩 비활성화 (10초 병목 제거)
            # WebSocket 매니저가 활성화된 경우에도 프리로딩 생략하여 속도 개선
            # 이유: _force_preload_websocket_buffer가 10초 병목의 주요 원인
            # if hasattr(self, 'ws_kline_manager') and self.ws_kline_manager:
            #     # 프리로딩 로직 임시 비활성화 (성능 개선)
            #     pass

            # 🔒 안전장치: 모든 데이터프레임 변수 초기화
            df_1m = df_3m = df_5m = df_15m = df_1d = None

            # ⚡ WebSocket 자동 구독: 개별 분석시 해당 심볼을 즉시 구독 (중복 방지)
            if hasattr(self, 'ws_kline_manager') and self.ws_kline_manager:
                try:
                    # 심볼 형식 변환 (BTC/USDT:USDT -> BTCUSDT)
                    ws_symbol = symbol.replace('/USDT:USDT', '').replace('/', '')
                    if not ws_symbol.endswith('USDT'):
                        ws_symbol = ws_symbol + 'USDT'

                    # ✅ 중복 구독 방지: 이미 구독된 심볼은 스킵
                    if hasattr(self, '_subscribed_symbols') and ws_symbol in self._subscribed_symbols:
                        if not self._scan_mode:
                            self._write_debug_log(f"[DEBUG] [{clean_symbol}] 이미 구독됨 - 스킵")
                        pass  # 이미 구독되어 있으면 아무것도 하지 않음
                    else:
                        # 필요한 타임프레임에 대해 즉시 구독 (개별 분석용)
                        if not self._scan_mode:
                            self._write_debug_log(f"[DEBUG] [{clean_symbol}] WebSocket 자동 구독 시작")

                        # 배치 구독으로 전략에 필요한 타임프레임 구독
                        self.ws_kline_manager.subscribe_batch(
                            symbols=[ws_symbol],
                            timeframes=['1m', '3m', '5m', '15m', '1d'],
                            load_history=True  # 하이브리드: 초기 히스토리 로드
                        )

                        # 구독 추적에 추가
                        if hasattr(self, '_subscribed_symbols'):
                            self._subscribed_symbols.add(ws_symbol)

                        if not self._scan_mode:
                            self._write_debug_log(f"[DEBUG] [{clean_symbol}] WebSocket 구독 완료")

                        # 구독 후 대기 없음 (극한 속도)
                        pass  # 대기 제거

                except Exception as e:
                    if not self._scan_mode:
                        self._write_debug_log(f"[DEBUG] [{clean_symbol}] WebSocket 구독 실패: {e}")

            # ⚡ REST API 모드: 필요한 타임프레임 직접 로드 (안정적이고 빠름)
            if not self._scan_mode:
                self._write_debug_log(f"[DEBUG] [{clean_symbol}] REST API 데이터 조회 시작")

            # ⚡ 완전 WebSocket 전용 모드: REST API 제거, WebSocket 버퍼에서만 데이터 조회
            rest_api_stats = {'success': [], 'failed': []}

            def safe_fetch_websocket_with_history(timeframe, limit):
                """캐싱 활성화된 데이터 조회 (get_ohlcv_data 사용)"""
                try:
                    # 🚀 캐싱 시스템이 적용된 get_ohlcv_data 사용
                    df = self.get_ohlcv_data(symbol, timeframe, limit)

                    if df is not None and len(df) >= 10:
                        # 캐시 히트 여부 체크 (limit 제거)
                        cache_key = f"{symbol}_{timeframe}"
                        is_cached = hasattr(self, '_ohlcv_cache') and cache_key in self._ohlcv_cache
                        source = "캐시" if is_cached else "WebSocket/API"
                        return df, source
                    elif df is not None and len(df) >= 5:
                        return df, f"부분({len(df)})"
                    else:
                        return None, "완전 실패"

                except Exception as e:
                    self.logger.debug(f"데이터 조회 실패: {symbol} {timeframe} - {e}")
                    return None, f"완전 실패"

            # ⚡ 최적화: 필수 데이터만 조회 (속도 향상)
            df_3m, source_3m = safe_fetch_websocket_with_history('3m', 250)  # 200봉 + 여유분
            if df_3m is not None:
                rest_api_stats['success'].append(f'3m({source_3m})')
            else:
                rest_api_stats['failed'].append(f"3m: {source_3m}")

            df_5m, source_5m = safe_fetch_websocket_with_history('5m', 100)
            if df_5m is not None:
                rest_api_stats['success'].append(f'5m({source_5m})')
            else:
                rest_api_stats['failed'].append(f"5m: {source_5m}")

            # ⚠️ 15분봉은 700봉 필요 (전략D 조건4: 700봉이내 MA480 5연속 하락 체크)
            df_15m, source_15m = safe_fetch_websocket_with_history('15m', 400)  # 절충안: 700→400
            if df_15m is not None:
                rest_api_stats['success'].append(f'15m({source_15m})')
            else:
                rest_api_stats['failed'].append(f"15m: {source_15m}")

            # 🔧 1분봉 데이터 수집 (필수 - 지표 계산용)
            df_1m, source_1m = safe_fetch_websocket_with_history('1m', 100)
            if df_1m is not None:
                rest_api_stats['success'].append(f'1m({source_1m})')
            else:
                rest_api_stats['failed'].append(f"1m: {source_1m}")

            # 🔧 일봉 데이터 수집 (최소한만 수집)
            df_1d, source_1d = safe_fetch_websocket_with_history('1d', 10)
            if df_1d is not None:
                rest_api_stats['success'].append(f'1d({source_1d})')
            else:
                rest_api_stats['failed'].append(f"1d: {source_1d}")

            if not self._scan_mode:
                self._write_debug_log(f"[DEBUG] [{clean_symbol}] WebSocket 데이터 조회 완료")

            # 데이터 부족 시 스킵
            missing_timeframes = []
            if df_1m is None or len(df_1m) < 3:
                missing_timeframes.append('1m')
            if df_3m is None or len(df_3m) < 3:
                missing_timeframes.append('3m')
            if df_5m is None or len(df_5m) < 3:
                missing_timeframes.append('5m')
            if df_15m is None or len(df_15m) < 3:
                missing_timeframes.append('15m')
            if df_1d is None or len(df_1d) < 3:
                missing_timeframes.append('1d')

            if missing_timeframes:
                # 첫 번째 실패 심볼에 대해서만 상세 로그 출력
                if not hasattr(self, '_first_rest_api_failure'):
                    self._first_rest_api_failure = True
                    self.logger.warning(f"[{clean_symbol}] REST API 데이터 로드 실패")
                    self.logger.warning(f"  성공: {rest_api_stats['success']}")
                    self.logger.warning(f"  실패: {rest_api_stats['failed']}")
                    print(f"⚠️ REST API 로드 실패 예시: {clean_symbol}")
                    print(f"   성공: {rest_api_stats['success']}")
                    print(f"   실패: {rest_api_stats['failed'][:2]}")  # 처음 2개만

                if not self._scan_mode:
                    self._write_debug_log(f"[DEBUG] [{clean_symbol}] 데이터 부족 - 스킵: {', '.join(missing_timeframes)}")
                return None

            # 🚀 데이터 검증 최소화 (성능 최우선)
            # ⚡ 스캔 모드시 모든 검증 스킵
            if not self._scan_mode:
                self._write_debug_log(f"[DEBUG] [{clean_symbol}] 데이터 검증 스킵 (성능 모드)")

            # 🔧 최소 데이터 요구사항 대폭 완화 (거의 모든 데이터 허용)
            min_data_available = True

            # 극단적 완화: 3분봉과 5분봉만 체크
            if df_3m is None or len(df_3m) < 5:  # 20 → 5로 대폭 완화
                min_data_available = False

            if df_5m is None or len(df_5m) < 5:  # 10 → 5로 대폭 완화
                min_data_available = False

            # 🚨 중요: 핵심 데이터만 체크
            if not min_data_available:
                # 최소한의 데이터만 있어도 WATCHLIST로 분류하도록 완화
                if not self._scan_mode:
                    self._write_debug_log(f"[DEBUG] [{clean_symbol}] 데이터 부족하지만 분석 계속 진행")
                # return None  # 이 라인을 주석 처리하여 분석을 계속 진행

            # 🚀 극한 최적화: 필수 지표만 계산 + 병렬화
            if df_1m is not None:
                df_1m = self.calculate_indicators(df_1m)
                if df_1m is None:
                    # 지표 계산 실패 시에도 기본값으로 계속 진행
                    if not self._scan_mode:
                        self._write_debug_log(f"[DEBUG] [{clean_symbol}] 1분봉 지표 계산 실패 - 기본값으로 진행")
            else:
                # 1분봉 데이터가 없어도 계속 진행 (다른 타임프레임으로 분석)
                if not self._scan_mode:
                    self._write_debug_log(f"[DEBUG] [{clean_symbol}] 1분봉 데이터 없음 - 다른 타임프레임으로 분석 계속")
            
            # 3분봉, 15분봉 지표는 필요할 때만 계산 (지연 계산)
            # analyze_symbol에서 check_surge_entry_conditions 호출 전에 계산
            
            
            # ⚡ 24시간 변동률 확인 (티커 우선, WebSocket 폴백)
            change_24h = 0
            if cached_ticker:
                ticker = cached_ticker
                change_24h = ticker.get('percentage', 0) or 0
                self.logger.debug(f"🎯 [{clean_symbol}] 티커 변동률 사용: {change_24h:.1f}%")
            else:
                # 🚨 티커 데이터가 없을 때만 WebSocket 데이터로 24시간 변동률 계산
                if df_1m is not None and len(df_1m) >= 1440:  # 24시간 = 1440분
                    try:
                        current_price = df_1m.iloc[-1]['close']
                        day_ago_price = df_1m.iloc[-1440]['close']
                        if day_ago_price > 0:
                            change_24h = ((current_price - day_ago_price) / day_ago_price) * 100
                    except:
                        change_24h = 0
                elif df_1m is not None and len(df_1m) > 0:
                    # WebSocket 데이터로 추정 (가용한 데이터로 근사 계산)
                    try:
                        available_minutes = len(df_1m)
                        current_price = df_1m.iloc[-1]['close']
                        earliest_price = df_1m.iloc[0]['close']
                        if earliest_price > 0 and available_minutes > 60:
                            # 현재 가용한 시간 구간의 실제 변동률만 계산 (정규화 하지 않음)
                            raw_change = ((current_price - earliest_price) / earliest_price) * 100
                            # 현실적인 범위로 제한하되, 정규화는 하지 않음
                            change_24h = max(-50, min(200, raw_change))
                            print(f"🔍 [{symbol.replace('/USDT:USDT', '')}] WebSocket 변동률 계산: {available_minutes}분 구간 {change_24h:.1f}% (현재:{current_price:.6f}, 시작:{earliest_price:.6f})")
                        else:
                            print(f"⚠️ [{symbol.replace('/USDT:USDT', '')}] WebSocket 변동률 계산 불가: earliest_price={earliest_price}, available_minutes={available_minutes}")
                            change_24h = 0
                    except Exception as e:
                        print(f"⚠️ [{symbol.replace('/USDT:USDT', '')}] WebSocket 변동률 계산 실패: {e}")
                        change_24h = 0

            # 일봉 캔들 변동률 (일봉 시가→고가)
            daily_candle_change = 0
            try:
                if df_1d is not None and len(df_1d) > 0:
                    latest_daily = df_1d.iloc[-1]
                    if pd.notna(latest_daily['open']) and pd.notna(latest_daily['high']) and latest_daily['open'] > 0:
                        daily_candle_change = ((latest_daily['high'] - latest_daily['open']) / latest_daily['open']) * 100
            except:
                daily_candle_change = 0
            
            # 현재 시간 먼저 정의 (예외 발생 시에도 사용 가능하도록)
            current_time = get_korea_time().strftime('%H:%M:%S')
            
            # 전략 분류: 20% 이상이면 급등특별전략
            is_special_strategy = change_24h >= 20.0
            
            # 🚀 극한 속도 모드: 가장 빠른 단순 조건 (250ms 목표)
            if hasattr(self, '_speed_test_mode') and self._speed_test_mode:
                # 데이터 조회 최소화: 1분봉만 사용
                try:
                    # WebSocket 우선 조회 (가장 빠름)
                    df_fast = self.get_websocket_kline_data(symbol, '1m', 50)
                    if df_fast is None or len(df_fast) < 10:
                        # 버퍼 없으면 즉시 포기 (REST API 폴백 금지)
                        return None
                    
                    # 최소한의 지표만 계산 (MA5, MA20 only)
                    if 'ma5' not in df_fast.columns:
                        df_fast['ma5'] = df_fast['close'].rolling(window=5).mean()
                        df_fast['ma20'] = df_fast['close'].rolling(window=20).mean()
                    
                    # 단순 조건: MA5 > MA20 (골든크로스 상태)
                    latest = df_fast.iloc[-1]
                    is_signal = (pd.notna(latest['ma5']) and pd.notna(latest['ma20']) and 
                                latest['ma5'] > latest['ma20'])
                    
                    if is_signal:
                        return {
                            'symbol': symbol,
                            'status': 'entry_signal',
                            'strategy_type': '속도테스트',
                            'price': current_price,
                            'timestamp': current_time,
                            'change_24h': change_24h
                        }
                    else:
                        return None
                        
                except Exception as e:
                    # 오류 시 즉시 포기
                    return None
            else:
                # 🚀 지연 계산: 3분봉, 15분봉 지표를 조건 체크 직전에만 계산
                if df_3m is not None:
                    df_3m = self.calculate_indicators(df_3m)
                if 'df_15m' in locals() and df_15m is not None:
                    df_15m = self.calculate_indicators(df_15m)
                elif 'df_15m' not in locals():
                    df_15m = None  # 🔒 안전장치: 변수 정의되지 않은 경우 None으로 설정
                
                # 일반 모드: 전체 조건 체크 (change_24h 전달) - 안전장치 추가
                try:
                    result_check = self.check_surge_entry_conditions(symbol, df_1m, df_3m, df_1d, df_15m, df_5m, change_24h)
                except NameError as e:
                    if 'df_15m' in str(e):
                        # df_15m 변수 미정의 에러 시 None으로 대체하여 재시도
                        result_check = self.check_surge_entry_conditions(symbol, df_1m, df_3m, df_1d, None, df_5m, change_24h)
                    else:
                        raise e
                
                # 반환값 타입 처리 (True/False/"watchlist" 혼용 문제 해결)
                if isinstance(result_check, tuple) and len(result_check) == 2:
                    is_signal, conditions = result_check
                    # "watchlist" 문자열 처리
                    if is_signal == "watchlist":
                        is_signal = False  # 조건 미충족으로 처리
                        # watchlist 상태는 나중에 분류 로직에서 처리
                else:
                    # 예상치 못한 반환값 처리
                    self._write_debug_log(f"[{clean_symbol}] 예상치 못한 반환값: {result_check}")
                    return None
            
            # 실패한 조건 수 계산 (1분봉 전략 기준)
            # A전략 제거됨 - failed_conditions 계산 제거

            # 현재가 조회 (result 딕셔너리에서 사용) - 안전장치 추가
            current_price = 0.0
            if df_1m is not None and len(df_1m) > 0:
                current_price = df_1m.iloc[-1]['close']
            elif df_3m is not None and len(df_3m) > 0:
                current_price = df_3m.iloc[-1]['close']
            elif df_5m is not None and len(df_5m) > 0:
                current_price = df_5m.iloc[-1]['close']
            else:
                # 가격 정보가 없으면 티커에서 시도
                try:
                    ticker = self.exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
                except:
                    current_price = 1.0  # 최후 대안

            # 변수 기본값 설정 (안전장치)
            if 'daily_candle_change' not in locals():
                daily_candle_change = 0

            # 전략별 평가 결과 파싱 - is_signal이 True인 경우 entry_signal로 처리
            # A전략 관련 코드 완전 제거됨 - 사용자 요청에 따라 전략A 제거
            strategy_3m_2nd_met = False
            strategy_3m_3rd_met = False
            strategy_5m_4th_met = False  # 🔒 안전장치: 변수 초기화 추가
            status_3m_3rd = 'no_signal'  # 기본값 설정
            status_5m_4th = 'no_signal'  # 기본값 설정
            passed_3m_2nd_count = 0
            passed_3m_3rd_count = 0
            
            # 조건별 상세 분석을 위한 파싱
            conditions_3m_2nd = []
            conditions_3m_3rd = []
            
            for cond in conditions:
                # 3분봉 2번째 전략 조건 수집
                if '[3분봉-2번째' in cond or '3분봉 2번째' in cond:
                    conditions_3m_2nd.append(cond)
                    if ': True' in cond:
                        passed_3m_2nd_count += 1
                # 3분봉 3번째 전략 조건 수집
                elif '[3분봉-3번째' in cond or '3분봉 3번째' in cond:
                    conditions_3m_3rd.append(cond)
                    if ': True' in cond:
                        passed_3m_3rd_count += 1
                # 전략 통과 여부 직접 파싱
                elif '[3분봉 2번째 전략] 조건 통과:' in cond:
                    parts = cond.split('→')
                    if len(parts) == 2:
                        strategy_3m_2nd_met = 'True' in parts[1]
                elif '[3분봉 3번째 전략] 조건 통과:' in cond:
                    parts = cond.split('→')
                    if len(parts) == 2:
                        strategy_3m_3rd_met = 'True' in parts[1]
                    if '/' in cond:
                        passed_3m_3rd_count = int(cond.split('조건 통과: ')[1].split('/')[0])
                elif '[5분봉 D전략] 조건 통과:' in cond:
                    parts = cond.split('→')
                    if len(parts) == 2:
                        strategy_5m_4th_met = 'True' in parts[1]

            # 3분봉 2번째 전략 조건들
            conditions_3m_2nd = [cond for cond in conditions if cond.startswith('[3분봉 2번째')]
            failed_3m_2nd = len([cond for cond in conditions_3m_2nd if ': False' in cond])

            # 3분봉 3번째 전략 조건들
            conditions_3m_3rd = [cond for cond in conditions if cond.startswith('[3분봉 3번째')]
            failed_3m_3rd = len([cond for cond in conditions_3m_3rd if ': False' in cond])

            # 5분봉 D전략 조건들 (디버깅 개선)
            conditions_5m_4th = [cond for cond in conditions if cond.startswith('[5분봉 D전략')]
            # ✅ FIX: 조건1~5만 카운트 (최종 조건 제외)
            import re
            failed_5m_4th = len([cond for cond in conditions_5m_4th
                                if re.search(r'\[5분봉 D전략-[1-5]\]', cond) and ': False' in cond])
            
            # 🔍 디버깅: D전략 조건 상세 분석 (상세 버전)
            true_conditions_5m = [cond for cond in conditions_5m_4th if ': True' in cond]
            false_conditions_5m = [cond for cond in conditions_5m_4th if ': False' in cond]
            
            d_strategy_debug = {
                'total_d_conditions': len(conditions_5m_4th),
                'true_conditions': len(true_conditions_5m),
                'false_conditions': len(false_conditions_5m),
                'failed_5m_4th_calc': failed_5m_4th,
                'true_list': true_conditions_5m,
                'false_list': false_conditions_5m
            }
            self._write_debug_log(f"[DEBUG-D전략] {symbol}: {d_strategy_debug}")

            # 각 전략별로 분석 결과 생성 (C전략 → D전략 순서로 변경)
            results = []

            # 🔄 C전략 먼저 처리: 3분봉 3번째 전략 결과 (실제 전략 통과 여부 기준)
            if strategy_3m_3rd_met:  # 전략 통과 (1 AND (2 OR 3) 구조)
                status_3m_3rd = 'entry_signal'
            else:
                # 🔧 개별 조건 실패 개수 기준으로 분류 (일관성 있는 분류)
                # 먼저 개별 조건들을 확인하여 실패 개수를 계산
                condition_3m_c1_met = any('[3분봉 3번째-1]' in cond and ': True' in cond for cond in conditions_3m_3rd)
                condition_3m_c2a_met = any('[3분봉 3번째-2A]' in cond and ': True' in cond for cond in conditions_3m_3rd)
                condition_3m_c2b_met = any('[3분봉 3번째-2B]' in cond and ': True' in cond for cond in conditions_3m_3rd)
                condition_3m_c3a_met = any('[3분봉 3번째-3A]' in cond and ': True' in cond for cond in conditions_3m_3rd)
                condition_3m_c3b_met = any('[3분봉 3번째-3B]' in cond and ': True' in cond for cond in conditions_3m_3rd)
                
                # 새로운 3개 조건 체계에 맞춘 실패 조건 카운트
                failed_conditions_preview = []
                
                # 조건1: BB200-BB480 골든크로스 확인
                condition_1_met = False
                for cond in conditions_3m_3rd:
                    if '[3분봉 3번째-1]' in cond and ': True' in cond:
                        condition_1_met = True
                        break
                
                # 조건2: (2A AND 2B AND 2C) 복합 조건 확인
                condition_2_met = False
                for cond in conditions_3m_3rd:
                    if '[3분봉 3번째-조건2] (2A AND 2B AND 2C): True' in cond:
                        condition_2_met = True
                        break
                
                # SuperTrend 확인
                supertrend_met = False
                for cond in conditions_3m_3rd:
                    if '[3분봉 3번째 전략] SuperTrend:' in cond and 'SuperTrend: True' in cond:
                        supertrend_met = True
                        break
                
                # 실패한 조건 개수 계산
                if not condition_1_met:
                    failed_conditions_preview.append("조건1")
                if not condition_2_met:
                    failed_conditions_preview.append("조건2")
                if not supertrend_met:
                    failed_conditions_preview.append("SuperTrend")
                
                failed_count_preview = len(failed_conditions_preview)
                
                # 🚨 FIX: 전략C 데이터 부족 검사 추가
                is_data_insufficient_c = any("데이터 부족" in cond for cond in conditions_3m_3rd)
                
                # 실패 개수에 따른 분류 (새로운 기준)
                if is_data_insufficient_c:  # 데이터 부족인 경우
                    status_3m_3rd = 'no_signal'
                    self._write_debug_log(f"[DATA INSUFFICIENT] {symbol}: 3분봉 데이터 부족으로 전략C 조건 검사 불가")
                elif failed_count_preview == 0:
                    status_3m_3rd = 'entry_signal'  # 모든 조건 통과
                elif failed_count_preview == 1:
                    status_3m_3rd = 'near_entry'  # 1개 미충족 → 진입임박
                elif failed_count_preview == 2:
                    status_3m_3rd = 'potential_entry'  # 2개 미충족 → 진입확률
                elif failed_count_preview == 3:  # 3개 모두 미충족 → 신호 없음
                    status_3m_3rd = 'no_signal'
                else:
                    status_3m_3rd = 'no_signal'

            # 🔍 디버그: 전략C 상태 출력 (디버그 모드에서만)
            if not self._scan_mode or (hasattr(self, '_debug_print_enabled') and self._debug_print_enabled):
                print(f"🔍 [전략C] {symbol.replace('/USDT:USDT', '')}: failed={failed_count_preview}, status={status_3m_3rd}")

            if status_3m_3rd != 'no_signal':
                # 🔧 전략C는 2개 조건으로 수정 (조건1 + 조건2 + SuperTrend)
                total_conditions_count = 3  # 조건1, 조건2, SuperTrend
                failed_count_logical = min(failed_count_preview, total_conditions_count)  # 최대값 제한
                
                result_3m_3rd = {
                    'symbol': symbol,
                    'status': status_3m_3rd,
                    'strategy_type': '전략C: 3분봉 시세 초입 포착',
                    'total_conditions': total_conditions_count,
                    'failed_count': failed_count_logical,
                    'conditions': conditions_3m_3rd,
                    'conditions_summary': [f"3분봉3차-복합조건 {total_conditions_count-failed_count_logical}/{total_conditions_count}개 통과"],
                    'price': current_price,
                    'timestamp': current_time,
                    'change_24h': change_24h,
                    'daily_candle_change': daily_candle_change
                }
                results.append(result_3m_3rd)

            # D전략 다음 처리: 5분봉 D전략 결과 (안전장치: 변수 존재 확인)
            strategy_5m_4th_met_safe = locals().get('strategy_5m_4th_met', False)
            
            # 🔍 디버깅: D전략 통과 조건 분석
            self._write_debug_log(f"[DEBUG-D전략] {symbol}: strategy_5m_4th_met_safe={strategy_5m_4th_met_safe}, failed_5m_4th={failed_5m_4th}")
            
            # 전략 D 데이터 부족 여부 확인
            is_data_insufficient = any("데이터 부족" in cond for cond in conditions_5m_4th)
            
            if strategy_5m_4th_met_safe:  # 전략 통과 (5개 조건 모두 충족)
                status_5m_4th = 'entry_signal'
            elif is_data_insufficient:  # 🚨 FIX: 데이터 부족인 경우 no_signal로 분류
                status_5m_4th = 'no_signal'  # watchlist → no_signal로 수정
                self._write_debug_log(f"[DATA INSUFFICIENT] {symbol}: 5분봉 데이터 부족으로 전략D 조건 검사 불가")
            else:
                # 실패 개수에 따른 분류 (전략D는 5개 조건)
                if failed_5m_4th == 0:  # 🚨 FIX: 모든 조건 통과
                    status_5m_4th = 'entry_signal'
                elif failed_5m_4th == 1:  # 1개 미충족 → 진입임박
                    status_5m_4th = 'near_entry'
                elif failed_5m_4th == 2:  # 2개 미충족 → 진입확률
                    status_5m_4th = 'potential_entry'
                elif failed_5m_4th == 3 or failed_5m_4th == 4:  # 3-4개 미충족 → 관심종목
                    status_5m_4th = 'watchlist'
                elif failed_5m_4th == 5:  # 5개 모두 미충족 → 신호 없음
                    status_5m_4th = 'no_signal'
                else:
                    status_5m_4th = 'no_signal'

            # 🔍 디버그: 전략D 상태 출력 (항상 출력으로 임시 변경)
            if not is_data_insufficient and (status_5m_4th == 'near_entry' or status_5m_4th == 'potential_entry'):
                clean_name = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                # conditions_5m_4th에서 각 조건 파싱
                d_conds = {}
                for cond in conditions_5m_4th:
                    if '[5분봉 D전략-1]' in cond:
                        d_conds['d1'] = 'True' in cond
                    elif '[5분봉 D전략-2]' in cond:
                        d_conds['d2'] = 'True' in cond
                    elif '[5분봉 D전략-3]' in cond:
                        d_conds['d3'] = 'True' in cond
                    elif '[5분봉 D전략-4]' in cond:
                        d_conds['d4'] = 'True' in cond
                    elif '[5분봉 D전략-5]' in cond:
                        d_conds['d5'] = 'True' in cond

                print(f"🔍 [전략D-{status_5m_4th.upper()}] {clean_name}: failed={failed_5m_4th}/5 | d1={d_conds.get('d1', '?')} d2={d_conds.get('d2', '?')} d3={d_conds.get('d3', '?')} d4={d_conds.get('d4', '?')} d5={d_conds.get('d5', '?')}")

            # 🔧 데이터 부족인 경우에도 결과에 포함 (no_signal인 경우만 제외)
            if status_5m_4th != 'no_signal':
                # 실패 개수 정확히 계산
                if is_data_insufficient:
                    actual_failed_for_display = 5  # 데이터 부족인 경우 모든 조건 실패로 표시
                else:
                    actual_failed_for_display = failed_5m_4th
                
                result_5m_4th = {
                    'symbol': symbol,
                    'status': status_5m_4th,
                    'strategy_type': '전략D: 5분봉 초입 초강력 타점',
                    'total_conditions': 5,
                    'failed_count': actual_failed_for_display,
                    'conditions': conditions_5m_4th,
                    'conditions_summary': [f"5분봉D전략-{5-actual_failed_for_display}/5개 통과"],
                    'price': current_price,
                    'timestamp': current_time,
                    'change_24h': change_24h,
                    'daily_candle_change': daily_candle_change
                }
                results.append(result_5m_4th)

            # 🗑️ 3분봉 2번째 전략 (비활성화됨) - 더 이상 사용하지 않음
            # strategy_3m_2nd_met 관련 코드 제거됨

            # 🔍 분석 결과 디버깅 출력 (AI16Z 문제 해결용)
            self._write_debug_log(f"[DEBUG] [{clean_symbol}] 최종 분석 결과:")
            self._write_debug_log(f"[DEBUG]   - is_signal (check_surge_entry_conditions): {is_signal}")
            # A전략 제거됨 - strategy_1m_15m_met 변수 삭제
            self._write_debug_log(f"[DEBUG]   - strategy_3m_2nd_met: {strategy_3m_2nd_met}")
            self._write_debug_log(f"[DEBUG]   - strategy_3m_3rd_met: {strategy_3m_3rd_met}")
            # 안전장치: strategy_5m_4th_met 변수 안전하게 참조 (스코프 문제 해결)
            strategy_5m_4th_met_value = locals().get('strategy_5m_4th_met', False)
            self._write_debug_log(f"[DEBUG]   - strategy_5m_4th_met: {strategy_5m_4th_met_value}")
            self._write_debug_log(f"[DEBUG]   - results 개수: {len(results) if results else 0}")
            
            if results:
                for i, result in enumerate(results):
                    self._write_debug_log(f"[DEBUG]   - 결과 {i+1}: {result['strategy_type']} - {result['status']}")
            else:
                self._write_debug_log(f"[DEBUG]   - 결과 없음 (모든 조건 미충족)")
            
            # 🔍 임시 디버깅: 결과 상태 확인
            if self._scan_mode and results:
                self.logger.debug(f"🔍 [DEBUG] {clean_symbol}: {len(results)}개 결과 반환")
                for result in results:
                    if isinstance(result, dict):
                        self.logger.debug(f"   - {result['strategy_type']}: {result['status']} (실패:{result.get('failed_count', 0)})")
                    else:
                        self.logger.debug(f"   - 타입 오류: {type(result)} - {result}")
            elif self._scan_mode and not results:
                self.logger.debug(f"❌ [DEBUG] {clean_symbol}: 결과 없음")
            
            # 🚨 안전장치: 모든 조건이 실패해도 최소한 WATCHLIST로라도 분류 (0개 결과 방지)
            if not results:
                # 기본 WATCHLIST 항목 생성 (데이터 부족이나 조건 미충족 시)
                fallback_result = {
                    'symbol': symbol,
                    'status': 'watchlist',
                    'strategy_type': '기본 관심목록 (조건 미충족)',
                    'total_conditions': 3,
                    'failed_count': 3,
                    'conditions': ["모든 조건 미충족 또는 데이터 부족"],
                    'conditions_summary': ["기본 관심목록 0/3개 통과"],
                    'price': current_price,
                    'timestamp': current_time,
                    'change_24h': change_24h,
                    'daily_candle_change': daily_candle_change if 'daily_candle_change' in locals() else 0
                }
                results = [fallback_result]
                if self._scan_mode:
                    self.logger.debug(f"🔄 [FALLBACK] {clean_symbol}: 기본 WATCHLIST로 분류")
            
            return results if results else None

        except Exception as e:
            self.logger.error(f"{symbol} 분석 실패: {e}")
            return None

    def _print_entry_signals(self, entry_signals):
        """ENTRY 신호 출력 함수 (거래 실행 제외)"""
        if not entry_signals:
            print(f"\n[SIGNAL] 진입신호 [전략C: 3분봉 시세 초입 포착]")
            print("   없음")
            print(f"\n[SIGNAL] 진입신호 [전략D: 5분봉 초입 초강력 타점]")
            print("   없음")
            return

        # 전략별로 그룹핑
        strategy_groups = {}
        for result in entry_signals:
            strategy_type = result.get('strategy_type', '전략C: 3분봉 시세 초입 포착')
            if strategy_type not in strategy_groups:
                strategy_groups[strategy_type] = []
            strategy_groups[strategy_type].append(result)

        # 전략별로 출력 (C+D → C → D 순서)
        strategy_order = ['전략C+D: 3분봉+5분봉 복합 진입', '전략C: 3분봉 시세 초입 포착', '전략D: 5분봉 초입 초강력 타점']
        for strategy in strategy_order:
            if strategy not in strategy_groups:
                continue
            signals = strategy_groups[strategy]
            print(f"\n[SIGNAL] 진입신호 [{strategy}]")
            for result in signals:
                clean_symbol = result['symbol'].replace('/USDT:USDT', '').replace('/USDT', '')
                # 충족된 조건들 가져오기
                satisfied_conditions = result.get('conditions_summary', ['전체조건충족'])
                conditions_text = " | ".join(satisfied_conditions) if satisfied_conditions else "전체조건충족"

                # 이미 계산된 24시간 변동률 사용 (API 호출 방지)
                try:
                    change_pct = result.get('change_24h', 0)
                    # 문자열을 숫자로 안전하게 변환
                    try:
                        change_pct = float(change_pct) if change_pct != 0 else 0.0
                    except (ValueError, TypeError):
                        change_pct = 0.0

                    # 🔥 진입신호 - 심볼명 초록색, 이모지 빨간색
                    print(f"\033[91m🔥\033[0m \033[92m\033[1m{clean_symbol}\033[0m [24h:{change_pct:+.1f}%]")
                    print(f"      🎯 충족조건: {conditions_text}")
                except Exception as e:
                    # 변동률 계산 실패시에도 기본 정보는 출력
                    change_pct = result.get('change_24h', 0)
                    try:
                        change_pct = float(change_pct) if change_pct != 0 else 0.0
                    except:
                        change_pct = 0.0
                    print(f"   \033[92m\033[1m{clean_symbol}\033[0m [24h:{change_pct:+.1f}%]")
                    print(f"      🎯 충족조건: {conditions_text}")
                    print(f"      ⚠️ 변동률 조회 오류: {e}")

    def _print_near_entry_signals(self, near_entry):
        """NEAR_ENTRY 신호 출력 함수"""
        # 심볼별로 NEAR 결과 그룹핑 (동일 심볼에 대해 두 전략 결과 모두 표시)
        near_by_symbol = {}
        for result in near_entry:
            symbol = result['symbol']
            if symbol not in near_by_symbol:
                near_by_symbol[symbol] = {}
            strategy_type = result.get('strategy_type', '전략C: 3분봉 시세 초입 포착')
            near_by_symbol[symbol][strategy_type] = result

        # 전략별로 NEAR 출력 (전략별 그룹화)
        if near_by_symbol:
            # 전략별로 그룹핑
            near_groups = {}
            for symbol, strategies in near_by_symbol.items():
                for strategy_type, result in strategies.items():
                    if strategy_type not in near_groups:
                        near_groups[strategy_type] = []
                    near_groups[strategy_type].append((symbol, result))

            # 전략별로 출력 (C+D → C → D 순서)
            strategy_order = ['전략C+D: 3분봉+5분봉 복합 진입', '전략C: 3분봉 시세 초입 포착', '전략D: 5분봉 초입 초강력 타점']
            for strategy_type in strategy_order:
                print(f"\n진입임박 [{strategy_type}] (1개 조건 미충족)")
                if strategy_type not in near_groups:
                    print("   없음")
                    continue
                symbol_results = near_groups[strategy_type]

                for symbol, result in symbol_results:
                    clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                    change_pct = result.get('change_24h', 0)
                    # 문자열을 숫자로 안전하게 변환
                    try:
                        change_pct = float(change_pct) if change_pct != 0 else 0.0
                    except (ValueError, TypeError):
                        change_pct = 0.0

                    if strategy_type == '전략D: 5분봉 초입 초강력 타점':
                        total_conditions = result.get('total_conditions', 6)
                        failed_count = result.get('failed_count', 0)

                        # 문자열을 숫자로 안전하게 변환
                        try:
                            total_conditions = int(total_conditions)
                            failed_count = int(failed_count)
                        except (ValueError, TypeError):
                            total_conditions = 6
                            failed_count = 0

                        # 통과한 조건 개수 계산 (음수 방지)
                        passed_count = max(0, total_conditions - failed_count)

                        # 🎨 새로운 형식으로 표시: UB [+-2.7%] (2/3) ⚠️ 1개 조건 미충족
                        if failed_count == 1:
                            print(f"   \033[93m\033[1m{clean_symbol}\033[0m [{change_pct:+.1f}%] ({passed_count}/{total_conditions}) ⚠️ 1개 조건 미충족")
                        else:
                            print(f"   {clean_symbol} [{change_pct:+.1f}%] ({passed_count}/{total_conditions}) ⚠️ {failed_count}개 조건 미충족")

                        # 실패한 조건들만 명확하게 표시 (최종 조건 제외)
                        all_conditions = result['conditions']
                        failed_main_conditions = [cond for cond in all_conditions
                                                 if ': False' in cond
                                                 and not cond.strip().startswith('ㄴ')
                                                 and '최종' not in cond]

                        for failed_condition in failed_main_conditions:
                            # 조건 설명 추출
                            condition_desc = self._extract_condition_description(failed_condition)

                            # 🎨 1개 실패(near_entry)인 경우 미충족 조건을 주황색으로 표시
                            if failed_count == 1:
                                print(f"\033[33m      ❌ {condition_desc}\033[0m")
                            else:
                                print(f"\033[91m      ❌ {condition_desc}\033[0m")

                            # 해당 조건의 바로 다음 상세 정보들만 출력
                            failed_idx = all_conditions.index(failed_condition)
                            for i in range(failed_idx + 1, len(all_conditions)):
                                if all_conditions[i].strip().startswith('ㄴ'):
                                    print(f"\033[91m         {all_conditions[i]}\033[0m")
                                else:
                                    break

                    elif strategy_type == '전략C: 3분봉 시세 초입 포착':
                        total_conditions = result.get('total_conditions', 6)
                        failed_count = result.get('failed_count', 0)

                        # 문자열을 숫자로 안전하게 변환
                        try:
                            total_conditions = int(total_conditions)
                            failed_count = int(failed_count)
                        except (ValueError, TypeError):
                            total_conditions = 6
                            failed_count = 0

                        # 통과한 조건 개수 계산 (음수 방지)
                        passed_count = max(0, total_conditions - failed_count)

                        # 🎨 새로운 형식으로 표시: UB [+-2.7%] (2/3) ⚠️ 1개 조건 미충족
                        if failed_count == 1:
                            print(f"   \033[93m\033[1m{clean_symbol}\033[0m [{change_pct:+.1f}%] ({passed_count}/{total_conditions}) ⚠️ 1개 조건 미충족")
                        else:
                            print(f"   {clean_symbol} [{change_pct:+.1f}%] ({passed_count}/{total_conditions}) ⚠️ {failed_count}개 조건 미충족")

                        # 실패한 조건들만 명확하게 표시 (최종 조건 제외)
                        all_conditions = result['conditions']
                        failed_main_conditions = [cond for cond in all_conditions
                                                 if ': False' in cond
                                                 and not cond.strip().startswith('ㄴ')
                                                 and '최종' not in cond]

                        for failed_condition in failed_main_conditions:
                            # 조건 설명 추출
                            condition_desc = self._extract_condition_description(failed_condition)

                            # 🎨 1개 실패(near_entry)인 경우 미충족 조건을 주황색으로 표시
                            if failed_count == 1:
                                print(f"\033[33m      ❌ {condition_desc}\033[0m")
                            else:
                                print(f"\033[91m      ❌ {condition_desc}\033[0m")

                            # 해당 조건의 바로 다음 상세 정보들만 출력
                            failed_idx = all_conditions.index(failed_condition)
                            for i in range(failed_idx + 1, len(all_conditions)):
                                if all_conditions[i].strip().startswith('ㄴ'):
                                    print(f"\033[91m         {all_conditions[i]}\033[0m")
                                else:
                                    break
        else:
            # 활성화된 전략만 표시 (C전략 → D전략 순서)
            print(f"\n진입임박 [전략C: 3분봉 시세 초입 포착] (1개 조건 미충족)")
            print("   없음")
            print(f"\n진입임박 [전략D: 5분봉 초입 초강력 타점] (1개 조건 미충족)")
            print("   없음")

    def _print_potential_entry_signals(self, potential_entry):
        """POTENTIAL_ENTRY 신호 출력 함수"""
        if potential_entry:
            # 전략별로 그룹핑
            potential_groups = {}
            for result in potential_entry:
                strategy_type = result.get('strategy_type', '전략C: 3분봉 시세 초입 포착')
                if strategy_type not in potential_groups:
                    potential_groups[strategy_type] = []
                potential_groups[strategy_type].append(result)

            # 전략별로 출력 (가로 정렬, C+D → C → D 순서)
            strategy_order = ['전략C+D: 3분봉+5분봉 복합 진입', '전략C: 3분봉 시세 초입 포착', '전략D: 5분봉 초입 초강력 타점']
            for strategy_type in strategy_order:
                print(f"\n진입확률 [{strategy_type}] (2개 조건 미충족)")
                if strategy_type not in potential_groups:
                    print("   없음")
                    continue
                results = potential_groups[strategy_type]

                # 심볼별로 미충족 조건 자세히 출력 (테이블 형식)
                for result in results:
                    clean_symbol = result['symbol'].replace('/USDT:USDT', '').replace('/USDT', '')
                    change_24h = result.get('change_24h', 0)
                    try:
                        change_24h = float(change_24h) if change_24h != 0 else 0.0
                    except (ValueError, TypeError):
                        change_24h = 0.0

                    failed_count = result.get('failed_count', 0)
                    total_conditions = result.get('total_conditions', 6)

                    try:
                        failed_count = int(failed_count)
                        total_conditions = int(total_conditions)
                    except (ValueError, TypeError):
                        failed_count = 0
                        total_conditions = 6

                    passed_count = total_conditions - failed_count

                    # 미충족 조건들 수집
                    all_conditions = result.get('conditions', [])
                    failed_main_conditions = [cond for cond in all_conditions
                                             if ': False' in cond
                                             and not cond.strip().startswith('ㄴ')
                                             and '최종' not in cond]

                    failed_msgs = []
                    for failed_condition in failed_main_conditions:
                        # 조건 번호를 구체적인 설명으로 변경
                        if '[3분봉 3번째-1]' in failed_condition:
                            failed_msgs.append("조건1: BB200상단-BB480상단 골든크로스")
                        elif '[3분봉 3번째-2A]' in failed_condition:
                            failed_msgs.append("조건2A: MA5-MA20 데드크로스 확인")
                        elif '[3분봉 3번째-2B]' in failed_condition:
                            failed_msgs.append("조건2B: MA1-MA5 골든크로스")
                        elif '[3분봉 3번째-2C]' in failed_condition:
                            failed_msgs.append("조건2C: MA5<MA20 또는 이격도 2%이내")
                        elif '[5분봉 D전략-1]' in failed_condition:
                            failed_msgs.append("D조건1: 15분봉 MA80<MA480")
                        elif '[5분봉 D전략-2]' in failed_condition:
                            failed_msgs.append("D조건2: 5분봉 SuperTrend 매수신호")
                        elif '[5분봉 D전략-3]' in failed_condition:
                            failed_msgs.append("D조건3: MA80-MA480 골든크로스 OR 이격도<5%")
                        elif '[5분봉 D전략-4]' in failed_condition:
                            failed_msgs.append("D조건4: MA480 하락+BB200-MA480 골든")
                        elif '[5분봉 D전략-5]' in failed_condition:
                            failed_msgs.append("D조건5: MA5-MA20 골든크로스")
                        # 단순한 조건명들 처리 (실제 출력에서 나오는 패턴들)
                        elif 'condition_3m_c1' in failed_condition or '조건1' in failed_condition:
                            failed_msgs.append("조건1: BB200상단-BB480상단 골든크로스")
                        elif 'condition_2' in failed_condition or '조건2' in failed_condition:
                            # 세부 조건을 확인하여 더 구체적으로 분류
                            if '2B' in failed_condition or 'c2b' in failed_condition:
                                failed_msgs.append("조건2B: MA1-MA5 골든크로스")
                            elif '2A' in failed_condition or 'c2a' in failed_condition:
                                failed_msgs.append("조건2A: MA5-MA20 데드크로스 확인")
                            elif '2C' in failed_condition or 'c2c' in failed_condition:
                                failed_msgs.append("조건2C: MA5<MA20 또는 이격도 2%이내")
                            else:
                                failed_msgs.append("조건2: 복합 MA 조건 (2A AND 2B AND 2C)")
                        else:
                            # 알 수 없는 조건은 _extract_condition_description 사용
                            condition_desc = self._extract_condition_description(failed_condition)
                            failed_msgs.append(condition_desc)

                    # 🎨 새로운 형식으로 표시: UB [+-2.7%] (2/3) ⚠️ 2개 조건 미충족
                    failed_count = total_conditions - passed_count
                    print(f"   {clean_symbol} [{change_24h:+.1f}%] ({passed_count}/{total_conditions}) ⚠️ {failed_count}개 조건 미충족")
                    # 미충족 조건들을 상세히 표시
                    for failed_msg in failed_msgs:
                        print(f"\033[91m      ❌ {failed_msg}\033[0m")
        else:
            # 모든 전략을 개별적으로 표시 (C전략 → D전략 순서)
            print(f"\n진입확률 [전략C: 3분봉 시세 초입 포착] (2개 조건 미충족)")
            print("   없음")
            print(f"\n진입확률 [전략D: 5분봉 초입 초강력 타점] (2개 조건 미충족)")
            print("   없음")

    def _print_watchlist_signals(self, watchlist):
        """WATCHLIST 신호 출력 함수"""
        if watchlist:
            # 전략별로 그룹핑
            watchlist_groups = {}
            for result in watchlist:
                strategy_type = result.get('strategy_type', '전략C: 3분봉 시세 초입 포착')
                if strategy_type not in watchlist_groups:
                    watchlist_groups[strategy_type] = []
                watchlist_groups[strategy_type].append(result)

            # 📊 미충족 조건 통계 수집
            failed_condition_stats = {}

            # 전략별로 출력 (C+D → C → D 순서)
            strategy_order = ['전략C+D: 3분봉+5분봉 복합 진입', '전략C: 3분봉 시세 초입 포착', '전략D: 5분봉 초입 초강력 타점']
            for strategy in strategy_order:
                # 🚨 FIX: 하드코딩 제거하고 실제 조건 상태 표시
                if strategy not in watchlist_groups:
                    print(f"\n[WATCHLIST] 관심종목 [{strategy}] (조건 미충족)")
                    print("   없음")
                    continue

                # 실제 조건 통계 계산
                items = watchlist_groups[strategy]
                failed_counts = [result.get('failed_count', 0) for result in items]
                total_counts = [result.get('total_conditions', 3 if 'C:' in strategy else 5) for result in items]

                # 대표값 계산 (가장 많은 유형)
                avg_failed = sum(failed_counts) / len(failed_counts) if failed_counts else 0
                avg_total = sum(total_counts) / len(total_counts) if total_counts else (3 if 'C:' in strategy else 5)

                print(f"\n[WATCHLIST] 관심종목 [{strategy}] ({avg_failed:.0f}개 조건 미충족, 평균 {avg_total-avg_failed:.0f}/{avg_total:.0f} 통과)")

                # 심볼 정보 수집
                symbol_infos = []
                for result in items:
                    clean_symbol = result['symbol'].replace('/USDT:USDT', '').replace('/USDT', '')
                    change_24h = result.get('change_24h', 0)
                    # 문자열을 숫자로 안전하게 변환
                    try:
                        change_24h = float(change_24h) if change_24h != 0 else 0.0
                    except (ValueError, TypeError):
                        change_24h = 0.0

                    failed_count = result.get('failed_count', 0)
                    total_conditions = result.get('total_conditions', 11)

                    # 문자열을 숫자로 안전하게 변환
                    try:
                        failed_count = int(failed_count)
                        total_conditions = int(total_conditions)
                    except (ValueError, TypeError):
                        failed_count = 0
                        total_conditions = 11

                    # 🔧 안전한 통과 조건 계산 (음수 방지)
                    passed_count = max(0, total_conditions - failed_count)

                    # 미충족 조건 추출 (통계용)
                    conditions = result.get('conditions', [])
                    failed_conditions = [cond for cond in conditions if ': False' in cond]

                    # 통계 수집
                    for failed_cond in failed_conditions:
                        cond_name = failed_cond.split(':')[0].strip()
                        if cond_name not in failed_condition_stats:
                            failed_condition_stats[cond_name] = 0
                        failed_condition_stats[cond_name] += 1

                    # 심볼 정보 포맷: SYMBOL(+변동률%, 통과/전체) - 음수 방지
                    symbol_infos.append(f"{clean_symbol}({change_24h:+.1f}%, {passed_count}/{total_conditions})")

                # 가로 정렬 출력 (한 줄에 5개씩)
                for i in range(0, len(symbol_infos), 5):
                    batch = symbol_infos[i:i+5]
                    print(f"   {' | '.join(batch)}")

            # 📊 전체 미충족 조건 통계 출력
            if failed_condition_stats:
                print(f"\n" + "="*60)
                print(f"📊 관심종목 미충족 조건 통계 (상위 10개)")
                print(f"="*60)

                # 빈도순으로 정렬
                sorted_stats = sorted(failed_condition_stats.items(), key=lambda x: x[1], reverse=True)

                for idx, (cond_name, count) in enumerate(sorted_stats[:10], 1):
                    # 조건 이름 간소화
                    display_name = cond_name.replace('[3분봉 2번째-', '조건').replace(']', '')
                    percentage = (count / len(watchlist)) * 100
                    print(f"{idx:2d}. {display_name:50s} : {count:2d}회 ({percentage:5.1f}%)")

                print(f"="*60)
        else:
            print(f"\n[WATCHLIST] 관심종목 (3~4개 조건 미충족)")
            print("   없음")

    def scan_symbols(self, symbols):
        """심볼들 병렬 스캔 (Rate Limit 고려) - 버그 수정된 안전 버전"""
        # 🔄 스캔 전 포지션 동기화 (수동 청산 반영) - 조용한 모드
        self.sync_positions_with_exchange(quiet=True)
        print(f"✅ [스캔 준비] {len(symbols)}개 심볼 스캔 시작 (활성 포지션: {len(self.active_positions)}개)")

        # ⚡ 스캔 모드 활성화 (디버그 로깅 최소화)
        self._scan_mode = True

        # ⚡ 스캔 중 로그 레벨을 ERROR로 변경 (WARNING 숨김)
        original_log_level = self.logger.level
        self.logger.setLevel(logging.ERROR)

        all_results = []
        
        # 🔍 임시 디버깅: 스캔 통계
        total_analyzed = 0
        results_found = 0
        
        print(f"🔍 스캔 시작: {len(symbols)}개 심볼 분석 예정")

        # 🎯 티커 데이터 미리 가져오기 (24시간 변동률 정확성 향상)
        print("📊 티커 데이터 수집 중...")
        tickers_cache = {}
        try:
            all_tickers = self.exchange.fetch_tickers()
            for symbol in symbols:
                if symbol in all_tickers:
                    tickers_cache[symbol] = all_tickers[symbol]
            print(f"✅ 티커 데이터 수집 완료: {len(tickers_cache)}개/{len(symbols)}개")
        except Exception as e:
            print(f"⚠️ 티커 데이터 수집 실패: {e} - WebSocket 데이터로 폴백")

        # 🚀 극한 속도 모드: 병렬 처리 간소화 (250ms 목표)
        if hasattr(self, '_speed_test_mode') and self._speed_test_mode:
            # 순차 처리로 변경 (병렬 처리 오버헤드 제거)
            for symbol in symbols:
                try:
                    cached_ticker = tickers_cache.get(symbol)
                    result = self.analyze_symbol(symbol, cached_ticker)
                    if result:
                        if isinstance(result, dict):
                            all_results.append(result)
                        elif isinstance(result, list):
                            all_results.extend(result)
                except Exception as e:
                    continue  # 에러 시 무시하고 계속
        else:
            # ⚡ 스캔 속도 개선: 캐시 조회는 안전하므로 병렬 증가
            # REST API는 별도 제한이 있으므로 스캔은 빠르게
            max_workers = min(len(symbols), 30)  # 10 → 30 (3배 빠르게!)
            
            # 🛡️ 스레드 안전 버전: future 객체와 symbol을 안전하게 매핑
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 안전한 매핑: 튜플로 저장하여 타입 안전성 보장
                submitted_futures = []
                for symbol in symbols:
                    try:
                        cached_ticker = tickers_cache.get(symbol)
                        future = executor.submit(self.analyze_symbol, symbol, cached_ticker)
                        submitted_futures.append((future, symbol))
                    except Exception as submit_error:
                        self.logger.error(f"{symbol} 작업 제출 실패: {submit_error}")

                # 캐시 통계
                cache_size = len(self._ohlcv_cache)
                expected_cache_entries = len(symbols) * 4  # 4 timeframes per symbol

                # WebSocket 버퍼 확인
                ws_buffer_count = 0
                if hasattr(self, 'ws_kline_manager') and self.ws_kline_manager:
                    if hasattr(self, '_websocket_kline_buffer'):
                        ws_buffer_count = len(self._websocket_kline_buffer)

                print(f"⚡ 병렬 분석 시작: {len(submitted_futures)}개 심볼 (스레드: {max_workers}개, 캐싱 활성화)")

                # 예상 API 호출 계산 (더 정확하게)
                expected_api_calls = max(0, expected_cache_entries - cache_size - ws_buffer_count)

                if cache_size >= expected_cache_entries * 0.8:
                    print(f"🔥 캐시 최적화: {cache_size}개 캐시 히트 → 초고속 (<5초)")
                elif ws_buffer_count > expected_cache_entries * 0.5:
                    print(f"🚀 WebSocket 모드: {ws_buffer_count}개 버퍼 → 고속 (<10초)")
                elif cache_size > 0 or ws_buffer_count > 0:
                    print(f"⚡ 하이브리드: 캐시({cache_size}) + WebSocket({ws_buffer_count}) + API({expected_api_calls}예상)")
                else:
                    print(f"🔄 첫 스캔: 데이터 수집 중 (캐시 구축), 다음 스캔부터 초고속")

                # 🚀 결과 수집 (타입 안전 보장 + 진행 상황 표시)
                completed_count = 0
                for future, symbol in submitted_futures:
                    completed_count += 1
                    # 진행 상황 출력 빈도 최소화 (250개 → 500개마다)
                    if completed_count % 500 == 0 or completed_count == len(submitted_futures):
                        print(f"⚡ 진행 중: {completed_count}/{len(submitted_futures)}", end='\r')

                    try:
                        # 🚀 타임아웃 단축: 캐싱으로 대부분 즉시 반환
                        result = future.result(timeout=2)  # 2초 타임아웃 (캐시 히트시 즉시)
                        
                        total_analyzed += 1
                        if result:
                            results_found += 1
                            # 결과 타입 검증
                            if isinstance(result, dict):
                                all_results.append(result)
                                # ⚡ 스캔 모드시 디버그 로깅 최소화
                                if not self._scan_mode:
                                    clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                                    self._write_debug_log(f"[{clean_symbol}] 결과 수집: {result.get('status', 'unknown')} (실패:{result.get('failed_count', 0)})")
                            elif isinstance(result, list):
                                # 리스트 결과 처리
                                all_results.extend(result)
                            else:
                                # ⚡ 스캔 모드시 경고 출력 스킵 (깔끔한 출력)
                                if not self._scan_mode:
                                    self.logger.warning(f"{symbol} 예상치 못한 결과 타입: {type(result)}")
                        else:
                            # ⚡ 스캔 모드시 None 결과 디버깅 스킵
                            if not self._scan_mode:
                                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                                self._write_debug_log(f"[{clean_symbol}] 결과 없음 (None 반환)")
                            
                    except Exception as e:
                        # ⚡ 타임아웃 에러 통합 처리 (concurrent.futures.TimeoutError 포함)
                        clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                        error_type = type(e).__name__
                        error_msg = str(e) if str(e) else "알 수 없는 에러"

                        # TimeoutError 계열은 스킵 (⚡ 스캔 모드시 경고 출력 안함)
                        if 'Timeout' in error_type or 'timeout' in error_msg.lower():
                            # ⚡ 스캔 모드시 경고 출력 스킵 (깔끔한 출력)
                            if not self._scan_mode:
                                self.logger.warning(f"{clean_symbol} 스캔 타임아웃 (10초 초과) - 스킵")
                            continue  # 다음 심볼로 진행

                        # ⚡ 스캔 모드시 상세 에러 로깅 스킵
                        if not self._scan_mode:
                            import traceback
                            self.logger.error(f"{clean_symbol} 스캔 중 오류: [{error_type}] {error_msg}")
                            self._write_debug_log(f"[{clean_symbol}] 스캔 에러 타입: {error_type}")
                            self._write_debug_log(f"[{clean_symbol}] 에러 메시지: {error_msg}")
                            self._write_debug_log(f"[{clean_symbol}] 스택트레이스:\n{traceback.format_exc()}")
        
        # 결과 분류
        entry_signals = []
        near_entry = []
        potential_entry = []
        watchlist = []
        
        # all_results는 이제 리스트의 리스트이므로 평평하게 만들어야 함
        flattened_results = []
        for result in all_results:
            if result is None:
                continue
            if isinstance(result, list):
                flattened_results.extend(result)
            else:
                flattened_results.append(result)

        # 🆕 분석 결과 저장 (전략 정보 조회용)
        if not hasattr(self, '_last_analysis_results'):
            self._last_analysis_results = {}

        for result in flattened_results:
            # 심볼별 전략 정보 저장 (entry_signal만 저장하여 덮어쓰기 방지)
            symbol = result.get('symbol')
            strategy_type = result.get('strategy_type')
            status = result.get('status')

            # ✅ entry_signal 상태인 것만 저장 (watchlist/near_entry는 저장하지 않음)
            if symbol and strategy_type and status == 'entry_signal':
                # 🔍 이미 저장된 값이 있는지 확인 (중복 방지)
                if symbol in self._last_analysis_results:
                    clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                    existing_strategy = self._last_analysis_results[symbol].get('strategy_type')
                    print(f"[전략저장-중복] {clean_symbol}: {existing_strategy} → {strategy_type} 저장 시도 (기존 값 유지)")
                else:
                    self._last_analysis_results[symbol] = {'strategy_type': strategy_type}
                    clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                    print(f"[전략저장] {clean_symbol} → {strategy_type}")

            # 분류 (디버깅 추가)
            if result['status'] == 'entry_signal':
                entry_signals.append(result)
                self.logger.debug(f"🎯 [DEBUG] ENTRY_SIGNAL: {result['symbol'].replace('/USDT:USDT', '')} - {result['strategy_type']}")
            elif result['status'] == 'near_entry':
                near_entry.append(result)
                self.logger.debug(f"🔥 [DEBUG] NEAR_ENTRY: {result['symbol'].replace('/USDT:USDT', '')} - {result['strategy_type']}")
            elif result['status'] == 'potential_entry':
                potential_entry.append(result)
                self.logger.debug(f"💡 [DEBUG] POTENTIAL_ENTRY: {result['symbol'].replace('/USDT:USDT', '')} - {result['strategy_type']}")
            elif result['status'] == 'watchlist':
                watchlist.append(result)
                self.logger.debug(f"👀 [DEBUG] WATCHLIST: {result['symbol'].replace('/USDT:USDT', '')} - {result['strategy_type']}")
            else:
                self.logger.debug(f"❌ [DEBUG] NO_SIGNAL: {result['symbol'].replace('/USDT:USDT', '')} - status: {result['status']}")

        # 📊 스캔 통계 출력 (전략별 분류 현황)
        print("\n" + "="*60)
        print("📊 스캔 결과 통계")
        print("="*60)

        # 전략별로 통계 수집
        stats_by_strategy = {}
        for result in all_results:
            strategy = result.get('strategy_type', 'Unknown')
            status = result.get('status', 'unknown')
            failed = result.get('failed_count', 0)

            if strategy not in stats_by_strategy:
                stats_by_strategy[strategy] = {
                    'entry_signal': 0,
                    'near_entry': 0,
                    'potential_entry': 0,
                    'watchlist': 0,
                    'no_signal': 0,
                    'failed_counts': {}
                }

            stats_by_strategy[strategy][status] = stats_by_strategy[strategy].get(status, 0) + 1

            # 실패 개수별 통계
            if status != 'no_signal':
                if failed not in stats_by_strategy[strategy]['failed_counts']:
                    stats_by_strategy[strategy]['failed_counts'][failed] = 0
                stats_by_strategy[strategy]['failed_counts'][failed] += 1

        # 전략별 통계 출력
        for strategy in ['전략C: 3분봉 시세 초입 포착', '전략D: 5분봉 초입 초강력 타점']:
            if strategy in stats_by_strategy:
                stats = stats_by_strategy[strategy]
                total = sum([stats.get('entry_signal', 0), stats.get('near_entry', 0),
                            stats.get('potential_entry', 0), stats.get('watchlist', 0)])

                print(f"\n[{strategy}]")
                print(f"  총 {total}개 심볼 분석")
                print(f"  - 진입신호 (0개 실패): {stats.get('entry_signal', 0)}개")
                print(f"  - 진입임박 (1개 실패): {stats.get('near_entry', 0)}개")
                print(f"  - 진입확률 (2개 실패): {stats.get('potential_entry', 0)}개")
                print(f"  - 관심종목 (3+개 실패): {stats.get('watchlist', 0)}개")

                # 실패 개수 분포
                if stats['failed_counts']:
                    print(f"  실패 개수 분포: ", end="")
                    for failed_count in sorted(stats['failed_counts'].keys()):
                        count = stats['failed_counts'][failed_count]
                        print(f"{failed_count}개={count}, ", end="")
                    print()

        print("="*60)

        # 결과 출력 및 반환

        # 📍 분류 기준 설명
        print("\n" + "="*60)
        print("📍 분류 기준 → 진입임박(NEAR): 1개 미충족 | 진입확률(POTENTIAL): 2개 미충족 | 관심종목(WATCHLIST): 3~4개 미충족")
        print("="*60)

        # 분류별 결과 출력 (출력 함수 호출)
        self._print_entry_signals(entry_signals)

        # 거래 실행 로직 (ENTRY 신호만 처리)
        if entry_signals:
            for result in entry_signals:
                clean_symbol = result['symbol'].replace('/USDT:USDT', '').replace('/USDT', '')

                # ⚡ 중복 방지: 먼저 신호 발송 기록 확인
                already_sent_signal = clean_symbol in self._sent_signals
                if already_sent_signal:
                    print(f"[중복방지] {clean_symbol} 이미 신호 발송됨 - 스킵")
                    continue

                # 실제 바이낸스 계좌에서 포지션 확인
                has_existing_position = self.check_existing_position(result['symbol'])

                if has_existing_position:
                    print(f"[진입방지] {clean_symbol} 계좌에 기존 포지션 존재 - 스킵")
                    continue

                # ✅ 진입 신호 발송 기록 (매매 실행 전에 먼저 기록)
                self._sent_signals.add(clean_symbol)

                # 🚀 속도 테스트 모드 확인
                if hasattr(self, '_trading_disabled') and self._trading_disabled:
                    print(f"[속도테스트] ⚡ {clean_symbol} 매매 실행 건너뛰기 (속도 우선)")
                    continue

                # 🎯 실제 매매 실행 (API 키 있을 때만)
                change_pct = result.get('change_24h', 0)
                try:
                    change_pct = float(change_pct) if change_pct != 0 else 0.0
                except (ValueError, TypeError):
                    change_pct = 0.0

                if hasattr(self.exchange, 'apiKey') and self.exchange.apiKey:
                    print(f"[매매실행] 🎯 {clean_symbol} 자동매매 실행 시작...")
                    try:
                        success = self.execute_trade(result['symbol'], result['price'])
                        if success:
                            print(f"[매매실행] ✅ {clean_symbol} 자동매매 성공!")
                        else:
                            print(f"[매매실행] ❌ {clean_symbol} 자동매매 실패")
                    except Exception as trade_error:
                        print(f"[매매실행] ❌ {clean_symbol} 매매 예외: {trade_error}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"[매매실행] ⚠️ {clean_symbol} API 키 없음 - 시뮬레이션 모드")
                    print(f"   📝 진입가: ${result['price']:.6f}")
                    print(f"   📈 24h 변동률: +{change_pct:.1f}%")
        
        # NEAR_ENTRY 신호 출력 (헬퍼 함수 호출)
        self._print_near_entry_signals(near_entry)

        # POTENTIAL_ENTRY 신호 출력 (헬퍼 함수 호출)
        self._print_potential_entry_signals(potential_entry)

        # WATCHLIST 신호 출력 (헬퍼 함수 호출)
        self._print_watchlist_signals(watchlist)

        # 🔍 임시 디버깅: 스캔 통계 출력
        self.logger.debug(f"📊 스캔 통계: {total_analyzed}개 분석, {results_found}개 결과, {len(all_results)}개 최종")
        
        # 🔍 임시 디버깅: all_results 내용 확인
        if all_results:
            self.logger.debug(f"📋 결과 샘플 (처음 3개):")
            for i, result in enumerate(all_results[:3]):
                self.logger.debug(f"  {i+1}. 타입: {type(result)}, 내용: {result}")
            
            # 결과 타입별 통계
            dict_count = sum(1 for r in all_results if isinstance(r, dict))
            tuple_count = sum(1 for r in all_results if isinstance(r, tuple))
            other_count = len(all_results) - dict_count - tuple_count
            self.logger.debug(f"📊 결과 타입 통계: dict={dict_count}, tuple={tuple_count}, 기타={other_count}")
        else:
            self.logger.debug("📋 all_results가 비어있음")

        # 📊 스캔 통계 출력
        print(f"\n{'='*80}")
        print(f"📊 스캔 통계:")
        print(f"   전체 심볼: {len(symbols)}개")
        print(f"   성공적으로 분석됨: {total_analyzed}개")
        print(f"   데이터 로드 실패/스킵: {len(symbols) - total_analyzed}개")
        print(f"   결과 발견: {results_found}개")
        print(f"")
        print(f"   진입 신호: {len(entry_signals)}개")
        print(f"   관심 종목: {len(watchlist)}개")
        print(f"   근접 진입: {len(near_entry)}개")
        print(f"   잠재 진입: {len(potential_entry)}개")
        print(f"{'='*80}\n")

        # ⚡ 스캔 모드 비활성화 및 로그 레벨 복원
        self._scan_mode = False
        self.logger.setLevel(original_log_level)

        return entry_signals
    
    def _get_strategy_info(self, symbol):
        """현재 심볼에 대한 전략 정보 반환"""
        try:
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')

            # 마지막 분석 결과에서 전략 타입 가져오기
            if hasattr(self, '_last_analysis_results') and symbol in self._last_analysis_results:
                strategy_type = self._last_analysis_results[symbol].get('strategy_type', '전략C: 3분봉 시세 초입 포착')
                print(f"[전략조회] {clean_symbol} → {strategy_type} (저장된 값)")
                return strategy_type
            else:
                # 기본값 반환
                print(f"[전략조회] {clean_symbol} → 전략C: 3분봉 시세 초입 포착 (기본값 - 저장된 값 없음)")
                if hasattr(self, '_last_analysis_results'):
                    saved_symbols = [s.replace('/USDT:USDT', '').replace('/USDT', '') for s in self._last_analysis_results.keys()]
                    print(f"[전략조회] 저장된 심볼: {saved_symbols}")
                return '전략C: 3분봉 시세 초입 포착'
        except Exception as e:
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            print(f"[전략조회] {clean_symbol} → 오류: {e}")
            return '전략C: 3분봉 시세 초입 포착'

    def send_unified_entry_alert(self, symbol, entry_price, quantity, entry_amount, is_dca=False, strategy_info='전략C: 3분봉 시세 초입 포착'):
        """통합 진입 알림 (DCA/기존 방식 공통)"""
        if not self.telegram_bot:
            return

        try:
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')

            # 실제 DCA 리미트 주문 가격 조회
            actual_dca_1st = None
            actual_dca_2nd = None
            dca_1st_status = "예정"
            dca_2nd_status = "예정"

            if is_dca and self.dca_manager and symbol in self.dca_manager.positions:
                position = self.dca_manager.positions[symbol]
                # pending_limit_orders 속성이 없으므로 임시로 빈 딕셔너리 사용
                pending_orders = getattr(position, 'pending_limit_orders', {})

                # 실제 배치된 DCA 주문 가격 확인
                if 'dca_1' in pending_orders:
                    actual_dca_1st = pending_orders['dca_1']['price']
                    dca_1st_status = "✅ 배치완료"
                if 'dca_2' in pending_orders:
                    actual_dca_2nd = pending_orders['dca_2']['price']
                    dca_2nd_status = "✅ 배치완료"

            # 실제 주문이 없으면 계산값 사용 (백업)
            trigger_3pct = actual_dca_1st if actual_dca_1st else entry_price * 0.97
            trigger_6pct = actual_dca_2nd if actual_dca_2nd else entry_price * 0.94
            stop_loss_price = entry_price * 0.90  # 손절가 계산 (-10%)
            exposure = entry_amount * self.leverage  # 레버리지 노출도

            # DCA 단계 확인 (최초진입 vs 추가진입 구분)
            entry_type = "🎯 [최초 진입]"
            if is_dca and self.dca_manager and symbol in self.dca_manager.positions:
                position = self.dca_manager.positions[symbol]
                current_stage = position.current_stage
                
                if current_stage == "first_dca":
                    entry_type = "📈 [1차 추가진입]"
                elif current_stage == "second_dca":
                    entry_type = "📈 [2차 추가진입]"
                elif current_stage == "initial":
                    entry_type = "🎯 [최초 진입]"

            message = f"{entry_type} {clean_symbol}" + chr(10)
            message += f"━━━━━━━━━━━━━━━━━━━━━━" + chr(10)
            message += f"💰 진입가: ${entry_price:.6f}" + chr(10)
            message += f"📦 수량: {quantity:.6f}" + chr(10)
            message += f"💵 투자금: ${entry_amount:.2f} ({self.leverage}배 레버리지)" + chr(10)
            message += f"📊 노출도: ${exposure:.2f} USDT" + chr(10)
            message += f"⏰ 시간: {get_korea_time().strftime('%H:%M:%S')}" + chr(10)
            message += f"━━━━━━━━━━━━━━━━━━━━━━" + chr(10)
            # 전략 정보 상세 표시
            strategy_display = {
                '전략C: 3분봉 시세 초입 포착': '🎯 전략C: 3분봉 시세 초입 포착\n   (복합 논리 조건 AND 5분봉 SuperTrend)',
                '전략D: 5분봉 초입 초강력 타점': '🎯 전략D: 5분봉 초입 초강력 타점\n   (3개 조건 모두 충족 AND 5분봉 SuperTrend)',
                '전략C+D: 3분봉+5분봉 복합 진입': '🎯 전략C+D: 3분봉+5분봉 복합 진입\n   (전략C와 전략D 모두 충족된 강력한 시그널)',
                '3분봉전략': '🎯 3분봉 전략'
            }.get(strategy_info, '🎯 알 수 없는 전략')

            message += f"🔧 전략: {strategy_display}" + chr(10)

            if is_dca:
                message += f"🔄 자동 DCA 순환매수 시스템" + chr(10)
                message += f"🎯 DCA 트리거:" + chr(10)
                message += f"   • 1차: -3% (${trigger_3pct:.6f}) {dca_1st_status}" + chr(10)
                message += f"   • 2차: -6% (${trigger_6pct:.6f}) {dca_2nd_status}" + chr(10)
                message += f"   • 손절: -10% (${stop_loss_price:.6f}) 자동 청산" + chr(10)
                message += f"⚡ 자동 관리: 진입/청산/손절"
            else:
                message += f"📊 수동 관리 모드" + chr(10)
                message += f"🎯 타점: -3%, -6% 수동 관리"

            self.telegram_bot.send_message(message)
        except Exception as e:
            self.logger.error(f"진입 알림 전송 실패: {e}")

    def send_unified_dca_trigger_alert(self, symbol, trigger_type, trigger_price, new_avg_price, add_amount):
        """통합 DCA 트리거 알림"""
        if not self.telegram_bot:
            return
            
        try:
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            
            # 트리거 유형에 따른 설명
            if trigger_type == "1차":
                trigger_desc = "3% 하락 도달"
                stage_desc = "1차 DCA 추가매수"
            elif trigger_type == "2차":
                trigger_desc = "6% 누적 하락 도달"
                stage_desc = "2차 DCA 추가매수"
            else:
                trigger_desc = "DCA 조건 충족"
                stage_desc = f"{trigger_type} 추가매수"
            
            exposure = add_amount * 8  # 8배 레버리지 노출도
            
            message = f"📈 [DCA {trigger_type}] {clean_symbol}\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"🔄 유형: {stage_desc}\n"
            message += f"💰 트리거가: ${trigger_price:.6f}\n"
            message += f"📉 새 평단가: ${new_avg_price:.6f}\n"
            message += f"💵 추가 투자: ${add_amount:.2f} (8배 레버리지)\n"
            message += f"📊 추가 노출: ${exposure:.2f} USDT\n"
            message += f"⏰ 시간: {get_korea_time().strftime('%H:%M:%S')}\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"📝 발동 사유: {trigger_desc}\n"
            message += f"✅ 자동 DCA 실행 완료"
            
            self.telegram_bot.send_message(message)
        except Exception as e:
            self.logger.error(f"DCA 트리거 알림 전송 실패: {e}")

    def send_trade_failure_alert(self, symbol, failure_reason):
        """진입 실패 텔레그램 알림 (중복 방지)"""
        try:
            if not self.telegram_bot:
                return
            
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            current_time = time.time()
            
            # 포지션 보유 중일 때는 텔레그램 메시지 차단
            if symbol in self.active_positions:
                print(f"[실패알림] 📵 {clean_symbol} 포지션 보유 중 - 실패 알림 차단")
                return
            
            # 중복 방지: 같은 심볼에 대해 5분 이내 실패 알림은 차단
            if (clean_symbol in self.last_failure_alerts and 
                current_time - self.last_failure_alerts[clean_symbol] < 300):  # 5분
                print(f"[실패알림] 📵 {clean_symbol} 중복 실패 알림 차단 (5분 이내)")
                return
            
            # 실패 알림 전송
            kst_time = get_korea_time().strftime('%H:%M:%S')
            message = f"❌ [진입 실패] {clean_symbol}\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"🚫 실패 사유: {failure_reason}\n"
            message += f"⏰ 시간: {kst_time}\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"💡 확인사항:\n"
            message += f"   • API 키 및 권한 설정\n"
            message += f"   • 계좌 잔고 및 여유 마진\n"
            message += f"   • 심볼 거래 활성화 상태\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"🔄 자동 재시도는 하지 않습니다"
            
            self.telegram_bot.send_message(message)
            
            # 마지막 실패 알림 시간 기록
            self.last_failure_alerts[clean_symbol] = current_time
            
            print(f"[실패알림] 📱 {clean_symbol} 진입 실패 알림 전송됨")
            
        except Exception as e:
            print(f"[실패알림] ❌ 텔레그램 실패 알림 전송 실패: {e}")

    def execute_trade(self, symbol, entry_price):
        """간단한 매매 실행"""
        # 🔒 중복 진입 방지: 진입 처리 중인 심볼 체크
        if not hasattr(self, '_entering_symbols'):
            self._entering_symbols = set()
        
        if symbol in self._entering_symbols:
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            print(f"[거래실행] ⚠️ {clean_symbol} 이미 진입 처리 중 - 스킵")
            return False
        
        # 진입 락 설정
        self._entering_symbols.add(symbol)
        
        try:
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            print(f"[거래실행] 🎯 {clean_symbol} 진입 시도...")
            print(f"[거래실행] 📊 진입가: ${entry_price:.6f}")

            # 🔄 실시간 포지션 동기화 (수동 청산 반영) - 조용한 모드
            self.sync_positions_with_exchange(quiet=True)

            # 최대 포지션 수 체크 (15종목 제한)
            current_positions = len(self.active_positions)
            print(f"[포지션확인] 📊 현재 포지션: {current_positions}/{self.max_positions}개 (동기화 완료)")

            if current_positions >= self.max_positions:
                failure_reason = f"최대 포지션 수 초과: {current_positions}/{self.max_positions}종목"
                print(f"[거래실행] ❌ {failure_reason}")
                self.send_trade_failure_alert(symbol, failure_reason)
                return False
            
            # 기존 포지션 확인 (추가 안전장치)
            if self.check_existing_position(symbol):
                print(f"[거래실행] ⚠️ {clean_symbol} 기존 포지션 존재 - 진입 취소")
                return False
            
            # API 키 재확인
            if not hasattr(self.exchange, 'apiKey') or not self.exchange.apiKey:
                failure_reason = "API 키 없음 - 실제 거래 불가"
                print(f"[거래실행] ❌ {failure_reason}")
                self.send_trade_failure_alert(symbol, failure_reason)
                return False
            
            # 계좌 잔고 확인
            print(f"[거래실행] 💰 계좌 잔고 확인 중...")
            try:
                balance = self.exchange.fetch_balance()
                usdt_balance = balance['USDT']['free']
                print(f"[거래실행] 💵 USDT 잔고: ${usdt_balance:.2f}")
            except Exception as e:
                failure_reason = f"잔고 조회 실패: {str(e)}"
                print(f"[거래실행] ❌ {failure_reason}")
                self.send_trade_failure_alert(symbol, failure_reason)
                return False
            
            # 진입 금액 계산 (원금 비율 × 레버리지)
            entry_amount = usdt_balance * self.position_size_pct
            
            # 최소 잔고 확인 (최소 마진은 나중에 최소 진입금액에 맞춰서 조정됨)
            if usdt_balance < self.min_balance:
                failure_reason = f"잔고 부족: ${usdt_balance:.2f} (최소 ${self.min_balance} 잔고 필요)"
                print(f"[거래실행] ❌ {failure_reason}")
                self.send_trade_failure_alert(symbol, failure_reason)
                return False
            
            # 레버리지 설정 (10배)
            try:
                self.exchange.set_leverage(self.leverage, symbol)
            except Exception as e:
                print(f"[거래실행] ⚠️ 레버리지 설정 실패 (무시): {e}")
            
            # 포지션 크기 계산 (10배 레버리지)
            position_value = entry_amount * self.leverage  # 10배 레버리지로 포지션 크기

            # 🚀 최소 주문 금액 확인 및 조정 (캐시 사용으로 고속화)
            markets = self._get_cached_markets()
            market = markets.get(symbol)
            min_cost = self.min_order_amount  # $6 (기본 $5 + 안전마진 $1)
            
            if market and 'limits' in market and 'cost' in market['limits'] and market['limits']['cost']['min']:
                min_cost = market['limits']['cost']['min']
            
            # 포지션 크기가 최소 금액보다 작으면 최소 진입 수량으로 조정
            if position_value < min_cost:
                print(f"[거래실행] ⚠️ 포지션 크기가 최소 금액 미달: ${position_value:.2f} < ${min_cost:.2f}")
                print(f"[거래실행] 📈 최소 진입 수량으로 자동 조정: ${min_cost:.2f}")
                position_value = min_cost
                # 조정된 포지션에 맞는 실제 마진 재계산
                entry_amount = position_value / self.leverage
                print(f"[거래실행] 💰 마진 자동 조정: ${entry_amount:.2f} (원래 {self.position_size_pct*100:.1f}%=${usdt_balance * self.position_size_pct:.2f} → 최소금액 충족)")
            
            # 현재가 기준으로 수량 재계산 (시장가 주문 정확성)
            current_price = self.get_current_price(symbol)
            if current_price is None:
                print(f"[거래실행] ❌ 현재가 조회 실패: {symbol}")
                return False
            quantity = position_value / current_price
            
            # 실제 주문 금액 검증 (최종 안전장치)
            actual_order_value = quantity * current_price
            if actual_order_value < self.min_order_amount:
                print(f"[거래실행] ⚠️ 최종 주문금액 미달: ${actual_order_value:.2f} < ${self.min_order_amount:.2f}")
                # 강제로 최소 주문금액으로 조정
                quantity = self.min_order_amount / current_price
                actual_order_value = self.min_order_amount
                print(f"[거래실행] 🔧 강제 조정: 수량={quantity:.6f}, 주문금액=${actual_order_value:.2f}")
            
            print(f"[거래실행] 📊 최종 계산:")
            print(f"   💰 마진: ${entry_amount:.2f}")
            print(f"   📈 포지션 크기: ${position_value:.2f}")
            print(f"   📦 수량: {quantity:.6f}")
            print(f"   🎯 예상 진입가: ${entry_price:.6f}")
            print(f"   💵 현재가: ${current_price:.6f}")
            print(f"   💸 실제 주문금액: ${actual_order_value:.2f}")
            
            # DCA 시스템을 통한 포지션 생성 시도
            if self.dca_manager:
                try:
                    # DCA 시스템으로 최초 진입 처리 (올바른 메소드명 사용)
                    dca_result = self.dca_manager.enter_new_position(
                        symbol=symbol,
                        entry_price=entry_price,
                        balance=usdt_balance,
                        leverage=self.leverage
                    )
                    
                    if dca_result and dca_result.get('success'):
                        clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                        print(f"[DCA진입] ✅ \033[92m\033[1m{clean_symbol}\033[0m DCA 최초 진입 성공!")
                        print(f"   💰 투자금: ${entry_amount:.2f} ({self.leverage}배 레버리지)")
                        print(f"   📦 수량: {dca_result['quantity']:.6f}")
                        print(f"   💵 진입가: ${dca_result['entry_price']:.6f}")
                        print(f"   🎯 DCA 트리거: -3%=${dca_result['entry_price'] * 0.97:.6f}, -6%=${dca_result['entry_price'] * 0.94:.6f}")
                        
                        # DCA 포지션 정보를 기존 시스템과 호환되도록 저장
                        self.active_positions[symbol] = {
                            'entry_price': dca_result['entry_price'],
                            'entry_time': get_korea_time(),
                            'quantity': dca_result['quantity'],
                            'entry_amount': entry_amount,
                            'leverage': self.leverage,
                            'order_id': dca_result.get('order_id'),
                            'dca_managed': True,  # DCA 시스템 관리 표시
                            'dca_position_id': dca_result.get('position_id')
                        }

                        # 진입 시점 데이터 수집
                        entry_data = self._collect_entry_data(symbol, dca_result['entry_price'])

                        # 포지션 통계 초기화
                        self.position_stats[symbol] = {
                            'max_profit_pct': 0.0,
                            'min_profit_pct': 0.0,  # 최저 수익률 추적
                            'current_profit_pct': 0.0,
                            'half_closed': False,
                            'reached_10_percent': False,
                            'ten_percent_half_exit_count': 0,
                            'five_percent_exit_done': False,  # 5% 청산 완료 여부
                            'ten_percent_exit_done': False,  # 10% 청산 완료 여부
                            'bb600_exit_done': False,  # BB600 돌파 절반청산 완료 여부 (1회만)
                            'dca_managed': True,
                            'entry_time': get_korea_time(),  # 진입 시간
                            'entry_data': entry_data  # Phase 1: 진입 시점 상세 데이터
                        }

                        # 전략 정보 조회
                        strategy_info = self._get_strategy_info(symbol)

                        # 통합 텔레그램 알림 (DCA 시스템 사용시)
                        self.send_unified_entry_alert(symbol, dca_result['entry_price'], dca_result['quantity'], entry_amount, is_dca=True, strategy_info=strategy_info)

                        # 📊 일일 사용 원금 추적 (Day ROE 계산용)
                        self.today_stats['total_entry_amount'] += entry_amount

                        # ✅ DCA 1차, 2차 지정가 주문 배치 확인 (1.0초 후 검증)
                        time.sleep(1.0)  # 주문 배치 시간 대기
                        if self.dca_manager and hasattr(self.dca_manager, 'get_pending_orders'):
                            try:
                                future_symbol = clean_symbol + 'USDT'  # BTC → BTCUSDT
                                pending_orders = self.dca_manager.get_pending_orders(future_symbol)

                                if pending_orders and len(pending_orders) >= 2:
                                    self.logger.info(f"[DCA주문확인] ✅ {clean_symbol} DCA 지정가 주문 {len(pending_orders)}개 배치 완료")
                                    for idx, order in enumerate(pending_orders, 1):
                                        order_price = order.get('price', 0)
                                        order_amount = order.get('amount', 0)
                                        print(f"   {idx}차: ${order_price:.6f}, 수량: {order_amount:.6f}")
                                elif pending_orders:
                                    self.logger.warning(f"[DCA주문확인] ⚠️ {clean_symbol} DCA 지정가 주문 일부만 배치됨: {len(pending_orders)}개 (예상: 2개)")
                                else:
                                    self.logger.error(f"[DCA주문확인] ❌ {clean_symbol} DCA 지정가 주문이 배치되지 않았습니다!")
                                    print(f"   → DCA 매니저 확인 필요")
                            except Exception as order_check_error:
                                self.logger.warning(f"[DCA주문확인] ⚠️ {clean_symbol} 지정가 주문 확인 실패: {order_check_error}")

                        # 🚀 WebSocket 실시간 모니터링 구독 시작
                        if self.ws_kline_manager:
                            try:
                                ws_symbol = clean_symbol + 'USDT'  # BTC/USDT:USDT → BTCUSDT
                                self.ws_kline_manager.subscribe_position(ws_symbol)
                                print(f"[WebSocket] 📡 {clean_symbol} 실시간 모니터링 시작")
                            except Exception as ws_error:
                                self.logger.warning(f"WebSocket 구독 실패: {ws_error}")

                        return True
                        
                    else:
                        print(f"[DCA진입] ⚠️ DCA 시스템 진입 실패, 기존 방식으로 전환")
                        # DCA 실패 시 기존 방식으로 fallback
                        
                except Exception as e:
                    print(f"[DCA진입] ❌ DCA 시스템 오류: {e}")
                    print(f"[DCA진입] 🔄 기존 방식으로 전환")
            
            # 🚨 기존 시장가 매수 주문 (DCA 시스템 없거나 실패시)
            # DCA fallback시에도 최소 주문 금액 재검증 필수!
            print(f"[기존방식] 🔄 기존 시장가 주문으로 진입 시도...")
            
            # 다시 한번 최소 주문 금액 확인 (DCA fallback시 안전장치)
            final_order_value = quantity * current_price
            if final_order_value < self.min_order_amount:
                print(f"[기존방식] ⚠️ DCA fallback 최종 검증: ${final_order_value:.2f} < ${self.min_order_amount}")
                # 최소 주문 금액으로 강제 조정
                quantity = self.min_order_amount / current_price
                final_order_value = self.min_order_amount
                entry_amount = final_order_value / self.leverage  # 마진도 재조정
                print(f"[기존방식] 🔧 최종 보정: 수량={quantity:.6f}, 주문금액=${final_order_value:.2f}, 마진=${entry_amount:.2f}")
            
            # 거래소 최소 수량 제약 확인 (기존 방식)
            try:
                market = self.exchange.market(symbol)
                limits = market.get('limits', {})
                amount_limits = limits.get('amount', {})
                min_amount = amount_limits.get('min', 0)

                if min_amount and quantity < min_amount:
                    print(f"[기존방식] ⚠️ 최소 수량 미달: {quantity:.6f} < {min_amount:.6f}")
                    
                    # 최소 수량으로 조정
                    quantity = min_amount
                    adjusted_order_value = quantity * current_price
                    entry_amount = adjusted_order_value / self.leverage
                    
                    print(f"[기존방식] ✅ 수량 조정: {quantity:.6f} (최소: {min_amount:.6f})")
                    print(f"[기존방식] 📊 투자금 조정: ${entry_amount:.2f}, 주문금액: ${adjusted_order_value:.2f}")
                    
            except Exception as limit_check_error:
                print(f"[기존방식] ⚠️ 거래소 제약 확인 실패: {limit_check_error}")

            try:
                print(f"[기존방식] 📦 최종 주문: 수량={quantity:.6f}, 예상금액=${quantity * current_price:.2f}")
                order = self.exchange.create_market_buy_order(symbol, quantity)
            except Exception as e:
                failure_reason = f"주문 실행 실패: {str(e)}"
                print(f"[거래실행] ❌ {failure_reason}")
                self.send_trade_failure_alert(symbol, failure_reason)
                return False
            
            if order and order.get('id'):
                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                print(f"[거래실행] ✅ \033[92m\033[1m{clean_symbol}\033[0m 진입 성공!")
                print(f"   💰 투자금: ${entry_amount:.2f} ({self.leverage}배 레버리지)")
                print(f"   📦 수량: {quantity:.6f}")
                print(f"   📝 주문ID: {order['id']}")
                
                # 포지션 추가 (기존 방식)
                self.active_positions[symbol] = {
                    'entry_price': entry_price,
                    'entry_time': get_korea_time(),
                    'quantity': quantity,
                    'entry_amount': entry_amount,
                    'leverage': self.leverage,
                    'order_id': order['id'],
                    'dca_managed': False  # 기존 방식 표시
                }

                # 진입 시점 데이터 수집
                entry_data = self._collect_entry_data(symbol, entry_price)

                # 포지션 통계 초기화
                self.position_stats[symbol] = {
                    'max_profit_pct': 0.0,
                    'min_profit_pct': 0.0,  # 최저 수익률 추적
                    'current_profit_pct': 0.0,
                    'half_closed': False,  # 10% 달성시 절반청산 여부
                    'reached_10_percent': False,  # 10% 이상 달성 여부
                    'ten_percent_half_exit_count': 0,  # 10% 절반청산 실행 횟수 (1회 제한)
                    'five_percent_exit_done': False,  # 5% 청산 완료 여부
                    'ten_percent_exit_done': False,  # 10% 청산 완료 여부
                    'bb600_exit_done': False,  # BB600 돌파 절반청산 완료 여부 (1회만)
                    'technical_exit_attempted': False,  # 기술적 청산 시도 여부
                    'entry_time': get_korea_time(),  # 진입 시간
                    'entry_data': entry_data  # Phase 1: 진입 시점 상세 데이터
                }

                # 📊 일일 사용 원금 추적 (Day ROE 계산용)
                self.today_stats['total_entry_amount'] += entry_amount

                # 🔄 기존 방식 진입 후 DCA 시스템에 변환 (DCA 주문 배치)
                if self.dca_manager:
                    try:
                        print(f"[DCA변환] 🔄 기존 방식 진입 → DCA 시스템 변환 시도...")
                        
                        # 거래소에서 실제 포지션 확인
                        actual_entry_price = order.get('average', entry_price)
                        actual_quantity = order.get('filled', quantity)
                        
                        # 현재 잔고 조회 (DCA 매니저 호출용)
                        try:
                            balance = self.exchange.fetch_balance()
                            total_balance = balance['USDT']['free']
                        except:
                            total_balance = 1000  # 기본값
                        
                        # DCA 시스템으로 포지션 변환
                        conversion_result = self.dca_manager._create_position_from_exchange(
                            symbol=symbol.replace('/USDT:USDT', ''),  # 심볼 정규화
                            entry_price=actual_entry_price,
                            total_balance=total_balance
                        )
                        
                        if conversion_result:  # DCAPosition 객체가 반환되면 성공
                            print(f"[DCA변환] ✅ DCA 시스템 변환 성공 - 1차/2차 DCA 주문 자동 배치")
                            # 기존 방식 포지션 표시를 DCA로 변경
                            self.active_positions[symbol]['dca_managed'] = True
                            
                            # DCA 포지션이 생성되었으므로 기존 포지션 정보 업데이트
                            clean_symbol = symbol.replace('/USDT:USDT', '')
                            if clean_symbol in self.dca_manager.positions:
                                print(f"[DCA변환] 📊 DCA 포지션 등록 확인: {clean_symbol}")
                        else:
                            print(f"[DCA변환] ⚠️ DCA 변환 실패 - 기존 방식으로 유지")
                            
                    except Exception as dca_convert_error:
                        print(f"[DCA변환] ⚠️ DCA 변환 오류: {dca_convert_error}")
                        print(f"[DCA변환] 📊 기존 방식으로 유지")
                
                # 전략 정보 수집 (텔레그램 알림용)
                strategy_info = self._get_strategy_info(symbol)
                
                # 통합 텔레그램 알림 (기존 방식 사용시)
                # DCA 시스템이 있으면 항상 DCA로 표시 (백업 실행이어도 DCA 시스템 활성화됨)
                is_dca_active = self.dca_manager is not None
                self.send_unified_entry_alert(symbol, entry_price, quantity, entry_amount, is_dca=is_dca_active, strategy_info=strategy_info)
                
                return True
            else:
                failure_reason = "주문 생성 실패 - 주문 ID 없음"
                print(f"[거래실행] ❌ {failure_reason}")
                self.send_trade_failure_alert(symbol, failure_reason)
                return False
                
        except Exception as e:
            failure_reason = f"매매 실행 중 예외 발생: {str(e)}"
            print(f"[거래실행] ❌ {failure_reason}")
            self.send_trade_failure_alert(symbol, failure_reason)
            return False
        finally:
            # 🔓 진입 락 해제 (성공/실패 관계없이)
            if hasattr(self, '_entering_symbols') and symbol in self._entering_symbols:
                self._entering_symbols.remove(symbol)

    def check_exit_signal(self, symbol, entry_price=None):
        """
        복합 청산 신호 체크 - 수익률 기반 + 기술적 청산 조건

        Args:
            symbol: 심볼명
            entry_price: 진입가 (수익률 계산용)

        Returns:
            dict: 청산 신호 정보
        """
        try:
            # 1분봉 데이터 조회
            df_1m = self.get_ohlcv_data(symbol, '1m', 1000)
            if df_1m is None or len(df_1m) < 600:
                return {'exit_signal': False, 'reason': '데이터 부족'}

            # 기술적 지표 계산 (ma5, bb80_upper 등)
            df_1m = self.calculate_indicators(df_1m)
            if df_1m is None:
                return {'exit_signal': False, 'reason': '지표 계산 실패'}

            latest = df_1m.iloc[-1]
            current_price = latest['close']
            
            # 수익률 체크 (진입가 기준)
            profit_pct = 0
            if entry_price:
                profit_pct = ((current_price - entry_price) / entry_price) * 100
            
            # 포지션 통계 업데이트 + DCA 수익률 동기화
            if symbol in self.position_stats:
                self.position_stats[symbol]['current_profit_pct'] = profit_pct

                # DCA 시스템 연동으로 최대 수익률 동기화
                dca_max_profit = profit_pct
                if self.dca_manager and symbol.replace('/USDT:USDT', '') in self.dca_manager.positions:
                    clean_symbol = symbol.replace('/USDT:USDT', '')
                    dca_position = self.dca_manager.positions[clean_symbol]
                    if hasattr(dca_position, 'max_profit_pct'):
                        # DCA 최대수익률을 백분율로 변환 (DCA는 소수점, 메인은 백분율)
                        dca_max_profit = max(profit_pct, dca_position.max_profit_pct * 100)

                # 메인 전략과 DCA 시스템 중 더 높은 수익률 사용
                if dca_max_profit > self.position_stats[symbol]['max_profit_pct']:
                    self.position_stats[symbol]['max_profit_pct'] = dca_max_profit
                    print(f"[수익률동기화] {symbol.replace('/USDT:USDT', '')} 최대수익률 업데이트: {dca_max_profit:.2f}%")

                # 최저 수익률 업데이트
                if profit_pct < self.position_stats[symbol]['min_profit_pct']:
                    self.position_stats[symbol]['min_profit_pct'] = profit_pct

                # 10% 이상 달성 기록 (현재 또는 과거 최대 수익률 기준)
                if profit_pct >= 10.0 or self.position_stats[symbol]['max_profit_pct'] >= 10.0:
                    self.position_stats[symbol]['reached_10_percent'] = True
            
            exit_signal = False
            exit_reason = ""
            partial_ratio = 1.0  # 기본값: 전량 청산

            # 🚨 0. 손절 체크 (최우선) - XVG 손절 버그 수정
            if not exit_signal and profit_pct < 0:
                # DCA 매니저가 있고 포지션이 있으면 DCA 손절 기준 사용
                stop_loss_pct = -10.0  # 기본값: -10%
                current_stage = 'initial'

                if self.dca_manager:
                    # 심볼 변환 (exchange 형식 → DCA 형식)
                    clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                    if clean_symbol in self.dca_manager.positions:
                        dca_position = self.dca_manager.positions[clean_symbol]
                        current_stage = dca_position.current_stage

                        # 단계별 손절 기준
                        if current_stage == 'initial':
                            stop_loss_pct = -10.0
                        elif current_stage == 'first_dca':
                            stop_loss_pct = -7.0
                        elif current_stage == 'second_dca':
                            stop_loss_pct = -5.0

                        # 손절 체크
                        if profit_pct <= stop_loss_pct:
                            exit_signal = True
                            exit_reason = f"🚨 손절청산 [{current_stage}단계] (수익률: {profit_pct:.2f}% < 손절선: {stop_loss_pct:.1f}%)"
                            self.logger.critical(f"🚨 손절 트리거: {symbol} - 단계: {current_stage}, 수익률: {profit_pct:.2f}%, 손절선: {stop_loss_pct:.1f}%")

                            # 텔레그램 알림 전송
                            if self.telegram_bot:
                                clean_symbol_display = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                                message = (f"🚨 [손절 청산] {clean_symbol_display}\n"
                                         f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                         f"📉 현재 수익률: {profit_pct:.2f}%\n"
                                         f"⚠️ 손절선: {stop_loss_pct:.1f}%\n"
                                         f"📊 DCA 단계: {current_stage}\n"
                                         f"💰 현재가: ${current_price:.6f}\n"
                                         f"💸 진입가: ${entry_price:.6f}\n"
                                         f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                         f"⚡ 전량 긴급 청산 실행")
                                self.telegram_bot.send_message(message)
                else:
                    # DCA 매니저가 없으면 기본 손절 -10% 적용
                    if profit_pct <= stop_loss_pct:
                        exit_signal = True
                        exit_reason = f"🚨 손절청산 [기본] (수익률: {profit_pct:.2f}% < 손절선: {stop_loss_pct:.1f}%)"
                        self.logger.critical(f"🚨 손절 트리거: {symbol} - 수익률: {profit_pct:.2f}%, 손절선: {stop_loss_pct:.1f}%")

                        # 텔레그램 알림 전송
                        if self.telegram_bot:
                            clean_symbol_display = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                            message = (f"🚨 [손절 청산] {clean_symbol_display}\n"
                                     f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                     f"📉 현재 수익률: {profit_pct:.2f}%\n"
                                     f"⚠️ 손절선: {stop_loss_pct:.1f}%\n"
                                     f"💰 현재가: ${current_price:.6f}\n"
                                     f"💸 진입가: ${entry_price:.6f}\n"
                                     f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                     f"⚡ 전량 긴급 청산 실행")
                            self.telegram_bot.send_message(message)

            # 1. 본절보호청산: 1~5% 구간에서만 적용
            if not exit_signal and symbol in self.position_stats:
                max_profit = self.position_stats[symbol]['max_profit_pct']
                # 1~5% 구간에서만 본절보호청산 적용
                if 1.0 <= max_profit < 5.0:
                    exit_threshold = 0.0
                    # 구간별 청산 기준 설정
                    if 4.0 <= max_profit < 5.0:
                        # 4~5%: 1% 이하로 하락 시 청산
                        exit_threshold = 1.0
                    elif 3.0 <= max_profit < 4.0:
                        # 3~4%: 0.75% 이하로 하락 시 청산
                        exit_threshold = 0.75
                    elif 2.0 <= max_profit < 3.0:
                        # 2~3%: 0.5% 이하로 하락 시 청산
                        exit_threshold = 0.5
                    elif 1.0 <= max_profit < 2.0:
                        # 1~2%: 0.25% 이하로 하락 시 청산
                        exit_threshold = 0.25
                    if profit_pct <= exit_threshold:
                        # 🚨 수익률 급변동 방지: 0.3초 재확인
                        import time
                        time.sleep(0.3)
                        
                        # 현재 가격 재조회로 수익률 재계산
                        try:
                            current_ticker = self.exchange.fetch_ticker(symbol)
                            current_price_recheck = current_ticker['last']
                            profit_pct_recheck = ((current_price_recheck - position['avg_price']) / position['avg_price']) * 100
                            
                            # 재확인 후에도 청산 조건 유지되는지 검증
                            if profit_pct_recheck <= exit_threshold:
                                exit_signal = True
                                exit_reason = f"본절보호청산 (최대 {max_profit:.2f}% → 현재 {profit_pct_recheck:.2f}%, 기준 {exit_threshold:.2f}%)"
                            else:
                                # 가격 회복으로 청산 조건 해제
                                self.logger.info(f"📈 {symbol} 가격 회복으로 본절보호청산 취소: {profit_pct:.2f}% → {profit_pct_recheck:.2f}%")
                        except Exception as recheck_error:
                            # 재확인 실패시 원래 로직 유지
                            exit_signal = True
                            exit_reason = f"본절보호청산 (최대 {max_profit:.2f}% → 현재 {profit_pct:.2f}%, 기준 {exit_threshold:.2f}%)"

            # 2. 수익률 기반 청산 로직 (플러스 수익률일 때만)
            if not exit_signal and profit_pct >= 0 and symbol in self.position_stats:
                max_profit = self.position_stats[symbol]['max_profit_pct']

                # 조건 1: 최대수익률 5% 이상이었다가 실제 손실 직전에 약수익 청산 (개선됨)
                if not exit_signal and max_profit >= 5.0 and profit_pct > 0 and profit_pct <= 0.5:
                    exit_signal = True
                    exit_reason = f"손실전환전약수익청산 (최대{max_profit:.2f}% → 현재{profit_pct:.2f}%)"
                    # 전량 청산

                # 조건 2: BB600 돌파 절반청산 (15분봉 또는 30분봉) - 딱 1회만 실행
                if not exit_signal and profit_pct >= 5.0:
                    # BB600 돌파 청산이 이미 실행되었는지 확인
                    bb600_exit_done = self.position_stats[symbol].get('bb600_exit_done', False)
                    
                    # 쿨다운 체크 (청산 실패 후 5분간 재시도 방지)
                    bb600_cooldown = self.position_stats[symbol].get('bb600_retry_cooldown', 0)
                    current_time = time.time()
                    in_cooldown = current_time < bb600_cooldown
                    
                    if not bb600_exit_done and not in_cooldown:
                        bb600_breakout_exit = self._check_bb600_breakout_exit(symbol)
                        if bb600_breakout_exit:
                            # 청산 시도 (플래그는 청산 성공 시에만 설정)
                            exit_signal = True
                            exit_reason = bb600_breakout_exit['reason']
                            partial_ratio = 0.5  # 절반 청산
                    elif in_cooldown:
                        # 쿨다운 중인 경우 디버그 메시지 (너무 자주 출력되지 않도록)
                        remaining_time = int(bb600_cooldown - current_time)
                        if remaining_time % 60 == 0:  # 1분마다만 출력
                            print(f"[쿨다운] ⏰ {symbol.replace('/USDT:USDT', '')} BB600 청산 쿨다운 중 (남은시간: {remaining_time//60}분)")

                # 조건 3: 5분봉 슈퍼트렌드 청산 시작캔들에 전량청산 (수익률 조건 제거)
                if not exit_signal:
                    # 5분봉 데이터 조회
                    df_5m_exit = self.get_ohlcv_data(symbol, '5m', limit=20)
                    if df_5m_exit is not None and len(df_5m_exit) >= 10:
                        # SuperTrend 지표 계산 (period=10, multiplier=3.0)
                        df_5m_exit = self.calculate_supertrend(df_5m_exit, period=10, multiplier=3.0)
                        if df_5m_exit is not None and len(df_5m_exit) >= 2:
                            recent_candles = df_5m_exit.tail(2)
                            prev_candle = recent_candles.iloc[0]
                            curr_candle = recent_candles.iloc[1]
                            
                            # SuperTrend 청산 시작 신호 감지
                            if ('supertrend_direction' in prev_candle and 'supertrend_direction' in curr_candle):
                                # 상승에서 하락으로 전환되는 첫 번째 캔들 (청산 시작 캔들)
                                if prev_candle['supertrend_direction'] == 1 and curr_candle['supertrend_direction'] == -1:
                                    exit_signal = True
                                    exit_reason = f"5분봉SuperTrend청산 (상승→하락 전환 시작캔들)"
                                    # 전량 청산 (partial_ratio 없음)
            
            # ❌ 모든 기존 청산 로직 제거됨 (사용자 요청)
            # 원래 여기에 복잡한 DCA 기술적 청산 로직들이 있었지만 모두 제거됨
            # ✅ 사용자 요청: 3개 청산 조건만 유지, 나머지 모든 로직 제거됨
            return {
                'exit_signal': exit_signal,
                'symbol': symbol,
                'current_price': current_price,
                'profit_pct': profit_pct,
                'exit_reason': exit_reason,
                'partial_ratio': partial_ratio if 'partial_ratio' in locals() else 1.0,
                'conditions': exit_conditions if 'exit_conditions' in locals() else []
            }
            
        except Exception as e:
            self.logger.error(f"청산 신호 체크 실패 ({symbol}): {e}")
            return {'exit_signal': False, 'reason': f'오류: {e}'}

    def _check_bb600_breakout_exit(self, symbol):
        """🔥 BB600 돌파 절반청산 조건 체크 (15분봉 또는 30분봉) - 1회 한정"""
        try:
            # 1회 한정 체크: 이미 BB600 부분청산을 실행한 심볼인지 확인
            if symbol in self.bb600_partial_liquidations:
                # 이미 실행된 경우 로그 출력 후 스킵
                liquidation_time = self.bb600_partial_liquidations[symbol]
                self.logger.debug(f"{symbol} BB600 부분청산 이미 실행됨 (시간: {liquidation_time}) - 스킵")
                return None
            
            # 포지션이 활성화된 상태인지 확인 (부분청산은 포지션이 있을 때만 실행)
            if symbol not in self.active_positions:
                return None
            
            # 15분봉과 30분봉 데이터 조회 (BB600 계산을 위해 충분한 데이터 확보)
            df_15m = self.get_ohlcv_data(symbol, '15m', limit=700)  # BB600 계산을 위해 더 많이
            df_30m = self.get_ohlcv_data(symbol, '30m', limit=700)  # BB600 계산을 위해 더 많이
            
            results = []
            
            # 15분봉 체크
            if df_15m is not None and len(df_15m) >= 5:
                df_15m_calc = self.calculate_indicators(df_15m)
                if df_15m_calc is not None and 'bb600_upper' in df_15m_calc.columns:
                    bb600_breakout_15m = self._check_bb600_breakout_timeframe(df_15m_calc, '15분봉')
                    if bb600_breakout_15m:
                        results.append(bb600_breakout_15m)
            
            # 30분봉 체크  
            if df_30m is not None and len(df_30m) >= 5:
                df_30m_calc = self.calculate_indicators(df_30m)
                if df_30m_calc is not None and 'bb600_upper' in df_30m_calc.columns:
                    bb600_breakout_30m = self._check_bb600_breakout_timeframe(df_30m_calc, '30분봉')
                    if bb600_breakout_30m:
                        results.append(bb600_breakout_30m)
            
            # 돌파 조건 중 하나라도 충족되면 청산
            if results:
                # BB600 부분청산 실행 기록 (1회 한정을 위한 기록)
                current_time = get_korea_time().strftime("%Y-%m-%d %H:%M:%S")
                self.bb600_partial_liquidations[symbol] = current_time
                self.logger.info(f"🎯 {symbol} BB600 부분청산 실행 기록됨 (시간: {current_time})")
                
                return results[0]  # 첫 번째 결과 반환
                
            return None
            
        except Exception as e:
            self.logger.error(f"BB600 돌파 체크 실패 {symbol}: {e}")
            return None

    def _check_bb600_breakout_timeframe(self, df, timeframe_name):
        """특정 타임프레임에서 BB600 돌파 체크"""
        try:
            if len(df) < 3:
                return None
                
            # 최근 3봉 확인
            recent_3 = df.tail(3)
            current_row = recent_3.iloc[-1]
            
            if 'close' not in current_row or 'bb600_upper' not in current_row:
                return None
                
            current_close = current_row['close']
            current_bb600_upper = current_row['bb600_upper']
            
            if pd.isna(current_close) or pd.isna(current_bb600_upper):
                return None
            
            # BB600 상단선 돌파 확인 (종가 기준) - 새로운 돌파만 감지
            if current_close > current_bb600_upper:
                # 이전 봉에서 돌파하지 않았는데 현재 봉에서 돌파한 경우만 신호 생성
                prev_row = recent_3.iloc[-2] if len(recent_3) >= 2 else None
                if prev_row is not None and 'close' in prev_row and 'bb600_upper' in prev_row:
                    prev_close = prev_row['close']
                    prev_bb600_upper = prev_row['bb600_upper']
                    
                    # 새로운 돌파인지 확인: 이전 봉에서는 돌파하지 않았고 현재 봉에서 돌파
                    if (not pd.isna(prev_close) and not pd.isna(prev_bb600_upper) and 
                        prev_close <= prev_bb600_upper):  # 이전에는 돌파하지 않았음
                        return {
                            'type': 'bb600_breakout',
                            'timeframe': timeframe_name,
                            'reason': f"BB600돌파절반청산 ({timeframe_name} BB600상단선 새로운 돌파)",
                            'current_price': current_close,
                            'bb600_upper': current_bb600_upper,
                            'breakout_pct': ((current_close - current_bb600_upper) / current_bb600_upper) * 100
                        }
            
            return None
            
        except Exception as e:
            self.logger.error(f"BB600 돌파 체크 실패 ({timeframe_name}): {e}")
            return None

    def _check_1m_supertrend_exit_signal(self, symbol, df_1m):
        """1분봉 SuperTrend 청산 시그널 체크 (상승→하락 전환)"""
        try:
            if df_1m is None or len(df_1m) < 20:
                return False
            
            # SuperTrend 계산 (period=10, multiplier=3.0)
            df_1m_st = self.calculate_supertrend(df_1m, period=10, multiplier=3.0)
            if df_1m_st is None or len(df_1m_st) < 2:
                return False
            
            # 최근 2개 캔들 확인
            recent_2 = df_1m_st.tail(2)
            prev_candle = recent_2.iloc[0]
            curr_candle = recent_2.iloc[1]
            
            # SuperTrend 방향 확인
            if ('supertrend_direction' in prev_candle and 'supertrend_direction' in curr_candle):
                prev_direction = prev_candle['supertrend_direction']
                curr_direction = curr_candle['supertrend_direction']
                
                # 상승(1)에서 하락(-1)으로 전환 시 청산 시그널
                if prev_direction == 1 and curr_direction == -1:
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"1분봉 SuperTrend 청산 시그널 체크 실패 {symbol}: {e}")
            return False

    def _execute_entry_signal(self, signal_data: dict):
        """WebSocket 스캐너로부터 진입 신호 처리"""
        try:
            symbol = signal_data.get('symbol')
            if not symbol:
                return
            
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            current_price = signal_data.get('current_price', 0)
            change_24h = signal_data.get('change_24h', 0)
            conditions = signal_data.get('conditions', {})
            
            # 🔒 중복 진입 방지: 진입 처리 중인 심볼 체크
            if not hasattr(self, '_entering_symbols'):
                self._entering_symbols = set()
            
            if symbol in self._entering_symbols:
                print(f"⚠️ {clean_symbol}: 이미 진입 처리 중 - 스킵")
                return
            
            # 진입 락 설정
            self._entering_symbols.add(symbol)
            
            try:
                # 기존 포지션 체크 (이중 확인)
                if symbol in self.active_positions:
                    print(f"⚠️ {clean_symbol}: 이미 포지션 보유 중 - 스킵")
                    return
                
                # 실제 거래소 포지션 확인 (최종 안전장치)
                if self.check_existing_position(symbol):
                    print(f"⚠️ {clean_symbol}: 거래소에 기존 포지션 존재 - 스킵")
                    return
                
                # 최대 포지션 개수 체크
                if len(self.active_positions) >= self.max_positions:
                    print(f"⚠️ {clean_symbol}: 최대 포지션 개수 초과 ({len(self.active_positions)}/{self.max_positions}) - 스킵")
                    return
                
                print(f"🎯 WebSocket 진입 신호: {clean_symbol} (${current_price:.4f}, {change_24h:+.1f}%)")
                
                # DCA 시스템을 통한 진입
                if self.dca_manager:
                    try:
                        entry_result = self.dca_manager.enter_position(
                            symbol=clean_symbol,
                            entry_price=current_price,
                            position_size_pct=self.position_size_pct,
                            leverage=self.leverage,
                            entry_reason=f"WebSocket신호({change_24h:+.1f}%)"
                        )
                        
                        if entry_result and entry_result.get('success'):
                            print(f"✅ {clean_symbol} WebSocket 진입 성공")
                            
                            # 텔레그램 알림
                            if self.telegram_bot:
                                try:
                                    message = (f"🎯 WebSocket 진입\n"
                                             f"심볼: {clean_symbol}\n"
                                             f"가격: ${current_price:.4f}\n"
                                             f"변동률: {change_24h:+.1f}%\n"
                                             f"데이터소스: WebSocket 전용")
                                    self.telegram_bot.send_message(message)
                                except Exception as e:
                                    print(f"텔레그램 알림 실패: {e}")
                        else:
                            print(f"❌ {clean_symbol} WebSocket 진입 실패")
                            
                    except Exception as e:
                        print(f"❌ {clean_symbol} DCA 진입 처리 실패: {e}")
                else:
                    print(f"⚠️ {clean_symbol}: DCA 시스템 비활성화 - 진입 스킵")
            
            except Exception as inner_e:
                print(f"❌ {clean_symbol} 내부 진입 처리 실패: {inner_e}")
                
        except Exception as e:
            print(f"❌ WebSocket 진입 신호 처리 실패: {e}")
        finally:
            # 🔓 진입 락 해제 (성공/실패 관계없이)
            if hasattr(self, '_entering_symbols') and symbol in self._entering_symbols:
                self._entering_symbols.remove(symbol)

    def execute_exit_trade(self, symbol, exit_reason="수동청산", partial_ratio=1.0):
        """
        청산 주문 실행 (DCA 시스템 연동)

        Args:
            symbol: 심볼명
            exit_reason: 청산 사유
            partial_ratio: 청산 비율 (1.0=전량, 0.5=절반)
        """
        try:
            # 중복 청산 방지: 청산 진행 중인지 확인
            if not hasattr(self, '_exiting_positions'):
                self._exiting_positions = set()

            if symbol in self._exiting_positions:
                print(f"[청산실행] ⏳ {symbol} 이미 청산 진행 중 (중복 청산 방지)")
                return False

            if symbol not in self.active_positions:
                print(f"[청산실행] ❌ {symbol} 활성 포지션 없음")
                return False

            # 청산 진행 플래그 설정
            self._exiting_positions.add(symbol)
            
            position_info = self.active_positions[symbol]
            is_dca_managed = position_info.get('dca_managed', False)
            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
            
            # DCA 시스템 관리 포지션인 경우
            if is_dca_managed and self.dca_manager:
                try:
                    # 🎯 DCA 시스템 우선순위 청산 요청
                    print(f"[청산요청] 📋 {clean_symbol} → DCA 시스템 청산 요청")
                    print(f"   📝 사유: {exit_reason}")
                    print(f"   📊 비율: {partial_ratio*100:.0f}%" if partial_ratio else "전량")
                    
                    # 청산 사유에 따른 DCA 시스템 호출
                    # 5%수익절반청산 로직 제거됨 - 이 조건은 더 이상 실행되지 않음
                    if False and "5%수익절반청산" in exit_reason and partial_ratio == 0.5:
                        dca_exit_result = self.dca_manager.handle_main_strategy_exit(
                            symbol=clean_symbol,
                            exit_reason="5_percent_half_exit",
                            partial_ratio=0.5
                        )
                    elif "10%수익추가청산" in exit_reason and partial_ratio == 0.5:
                        dca_exit_result = self.dca_manager.handle_main_strategy_exit(
                            symbol=clean_symbol,
                            exit_reason="10_percent_quarter_exit",
                            partial_ratio=0.5  # 남은 물량의 50% = 전체의 25%
                        )
                    elif "10%수익률절반청산" in exit_reason and partial_ratio == 0.5:
                        # 레거시 지원
                        dca_exit_result = self.dca_manager.handle_main_strategy_exit(
                            symbol=clean_symbol,
                            exit_reason="10_percent_half_exit",
                            partial_ratio=0.5
                        )
                    elif "본절보호청산" in exit_reason:
                        dca_exit_result = self.dca_manager.handle_main_strategy_exit(
                            symbol=clean_symbol,
                            exit_reason="principal_protection_exit",
                            partial_ratio=partial_ratio
                        )
                    elif "기술적청산" in exit_reason or "고수익" in exit_reason:
                        dca_exit_result = self.dca_manager.handle_main_strategy_exit(
                            symbol=clean_symbol,
                            exit_reason="technical_exit",
                            partial_ratio=partial_ratio
                        )
                    else:
                        # 기타 청산은 DCA 기본 로직으로 처리
                        dca_exit_result = self.dca_manager.handle_main_strategy_exit(
                            symbol=clean_symbol,
                            exit_reason=exit_reason,
                            partial_ratio=partial_ratio
                        )

                    if dca_exit_result and dca_exit_result.get('success'):
                        print(f"[청산완료] ✅ {clean_symbol} DCA 청산 성공!")
                        print(f"   📝 사유: {exit_reason}")
                        print(f"   📊 청산 타입: {dca_exit_result.get('exit_type', 'N/A')}")
                        print(f"   💬 메시지: {dca_exit_result.get('message', 'N/A')}")

                        # 최대수익률 정보 가져오기
                        max_profit_pct = 0.0
                        if symbol in self.position_stats:
                            max_profit_pct = self.position_stats[symbol].get('max_profit_pct', 0.0)
                            print(f"   📈 최대수익률: {max_profit_pct:+.2f}%")

                        # 로그 파일에도 기록
                        self.logger.info(f"✅ {clean_symbol} DCA 청산 완료 - 타입: {dca_exit_result.get('exit_type')}, 최대수익률: {max_profit_pct:+.2f}%, 사유: {exit_reason}")

                        # BB600 돌파 청산 성공시 플래그 설정 (1회만 실행)
                        if "BB600돌파" in exit_reason and partial_ratio == 0.5 and symbol in self.position_stats:
                            self.position_stats[symbol]['bb600_exit_done'] = True
                            print(f"[플래그설정] ✅ {clean_symbol} BB600 돌파 청산 완료 플래그 설정")

                        # 포지션 정보 업데이트 또는 삭제
                        if partial_ratio >= 1.0:
                            # 전량 청산
                            del self.active_positions[symbol]
                            if symbol in self.position_stats:
                                del self.position_stats[symbol]
                            
                            # 🎯 BB600 부분청산 기록 초기화 (재진입 시 다시 실행 가능하도록)
                            if symbol in self.bb600_partial_liquidations:
                                del self.bb600_partial_liquidations[symbol]
                                self.logger.info(f"🔄 {symbol} BB600 부분청산 기록 초기화 (재진입 시 재실행 가능)")
                            
                            # 🚨 DCA 시스템에 즉시 청산 통지 (동기화 갭 해결)
                            if self.dca_manager and hasattr(self.dca_manager, 'notify_liquidation_from_strategy'):
                                try:
                                    self.dca_manager.notify_liquidation_from_strategy(
                                        symbol=clean_symbol, 
                                        reason=f"main_strategy_liquidation: {exit_reason}"
                                    )
                                    print(f"[동기화] 🔄 {clean_symbol} DCA 시스템에 청산 완료 통지")
                                except Exception as sync_error:
                                    print(f"[동기화] ⚠️ {clean_symbol} DCA 청산 통지 실패: {sync_error}")
                                    self.logger.warning(f"DCA 청산 통지 실패: {sync_error}")

                            # DCA 지정가 주문 자동 취소 (올바른 심볼 형식으로 전달)
                            if self.dca_manager and hasattr(self.dca_manager, 'cancel_all_pending_orders'):
                                try:
                                    future_symbol = clean_symbol + 'USDT'  # BTC → BTCUSDT
                                    cancelled_count = self.dca_manager.cancel_all_pending_orders(future_symbol)
                                    if cancelled_count > 0:
                                        print(f"[주문취소] 🗑️ {clean_symbol} DCA 지정가 주문 {cancelled_count}개 자동 취소")
                                        self.logger.info(f"{clean_symbol} 전량청산 완료 → DCA 지정가 주문 {cancelled_count}개 자동 취소")
                                    else:
                                        print(f"[주문취소] ℹ️ {clean_symbol} 취소할 DCA 지정가 주문 없음")
                                except Exception as cancel_error:
                                    print(f"[주문취소] ⚠️ {clean_symbol} DCA 주문 취소 실패: {cancel_error}")
                                    self.logger.warning(f"{clean_symbol} DCA 주문 자동 취소 실패: {cancel_error}")

                            # 🚀 WebSocket 실시간 모니터링 구독 해제 (4h 제외 - REST API 필터링 전용)
                            if self.ws_kline_manager:
                                try:
                                    ws_symbol = clean_symbol + 'USDT'  # BTC/USDT:USDT → BTCUSDT
                                    # 모든 타임프레임 구독 해제
                                    for tf in ['3m', '5m', '15m', '1d']:
                                        self.ws_kline_manager.unsubscribe_kline(ws_symbol, tf)
                                    print(f"[WebSocket] 🔌 {clean_symbol} 실시간 모니터링 종료")
                                except Exception as ws_error:
                                    self.logger.warning(f"WebSocket 구독 해제 실패: {ws_error}")

                        else:
                            # 부분 청산 - DCA 시스템에서 업데이트된 정보 반영
                            print(f"[부분청산] 📊 {clean_symbol} 부분청산 완료 - 남은 포지션 업데이트")
                            # 부분 청산의 경우 DCA 시스템에서 포지션 관리
                            
                            # 부분 청산 시 position_stats 플래그 업데이트
                            if symbol in self.position_stats:
                                # 5%수익절반청산 로직 제거됨
                                # if "5%수익절반청산" in exit_reason:
                                #     if not self.position_stats[symbol].get('five_percent_exit_done', False):
                                #         self.position_stats[symbol]['five_percent_exit_done'] = True
                                #         print(f"[청산플래그] {clean_symbol} 5% 절반청산 완료")
                                if "10%수익추가청산" in exit_reason:
                                    if not self.position_stats[symbol].get('ten_percent_exit_done', False):
                                        self.position_stats[symbol]['ten_percent_exit_done'] = True
                                        self.position_stats[symbol]['reached_10_percent'] = True
                                        print(f"[청산플래그] {clean_symbol} 10% 추가청산 완료")
                                elif "10%수익률절반청산" in exit_reason:
                                    # 레거시 지원
                                    if not self.position_stats[symbol].get('half_closed', False):
                                        self.position_stats[symbol]['half_closed'] = True
                                        self.position_stats[symbol]['ten_percent_half_exit_count'] = self.position_stats[symbol].get('ten_percent_half_exit_count', 0) + 1
                                        print(f"[청산플래그] {clean_symbol} 10% 절반청산 카운터 증가: {self.position_stats[symbol]['ten_percent_half_exit_count']}")
                                elif "50%급등익절청산" in exit_reason or "10%달성후하락50%청산" in exit_reason:
                                    if not self.position_stats[symbol].get('half_closed', False):
                                        self.position_stats[symbol]['half_closed'] = True

                            # 청산 진행 플래그 해제
                            if symbol in self._exiting_positions:
                                self._exiting_positions.remove(symbol)

                            return True
                    else:
                        print(f"[DCA청산] ⚠️ DCA 청산 실패, 기존 방식으로 긴급 청산 실행")
                        # 긴급 청산: 기존 방식으로 즉시 청산
                        emergency_exit_result = self._execute_emergency_exit(symbol, exit_reason, partial_ratio)
                        if emergency_exit_result:
                            print(f"[청산완료] ✅ {clean_symbol} 청산 완료")
                            return True
                        else:
                            print(f"[청산실패] ❌ {clean_symbol} 청산 실패")
                            return False
                            
                except Exception as e:
                    print(f"[DCA청산] ❌ DCA 청산 오류: {e}")
                    print(f"[DCA청산] 🔄 기존 방식으로 전환")
            
            # 기존 방식 청산 (DCA 시스템 없거나 실패시)
            total_quantity = position_info['quantity']
            exit_quantity = total_quantity * partial_ratio

            # 시장가 매도 주문 (reduceOnly로 숏 전환 방지)
            order = self.exchange.create_market_order(
                symbol=symbol,
                side='sell',
                amount=exit_quantity,
                params={'reduceOnly': True}
            )

            if order and order.get('id'):
                current_price = order.get('average', 0) or order.get('price', 0)
                entry_price = position_info['entry_price']

                # 수익률 계산
                if entry_price and current_price:
                    profit_pct = ((current_price - entry_price) / entry_price) * 100
                    profit_amount = (current_price - entry_price) * exit_quantity
                else:
                    profit_pct = 0
                    profit_amount = 0

                # 최대수익률 정보 가져오기
                max_profit_pct = 0.0
                if symbol in self.position_stats:
                    max_profit_pct = self.position_stats[symbol].get('max_profit_pct', 0.0)

                print(f"[청산완료] ✅ {clean_symbol} 청산 성공!")
                print(f"   💰 청산가: ${current_price:.6f}")
                print(f"   📦 청산수량: {exit_quantity:.6f} ({partial_ratio*100:.0f}%)")
                print(f"   📈 수익률: {profit_pct:+.2f}% (최대: {max_profit_pct:+.2f}%)")
                print(f"   💵 수익금: ${profit_amount:+.2f}")
                print(f"   📝 사유: {exit_reason}")

                # 로그 파일에도 기록
                self.logger.info(f"✅ {clean_symbol} 청산 완료 - 수익률: {profit_pct:+.2f}% (최대: {max_profit_pct:+.2f}%), 수익금: ${profit_amount:+.2f}, 사유: {exit_reason}")

                # 텔레그램 청산 알림
                if self.telegram_bot:
                    try:
                        # 안전한 수익률 포맷팅
                        profit_display = f"{profit_pct:+.2f}%"

                        message = f"🏁 [DCA 청산] {clean_symbol}\n"
                        message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        message += f"💰 수익률: {profit_display}\n"
                        message += f"📈 최대수익률: {max_profit_pct:+.2f}%\n"
                        message += f"💵 수익금: ${profit_amount:+.2f}\n"
                        message += f"🔍 사유: {exit_reason}\n"
                        message += f"📦 청산비율: {partial_ratio*100:.0f}%\n"
                        message += f"⏰ 시간: {get_korea_time().strftime('%H:%M:%S')}\n"
                        message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        
                        if "기술적청산" in exit_reason:
                            message += f"📊 청산 조건:\n"
                            message += f"   • 수익률 1% 이상 달성\n"
                            message += f"   • 기술적 청산 신호 발생\n"
                        elif "고수익기술적청산" in exit_reason:
                            message += f"📊 청산 조건:\n"
                            message += f"   • 수익률 10% 이상 달성\n"
                            message += f"   • MA5-BB480 이격도 ≤ 0.5%\n"
                        elif "10%미만하락청산" in exit_reason:
                            message += f"📊 청산 조건:\n"
                            message += f"   • 10% 이상 달성 후 하락\n"
                            message += f"   • 기술적 청산 미달성\n"
                        elif "본절보호청산" in exit_reason:
                            message += f"📊 청산 조건:\n"
                            message += f"   • 1~5% 최대수익률 달성 후 기준치 하락\n"
                            message += f"   • 수익 보호를 위한 조기 청산\n"
                        elif "최대수익률절반청산" in exit_reason:
                            message += f"📊 청산 조건:\n"
                            message += f"   • 수익률 1.5% 이상 달성\n"
                            message += f"   • 최대수익률 절반 하락\n"
                        
                        message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        message += f"✅ 자동 청산 완료"
                        
                        self.telegram_bot.send_message(message)
                    except Exception as e:
                        self.logger.error(f"청산 알림 전송 실패: {e}")
                
                # 포지션 관리
                if partial_ratio >= 1.0:  # 전량 청산
                    del self.active_positions[symbol]
                    if symbol in self.position_stats:
                        del self.position_stats[symbol]
                    
                    # 🚨 DCA 시스템에 즉시 청산 통지 (동기화 갭 해결)
                    if self.dca_manager and hasattr(self.dca_manager, 'notify_liquidation_from_strategy'):
                        try:
                            self.dca_manager.notify_liquidation_from_strategy(
                                symbol=clean_symbol, 
                                reason=f"fallback_liquidation: {exit_reason}"
                            )
                            print(f"[동기화] 🔄 {clean_symbol} DCA 시스템에 청산 완료 통지 (fallback)")
                        except Exception as sync_error:
                            print(f"[동기화] ⚠️ {clean_symbol} DCA 청산 통지 실패: {sync_error}")
                            self.logger.warning(f"DCA 청산 통지 실패 (fallback): {sync_error}")

                    # DCA 지정가 주문 자동 취소 (올바른 심볼 형식으로 전달)
                    if self.dca_manager and hasattr(self.dca_manager, 'cancel_all_pending_orders'):
                        try:
                            future_symbol = clean_symbol + 'USDT'  # BTC → BTCUSDT
                            cancelled_count = self.dca_manager.cancel_all_pending_orders(future_symbol)
                            if cancelled_count > 0:
                                print(f"[주문취소] 🗑️ {clean_symbol} DCA 지정가 주문 {cancelled_count}개 자동 취소 (fallback)")
                                self.logger.info(f"{clean_symbol} 전량청산 완료 → DCA 지정가 주문 {cancelled_count}개 자동 취소")
                            else:
                                print(f"[주문취소] ℹ️ {clean_symbol} 취소할 DCA 지정가 주문 없음 (fallback)")
                        except Exception as cancel_error:
                            print(f"[주문취소] ⚠️ {clean_symbol} DCA 주문 취소 실패: {cancel_error}")
                            self.logger.warning(f"{clean_symbol} DCA 주문 자동 취소 실패: {cancel_error}")
                else:  # 부분 청산
                    self.active_positions[symbol]['quantity'] = total_quantity - exit_quantity

                    # 부분 청산 시 position_stats 플래그 업데이트
                    if symbol in self.position_stats:
                        if "5%수익절반청산" in exit_reason:
                            if not self.position_stats[symbol].get('five_percent_exit_done', False):
                                self.position_stats[symbol]['five_percent_exit_done'] = True
                                print(f"[청산플래그] {clean_symbol} 5% 절반청산 완료 (fallback)")
                        elif "10%수익추가청산" in exit_reason:
                            if not self.position_stats[symbol].get('ten_percent_exit_done', False):
                                self.position_stats[symbol]['ten_percent_exit_done'] = True
                                self.position_stats[symbol]['reached_10_percent'] = True
                                print(f"[청산플래그] {clean_symbol} 10% 추가청산 완료 (fallback)")
                        elif "10%수익률절반청산" in exit_reason:
                            # 레거시 지원
                            if not self.position_stats[symbol].get('half_closed', False):
                                self.position_stats[symbol]['half_closed'] = True
                                self.position_stats[symbol]['ten_percent_half_exit_count'] = self.position_stats[symbol].get('ten_percent_half_exit_count', 0) + 1
                                print(f"[청산플래그] {clean_symbol} 10% 절반청산 카운터 증가: {self.position_stats[symbol]['ten_percent_half_exit_count']}")
                        elif "50%급등익절청산" in exit_reason or "10%달성후하락50%청산" in exit_reason:
                            if not self.position_stats[symbol].get('half_closed', False):
                                self.position_stats[symbol]['half_closed'] = True

                    # 📊 부분청산 데이터를 accumulator에 누적 (즉시 통계 반영하지 않음)
                    if symbol not in self.partial_exit_accumulator:
                        self.partial_exit_accumulator[symbol] = {
                            'partial_exits': [],
                            'total_pnl': 0.0,
                            'exit_count': 0
                        }

                    # 청산 데이터 수집
                    exit_data = self._collect_exit_data(symbol, current_price, exit_reason)
                    position_stats = self.position_stats.get(symbol, {})
                    entry_data = position_stats.get('entry_data', {})

                    partial_exit_detail = {
                        'exit_reason': exit_reason,
                        'exit_price': current_price,
                        'exit_quantity': exit_quantity,
                        'profit_pct': profit_pct,
                        'profit_amount': profit_amount,
                        'timestamp': get_korea_time().isoformat(),
                        'entry_price': entry_price,
                        'entry_conditions': entry_data,
                        'exit_conditions': exit_data
                    }

                    # accumulator에 부분청산 데이터 추가
                    self.partial_exit_accumulator[symbol]['partial_exits'].append(partial_exit_detail)
                    self.partial_exit_accumulator[symbol]['total_pnl'] += profit_amount
                    self.partial_exit_accumulator[symbol]['exit_count'] += 1

                    self.logger.info(f"📊 부분청산 누적 (기존방식): {clean_symbol} 손익 ${profit_amount:.2f} (누적 {self.partial_exit_accumulator[symbol]['exit_count']}회, 총 손익 ${self.partial_exit_accumulator[symbol]['total_pnl']:.2f})")

                    # 청산 진행 플래그 해제
                    if symbol in self._exiting_positions:
                        self._exiting_positions.remove(symbol)

                    return True  # 부분청산은 여기서 종료 (전량 청산 시 통계 반영)

                # 📊 전량 청산: 부분청산 누적 데이터 확인 및 합산
                partial_exits_data = []
                accumulated_pnl = 0.0
                partial_exit_count = 0

                if symbol in self.partial_exit_accumulator:
                    accumulator = self.partial_exit_accumulator[symbol]
                    partial_exits_data = accumulator['partial_exits']
                    accumulated_pnl = accumulator['total_pnl']
                    partial_exit_count = accumulator['exit_count']

                    self.logger.info(f"📊 부분청산 합산 (기존방식): {clean_symbol} 부분청산 {partial_exit_count}회, 누적 손익 ${accumulated_pnl:.2f}")

                # 최종 청산 손익 = 마지막 전량 청산 손익 + 누적 부분청산 손익
                final_profit_amount = profit_amount + accumulated_pnl

                if partial_exit_count > 0:
                    self.logger.info(f"📊 전량청산 기록 (기존방식): {clean_symbol} @ ${current_price:.6f}, "
                                   f"최종청산 손익: ${profit_amount:.2f}, 부분청산 {partial_exit_count}회 손익: ${accumulated_pnl:.2f}, "
                                   f"총 손익: ${final_profit_amount:.2f}")

                # 거래 통계 업데이트 (부분청산 + 전량청산 = 1거래)
                current_trading_day = self._get_trading_day()
                if self.today_stats['date'] != current_trading_day:
                    self._reset_daily_stats(current_trading_day)

                self.today_stats['total_trades'] += 1
                self.today_stats['total_pnl'] += final_profit_amount  # 부분청산 포함 총 손익

                # 승패 판정: 최종 총 손익 기준
                if final_profit_amount > 0:
                    self.today_stats['wins'] += 1
                else:
                    self.today_stats['losses'] += 1

                # 승률 계산
                total_trades = self.today_stats['total_trades']
                if total_trades > 0:
                    self.today_stats['win_rate'] = (self.today_stats['wins'] / total_trades) * 100

                # Phase 1: 청산 데이터 수집 (기존 방식 청산)
                exit_data = self._collect_exit_data(symbol, current_price, exit_reason)

                # Phase 1: DCA 포지션 관리 데이터 수집 (부분청산 내역 포함)
                dca_data = {
                    'partial_exit_count': partial_exit_count,
                    'partial_exits': partial_exits_data,
                    'accumulated_pnl': accumulated_pnl,
                    'final_exit_pnl': profit_amount,
                    'total_pnl': final_profit_amount
                }

                # Phase 1: 거래 상세 정보 추가 (핵심!)
                position_stats = self.position_stats.get(symbol, {})
                entry_data = position_stats.get('entry_data', {})
                trade_detail = {
                    'symbol': clean_symbol,
                    'order_id': str(order.get('id', 'N/A')),
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'quantity': exit_quantity,
                    'profit_pct': profit_pct,
                    'profit_amount': final_profit_amount,  # 부분청산 포함 총 손익
                    'final_exit_profit': profit_amount,  # 최종 청산만의 손익
                    'partial_exit_profit': accumulated_pnl,  # 부분청산 누적 손익
                    'partial_exit_count': partial_exit_count,
                    'timestamp': get_korea_time().isoformat(),
                    'trade_type': 'win' if final_profit_amount > 0 else 'loss',
                    'entry_conditions': entry_data,  # 진입 조건
                    'exit_conditions': exit_data,    # 청산 조건
                    'position_management': dca_data  # DCA 정보 (부분청산 내역 포함)
                }

                # trades_detail 배열에 추가
                if 'trades_detail' not in self.today_stats:
                    self.today_stats['trades_detail'] = []
                self.today_stats['trades_detail'].append(trade_detail)

                # 📊 accumulator 데이터 삭제 (포지션 완전히 종료됨)
                if symbol in self.partial_exit_accumulator:
                    del self.partial_exit_accumulator[symbol]
                    self.logger.info(f"📊 부분청산 누적 데이터 정리 완료 (기존방식): {clean_symbol}")

                # 통계 파일 저장
                self._save_daily_stats()

                self.logger.info(f"📊 일일통계 업데이트 (기존방식): 거래 {total_trades}회, 총 손익 ${final_profit_amount:.2f}")

                # 청산 진행 플래그 해제
                if symbol in self._exiting_positions:
                    self._exiting_positions.remove(symbol)

                return True
            else:
                print(f"[청산실행] ❌ 청산 주문 실행 실패")
                # 실패 시에도 플래그 해제
                if hasattr(self, '_exiting_positions') and symbol in self._exiting_positions:
                    self._exiting_positions.remove(symbol)
                return False

        except Exception as e:
            print(f"[청산실행] ❌ 청산 실행 실패: {e}")
            # 예외 발생 시에도 플래그 해제
            if hasattr(self, '_exiting_positions') and symbol in self._exiting_positions:
                self._exiting_positions.remove(symbol)
            return False

    def _execute_emergency_exit(self, symbol, exit_reason="긴급청산", partial_ratio=1.0):
        """
        긴급 청산 메서드 - DCA 시스템 실패 시 사용하는 기존 방식 청산
        DCA 청산이 실패하거나 불가능할 때 호출되는 응급 조치
        """
        try:
            print(f"[긴급청산] 🚨 {symbol} 긴급 청산 시작 - 사유: {exit_reason}")
            
            # 현재 포지션 정보 확인
            if symbol not in self.active_positions:
                print(f"[긴급청산] ⚠️ {symbol} 활성 포지션 없음")
                return False
            
            position = self.active_positions[symbol]
            quantity = position.get('quantity', 0)
            entry_price = position.get('entry_price', 0)
            
            if quantity <= 0:
                print(f"[긴급청산] ⚠️ {symbol} 청산할 수량 없음")
                return False
            
            # 현재가 조회
            ticker = self.exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            
            # 긴급 청산 수량 계산
            exit_quantity = quantity * partial_ratio
            
            print(f"[긴급청산] 📋 {symbol}: 현재가 ${current_price:.6f}, 청산수량 {exit_quantity:.6f}")
            
            # 긴급 시장가 매도 주문 실행
            try:
                order = self.exchange.create_market_sell_order(symbol, exit_quantity)
                print(f"[긴급청산] ✅ {symbol} 긴급 청산 주문 완료: {order.get('id', 'N/A')}")
                
                # 수익률 계산
                profit_pct = (current_price - entry_price) / entry_price * 100
                profit_amount = (current_price - entry_price) * exit_quantity
                
                print(f"[긴급청산] 💰 {symbol} 청산 완료 - 수익률: {profit_pct:+.2f}%, 수익금: ${profit_amount:+.2f}")
                
                # 포지션 관리
                if partial_ratio >= 1.0:  # 전량 청산
                    del self.active_positions[symbol]
                    if symbol in self.position_stats:
                        del self.position_stats[symbol]
                    print(f"[긴급청산] 🏁 {symbol} 전량 청산 완료")
                else:  # 부분 청산
                    self.active_positions[symbol]['quantity'] = quantity - exit_quantity
                    print(f"[긴급청산] 📊 {symbol} 부분 청산 완료 - 잔여수량: {self.active_positions[symbol]['quantity']:.6f}")
                
                # 청산 진행 플래그 해제
                if hasattr(self, '_exiting_positions') and symbol in self._exiting_positions:
                    self._exiting_positions.remove(symbol)
                
                return True
                
            except Exception as order_error:
                print(f"[긴급청산] ❌ {symbol} 긴급 청산 주문 실패: {order_error}")
                return False
                
        except Exception as e:
            print(f"[긴급청산] ❌ {symbol} 긴급 청산 오류: {e}")
            # 예외 발생 시에도 플래그 해제
            if hasattr(self, '_exiting_positions') and symbol in self._exiting_positions:
                self._exiting_positions.remove(symbol)
            return False

    def monitor_positions_realtime(self):
        """실시간 포지션 모니터링 (고속 최적화)"""
        # 5분마다 바이낸스와 동기화 (동기화 문제 방지)
        if not hasattr(self, '_last_sync_time'):
            self._last_sync_time = 0

        current_time = time.time()
        if current_time - self._last_sync_time > 5:  # 5초 (청산 후 빠른 반영)
            self.sync_positions_with_exchange()
            self._last_sync_time = current_time

        # DCA 주문 점검 및 복구 (30초마다)
        if not hasattr(self, '_last_dca_check_time'):
            self._last_dca_check_time = 0

        if current_time - self._last_dca_check_time > 30:  # 30초마다
            if self.dca_manager:
                try:
                    # DCA 주문 점검 메서드가 있는지 확인 후 호출
                    if hasattr(self.dca_manager, 'check_and_fix_missing_dca_orders'):
                        self.dca_manager.check_and_fix_missing_dca_orders()
                    else:
                        # 대체 메서드 호출 (일반적인 포지션 동기화)
                        if hasattr(self.dca_manager, 'sync_positions_with_exchange'):
                            self.dca_manager.sync_positions_with_exchange()
                    self._last_dca_check_time = current_time
                except Exception as e:
                    self.logger.error(f"DCA 주문 점검 오류: {e}")
        
        # 🛡️ 강화된 DCA 주문 복구 (1분마다)
        if not hasattr(self, '_last_enhanced_dca_recovery_time'):
            self._last_enhanced_dca_recovery_time = 0
        
        if (hasattr(self, 'dca_recovery') and self.dca_recovery and 
            current_time - self._last_enhanced_dca_recovery_time > 60):  # 1분
            try:
                # 현재 거래소 포지션 정보 구성
                exchange_positions = {}
                current_prices = {}
                
                for symbol in self.active_positions.keys():
                    try:
                        positions = self.exchange.fetch_positions([symbol])
                        if positions and positions[0].get('contracts', 0) > 0:
                            mark_price = positions[0]['markPrice']
                            exchange_positions[symbol] = {
                                'contracts': positions[0]['contracts'],
                                'markPrice': mark_price
                            }
                            current_prices[symbol] = mark_price
                    except Exception as pos_error:
                        print(f"[강화복구] ⚠️ {symbol} 포지션 조회 실패: {pos_error}")
                
                # 강화된 DCA 주문 복구 실행
                if exchange_positions:
                    recovery_result = self.dca_recovery.enhanced_scan_and_recover(
                        exchange_positions, current_prices
                    )
                    
                    # DCA 복구 결과는 로그 파일에만 기록 (콘솔 출력 제거)
                    if recovery_result.get('successful_recoveries', 0) > 0:
                        self.logger.debug(f"DCA 복구 완료: {recovery_result['successful_recoveries']}개 주문")
                    elif recovery_result.get('missing_orders_detected'):
                        self.logger.debug(f"DCA 누락 감지: {len(recovery_result['missing_orders_detected'])}개 주문")
                    elif recovery_result.get('predictive_placements'):
                        self.logger.debug(f"DCA 예측 배치: {len(recovery_result['predictive_placements'])}건")
                    else:
                        # 성공 로그는 15분에 한번만 (스팸 방지)
                        if not hasattr(self, '_last_enhanced_success_log'):
                            self._last_enhanced_success_log = 0
                        if current_time - self._last_enhanced_success_log > 900:  # 15분마다
                            print(f"[강화복구] ✅ 모든 DCA 주문 정상 (스캔: {recovery_result.get('scan_duration', 0):.1f}초)")
                            self._last_enhanced_success_log = current_time
                
                self._last_enhanced_dca_recovery_time = current_time
                
            except Exception as recovery_error:
                print(f"[강화복구] ❌ 강화된 DCA 복구 실패: {recovery_error}")
        
        # 🎯 DCA 트리거 모니터링 (PHB 등 -3% DCA 진입용)
        if not hasattr(self, '_last_dca_trigger_check'):
            self._last_dca_trigger_check = 0
        
        if current_time - self._last_dca_trigger_check > 10:  # 10초마다 체크
            if self.dca_manager and hasattr(self.dca_manager, 'positions'):
                try:
                    # 각 DCA 포지션의 트리거 확인
                    for symbol, position in self.dca_manager.positions.items():
                        if position.is_active:
                            # 현재가 조회
                            current_price = self.get_accurate_current_price(symbol)
                            if current_price:
                                # 수익률 계산
                                profit_pct = (current_price - position.average_price) / position.average_price
                                
                                # DCA 트리거 체크
                                if hasattr(self.dca_manager, '_check_dca_triggers'):
                                    # DCA 매니저에서 트리거 체크
                                    total_balance = 100.0  # 임시값 (실제로는 잔고 조회)
                                    trigger_result = self.dca_manager._check_dca_triggers(
                                        position, current_price, total_balance, profit_pct
                                    )
                                    
                                    if trigger_result and trigger_result.get('trigger_activated'):
                                        clean_symbol = symbol.replace('/USDT:USDT', '')
                                        self.logger.info(f"🔻 DCA 트리거 실행: {clean_symbol} - {trigger_result['trigger_info']['type']}")
                                        print(f"🔻 DCA 트리거: {clean_symbol} ({profit_pct*100:.1f}%) - {trigger_result['trigger_info']['type']}")
                    
                    self._last_dca_trigger_check = current_time
                except Exception as e:
                    self.logger.error(f"DCA 트리거 모니터링 오류: {e}")
        
        # 🔧 기본 DCA 주문 복구 (백업용 - 5분마다)  
        elif not hasattr(self, '_last_dca_recovery_time'):
            self._last_dca_recovery_time = 0
        
        elif (hasattr(self, 'dca_recovery') and self.dca_recovery and 
              current_time - self._last_dca_recovery_time > 300):  # 5분
            try:
                # 현재 거래소 포지션 정보 구성
                exchange_positions = {}
                for symbol in self.active_positions.keys():
                    try:
                        positions = self.exchange.fetch_positions([symbol])
                        if positions and positions[0].get('contracts', 0) > 0:
                            exchange_positions[symbol] = {
                                'contracts': positions[0]['contracts'],
                                'markPrice': positions[0]['markPrice']
                            }
                    except Exception as pos_error:
                        print(f"[기본복구] ⚠️ {symbol} 포지션 조회 실패: {pos_error}")
                
                # 기본 DCA 주문 복구 실행
                if exchange_positions:
                    recovery_result = self.dca_recovery.enhanced_scan_and_recover(exchange_positions)
                    
                    if recovery_result.get('successful_recoveries', 0) > 0:
                        print(f"[기본복구] ✅ {recovery_result['successful_recoveries']}개 주문 복구 완료")
                
                self._last_dca_recovery_time = current_time
                
            except Exception as recovery_error:
                print(f"[기본복구] ❌ DCA 주문 복구 실패: {recovery_error}")
        
        # 🎯 DCA 주문 누락 체크 및 자동 배치 (5분마다)
        if not hasattr(self, '_last_dca_order_check_time'):
            self._last_dca_order_check_time = 0

        if current_time - self._last_dca_order_check_time > 300:  # 5분
            try:
                if self.dca_manager and hasattr(self.dca_manager, 'add_limit_orders_to_existing_positions'):
                    self.dca_manager.add_limit_orders_to_existing_positions()
                    # DCA order check completed - log only when there are actual orders placed
                self._last_dca_order_check_time = current_time
            except Exception as dca_order_error:
                self.logger.warning(f"[DCA주문체크] ⚠️ DCA 주문 체크 실패: {dca_order_error}")

        # 📊 거래 내역 동기화 (10분마다)
        if not hasattr(self, '_last_history_sync_time'):
            self._last_history_sync_time = 0

        if (hasattr(self, 'trade_history_sync') and self.trade_history_sync and
            current_time - self._last_history_sync_time > 600):  # 10분
            try:
                sync_result = self.trade_history_sync.sync_trade_history()
                
                if sync_result.get('new_trades_found', 0) > 0:
                    print(f"[거래동기화] ✅ {sync_result['new_trades_found']}건 신규 거래 발견 및 동기화")
                    
                    # 일일 통계 출력 업데이트
                    summary = self.trade_history_sync.get_daily_summary()
                    # 손익 색상 구분
                    if summary['total_pnl'] >= 0:
                        pnl_color = "\033[92m"  # 녹색 (수익)
                        pnl_emoji = "💚"
                    else:
                        pnl_color = "\033[91m"  # 빨간색 (손실)
                        pnl_emoji = "💔"
                    
                    print(f"[통계업데이트] 총 {summary['total_trades']}회 거래, "
                          f"{summary['win_rate']:.1f}% 승률, {pnl_emoji} {pnl_color}${summary['total_pnl']:+.2f}\033[0m 손익")
                elif not sync_result.get('error'):
                    # 15분에 한번만 정상 로그 (스팸 방지)
                    if not hasattr(self, '_last_sync_success_log'):
                        self._last_sync_success_log = 0
                    if current_time - self._last_sync_success_log > 900:  # 15분
                        print(f"[거래동기화] ✅ 거래 내역 정상 동기화 확인")
                        self._last_sync_success_log = current_time
                
                self._last_history_sync_time = current_time
                
            except Exception as sync_error:
                print(f"[거래동기화] ❌ 거래 내역 동기화 실패: {sync_error}")
        
        # 🔄 순환매 기회 모니터링 및 실행 (5초마다)
        if not hasattr(self, '_last_cyclic_check_time'):
            self._last_cyclic_check_time = 0

        if current_time - self._last_cyclic_check_time > 5:  # 5초
            try:
                if (self.dca_manager and hasattr(self.dca_manager, 'monitor_cyclic_opportunities') and
                    hasattr(self.dca_manager, 'execute_cyclic_trading')):
                    
                    # 순환매 기회 모니터링
                    opportunities = self.dca_manager.monitor_cyclic_opportunities(
                        self.active_positions, current_prices
                    )
                    
                    if opportunities:
                        print(f"[순환매] 🔄 {len(opportunities)}개 기회 감지")
                        
                        # 순환매 실행
                        execution_result = self.dca_manager.execute_cyclic_trading(opportunities)
                        
                        if execution_result['executed'] > 0:
                            print(f"[순환매] ✅ {execution_result['executed']}건 부분청산 실행 완료")
                            
                            # 성공한 순환매 결과 로깅 및 DCA 재주문
                            for result in execution_result['results']:
                                if result['success']:
                                    symbol = result['symbol']
                                    realized_profit = result['result'].get('realized_profit', 0)
                                    executed_amount = result['result'].get('executed_amount', 0)
                                    print(f"   • {symbol}: 수량={executed_amount:.6f}, 수익=${realized_profit:+.4f}")
                                    
                                    # 🔄 부분청산 이후 DCA 재주문 로직
                                    if (self.dca_manager and symbol in self.dca_manager.positions and 
                                        hasattr(self.dca_manager, 'place_missing_dca_orders_after_partial_exit')):
                                        try:
                                            dca_position = self.dca_manager.positions[symbol]
                                            
                                            # 최대 순환매 3회 제한 체크
                                            if dca_position.cyclic_count < dca_position.max_cyclic_count:
                                                # 현재가 조회
                                                current_price = self.get_current_price(symbol)
                                                if current_price:
                                                    # DCA 재주문 실행 (빈 단계에 자동 지정가 주문)
                                                    reorder_result = self.dca_manager.place_missing_dca_orders_after_partial_exit(
                                                        symbol, current_price
                                                    )
                                                    
                                                    if reorder_result.get('orders_placed', 0) > 0:
                                                        clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                                                        print(f"[DCA재주문] 🔄 {clean_symbol}: {reorder_result['orders_placed']}개 DCA 주문 재등록")
                                                        
                                                        # 순환매 카운트 증가
                                                        dca_position.cyclic_count += 1
                                                        print(f"[순환매카운트] 📊 {clean_symbol}: {dca_position.cyclic_count}/{dca_position.max_cyclic_count}회")
                                                    else:
                                                        print(f"[DCA재주문] ⚠️ {symbol}: DCA 재주문 불필요 또는 실패")
                                            else:
                                                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                                                print(f"[순환매제한] 🚫 {clean_symbol}: 최대 순환매 {dca_position.max_cyclic_count}회 도달")
                                                
                                        except Exception as reorder_error:
                                            print(f"[DCA재주문] ❌ {symbol} DCA 재주문 실패: {reorder_error}")
                                    
                                    # 텔레그램 알림은 DCA 매니저에서 자동 전송
                                    
                        elif any(not r['success'] for r in execution_result['results']):
                            # 실패한 결과만 표시
                            failed_count = sum(1 for r in execution_result['results'] if not r['success'])
                            print(f"[순환매] ⚠️ {failed_count}건 실행 실패")
                    
                    # 15분에 한번만 정상 상태 로그 (스팸 방지)
                    elif not opportunities:
                        if not hasattr(self, '_last_cyclic_success_log'):
                            self._last_cyclic_success_log = 0
                        if current_time - self._last_cyclic_success_log > 900:  # 15분
                            print(f"[순환매] ✅ 순환매 기회 모니터링 정상 (현재 기회 없음)")
                            self._last_cyclic_success_log = current_time
                
                self._last_cyclic_check_time = current_time
                
            except Exception as cyclic_error:
                print(f"[순환매] ❌ 순환매 모니터링 실패: {cyclic_error}")
        
        # 🚨 일일 손실 추적 및 선별적 비상청산 (30초마다)
        if not hasattr(self, '_last_daily_loss_check_time'):
            self._last_daily_loss_check_time = 0

        if current_time - self._last_daily_loss_check_time > 30:  # 30초
            try:
                if self.dca_manager and hasattr(self.dca_manager, 'update_daily_loss_tracker'):
                    self.dca_manager.update_daily_loss_tracker()
                self._last_daily_loss_check_time = current_time
            except Exception as daily_loss_error:
                print(f"[일일손실추적] ❌ 일일 손실 추적 실패: {daily_loss_error}")
        
        # 🎯 본절청산 시스템 (5%~10% 수익 절반 하락시 전량청산)
        if not hasattr(self, '_last_breakeven_check'):
            self._last_breakeven_check = 0
        
        if current_time - self._last_breakeven_check > 5:  # 5초마다 체크
            if self.active_positions and self.dca_manager:
                try:
                    for symbol in list(self.active_positions.keys()):
                        if symbol in self.dca_manager.positions:
                            dca_position = self.dca_manager.positions[symbol]
                            if dca_position.is_active:
                                # 현재가 조회
                                current_price = self.get_current_price(symbol)
                                if current_price:
                                    # 현재 수익률 계산
                                    current_profit_pct = (current_price - dca_position.average_price) / dca_position.average_price
                                    
                                    # 최대 수익률이 5% 이상 10% 미만인 경우
                                    max_profit_pct = dca_position.max_profit_pct
                                    if 0.05 <= max_profit_pct < 0.1:
                                        # 최대 수익률의 절반 하락 체크
                                        half_profit_threshold = max_profit_pct * 0.5
                                        
                                        # 🔧 수정: 현재 수익률이 양수 범위에서만 절반 하락시 청산
                                        if current_profit_pct > 0 and current_profit_pct <= half_profit_threshold:
                                            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                                            print(f"[본절청산] 🎯 {clean_symbol} 절반 하락 감지: "
                                                  f"최대 {max_profit_pct*100:.1f}% → 현재 {current_profit_pct*100:.1f}% "
                                                  f"(임계값 {half_profit_threshold*100:.1f}%)")
                                            
                                            # 전량 청산 실행
                                            exit_reason = f"본절청산 (최대 {max_profit_pct*100:.1f}% → {current_profit_pct*100:.1f}% 절반하락)"
                                            if self.execute_exit_trade(symbol, exit_reason, partial_ratio=1.0):
                                                print(f"[본절청산] ✅ {clean_symbol} 본절청산 완료")
                                                # breakeven_protection_active 플래그 리셋
                                                dca_position.breakeven_protection_active = False
                                            else:
                                                print(f"[본절청산] ❌ {clean_symbol} 본절청산 실패")
                                
                                # 최대 수익률 업데이트 (DCA 매니저에서도 처리하지만 중복 체크)
                                if current_profit_pct > dca_position.max_profit_pct:
                                    dca_position.max_profit_pct = current_profit_pct
                                    # 5% 도달시 breakeven_protection_active 활성화
                                    if current_profit_pct >= 0.05 and not dca_position.breakeven_protection_active:
                                        dca_position.breakeven_protection_active = True
                                        clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                                        print(f"[본절청산] 📊 {clean_symbol} 본절보호 활성화 (수익률 {current_profit_pct*100:.1f}%)")
                    
                    self._last_breakeven_check = current_time
                    
                except Exception as breakeven_error:
                    print(f"[본절청산] ❌ 본절청산 체크 실패: {breakeven_error}")

        # 🚨 실시간 손절 감지 (3초마다 - 고속 손절)
        if self.active_positions:
            try:
                for symbol in list(self.active_positions.keys()):
                    if symbol in self.dca_manager.positions:
                        dca_position = self.dca_manager.positions[symbol]
                        if dca_position.is_active:
                            # 현재가 조회
                            current_price = self.get_current_price(symbol)
                            if current_price:
                                # 단계별 손절 조건 체크 (옵션C)
                                stop_loss_pct = self.dca_manager.config['stop_loss_by_stage'].get(
                                    dca_position.current_stage, -0.10
                                )
                                stop_loss_multiplier = 1 + stop_loss_pct  # -0.10 -> 0.90, -0.07 -> 0.93, -0.05 -> 0.95
                                stop_loss_price = dca_position.average_price * stop_loss_multiplier

                                if current_price <= stop_loss_price:
                                    clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                                    stop_loss_pct_display = abs(stop_loss_pct * 100)
                                    print(f"[실시간손절] 🚨 {clean_symbol} 손절 감지 ({dca_position.current_stage}단계: -{stop_loss_pct_display:.0f}%): 현재가 ${current_price:.6f} <= 손절가 ${stop_loss_price:.6f}")

                                    # 즉시 손절 실행
                                    exit_reason = f"평균가 -{stop_loss_pct_display:.0f}% 손절 ({dca_position.current_stage})"
                                    if self.execute_exit_trade(symbol, exit_reason, partial_ratio=1.0):
                                        print(f"[실시간손절] ✅ {clean_symbol} 손절 완료")
                                    else:
                                        print(f"[실시간손절] ❌ {clean_symbol} 손절 실패")
            except Exception as stop_loss_error:
                print(f"[실시간손절] ❌ 손절 감지 실패: {stop_loss_error}")

        # 🎯 새로운 5가지 청산 조건 체크 (BB600 포함)
        if not hasattr(self, '_last_new_exit_check'):
            self._last_new_exit_check = 0

        if current_time - self._last_new_exit_check > 2:  # 2초마다 체크
            if self.dca_manager and self.active_positions:
                try:
                    for symbol in list(self.active_positions.keys()):
                        # 현재가 조회
                        current_price = self.get_current_price(symbol)
                        if current_price:
                            # DCA 매니저의 새로운 청산 시스템 호출
                            exit_signal = self.dca_manager.check_all_new_exit_signals(symbol, current_price)
                            if exit_signal:
                                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                                exit_type = exit_signal['exit_type']
                                exit_ratio = exit_signal.get('exit_ratio', 1.0)
                                trigger_info = exit_signal.get('trigger_info', '')
                                
                                print(f"[청산신호] 🎯 {clean_symbol} {exit_type} 감지: {trigger_info}")
                                
                                # 청산 실행
                                result = self.dca_manager.execute_new_exit(symbol, exit_signal)
                                if isinstance(result, dict):
                                    if result.get('success', False):
                                        print(f"[청산실행] ✅ {clean_symbol} {exit_type} 청산 완료")
                                    elif not result.get('silent', False):
                                        print(f"[청산실행] ❌ {clean_symbol} {exit_type} 청산 실패")
                                    # silent=True인 경우 메시지 출력하지 않음
                                else:
                                    # 호환성을 위한 기존 방식 처리
                                    if result:
                                        print(f"[청산실행] ✅ {clean_symbol} {exit_type} 청산 완료")
                                    else:
                                        print(f"[청산실행] ❌ {clean_symbol} {exit_type} 청산 실패")
                    
                    self._last_new_exit_check = current_time
                    
                except Exception as e:
                    self.logger.error(f"새로운 청산 조건 체크 실패: {e}")
        
        # 🚨 긴급 청산 요청 처리 (API 밴 상황 대응)
        if hasattr(self, '_emergency_exit_requests') and self._emergency_exit_requests:
            try:
                for symbol in list(self._emergency_exit_requests):
                    clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                    print(f"[긴급청산] 🚨 {clean_symbol} API 밴 대응 청산 시도")
                    
                    # 메인 전략의 청산 시스템 사용 (API 사용량 최소화)
                    if self.execute_exit_trade(symbol, "API밴 대응 긴급청산", partial_ratio=1.0):
                        print(f"[긴급청산] ✅ {clean_symbol} 청산 완료")
                        self._emergency_exit_requests.remove(symbol)
                    else:
                        print(f"[긴급청산] ❌ {clean_symbol} 청산 실패 - 재시도 대기")
                        
            except Exception as e:
                self.logger.error(f"긴급 청산 요청 처리 실패: {e}")

        # 🎯 DCA 포지션 수익률 체크 및 비활성화 (5초마다)
        if not hasattr(self, '_last_dca_profit_check'):
            self._last_dca_profit_check = 0

        if current_time - self._last_dca_profit_check > 5:  # 5초
            if self.dca_manager and self.active_positions:
                try:
                    # 2차 DCA 대상 카운트
                    first_dca_count = 0

                    for symbol in list(self.active_positions.keys()):
                        if symbol in self.dca_manager.positions:
                            position = self.dca_manager.positions[symbol]

                            # FIRST_DCA 단계 카운트
                            if position.current_stage == "first_dca":
                                first_dca_count += 1

                            # 현재가 조회
                            current_price = self.get_current_price(symbol)
                            if current_price is None:
                                continue  # 가격 조회 실패시 스킵

                            # 🎯 DCA 지정가 주문 체결 확인 (우선순위)
                            try:
                                balance = self.exchange.fetch_balance()
                                total_balance = balance.get('USDT', {}).get('free', 0)
                                self.dca_manager.check_pending_limit_orders(symbol, current_price, total_balance)
                            except Exception as limit_check_error:
                                pass  # 조용히 실패

                            # DCA 트리거 체크 (최대 수익률 업데이트 및 5% 수익 DCA 비활성화 포함)
                            self.dca_manager.check_dca_triggers(symbol, current_price)

                    # 2차 DCA 대상이 없을 경우 - 로그 생략 (스팸 방지)

                    self._last_dca_profit_check = current_time
                except Exception as dca_check_error:
                    pass  # 조용히 실패 (다음 주기에 재시도)

    def get_real_position_info(self, symbol):
        """거래소에서 실시간 포지션 정보 조회 (하이브리드 동기화)"""
        try:
            positions = self.exchange.fetch_positions([symbol])
            position = next((p for p in positions if p['symbol'] == symbol and abs(p['contracts']) > 0), None)
            
            if position:
                return {
                    'entry_price': float(position['entryPrice']) if position['entryPrice'] else 0,
                    'current_price': float(position['markPrice']) if position['markPrice'] else 0,
                    'unrealized_pnl': float(position['unrealizedPnl']) if position['unrealizedPnl'] else 0,
                    'quantity': abs(float(position['contracts'])) if position['contracts'] else 0,
                    'side': position['side'],
                    'percentage': float(position['percentage']) if position['percentage'] else 0
                }
            return None
        except Exception as e:
            # API 실패시 조용히 None 반환
            return None

    def get_accurate_current_price(self, symbol):
        """실시간 현재가 조회 (ticker 사용)"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            # 안전한 ticker 데이터 접근
            if isinstance(ticker, dict) and 'last' in ticker:
                return float(ticker['last'])
            elif isinstance(ticker, (list, tuple)) and len(ticker) > 0:
                return float(ticker[0]) if ticker[0] is not None else None
            else:
                return None
        except Exception as e:
            # ticker 실패시 1분봉 종가 사용
            try:
                df_1m = self.get_ohlcv_data(symbol, '1m', limit=1)
                if df_1m is not None and len(df_1m) > 0:
                    return float(df_1m.iloc[-1]['close'])
            except:
                pass
            return None

    def calculate_profit_with_verification(self, symbol, cached_profit_pct):
        """수익률 계산 with 실시간 검증 (하이브리드 방식)"""
        try:
            # 1. 중요한 순간 판단
            is_critical = (
                abs(cached_profit_pct) > 5.0 or  # 5% 이상 수익/손실
                abs(cached_profit_pct) >= 9.5 or  # 10% 근처
                (symbol in self.position_stats and 
                 self.position_stats[symbol].get('max_profit_pct', 0) >= 8.0)  # 과거 8% 이상 달성
            )
            
            # 2. 중요한 순간이거나 주기적 검증 시점이면 실시간 검증
            current_time = time.time()
            need_sync = (
                is_critical or 
                (current_time - self.last_exchange_sync_time > self.exchange_sync_interval)
            )
            
            if need_sync:
                real_position = self.get_real_position_info(symbol)
                if real_position and real_position['quantity'] > 0:
                    # 거래소 직접 계산 손익률 사용
                    if real_position['percentage'] != 0:
                        real_profit_pct = real_position['percentage']
                    else:
                        # percentage가 0이면 직접 계산
                        if real_position['entry_price'] > 0:
                            real_profit_pct = ((real_position['current_price'] - real_position['entry_price']) / 
                                             real_position['entry_price']) * 100
                        else:
                            real_profit_pct = cached_profit_pct
                    
                    # 3. 차이가 크면 포지션 강제 동기화
                    if abs(cached_profit_pct - real_profit_pct) > self.sync_accuracy_threshold:
                        self.force_sync_position(symbol, real_position)
                        self.last_exchange_sync_time = current_time
                        return real_profit_pct
                    
                    # 4. 캐시 업데이트
                    self.position_cache[symbol] = {
                        'real_position': real_position,
                        'last_update': current_time
                    }
                    
                    self.last_exchange_sync_time = current_time
                    return real_profit_pct
            
            # 5. 검증 불필요하거나 실패시 캐시된 값 사용
            return cached_profit_pct
            
        except Exception as e:
            # 오류시 캐시된 값 반환
            return cached_profit_pct

    def force_sync_position(self, symbol, real_position):
        """포지션 강제 동기화"""
        try:
            if symbol in self.active_positions and real_position:
                # 메인 시스템 포지션 업데이트
                self.active_positions[symbol].update({
                    'entry_price': real_position['entry_price'],
                    'quantity': real_position['quantity'],
                    'current_price': real_position['current_price']
                })
                
                # DCA 시스템과 동기화
                if self.dca_manager and symbol in self.dca_manager.positions:
                    dca_pos = self.dca_manager.positions[symbol]
                    if hasattr(dca_pos, 'sync_with_exchange'):
                        dca_pos.sync_with_exchange(real_position)
                
                print(f"[강제동기화] {symbol.replace('/USDT:USDT', '')} 거래소 데이터로 동기화 완료")
                
        except Exception as e:
            print(f"[강제동기화] ❌ {symbol} 동기화 실패: {e}")

    def is_critical_moment(self):
        """중요한 순간 판단 (추가 실시간 검증 필요)"""
        # 활성 포지션 중 하나라도 중요한 수익률 구간에 있으면 true
        for symbol in self.active_positions:
            if symbol in self.position_stats:
                current_profit = self.position_stats[symbol].get('current_profit_pct', 0)
                max_profit = self.position_stats[symbol].get('max_profit_pct', 0)
                
                if (abs(current_profit) > 8.0 or max_profit > 8.0 or 
                    9.5 <= current_profit <= 10.5):  # 10% 근처
                    return True
        return False

        if not self.active_positions:
            return
        
        # 🎨 예쁜 포지션 요약 보고
        if self.active_positions:
            position_count = len(self.active_positions)
            position_summary = []
            for symbol, pos_info in self.active_positions.items():
                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                # DCA 관리 여부에 따른 이모지 구분
                if pos_info.get('dca_managed', False):
                    position_summary.append(f"🔄\033[97m\033[1m{clean_symbol}\033[0m")  # DCA 관리
                else:
                    position_summary.append(f"📊\033[97m\033[1m{clean_symbol}\033[0m")  # 일반 관리
            
            # 포지션 수에 따른 이모지 선택
            if position_count >= 10:
                count_emoji = "🔥"
                count_color = "\033[93m\033[1m"  # 노란색 굵게
            elif position_count >= 5:
                count_emoji = "⚡"
                count_color = "\033[92m\033[1m"  # 녹색 굵게
            else:
                count_emoji = "💼"
                count_color = "\033[96m\033[1m"  # 청록색 굵게
            
            print(f"🏦 \033[97m\033[1m포지션 현황\033[0m: {count_emoji} {count_color}{position_count}개 보유중\033[0m → {' • '.join(position_summary)}")
        else:
            print(f"🏦 \033[97m\033[1m포지션 현황\033[0m: 📭 \033[90m포지션 없음\033[0m")
        
        # 1. 현재가 일괄 조회 (가장 빠른 방법)
        try:
            symbols_list = list(self.active_positions.keys())
            tickers = self.exchange.fetch_tickers(symbols_list)
            
            for symbol in symbols_list:
                try:
                    if symbol not in tickers:
                        continue
                    
                    position_info = self.active_positions[symbol]
                    current_price = tickers[symbol]['last']
                    
                    # DCA 시스템 관리 포지션인지 확인
                    is_dca_managed = position_info.get('dca_managed', False)
                    
                    if is_dca_managed and self.dca_manager:
                        # DCA 시스템에서 수익률과 평균가 조회
                        try:
                            dca_position_id = position_info.get('dca_position_id')
                            if dca_position_id:
                                # 🎯 1단계: DCA 지정가 주문 체결 확인 (우선순위)
                                try:
                                    balance = self.exchange.fetch_balance()
                                    total_balance = balance.get('USDT', {}).get('free', 0)

                                    limit_order_filled = self.dca_manager.check_pending_limit_orders(
                                        symbol, current_price, total_balance
                                    )

                                    if limit_order_filled:
                                        clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                                        # DCA limit order filled - simplified logging
                                        print(f"[DCA] {clean_symbol}: 지정가 체결")
                                except Exception as limit_check_error:
                                    self.logger.error(f"지정가 주문 체결 확인 실패 {symbol}: {limit_check_error}")

                                # 🎯 2단계: DCA 트리거 조건 확인 (-3%, -6% 하락 - 시장가 백업)
                                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                                # Simplified DCA trigger checking - verbose logs removed
                                dca_trigger_result = self.dca_manager.check_dca_triggers(
                                    symbol, current_price
                                )
                                
                                if dca_trigger_result and dca_trigger_result.get('trigger_activated'):
                                    trigger_info = dca_trigger_result['trigger_info']
                                    clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                                    # Simplified DCA trigger notification
                                    print(f"🎯 {clean_symbol} DCA {trigger_info['stage']} 발동 ({trigger_info['drop_pct']:.2f}% 하락)")
                                    
                                    # 통합 DCA 트리거 알림 (중복 방지를 위해 메인 전략에서 발송)
                                    # DCA 매니저의 자체 알림은 비활성화하고 여기서 통합 알림 발송
                                    new_avg_price = dca_trigger_result.get('new_average_price', current_price)
                                    self.send_unified_dca_trigger_alert(
                                        symbol, 
                                        trigger_info['stage'], 
                                        current_price, 
                                        new_avg_price, 
                                        trigger_info['additional_amount']
                                    )
                                
                                # 🔧 DCA 수익률 실시간 업데이트 (즉시 호출)
                                self.dca_manager.check_dca_triggers(symbol, current_price)
                                
                                # DCA 평균 진입가와 수익률 조회
                                dca_stats = self.dca_manager.get_position_stats(symbol)
                                if dca_stats:
                                    entry_price = dca_stats['average_price']
                                    profit_pct = dca_stats['profit_pct']
                                    
                                    # 포지션 정보 업데이트 (DCA 평균가 반영)
                                    self.active_positions[symbol]['entry_price'] = entry_price
                                    self.active_positions[symbol]['quantity'] = dca_stats['total_quantity']
                                else:
                                    # DCA 통계 조회 실패시 기존 방식 + 하이브리드 검증
                                    entry_price = position_info['entry_price']
                                    cached_profit_pct = ((current_price - entry_price) / entry_price) * 100
                                    profit_pct = self.calculate_profit_with_verification(symbol, cached_profit_pct)
                            else:
                                # DCA ID 없음, 기존 방식 + 하이브리드 검증
                                entry_price = position_info['entry_price']
                                cached_profit_pct = ((current_price - entry_price) / entry_price) * 100
                                profit_pct = self.calculate_profit_with_verification(symbol, cached_profit_pct)
                        except Exception as e:
                            print(f"[DCA모니터링] ⚠️ DCA 시스템 조회 실패: {e}")
                            # DCA 오류시 기존 방식 + 하이브리드 검증
                            entry_price = position_info['entry_price']
                            cached_profit_pct = ((current_price - entry_price) / entry_price) * 100
                            profit_pct = self.calculate_profit_with_verification(symbol, cached_profit_pct)
                    else:
                        # 기존 방식 (DCA 미적용) + 하이브리드 검증
                        entry_price = position_info['entry_price']
                        cached_profit_pct = ((current_price - entry_price) / entry_price) * 100
                        profit_pct = self.calculate_profit_with_verification(symbol, cached_profit_pct)
                    
                    # 포지션 통계 업데이트
                    if symbol in self.position_stats:
                        self.position_stats[symbol]['current_profit_pct'] = profit_pct
                        if profit_pct > self.position_stats[symbol]['max_profit_pct']:
                            self.position_stats[symbol]['max_profit_pct'] = profit_pct
                        if profit_pct < self.position_stats[symbol]['min_profit_pct']:
                            self.position_stats[symbol]['min_profit_pct'] = profit_pct

                        # 10% 이상 달성 기록
                        if profit_pct >= 10.0:
                            self.position_stats[symbol]['reached_10_percent'] = True
                    
                    # 빠른 청산 조건 체크 (중요한 것만)
                    exit_signal = False
                    exit_reason = ""
                    
                    # position_stats 없으면 즉시 초기화 (청산 시스템 보완)
                    if symbol not in self.position_stats:
                        print(f"[청산보완] {symbol} position_stats 누락 → 즉시 초기화")
                        self.position_stats[symbol] = {
                            'max_profit_pct': profit_pct if profit_pct > 0 else 0.0,
                            'min_profit_pct': profit_pct if profit_pct < 0 else 0.0,
                            'current_profit_pct': profit_pct,
                            'half_closed': False,
                            'reached_10_percent': profit_pct >= 10.0,
                            'ten_percent_half_exit_count': 0,
                            'five_percent_exit_done': False,
                            'ten_percent_exit_done': False,
                            'bb600_exit_done': False,  # BB600 돌파 절반청산 완료 여부 (1회만)
                            'technical_exit_attempted': False
                        }

                    if profit_pct > 0:
                        # 포지션 통계 업데이트 (중복이지만 안전성 위해)
                        self.position_stats[symbol]['current_profit_pct'] = profit_pct
                        if profit_pct > self.position_stats[symbol]['max_profit_pct']:
                            self.position_stats[symbol]['max_profit_pct'] = profit_pct
                        if profit_pct < self.position_stats[symbol]['min_profit_pct']:
                            self.position_stats[symbol]['min_profit_pct'] = profit_pct
                        if profit_pct >= 10.0:
                            self.position_stats[symbol]['reached_10_percent'] = True
                        
                        # 🆕 새로운 4가지 청산 방식 확인 (기존 청산 로직 완전 교체)
                        if self.dca_manager and hasattr(self.dca_manager, 'check_all_new_exit_signals'):
                            # 새로운 청산 시스템 사용
                            new_exit_signal = self.dca_manager.check_all_new_exit_signals(symbol, current_price)
                            if new_exit_signal:
                                exit_signal = True
                                exit_type = new_exit_signal['exit_type']
                                exit_ratio = new_exit_signal['exit_ratio']
                                
                                # 청산 이유 설정
                                if exit_type == "supertrend_exit":
                                    exit_reason = f"SuperTrend 전량청산 (수익조건+시그널)"
                                elif exit_type == "bb600_partial_exit":
                                    exit_reason = f"BB600 50% 익절 ({new_exit_signal.get('timeframe', '15m')}봉)"
                                elif exit_type == "breakeven_protection":
                                    exit_reason = f"약수익보호 전량청산 (최대{new_exit_signal.get('max_profit_pct', 0):.1f}%)"
                                elif exit_type == "weak_rise_dump_protection":
                                    exit_reason = f"약상승후 급락 리스크 회피 (최대{new_exit_signal.get('max_profit_pct', 0):.1f}%→{new_exit_signal.get('current_profit_pct', 0):.1f}%)"
                                else:
                                    exit_reason = f"새로운청산방식 ({exit_type})"
                        else:
                            # 🔄 DCA 순환매 일부청산은 기존 시스템 유지 (4번째 청산 방식)
                            # 기존 청산 로직은 완전히 비활성화됨
                            pass

                    # 4. 본절보호청산: 1~5% 구간에서만 적용
                    if not exit_signal and symbol in self.position_stats:
                        max_profit = self.position_stats[symbol]['max_profit_pct']
                        # 1~5% 구간에서만 본절보호청산 적용
                        if 1.0 <= max_profit < 5.0:
                            exit_threshold = 0.0
                            # 구간별 청산 기준 설정
                            if 4.0 <= max_profit < 5.0:
                                exit_threshold = 1.0  # 4~5%: 1% 이하
                            elif 3.0 <= max_profit < 4.0:
                                exit_threshold = 0.75  # 3~4%: 0.75% 이하
                            elif 2.0 <= max_profit < 3.0:
                                exit_threshold = 0.5  # 2~3%: 0.5% 이하
                            elif 1.0 <= max_profit < 2.0:
                                exit_threshold = 0.25  # 1~2%: 0.25% 이하
                            if profit_pct <= exit_threshold:
                                # 🚨 수익률 급변동 방지: 0.1초 재확인
                                import time
                                time.sleep(0.1)
                                
                                # 현재 가격 재조회로 수익률 재계산
                                try:
                                    current_ticker = self.exchange.fetch_ticker(symbol)
                                    current_price_recheck = current_ticker['last']
                                    profit_pct_recheck = ((current_price_recheck - position['avg_price']) / position['avg_price']) * 100
                                    
                                    # 재확인 후에도 청산 조건 유지되는지 검증
                                    if profit_pct_recheck <= exit_threshold:
                                        exit_signal = True
                                        exit_reason = f"본절보호청산 (최대 {max_profit:.2f}% → 현재 {profit_pct_recheck:.2f}%, 기준 {exit_threshold:.2f}%)"
                                    else:
                                        # 가격 회복으로 청산 조건 해제
                                        self.logger.info(f"📈 {symbol} 가격 회복으로 본절보호청산 취소: {profit_pct:.2f}% → {profit_pct_recheck:.2f}%")
                                except Exception as recheck_error:
                                    # 재확인 실패시 원래 로직 유지
                                    exit_signal = True
                                    exit_reason = f"본절보호청산 (최대 {max_profit:.2f}% → 현재 {profit_pct:.2f}%, 기준 {exit_threshold:.2f}%)"

                    clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                    
                    if exit_signal:
                        # 청산 시작 (상세 로그는 execute_exit_trade에서 출력)

                        # 🆕 새로운 청산 시스템 실행
                        if self.dca_manager and hasattr(self.dca_manager, 'execute_new_exit') and 'new_exit_signal' in locals():
                            # 새로운 청산 시스템 사용
                            success = self.dca_manager.execute_new_exit(symbol, new_exit_signal)
                            if success:
                                print(f"[새로운청산] ✅ {clean_symbol} {exit_reason} 완료")
                            else:
                                print(f"[새로운청산] ❌ {clean_symbol} {exit_reason} 실패")
                        elif self.dca_manager and hasattr(self.dca_manager, 'queue_exit_request'):
                            # 청산 유형과 우선순위 결정
                            if "10%수익률절반청산" in exit_reason:
                                priority = "HIGH"
                                partial_ratio = 0.5
                                exit_type = "PARTIAL_PROFIT"
                            elif "손절" in exit_reason or "급락" in exit_reason:
                                priority = "EMERGENCY"
                                partial_ratio = 1.0
                                exit_type = "STOP_LOSS"
                            else:
                                priority = "MEDIUM"
                                partial_ratio = 1.0
                                exit_type = "PROFIT_PROTECTION"
                            
                            # 청산 요청을 큐에 추가
                            success = self.dca_manager.queue_exit_request(
                                symbol=symbol,
                                exit_type=exit_type,
                                priority=priority,
                                partial_ratio=partial_ratio,
                                reason=exit_reason,
                                trigger_price=current_price
                            )
                            
                            if success:
                                # 즉시 큐 처리 (실시간 동기화)
                                queue_result = self.dca_manager.process_exit_queue()
                                if queue_result.get('processed', 0) > 0:
                                    # 청산 성공 (플래그는 execute_exit_trade 내부에서 처리)
                                    if profit_pct >= 10.0:
                                        self.position_stats[symbol]['reached_10_percent'] = True
                                else:
                                    print(f"⚠️ {clean_symbol} 청산 처리 실패")
                            else:
                                # 큐 추가 실패시 기존 방식으로 fallback
                                self._execute_legacy_exit(symbol, exit_reason, partial_ratio, current_price)
                        else:
                            # DCA 시스템 없으면 기존 방식
                            partial_ratio = 0.5 if ("5%수익절반청산" in exit_reason or
                                                   "10%수익추가청산" in exit_reason or
                                                   "10%수익률절반청산" in exit_reason or
                                                   "50%급등익절청산" in exit_reason or
                                                   "10%달성후하락50%청산" in exit_reason) else 1.0

                            if self.execute_exit_trade(symbol, exit_reason, partial_ratio=partial_ratio):
                                # 청산 성공 (플래그는 execute_exit_trade 내부에서 처리)
                                if profit_pct >= 10.0:
                                    self.position_stats[symbol]['reached_10_percent'] = True
                    
                    # 📊 실시간 모니터링 출력 (청산 신호와 무관하게 항상 표시)
                    stats = self.position_stats.get(symbol, {})
                    max_profit = stats.get('max_profit_pct', 0)
                    reached_10 = stats.get('reached_10_percent', False)
                    half_closed = stats.get('half_closed', False)
                    
                    status_info = []
                    if reached_10:
                        status_info.append("10%달성")
                    if half_closed:
                        status_info.append("50%청산됨")
                    if max_profit > profit_pct and max_profit > 5:
                        status_info.append(f"최고{max_profit:.1f}%")
                    
                    status_str = f"({'/'.join(status_info)})" if status_info else ""
                    
                    # DCA 상황도 함께 출력
                    entry_amount = position_info.get('entry_amount', 0)
                    # entry_amount가 0이면 현재 포지션 크기로부터 역산하여 계산
                    if entry_amount == 0:
                        quantity = position_info.get('quantity', 0)
                        entry_price = position_info.get('entry_price', 0)
                        leverage = position_info.get('leverage', self.leverage)
                        if quantity > 0 and entry_price > 0 and leverage > 0:
                            position_value = quantity * entry_price
                            entry_amount = position_value / leverage
                    
                    # 진입가 정보
                    entry_price_display = position_info.get('entry_price', 0)
                    entry_info = f"진입가${entry_price_display:.6f}"
                    amount_info = f"진입금${entry_amount:.2f}"
                    
                    # 수익률 색상 구분
                    if profit_pct >= 0:
                        profit_color = "\033[92m"  # 녹색 (플러스)
                        profit_emoji = "📈"
                    else:
                        profit_color = "\033[91m"  # 빨간색 (마이너스)
                        profit_emoji = "📉"
                    
                    # 하이브리드 동기화 상태 표시
                    sync_status = ""
                    current_time = time.time()
                    if symbol in self.position_cache:
                        last_update = self.position_cache[symbol].get('last_update', 0)
                        if current_time - last_update < 60:  # 1분 이내 검증됨
                            sync_status = " 🔄검증됨"
                    
                    # 🎨 예쁜 실시간 모니터링 출력
                    # 수익률 크기에 따른 이모지 강화
                    if profit_pct >= 50.0:
                        profit_emoji = "🚀"
                        profit_color = "\033[93m\033[1m"  # 노란색 굵게 (대박)
                    elif profit_pct >= 20.0:
                        profit_emoji = "🔥"
                        profit_color = "\033[92m\033[1m"  # 녹색 굵게 (대성공)
                    elif profit_pct >= 10.0:
                        profit_emoji = "💎"
                        profit_color = "\033[92m\033[1m"  # 녹색 굵게 (성공)
                    elif profit_pct >= 5.0:
                        profit_emoji = "📈"
                        profit_color = "\033[92m"        # 녹색 (좋음)
                    elif profit_pct >= 0:
                        profit_emoji = "📊"
                        profit_color = "\033[96m"        # 청록색 (플러스)
                    else:
                        profit_emoji = "📉"
                        profit_color = "\033[91m"        # 빨간색 (마이너스)
                    
                    # 청산 신호 이모지
                    exit_indicator = ""
                    if exit_signal:
                        if "10%" in exit_reason:
                            exit_indicator = " 🎯"
                        elif "급등" in exit_reason:
                            exit_indicator = " 🚀"
                        elif "손절" in exit_reason or "급락" in exit_reason:
                            exit_indicator = " ⚠️"
                        else:
                            exit_indicator = " 🔔"
                    
                    # 상태 뱃지 색상 강화
                    if status_str:
                        status_str = f"\033[95m{status_str}\033[0m"  # 자주색
                    
                    # 심볼명 강화 (크기와 색상)
                    symbol_display = f"\033[97m\033[1m{clean_symbol}\033[0m"  # 흰색 굵게
                    
                    # 수익률 표시 강화
                    profit_display = f"{profit_color}{profit_pct:+.2f}%\033[0m"
                    
                    # 진입 정보 색상
                    entry_info_colored = f"\033[94m{entry_info}\033[0m"  # 파란색
                    amount_info_colored = f"\033[93m{amount_info}\033[0m"  # 노란색
                    
                    # 동기화 상태 강화
                    if sync_status:
                        sync_status = f"\033[92m{sync_status}\033[0m"  # 녹색
                    
                    # Simplified position display - verbose logging removed
                    if exit_signal:
                        print(f"💰 {clean_symbol}: {profit_pct:+.2f}% 청산신호: {exit_reason}")
                    else:
                        print(f"💰 {clean_symbol}: {profit_pct:+.2f}%")
                        
                except Exception as e:
                    print(f"[실시간모니터링] ⚠️ {symbol} 개별 처리 실패: {e}")
                    
        except Exception as e:
            print(f"[실시간모니터링] ❌ 일괄 조회 실패, 개별 조회로 전환: {e}")
            # 일괄 조회 실패시 기존 방식으로 폴백
            self.monitor_positions_fallback()
    
    def monitor_positions_detailed(self):
        """상세 포지션 모니터링 (기술적 분석 포함)"""
        if not self.active_positions:
            return
        
        print(f"\n[상세모니터링] 활성 포지션 {len(self.active_positions)}개 기술적 분석...")
        
        for symbol in list(self.active_positions.keys()):
            try:
                position_info = self.active_positions[symbol]
                entry_price = position_info['entry_price']
                
                # 청산 신호 체크 (전체 조건)
                exit_result = self.check_exit_signal(symbol, entry_price)
                
                if exit_result.get('exit_signal'):
                    exit_reason = exit_result.get('exit_reason', '기술적청산')
                    partial_ratio = exit_result.get('partial_ratio', 1.0)  # 📊 부분청산 비율 추출
                    clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')

                    print(f"[상세모니터링] 🚨 {clean_symbol} 기술적청산: {exit_reason}")

                    # 기술적 청산 실행
                    if self.execute_exit_trade(symbol, exit_reason, partial_ratio=partial_ratio):
                        print(f"[상세모니터링] ✅ {clean_symbol} 기술적청산 완료")
                    else:
                        print(f"[상세모니터링] ❌ {clean_symbol} 기술적청산 실패")
                        
                # API 호출 간격 조절 (Rate Limit 방지)
                time.sleep(0.5)  # 500ms 간격
                        
            except Exception as e:
                print(f"[상세모니터링] ❌ {symbol} 분석 실패: {e}")
    
    def monitor_positions_fallback(self):
        """포지션 모니터링 폴백 (개별 조회)"""
        for symbol in list(self.active_positions.keys()):
            try:
                position_info = self.active_positions[symbol]
                entry_price = position_info['entry_price']
                
                # 개별 현재가 조회 (하이브리드 방식)
                current_price = self.get_accurate_current_price(symbol)
                if current_price is None:
                    continue
                    
                # 수익률 계산 (하이브리드 검증)
                cached_profit_pct = ((current_price - entry_price) / entry_price) * 100
                profit_pct = self.calculate_profit_with_verification(symbol, cached_profit_pct)
                
                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                # Simplified fallback monitoring logging
                if abs(profit_pct) > 5.0:  # Only show significant changes
                    print(f"📊 {clean_symbol}: {profit_pct:+.2f}%")

                time.sleep(0.3)  # 300ms 간격 (Rate Limit 방지)
                
            except Exception as e:
                print(f"[폴백모니터링] ❌ {symbol} 조회 실패: {e}")
    
    def update_trade_stats(self, event_type: str = None, data: dict = None, profit_pct: float = None, profit_amount: float = None):
        """DCA 매니저에서 호출되는 거래 통계 업데이트 콜백"""
        try:
            # 새로운 DCA 이벤트 처리 (event_type과 data가 있는 경우)
            if event_type and data:
                if event_type == "dca_entry":
                    symbol = data.get('symbol', '')
                    stage = data.get('stage', '')
                    price = data.get('price', 0)
                    amount = data.get('amount', 0)
                    new_average = data.get('new_average', 0)
                    
                    self.logger.info(f"📊 DCA 진입 기록: {symbol} {stage} @ ${price:.6f}, 금액: ${amount:.2f}, 새 평균가: ${new_average:.6f}")
                    
                    # DCA 진입 통계 (별도 관리)
                    if not hasattr(self, 'dca_stats'):
                        self.dca_stats = {'total_entries': 0, 'first_dca': 0, 'second_dca': 0}
                    
                    self.dca_stats['total_entries'] += 1
                    if stage == 'first_dca':
                        self.dca_stats['first_dca'] += 1
                    elif stage == 'second_dca':
                        self.dca_stats['second_dca'] += 1
                
                elif event_type == "dca_stage_exit":
                    symbol = data.get('symbol', '')
                    stage = data.get('stage', '')
                    exit_price = data.get('exit_price', 0)
                    profit_pct = data.get('profit_pct', 0)
                    exit_amount = data.get('exit_amount', 0)
                    remaining_amount = data.get('remaining_amount', 0)
                    profit_amount = data.get('profit_amount', 0)  # 실제 손익 금액

                    self.logger.info(f"📊 DCA 부분청산 기록: {symbol} {stage} @ ${exit_price:.6f}, 수익률: {profit_pct:.2f}%, 청산금액: ${exit_amount:.2f}")

                    # DCA 청산 통계 (별도 관리)
                    if not hasattr(self, 'dca_exit_stats'):
                        self.dca_exit_stats = {'total_exits': 0, 'profitable_exits': 0}

                    self.dca_exit_stats['total_exits'] += 1
                    if profit_pct > 0:
                        self.dca_exit_stats['profitable_exits'] += 1

                    # 📊 부분청산 데이터를 accumulator에 누적 (즉시 통계 반영하지 않음)
                    # 전량 청산 시점에 모든 부분청산 데이터를 합산하여 1거래로 기록

                    if symbol not in self.partial_exit_accumulator:
                        self.partial_exit_accumulator[symbol] = {
                            'partial_exits': [],
                            'total_pnl': 0.0,
                            'exit_count': 0
                        }

                    # Phase 1: 청산 데이터 수집 (DCA 이벤트)
                    exit_data_event = self._collect_exit_data(symbol, exit_price, f"DCA {stage} 청산")

                    # Phase 1: DCA 포지션 관리 데이터 수집
                    dca_data_event = {
                        'dca_executed': True,
                        'stage': stage,
                        'exit_amount': exit_amount,
                        'remaining_amount': remaining_amount
                    }

                    # Phase 1: 거래 상세 정보 추가 (accumulator에 저장)
                    position_stats_event = self.position_stats.get(symbol, {})
                    entry_data_event = position_stats_event.get('entry_data', {})
                    entry_price_event = self.active_positions.get(symbol, {}).get('entry_price', 0)

                    partial_exit_detail = {
                        'stage': stage,
                        'exit_price': exit_price,
                        'exit_amount': exit_amount,
                        'profit_pct': profit_pct,
                        'profit_amount': profit_amount,
                        'timestamp': get_korea_time().isoformat(),
                        'entry_price': entry_price_event,
                        'entry_conditions': entry_data_event,
                        'exit_conditions': exit_data_event,
                        'position_management': dca_data_event
                    }

                    # accumulator에 부분청산 데이터 추가
                    self.partial_exit_accumulator[symbol]['partial_exits'].append(partial_exit_detail)
                    self.partial_exit_accumulator[symbol]['total_pnl'] += profit_amount
                    self.partial_exit_accumulator[symbol]['exit_count'] += 1

                    self.logger.info(f"📊 부분청산 누적: {symbol} {stage} 손익 ${profit_amount:.2f} (누적 {self.partial_exit_accumulator[symbol]['exit_count']}회, 총 손익 ${self.partial_exit_accumulator[symbol]['total_pnl']:.2f})")

                    return  # DCA 부분청산 이벤트는 여기서 종료 (전량 청산 시 통계 반영)

                elif event_type == "dca_full_exit":
                    # DCA 전량 청산 이벤트 처리
                    symbol = data.get('symbol', '')
                    exit_price = data.get('exit_price', 0)
                    entry_price = data.get('entry_price', 0)
                    profit_pct = data.get('profit_pct', 0)
                    profit_amount = data.get('profit_amount', 0)
                    exit_quantity = data.get('exit_quantity', 0)
                    exit_reason = data.get('exit_reason', '수동청산')
                    is_auto_exit = data.get('is_auto_exit', False)
                    order_id = data.get('order_id', 'DCA_FULL_EXIT')

                    # 📊 부분청산 누적 데이터 확인 및 합산
                    partial_exits_data = []
                    accumulated_pnl = 0.0
                    partial_exit_count = 0

                    if symbol in self.partial_exit_accumulator:
                        accumulator = self.partial_exit_accumulator[symbol]
                        partial_exits_data = accumulator['partial_exits']
                        accumulated_pnl = accumulator['total_pnl']
                        partial_exit_count = accumulator['exit_count']

                        self.logger.info(f"📊 부분청산 합산: {symbol} 부분청산 {partial_exit_count}회, 누적 손익 ${accumulated_pnl:.2f}")

                    # 최종 청산 손익 = 마지막 전량 청산 손익 + 누적 부분청산 손익
                    final_profit_amount = profit_amount + accumulated_pnl

                    # 자동/수동 청산 구분 로그
                    exit_type = "자동청산" if is_auto_exit else "수동청산"
                    if partial_exit_count > 0:
                        self.logger.info(f"📊 DCA 전량청산 기록 ({exit_type}): {symbol} @ ${exit_price:.6f}, "
                                       f"최종청산 손익: ${profit_amount:.2f}, 부분청산 {partial_exit_count}회 손익: ${accumulated_pnl:.2f}, "
                                       f"총 손익: ${final_profit_amount:.2f}")
                    else:
                        self.logger.info(f"📊 DCA 전량청산 기록 ({exit_type}): {symbol} @ ${exit_price:.6f}, 수익률: {profit_pct:.2f}%, 수익금: ${profit_amount:.2f}")

                    # 일일 통계 업데이트 (부분청산 + 전량청산 = 1거래)
                    current_trading_day = self._get_trading_day()
                    if self.today_stats['date'] != current_trading_day:
                        self._reset_daily_stats(current_trading_day)

                    self.today_stats['total_trades'] += 1
                    self.today_stats['total_pnl'] += final_profit_amount  # 부분청산 포함 총 손익

                    # 승패 판정: 최종 총 손익 기준
                    if final_profit_amount > 0:
                        self.today_stats['wins'] += 1
                    else:
                        self.today_stats['losses'] += 1

                    # 승률 계산
                    total_trades = self.today_stats['total_trades']
                    if total_trades > 0:
                        self.today_stats['win_rate'] = (self.today_stats['wins'] / total_trades) * 100

                    # 청산 데이터 수집
                    exit_data = self._collect_exit_data(symbol, exit_price, exit_reason)

                    # DCA 포지션 관리 데이터 (부분청산 내역 포함)
                    dca_data = {
                        'dca_executed': True,
                        'full_exit': True,
                        'exit_type': exit_type,
                        'is_auto_exit': is_auto_exit,
                        'partial_exit_count': partial_exit_count,
                        'partial_exits': partial_exits_data,  # 모든 부분청산 내역
                        'accumulated_pnl': accumulated_pnl,
                        'final_exit_pnl': profit_amount,
                        'total_pnl': final_profit_amount
                    }

                    # 거래 상세 정보
                    position_stats = self.position_stats.get(symbol, {})
                    entry_data = position_stats.get('entry_data', {})

                    trade_detail = {
                        'symbol': symbol.replace('/USDT:USDT', '').replace('/USDT', ''),
                        'order_id': order_id,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'quantity': exit_quantity,
                        'profit_pct': profit_pct,  # 최종 청산의 수익률
                        'max_roe_pct': position_stats.get('max_profit_pct', 0.0),  # 최고 수익률
                        'min_roe_pct': position_stats.get('min_profit_pct', 0.0),  # 최저 수익률
                        'profit_amount': final_profit_amount,  # 부분청산 포함 총 손익
                        'final_exit_profit': profit_amount,  # 최종 청산만의 손익
                        'partial_exit_profit': accumulated_pnl,  # 부분청산 누적 손익
                        'partial_exit_count': partial_exit_count,
                        'timestamp': get_korea_time().isoformat(),
                        'trade_type': 'win' if final_profit_amount > 0 else 'loss',
                        'entry_conditions': entry_data,
                        'exit_conditions': exit_data,
                        'position_management': dca_data
                    }

                    # trades_detail 배열에 추가
                    if 'trades_detail' not in self.today_stats:
                        self.today_stats['trades_detail'] = []
                    self.today_stats['trades_detail'].append(trade_detail)

                    # 📊 accumulator 데이터 삭제 (포지션 완전히 종료됨)
                    if symbol in self.partial_exit_accumulator:
                        del self.partial_exit_accumulator[symbol]
                        self.logger.info(f"📊 부분청산 누적 데이터 정리 완료: {symbol}")

                    # 통계 파일 저장
                    self._save_daily_stats()

                    self.logger.info(f"📊 일일통계 업데이트 ({exit_type}): 거래 {total_trades}회, 총 손익 ${final_profit_amount:.2f}")

                    return  # DCA 전량 청산 이벤트 종료

            # 기존 거래 완료 통계 처리 (호환성 유지)
            if profit_pct is not None and profit_amount is not None:
                # 거래 통계 업데이트 (9시 기준 날짜 체크)
                current_trading_day = self._get_trading_day()
                if self.today_stats['date'] != current_trading_day:
                    self._reset_daily_stats(current_trading_day)
                
                self.today_stats['total_trades'] += 1
                self.today_stats['total_pnl'] += profit_amount
                
                if profit_pct > 0:
                    self.today_stats['wins'] += 1
                else:
                    self.today_stats['losses'] += 1
                
                # 승률 계산
                total_trades = self.today_stats['total_trades']
                if total_trades > 0:
                    self.today_stats['win_rate'] = (self.today_stats['wins'] / total_trades) * 100
                
                self.logger.info(f"📊 통계 업데이트: 거래 {total_trades}회, 수익률 {profit_pct*100:.2f}%, 수익금 ${profit_amount:.2f}")
            
        except Exception as e:
            self.logger.error(f"통계 업데이트 실패: {e}")

    def print_daily_stats(self):
        """일일 거래 통계 출력"""
        try:
            # 9시 기준 날짜 체크 및 통계 리셋
            current_trading_day = self._get_trading_day()
            if self.today_stats['date'] != current_trading_day:
                self._reset_daily_stats(current_trading_day)
            
            # 🔄 DCA 시스템과 daily_stats 동기화
            self._sync_dca_with_daily_stats()
            
            # 📊 바이낸스 주문 기록과 동기화 (실제 거래 기록 반영)
            if self.order_history_sync and hasattr(self, '_last_order_sync') and (time.time() - self._last_order_sync > 60):
                try:
                    print("   📊 바이낸스 거래 기록 동기화 중...")
                    summary = self.order_history_sync.get_daily_summary()
                    if summary and summary['total_trades'] > 0:
                        # 바이낸스 실제 거래 기록으로 통계 업데이트
                        self.today_stats['total_trades'] = summary['total_trades']
                        self.today_stats['wins'] = summary['wins']
                        self.today_stats['losses'] = summary['losses']
                        self.today_stats['win_rate'] = summary['win_rate']
                        self.today_stats['total_pnl'] = summary['realized_pnl']
                        self.today_stats['total_entry_amount'] = summary['volume_usdt']
                        print(f"   ✅ 거래 기록 동기화 완료: {summary['total_trades']}개 거래")
                        self._save_daily_stats()
                    self._last_order_sync = time.time()
                except Exception as e:
                    print(f"   ⚠️ 거래 기록 동기화 실패: {e}")
            elif not hasattr(self, '_last_order_sync'):
                self._last_order_sync = time.time()
            
            stats = self.today_stats
            print(f"\n📊 [일일통계] {stats['date']}")
            print(f"   💰 총 거래: {stats['total_trades']}회")
            print(f"   ✅ 수익: {stats['wins']}회 | ❌ 손실: {stats['losses']}회")
            print(f"   📈 승률: {stats['win_rate']:.1f}%")

            # Day ROE(%) 계산 및 출력
            day_roe_pct = 0.0
            if stats['total_entry_amount'] > 0:
                day_roe_pct = (stats['total_pnl'] / stats['total_entry_amount']) * 100
            if day_roe_pct >= 0:
                roe_color = "\033[92m"  # 녹색
                roe_emoji = "📈"
            else:
                roe_color = "\033[91m"  # 빨간색
                roe_emoji = "📉"
            print(f"   {roe_emoji} Day ROE: {roe_color}{day_roe_pct:+.2f}%\033[0m (원금: ${stats['total_entry_amount']:.2f})")

            # 총 손익 색상 구분
            if stats['total_pnl'] >= 0:
                pnl_color = "\033[92m"  # 녹색 (수익)
                pnl_emoji = "💚"
            else:
                pnl_color = "\033[91m"  # 빨간색 (손실)
                pnl_emoji = "💔"
            
            # 🔄 실시간 활성 포지션 손익 계산 (정확한 현재 손익)
            current_total_pnl = 0.0
            if self.active_positions:
                for symbol, pos_info in self.active_positions.items():
                    try:
                        current_price = self.get_current_price(symbol)
                        entry_price = pos_info.get('entry_price', 0)
                        entry_amount = pos_info.get('entry_amount', 0)
                        quantity = pos_info.get('quantity', 0)
                        position_side = pos_info.get('side', 'long')
                        
                        # DCA 평균가 우선 사용
                        if self.dca_manager and symbol in self.dca_manager.positions:
                            dca_position = self.dca_manager.positions[symbol]
                            if dca_position.is_active:
                                entry_price = dca_position.average_price
                                entry_amount = dca_position.total_amount_usdt if hasattr(dca_position, 'total_amount_usdt') else entry_amount
                        
                        if current_price and entry_price and entry_amount:
                            # 포지션 방향 고려한 수익률 계산
                            if quantity < 0:
                                position_side = 'short'
                            elif quantity > 0:
                                position_side = 'long'
                            
                            if position_side == 'short':
                                price_change_pct = ((entry_price - current_price) / entry_price) * 100
                            else:
                                price_change_pct = ((current_price - entry_price) / entry_price) * 100
                            
                            # 원금 기준 손익 계산
                            position_pnl = entry_amount * (price_change_pct / 100)
                            current_total_pnl += position_pnl
                    except:
                        continue
            
            # 일일집계가 비정상적으로 높으면 실시간 손익으로 대체
            if abs(stats['total_pnl']) > 50.0:  # $50 이상은 비정상
                print(f"   💵 일일집계 손익: ⚠️ \033[93m${stats['total_pnl']:+.2f} (비정상 - 리셋 필요)\033[0m")
                # 실시간 손익을 올바른 손익으로 표시
                if current_total_pnl >= 0:
                    correct_pnl_color = "\033[92m"
                    correct_pnl_emoji = "💚"
                else:
                    correct_pnl_color = "\033[91m"
                    correct_pnl_emoji = "💔"
                print(f"   💵 올바른 실시간 손익: {correct_pnl_emoji} {correct_pnl_color}${current_total_pnl:+.2f}\033[0m")
                
                # 비정상적인 일일 통계를 실시간 손익으로 자동 교정
                print(f"   🔄 일일통계 자동 교정 중...")
                self.today_stats['total_pnl'] = current_total_pnl
                self._save_daily_stats()  # 교정된 값 저장
                print(f"   ✅ 일일통계가 실시간 손익 ${current_total_pnl:+.2f}로 교정되었습니다")
            else:
                print(f"   💵 총 손익: {pnl_emoji} {pnl_color}${stats['total_pnl']:+.2f}\033[0m")
            
            # 💰 전체 시드 대비 수익률 계산 및 표시
            try:
                # 현재 잔고 조회
                balance = self.exchange.fetch_balance()
                current_usdt_balance = balance['USDT']['total'] if 'USDT' in balance else 0
                
                # 활성 포지션의 미실현 손익 계산
                unrealized_pnl = current_total_pnl  # 위에서 계산한 값 재사용
                
                # 총 자산 = 잔고 + 미실현 손익
                total_assets = current_usdt_balance + unrealized_pnl
                
                # 실제 거래 데이터에서 초기 시드 계산
                initial_seed = self._calculate_actual_seed(current_usdt_balance, unrealized_pnl)
                
                # 전체 수익률 계산
                total_return_pct = ((total_assets - initial_seed) / initial_seed * 100) if initial_seed > 0 else 0
                
                # 색상 설정
                if total_return_pct >= 0:
                    return_color = "\033[92m"  # 녹색
                    return_emoji = "📈"
                else:
                    return_color = "\033[91m"  # 빨간색
                    return_emoji = "📉"
                
                print(f"   💰 계좌정보: 잔고 ${current_usdt_balance:.2f} | 미실현 ${unrealized_pnl:+.2f} | 총자산 ${total_assets:.2f}")
                print(f"   {return_emoji} 전체 수익률: {return_color}{total_return_pct:+.2f}%\033[0m (시드: ${initial_seed:.2f})")
                
            except Exception as e:
                print(f"   ⚠️ 전체 수익률 계산 실패: {e}")
            
            # 상세 거래 내역 표시
            if 'trades_detail' in stats and stats['trades_detail']:
                profit_trades = []
                loss_trades = []
                
                for trade in stats['trades_detail']:
                    symbol = trade.get('symbol', 'Unknown').replace('/USDT:USDT', '').replace('/USDT', '')
                    profit_amount = trade.get('profit_amount', 0)
                    profit_pct = trade.get('profit_pct', 0)
                    max_roe_pct = trade.get('max_roe_pct', 0)
                    min_roe_pct = trade.get('min_roe_pct', 0)
                    leverage = 10.0  # 기본 레버리지
                    leverage_profit_pct = profit_pct * leverage  # 레버리지 수익률

                    if profit_amount >= 0:
                        profit_trades.append({
                            'symbol': symbol,
                            'amount': profit_amount,
                            'pct': profit_pct,
                            'leverage_pct': leverage_profit_pct,
                            'max_roe': max_roe_pct,
                            'min_roe': min_roe_pct
                        })
                    else:
                        loss_trades.append({
                            'symbol': symbol,
                            'amount': profit_amount,
                            'pct': profit_pct,
                            'leverage_pct': leverage_profit_pct,
                            'max_roe': max_roe_pct,
                            'min_roe': min_roe_pct
                        })

                # 수익 거래들 표시
                if profit_trades:
                    print(f"   ✅ 수익거래:")
                    for trade in profit_trades:
                        print(f"      {trade['symbol']}: {trade['leverage_pct']:+.2f}%({trade['pct']:+.2f}%) (+${trade['amount']:.2f}) [최고:{trade['max_roe']:+.2f}% / 최저:{trade['min_roe']:+.2f}%]")

                # 손실 거래들 표시
                if loss_trades:
                    print(f"   ❌ 손실거래:")
                    for trade in loss_trades:
                        print(f"      {trade['symbol']}: {trade['leverage_pct']:+.2f}%({trade['pct']:+.2f}%) (${trade['amount']:.2f}) [최고:{trade['max_roe']:+.2f}% / 최저:{trade['min_roe']:+.2f}%]")
            
            # DCA 통계 출력
            if hasattr(self, 'dca_stats') and self.dca_stats['total_entries'] > 0:
                dca_stats = self.dca_stats
                print(f"   🔄 DCA 진입: {dca_stats['total_entries']}회 (1차: {dca_stats['first_dca']}회, 2차: {dca_stats['second_dca']}회)")
            
            if hasattr(self, 'dca_exit_stats') and self.dca_exit_stats['total_exits'] > 0:
                dca_exit_stats = self.dca_exit_stats
                dca_exit_rate = (dca_exit_stats['profitable_exits'] / dca_exit_stats['total_exits']) * 100
                print(f"   🎯 DCA 청산: {dca_exit_stats['total_exits']}회 (수익청산: {dca_exit_stats['profitable_exits']}회, 성공률: {dca_exit_rate:.1f}%)")
            
                
        except Exception as e:
            print(f"[일일통계] ❌ 통계 출력 실패: {e}")

    def _get_trading_day(self):
        """한국시간 9시 기준 거래일 계산"""
        korea_now = get_korea_time()
        
        # 한국시간 9시 이전이면 전날로 계산
        if korea_now.hour < 9:
            trading_day = (korea_now - timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            trading_day = korea_now.strftime('%Y-%m-%d')
            
        return trading_day

    def _collect_entry_data(self, symbol, entry_price):
        """진입 시점 상세 데이터 수집 (Phase 1)"""
        try:
            # 1분봉 데이터 조회
            df_1m = self.get_ohlcv_data(symbol, '1m', limit=100)
            if df_1m is None or len(df_1m) == 0:
                return {}

            # 지표 계산
            df_1m = self.calculate_indicators(df_1m)
            if df_1m is None or len(df_1m) == 0:
                return {}

            latest = df_1m.iloc[-1]

            # 급등률 계산
            surge_rate = 0.0
            if len(df_1m) >= 2:
                prev_close = df_1m.iloc[-2]['close']
                if prev_close > 0:
                    surge_rate = ((latest['close'] - prev_close) / prev_close) * 100

            # 거래량 급증률 계산
            volume_surge = 0.0
            if len(df_1m) >= 20:
                recent_volume = latest['volume']
                avg_volume = df_1m.tail(20)['volume'].mean()
                if avg_volume > 0:
                    volume_surge = ((recent_volume - avg_volume) / avg_volume) * 100

            # Phase 1: 진입 조건 상세 데이터
            entry_data = {
                'surge_rate': round(surge_rate, 2),
                'volume_surge': round(volume_surge, 2),
                'ma5_at_entry': float(latest.get('ma5', 0)),
                'bb80_upper_at_entry': float(latest.get('bb80_upper', 0)),
                'bb480_upper_at_entry': float(latest.get('bb480_upper', 0)),
                'bb600_upper_at_entry': float(latest.get('bb600_upper', 0)),
                'rsi_at_entry': float(latest.get('rsi', 0)),
                'price_vs_ma5_pct': round(((latest['close'] - latest.get('ma5', latest['close'])) / latest.get('ma5', latest['close'])) * 100, 2) if latest.get('ma5', 0) > 0 else 0,
            }

            return entry_data

        except Exception as e:
            self.logger.error(f"진입 데이터 수집 실패: {e}")
            return {}

    def _collect_exit_data(self, symbol, exit_price, exit_reason):
        """청산 시점 상세 데이터 수집 (Phase 1)"""
        try:
            # 포지션 정보 가져오기
            if symbol not in self.position_stats:
                return {}

            position_stats = self.position_stats[symbol]
            position_info = self.active_positions.get(symbol, {})

            # 1분봉 데이터 조회 (청산 시점 지표)
            df_1m = self.get_ohlcv_data(symbol, '1m', limit=100)
            if df_1m is not None and len(df_1m) > 0:
                df_1m = self.calculate_indicators(df_1m)

            latest = df_1m.iloc[-1] if df_1m is not None and len(df_1m) > 0 else {}

            # 보유 시간 계산
            entry_time = position_stats.get('entry_time', get_korea_time())
            exit_time = get_korea_time()
            holding_duration = (exit_time - entry_time).total_seconds() / 60  # 분 단위

            # Phase 1: 청산 조건 상세 데이터
            exit_data = {
                'max_profit_pct': position_stats.get('max_profit_pct', 0.0),
                'holding_time_minutes': round(holding_duration, 1),
                'ma5_at_exit': float(latest.get('ma5', 0)),
                'bb80_upper_at_exit': float(latest.get('bb80_upper', 0)),
                'bb480_upper_at_exit': float(latest.get('bb480_upper', 0)),
                'bb600_upper_at_exit': float(latest.get('bb600_upper', 0)),
                'rsi_at_exit': float(latest.get('rsi', 0)),
                'exit_reason': exit_reason,
                'half_closed': position_stats.get('half_closed', False),
                'reached_10_percent': position_stats.get('reached_10_percent', False)
            }

            return exit_data

        except Exception as e:
            self.logger.error(f"청산 데이터 수집 실패: {e}")
            return {}

    def _reset_daily_stats(self, new_date):
        """일일 통계 리셋 (9시 기준 날짜 변경시)"""
        self.today_stats = {
            'date': new_date,
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0.0,
            'total_entry_amount': 0.0,  # 일일 사용된 총 원금 (Day ROE 계산용)
            'win_rate': 0.0,
            'trades_detail': []
        }

        # 📊 부분청산 누적 데이터도 초기화 (날짜가 바뀌면 리셋)
        # 주의: 활성 포지션이 있는 경우 데이터 손실 가능성 있음
        if hasattr(self, 'partial_exit_accumulator') and self.partial_exit_accumulator:
            self.logger.warning(f"📊 날짜 변경으로 부분청산 누적 데이터 초기화: {len(self.partial_exit_accumulator)}개 포지션")
            self.partial_exit_accumulator = {}

        self.logger.info(f"📊 일일통계 리셋: {new_date} (한국시간 9시 기준)")

    def _load_daily_stats(self):
        """일일 통계 파일 로드 (재시작 시 복원) - 계층적 구조"""
        try:
            import json
            import os
            from datetime import datetime

            # 통계 파일 저장 폴더 생성
            stats_dir = "trading_stats"
            if not os.path.exists(stats_dir):
                os.makedirs(stats_dir)
                self.logger.info(f"📁 통계 폴더 생성: {stats_dir}")

            # 현재 거래일 확인
            trading_day = self._get_trading_day()
            date_obj = datetime.strptime(trading_day, '%Y-%m-%d')
            year = date_obj.year
            month = date_obj.month

            # 연도/월 폴더 및 파일 경로
            year_dir = os.path.join(stats_dir, str(year))
            daily_file = os.path.join(year_dir, f"daily_{month:02d}.json")

            # 월간 파일이 존재하면 로드
            if os.path.exists(daily_file):
                with open(daily_file, 'r', encoding='utf-8') as f:
                    monthly_data = json.load(f)

                # 해당 날짜 데이터 추출
                day_data = monthly_data.get('days', {}).get(trading_day)

                if day_data:
                    self.today_stats['total_trades'] = day_data.get('total_trades', 0)
                    self.today_stats['wins'] = day_data.get('wins', 0)
                    self.today_stats['losses'] = day_data.get('losses', 0)
                    self.today_stats['total_pnl'] = day_data.get('total_pnl', 0.0)
                    self.today_stats['win_rate'] = day_data.get('win_rate', 0.0)
                    self.today_stats['trades_detail'] = day_data.get('trades', [])

                    self.logger.info(f"📊 통계 복원: 거래 {self.today_stats['total_trades']}회, "
                                   f"수익 {self.today_stats['wins']}회, 손실 {self.today_stats['losses']}회, "
                                   f"총 손익 ${self.today_stats['total_pnl']:.2f}")
                else:
                    self.logger.info(f"📊 {trading_day} 데이터 없음 (신규 시작)")
            else:
                self.logger.info(f"📊 월간 통계 파일 없음: {daily_file} (신규 시작)")

        except Exception as e:
            self.logger.error(f"📊 통계 로드 실패: {e}")

    def _sync_dca_with_daily_stats(self):
        """DCA 시스템의 완료된 거래를 daily_stats에 동기화"""
        try:
            if not hasattr(self, 'dca_manager') or not self.dca_manager:
                return

            # 오늘 완료된 DCA 거래 확인
            today_date = self._get_trading_day()
            completed_trades = []
            
            # DCA 포지션에서 완료된 거래 찾기
            for symbol, position in self.dca_manager.positions.items():
                if not position.is_active and hasattr(position, 'total_cyclic_profit'):
                    # 순환 수익이 있고 비활성 상태인 포지션
                    profit = position.total_cyclic_profit
                    
                    # 이미 daily_stats에 반영된 거래인지 확인
                    already_recorded = False
                    for trade in self.today_stats.get('trades_detail', []):
                        if (trade.get('symbol') == symbol.replace('/USDT:USDT', '') and 
                            abs(trade.get('profit_amount', 0) - profit) < 0.01):
                            already_recorded = True
                            break
                    
                    if not already_recorded and profit != 0:
                        completed_trades.append({
                            'symbol': symbol,
                            'profit': profit,
                            'position': position
                        })
            
            # 완료된 거래들을 daily_stats에 추가
            for trade in completed_trades:
                symbol = trade['symbol']
                profit = trade['profit']
                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                
                # daily_stats 업데이트
                self.today_stats['total_trades'] += 1
                self.today_stats['total_pnl'] += profit
                
                if profit > 0:
                    self.today_stats['wins'] += 1
                else:
                    self.today_stats['losses'] += 1
                
                # 승률 재계산
                total_trades = self.today_stats['total_trades']
                if total_trades > 0:
                    self.today_stats['win_rate'] = (self.today_stats['wins'] / total_trades) * 100
                
                # trades_detail에 추가
                if 'trades_detail' not in self.today_stats:
                    self.today_stats['trades_detail'] = []
                
                trade_detail = {
                    'symbol': clean_symbol,
                    'order_id': 'DCA_SYNC',
                    'entry_price': getattr(trade['position'], 'initial_entry_price', 0),
                    'exit_price': 0,  # DCA는 평균가 청산
                    'quantity': 0,
                    'profit_pct': 0,
                    'profit_amount': profit,
                    'timestamp': get_korea_time().isoformat(),
                    'trade_type': 'win' if profit > 0 else 'loss',
                    'entry_conditions': {'sync_type': 'DCA_completed'},
                    'exit_conditions': {'sync_type': 'DCA_completed'},
                    'position_management': {'dca_stage': 'completed'}
                }
                
                self.today_stats['trades_detail'].append(trade_detail)
                self.logger.info(f"📊 DCA 동기화: {clean_symbol} 거래 추가 (수익: ${profit:.2f})")
            
            if completed_trades:
                # 업데이트된 통계 저장
                self._save_daily_stats()
                
        except Exception as e:
            self.logger.error(f"DCA 동기화 실패: {e}")

    def _calculate_actual_seed(self, current_balance, unrealized_pnl):
        """실제 거래 데이터를 기반으로 초기 시드 계산 (수정된 로직)"""
        try:
            total_assets = current_balance + unrealized_pnl
            
            # 방법 1: 일일 통계에서 총 실현손익 확인
            daily_stats_file = 'daily_stats.json'
            try:
                with open(daily_stats_file, 'r', encoding='utf-8') as f:
                    daily_stats = json.load(f)
                    total_realized_pnl = daily_stats.get('total_pnl', 0.0)
            except (FileNotFoundError, json.JSONDecodeError):
                total_realized_pnl = 0.0
            
            # 방법 2: 거래가 없는 경우 현재 총자산을 시드로 사용
            if total_realized_pnl == 0.0 and unrealized_pnl == 0.0:
                # 거래 없음: 현재 잔고가 곧 초기 시드
                return total_assets
            
            # 방법 3: 거래가 있는 경우 역산
            # 올바른 공식: 초기시드 + 실현손익 = 현재 잔고
            # 따라서: 초기시드 = 현재 잔고 - 실현손익
            # (미실현손익은 아직 확정되지 않은 손익이므로 시드 계산에서 제외)
            calculated_seed = current_balance - total_realized_pnl
            
            # 합리적인 범위 검증 (최소 $30, 최대 $200)
            min_seed = 30.0
            max_seed = 200.0
            
            # 범위 내로 조정
            if calculated_seed < min_seed:
                calculated_seed = min_seed
            elif calculated_seed > max_seed:
                calculated_seed = max_seed
            
            return calculated_seed
            
        except Exception as e:
            print(f"   ⚠️ 시드 계산 실패: {e}")
            # 기본값: 현재 총자산을 시드로 사용 (0% 수익률)
            return current_balance + unrealized_pnl

    def _save_daily_stats(self):
        """일일 통계 파일 저장 - 계층적 구조"""
        try:
            import json
            import os
            from datetime import datetime

            # 통계 파일 저장 폴더 확인
            stats_dir = "trading_stats"
            if not os.path.exists(stats_dir):
                os.makedirs(stats_dir)

            # 현재 거래일 확인
            trading_day = self._get_trading_day()
            date_obj = datetime.strptime(trading_day, '%Y-%m-%d')
            year = date_obj.year
            month = date_obj.month

            # 연도 폴더 생성
            year_dir = os.path.join(stats_dir, str(year))
            if not os.path.exists(year_dir):
                os.makedirs(year_dir)

            # 월간 파일 경로
            daily_file = os.path.join(year_dir, f"daily_{month:02d}.json")

            # 기존 월간 데이터 로드 (없으면 새로 생성)
            if os.path.exists(daily_file):
                with open(daily_file, 'r', encoding='utf-8') as f:
                    monthly_data = json.load(f)
            else:
                monthly_data = {
                    'year': year,
                    'month': month,
                    'days': {},
                    'summary': {}
                }

            # 오늘 날짜 데이터 업데이트
            monthly_data['days'][trading_day] = {
                'total_trades': self.today_stats['total_trades'],
                'wins': self.today_stats['wins'],
                'losses': self.today_stats['losses'],
                'total_pnl': self.today_stats['total_pnl'],
                'win_rate': self.today_stats['win_rate'],
                'trades': self.today_stats.get('trades_detail', []),
                'last_updated': get_korea_time().isoformat()
            }

            # 월간 요약 재계산
            days = monthly_data['days']
            month_total_trades = sum(day['total_trades'] for day in days.values())
            month_wins = sum(day['wins'] for day in days.values())
            month_losses = sum(day['losses'] for day in days.values())
            month_pnl = sum(day['total_pnl'] for day in days.values())
            month_win_rate = (month_wins / month_total_trades * 100) if month_total_trades > 0 else 0

            # 최고/최악의 날
            best_day = max(days.items(), key=lambda x: x[1]['total_pnl']) if days else None
            worst_day = min(days.items(), key=lambda x: x[1]['total_pnl']) if days else None

            monthly_data['summary'] = {
                'total_trades': month_total_trades,
                'wins': month_wins,
                'losses': month_losses,
                'total_pnl': month_pnl,
                'win_rate': month_win_rate,
                'best_day': best_day[0] if best_day else None,
                'best_day_pnl': best_day[1]['total_pnl'] if best_day else 0,
                'worst_day': worst_day[0] if worst_day else None,
                'worst_day_pnl': worst_day[1]['total_pnl'] if worst_day else 0
            }

            # 월간 파일 저장
            with open(daily_file, 'w', encoding='utf-8') as f:
                json.dump(monthly_data, f, ensure_ascii=False, indent=2)

            self.logger.debug(f"📊 통계 저장 완료: {daily_file}")

        except Exception as e:
            self.logger.error(f"📊 통계 저장 실패: {e}")

    def sync_positions_with_exchange(self, quiet=False):
        """
        바이낸스 계좌와 활성 포지션 동기화 - 강화된 검증 시스템

        Args:
            quiet: True이면 변경사항 있을 때만 출력 (기본: False)
        """
        try:
            # 필수 속성 초기화 확인 (안전장치)
            if not hasattr(self, 'active_positions'):
                self.active_positions = {}
            if not hasattr(self, 'position_stats'):
                self.position_stats = {}

            if not hasattr(self.exchange, 'apiKey') or not self.exchange.apiKey:
                print(f"[포지션동기화] 🔓 API 키 없음 - 스캔 전용 모드")
                return

            # 포지션 동기화 시작 (조용한 모드)
            
            # === 동기화 통계 초기화 ===
            sync_stats = {
                'total_exchange_positions': 0,
                'synced_positions': 0,
                'new_positions': 0,
                'updated_positions': 0,
                'removed_positions': 0,
                'price_corrections': 0,
                'dca_corrections': 0,
                'quantity_corrections': 0,
                'side_corrections': 0,
                'validation_errors': 0,
                'sync_duration': 0
            }
            
            # 동기화 시작 시간 기록
            sync_start_time = time.time()
            
            # === 1단계: 거래소 포지션 조회 ===
            # Rate Limit 상태 체크 및 대안 처리
            if hasattr(self, '_api_rate_limited') and self._api_rate_limited:
                print(f"[포지션동기화] 🚨 Rate limit 상태 - 기존 포지션 정보로 동기화")
                
                # Rate Limit 상태에서도 기존 포지션 정보는 유지
                if hasattr(self, 'active_positions') and self.active_positions:
                    position_count = len(self.active_positions)
                    print(f"📊 [계좌포지션] 보유중: {position_count}개 (Rate Limit으로 인한 캐시 정보)")
                    
                    # 기존 포지션 표시
                    for symbol, position in self.active_positions.items():
                        clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                        entry_price = position.get('entry_price', 0)
                        print(f"   🔹 {clean_symbol}: ${entry_price:.6f} (캐시)")
                else:
                    print(f"📊 [계좌포지션] 보유중: 없음 (Rate Limit 상태)")
                
                # DCA 시스템 포지션 정보도 표시
                if self.dca_manager and hasattr(self.dca_manager, 'positions'):
                    dca_count = len([p for p in self.dca_manager.positions.values() if p.is_active])
                    print(f"📊 [DCA포지션] 활성: {dca_count}개")
                    
                    for symbol, position in self.dca_manager.positions.items():
                        if position.is_active:
                            print(f"   🔸 {symbol}: ${position.average_price:.6f} (DCA)")
                
                # 포지션 불일치 경고
                local_count = len(self.active_positions) if hasattr(self, 'active_positions') else 0
                dca_count = len([p for p in self.dca_manager.positions.values() if p.is_active]) if self.dca_manager else 0
                
                if local_count != dca_count:
                    print(f"⚠️ [포지션 불일치] 로컬: {local_count}개, DCA: {dca_count}개")
                    print(f"   Rate Limit으로 인해 거래소 동기화가 불가능한 상태입니다.")
                    print(f"   시스템 복구 후 수동으로 포지션을 확인해주세요.")
                
                return  # API 호출 없이 종료
                
            # 포지션 조회 시도 (Rate Limit 대응)
            try:
                positions = self.exchange.fetch_positions()
                # 포지션이 있을 때만 진행 상황 출력
                if any(pos['contracts'] > 0 for pos in positions):
                    print(f"[포지션동기화] 📥 1단계: 거래소 포지션 조회 중...")
                    print(f"[포지션동기화] 📊 거래소로부터 {len(positions)}개 포지션 데이터 수신")
            except Exception as e:
                # API 에러 처리 (Rate Limit 감지 포함)
                error_str = str(e).lower()
                if ("418" in str(e) or "429" in str(e) or 
                    "too many requests" in error_str or "rate limit" in error_str):
                    print(f"[포지션동기화] 🚨 Rate Limit 감지 - API 호출 차단: {e}")
                    self._api_rate_limited = True
                    self._last_rate_limit_check = time.time()
                    
                    # Rate Limit 상황에서 기존 포지션 정보 표시
                    if hasattr(self, 'active_positions') and self.active_positions:
                        position_count = len(self.active_positions)
                        print(f"📊 [계좌포지션] 보유중: {position_count}개 (API 에러로 인한 캐시 정보)")
                        for symbol, position in self.active_positions.items():
                            clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                            entry_price = position.get('entry_price', 0)
                            print(f"   🔹 {clean_symbol}: ${entry_price:.6f} (캐시)")
                    else:
                        print(f"📊 [계좌포지션] 보유중: 없음 (API 에러)")
                    return
                else:
                    self.logger.error(f"포지션 조회 실패: {e}")
                    return
            
            # 실제 포지션만 필터링
            active_exchange_positions = {}
            position_validation_report = []
            
            for position in positions:
                if position['contracts'] > 0:  # 실제 포지션이 있는 경우
                    sync_stats['total_exchange_positions'] += 1
                    symbol = position['symbol']
                    
                    # USDT 선물만 처리
                    if symbol.endswith('/USDT:USDT'):
                        validation_result = self._validate_position_data(symbol, position)
                        position_validation_report.append(validation_result)
                        
                        if validation_result['valid']:
                            active_exchange_positions[symbol] = validation_result['position_data']
                        else:
                            sync_stats['validation_errors'] += 1
                            print(f"[포지션동기화] ❌ {symbol} 검증 실패: {validation_result['error']}")
            
            # === 2단계: DCA 시스템과의 동기화 검증 ===
            dca_sync_report = self._sync_with_dca_system(active_exchange_positions, sync_stats)
            
            # === 3단계: 로컬 포지션과의 상세 비교 ===
            local_sync_report = self._detailed_local_sync(active_exchange_positions, sync_stats)
            
            # === 4단계: 수익률 계산 및 검증 ===
            profit_validation_report = self._validate_profit_calculations(active_exchange_positions)
            
            # === 5단계: 포지션 상태 업데이트 ===
            self._update_position_states(active_exchange_positions, sync_stats)
            
            # === 6단계: 누락 포지션 처리 ===
            missing_positions_report = self._handle_missing_positions(active_exchange_positions, sync_stats)
            
            # === 7단계: 제거된 포지션 처리 ===
            removed_positions_report = self._handle_removed_positions(active_exchange_positions, sync_stats)
            
            # 동기화 소요 시간 계산
            sync_stats['sync_duration'] = time.time() - sync_start_time
            
            # === 최종 동기화 보고서 생성 ===
            self._generate_sync_summary_report(sync_stats, {
                'position_validation': position_validation_report,
                'dca_sync': dca_sync_report,
                'local_sync': local_sync_report,
                'profit_validation': profit_validation_report,
                'missing_positions': missing_positions_report,
                'removed_positions': removed_positions_report
            }, quiet=quiet)
            
        except Exception as e:
            print(f"[포지션동기화] ❌ 동기화 실패: {e}")
            import traceback
            print(f"[포지션동기화] 🔍 오류 상세: {traceback.format_exc()}")

    def _validate_position_data(self, symbol, position):
        """포지션 데이터 검증 및 정규화"""
        try:
            # 필수 필드 검증
            required_fields = ['entryPrice', 'contracts', 'side', 'timestamp']
            for field in required_fields:
                if field not in position or position[field] is None:
                    return {
                        'valid': False,
                        'error': f'필수 필드 누락: {field}',
                        'symbol': symbol
                    }
            
            # 데이터 정규화
            exchange_entry_price = float(position['entryPrice'])
            quantity = abs(float(position['contracts']))
            leverage = position.get('leverage') or self.leverage or 10
            position_side = position.get('side', 'long').lower()
            
            # 데이터 유효성 검증
            if exchange_entry_price <= 0:
                return {'valid': False, 'error': '진입가 유효하지 않음', 'symbol': symbol}
            if quantity <= 0:
                return {'valid': False, 'error': '수량 유효하지 않음', 'symbol': symbol}
            if leverage <= 0:
                leverage = 10  # 기본값 설정
            
            # 포지션 가치 계산
            position_value = quantity * exchange_entry_price
            entry_amount = position_value / leverage

            # 🚫 최소 투자금 필터: $0.01 미만 포지션 제외 (부분청산 후 잔여 포지션도 모니터링)
            if entry_amount < 0.01:
                return {
                    'valid': False,
                    'error': f'투자금 너무 작음 (${entry_amount:.2f} < $0.01)',
                    'symbol': symbol
                }

            # 현재가 조회
            current_price = self.get_current_price(symbol)
            if current_price is None:
                current_price = exchange_entry_price
            
            # 수익률 계산 (방향 고려)
            if position_side == 'long':
                profit_pct = (current_price - exchange_entry_price) / exchange_entry_price * 100
            else:
                profit_pct = (exchange_entry_price - current_price) / exchange_entry_price * 100
            
            # 검증된 포지션 데이터 반환
            position_data = {
                'entry_price': exchange_entry_price,
                'quantity': quantity if position_side == 'long' else -quantity,
                'side': position_side,
                'leverage': leverage,
                'entry_amount': entry_amount,
                'position_value': position_value,
                'current_price': current_price,
                'profit_pct': profit_pct,
                'timestamp': position['timestamp'],
                'validation_time': time.time()
            }
            
            # 개별 심볼 포지션 검증 완료 메시지 삭제 (과거 메시지)
            # print(f"[포지션검증] ✅ {symbol.replace('/USDT:USDT', '')} 검증 완료")
            # print(f"   진입가: ${exchange_entry_price:.4f} | 현재가: ${current_price:.4f} | 수익률: {profit_pct:.2f}%")
            # print(f"   수량: {quantity:.4f} | 방향: {position_side} | 레버리지: {leverage}x")
            
            return {
                'valid': True,
                'position_data': position_data,
                'symbol': symbol
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f'검증 중 오류: {str(e)}',
                'symbol': symbol
            }

    def _sync_with_dca_system(self, active_exchange_positions, sync_stats):
        """DCA 시스템과의 동기화 검증"""
        dca_sync_report = []
        
        if not self.dca_manager:
            # DCA 시스템이 비활성화된 경우 조용히 반환 (스팸 방지)
            return dca_sync_report
        
        # DCA 시스템 동기화 검증 시작 (조용한 모드)
        
        for symbol, position_data in active_exchange_positions.items():
            dca_status = {
                'symbol': symbol,
                'has_dca_position': False,
                'price_synced': False,
                'quantity_synced': False,
                'dca_corrections_made': []
            }
            
            if symbol in self.dca_manager.positions:
                dca_position = self.dca_manager.positions[symbol]
                dca_status['has_dca_position'] = True
                
                if dca_position.is_active:
                    # 평균가 동기화 검증
                    exchange_price = position_data['entry_price']
                    dca_avg_price = dca_position.average_price
                    price_diff_pct = abs(exchange_price - dca_avg_price) / exchange_price * 100
                    
                    if price_diff_pct > 0.05:  # 0.05% 이상 차이
                        print(f"[DCA동기화] ⚠️ {symbol.replace('/USDT:USDT', '')} 평균가 차이 감지:")
                        print(f"   거래소: ${exchange_price:.6f} | DCA: ${dca_avg_price:.6f} (차이: {price_diff_pct:.2f}%)")
                        
                        # DCA 평균가 교정
                        old_price = dca_position.average_price
                        dca_position.average_price = exchange_price
                        
                        correction_info = {
                            'type': 'price_correction',
                            'old_value': old_price,
                            'new_value': exchange_price,
                            'difference_pct': price_diff_pct
                        }
                        dca_status['dca_corrections_made'].append(correction_info)
                        sync_stats['price_corrections'] += 1
                        sync_stats['dca_corrections'] += 1
                        
                        print(f"[DCA동기화] 🎯 {symbol.replace('/USDT:USDT', '')} 평균가 교정 완료: ${exchange_price:.6f}")
                    else:
                        dca_status['price_synced'] = True
                        # 변경사항이 없으면 로그 출력하지 않음
                        self.logger.debug(f"[DCA동기화] ✅ {symbol.replace('/USDT:USDT', '')} 평균가 동기화됨: ${exchange_price:.6f}")
                    
                    # 수량 동기화 검증
                    if hasattr(dca_position, 'total_quantity'):
                        exchange_quantity = abs(position_data['quantity'])
                        dca_quantity = dca_position.total_quantity
                        quantity_diff_pct = abs(exchange_quantity - dca_quantity) / exchange_quantity * 100 if exchange_quantity > 0 else 0
                        
                        if quantity_diff_pct > 1.0:  # 1% 이상 차이
                            print(f"[DCA동기화] ⚠️ {symbol.replace('/USDT:USDT', '')} 수량 차이:")
                            print(f"   거래소: {exchange_quantity:.4f} | DCA: {dca_quantity:.4f} (차이: {quantity_diff_pct:.2f}%)")
                            
                            old_quantity = dca_position.total_quantity
                            dca_position.total_quantity = exchange_quantity
                            
                            correction_info = {
                                'type': 'quantity_correction',
                                'old_value': old_quantity,
                                'new_value': exchange_quantity,
                                'difference_pct': quantity_diff_pct
                            }
                            dca_status['dca_corrections_made'].append(correction_info)
                            sync_stats['quantity_corrections'] += 1
                            
                            print(f"[DCA동기화] 🔄 {symbol.replace('/USDT:USDT', '')} 수량 교정 완료")
                        else:
                            dca_status['quantity_synced'] = True
                            # DCA 수량을 거래소에 적용
                            position_data['quantity'] = dca_quantity if position_data['side'] == 'long' else -dca_quantity
                    
                    # DCA 관리 플래그 설정
                    position_data['dca_managed'] = True
                    position_data['dca_average_price'] = dca_position.average_price
                    position_data['dca_total_quantity'] = getattr(dca_position, 'total_quantity', abs(position_data['quantity']))
                    
            else:
                # DCA로 관리되지 않는 포지션은 debug 로그로만 출력
                self.logger.debug(f"[DCA동기화] ℹ️ {symbol.replace('/USDT:USDT', '')} DCA 시스템에서 관리되지 않음")
                position_data['dca_managed'] = False
            
            dca_sync_report.append(dca_status)
        
        return dca_sync_report

    def _detailed_local_sync(self, active_exchange_positions, sync_stats):
        """로컬 포지션과의 상세 비교"""
        local_sync_report = []
        
        self.logger.debug(f"[로컬동기화] 🔍 거래소 {len(active_exchange_positions)}개 vs 로컬 {len(self.active_positions)}개 포지션 비교")
        
        for symbol, exchange_pos in active_exchange_positions.items():
            sync_details = {
                'symbol': symbol,
                'status': 'unknown',
                'differences': [],
                'corrections_made': []
            }
            
            if symbol in self.active_positions:
                local_pos = self.active_positions[symbol]
                
                # 상세 비교 항목들
                comparisons = [
                    ('entry_price', 'entry_price', 0.05),  # 0.05% 허용 오차
                    ('quantity', 'quantity', 1.0),         # 1% 허용 오차
                    ('side', 'side', 0),                   # 정확히 일치해야 함
                    ('leverage', 'leverage', 0.1)          # 0.1 허용 오차
                ]
                
                for field, local_field, tolerance in comparisons:
                    exchange_val = exchange_pos.get(field, 0)
                    local_val = local_pos.get(local_field, 0)
                    
                    if field in ['entry_price', 'quantity', 'leverage']:
                        if abs(exchange_val) > 0:
                            diff_pct = abs(exchange_val - local_val) / abs(exchange_val) * 100
                            if diff_pct > tolerance:
                                sync_details['differences'].append({
                                    'field': field,
                                    'exchange_value': exchange_val,
                                    'local_value': local_val,
                                    'difference_pct': diff_pct
                                })
                    elif field == 'side':
                        if exchange_val != local_val:
                            sync_details['differences'].append({
                                'field': field,
                                'exchange_value': exchange_val,
                                'local_value': local_val,
                                'difference_pct': 0
                            })
                
                # 차이점이 있으면 업데이트
                if sync_details['differences']:
                    sync_details['status'] = 'updated'
                    sync_stats['updated_positions'] += 1
                    
                    # 로컬 포지션 업데이트
                    for diff in sync_details['differences']:
                        field = diff['field']
                        local_field = field  # 동일한 필드명 사용
                        old_value = self.active_positions[symbol].get(local_field)
                        new_value = exchange_pos[field]
                        
                        self.active_positions[symbol][local_field] = new_value
                        sync_details['corrections_made'].append({
                            'field': field,
                            'old_value': old_value,
                            'new_value': new_value
                        })
                    
                    print(f"[로컬동기화] 🔄 {symbol.replace('/USDT:USDT', '')} 업데이트: {len(sync_details['differences'])}개 차이점 수정")
                else:
                    sync_details['status'] = 'synced'
                    sync_stats['synced_positions'] += 1
                    # 변경사항이 없으면 로그 출력하지 않음
                    self.logger.debug(f"[로컬동기화] ✅ {symbol.replace('/USDT:USDT', '')} 이미 동기화됨")
                    
            else:
                sync_details['status'] = 'new'
                sync_stats['new_positions'] += 1
                self.logger.debug(f"[로컬동기화] 🆕 {symbol.replace('/USDT:USDT', '')} 신규 포지션 발견")
            
            local_sync_report.append(sync_details)
        
        return local_sync_report

    def _validate_profit_calculations(self, active_exchange_positions):
        """수익률 계산 검증"""
        profit_validation_report = []
        
        self.logger.debug(f"[수익률검증] 💰 {len(active_exchange_positions)}개 포지션 수익률 계산 검증...")
        
        for symbol, position_data in active_exchange_positions.items():
            validation_result = {
                'symbol': symbol,
                'valid': True,
                'calculated_profit_pct': 0,
                'position_side': position_data['side'],
                'errors': []
            }
            
            try:
                entry_price = position_data['entry_price']
                current_price = position_data['current_price']
                side = position_data['side']
                quantity = position_data['quantity']
                
                # 방향별 수익률 계산
                if side == 'long':
                    profit_pct = (current_price - entry_price) / entry_price * 100
                elif side == 'short':
                    profit_pct = (entry_price - current_price) / entry_price * 100
                else:
                    validation_result['valid'] = False
                    validation_result['errors'].append(f"알 수 없는 포지션 방향: {side}")
                    profit_pct = 0
                
                validation_result['calculated_profit_pct'] = profit_pct
                
                # 포지션 데이터에 수익률 업데이트
                position_data['profit_pct'] = profit_pct
                
                # 수익률 검증 로그
                symbol_name = symbol.replace('/USDT:USDT', '')
                self.logger.debug(f"[수익률검증] 📊 {symbol_name} ({side}): {profit_pct:.2f}%")
                self.logger.debug(f"   진입가: ${entry_price:.4f} | 현재가: ${current_price:.4f}")
                
                # position_stats에도 업데이트
                if symbol in self.position_stats:
                    self.position_stats[symbol]['current_profit_pct'] = profit_pct

                    # 최대 수익률 업데이트
                    if profit_pct > self.position_stats[symbol].get('max_profit_pct', 0):
                        self.position_stats[symbol]['max_profit_pct'] = profit_pct

                    # 최저 수익률 업데이트
                    if profit_pct < self.position_stats[symbol].get('min_profit_pct', 0):
                        self.position_stats[symbol]['min_profit_pct'] = profit_pct
                
            except Exception as e:
                validation_result['valid'] = False
                validation_result['errors'].append(f"수익률 계산 오류: {str(e)}")
                self.logger.debug(f"[수익률검증] ❌ {symbol.replace('/USDT:USDT', '')} 수익률 계산 실패: {e}")
            
            profit_validation_report.append(validation_result)
        
        return profit_validation_report

    def _update_position_states(self, active_exchange_positions, sync_stats):
        """포지션 상태 업데이트"""
        # 실제 업데이트할 포지션이 있을 때만 메시지 출력
        if active_exchange_positions:
            print(f"[상태업데이트] 🔄 포지션 상태 업데이트 중...")
        
        for symbol, position_data in active_exchange_positions.items():
            # active_positions 업데이트
            self.active_positions[symbol] = position_data
            
            # position_stats 업데이트 또는 초기화
            if symbol not in self.position_stats:
                try:
                    entry_data = self._collect_entry_data(symbol, position_data['entry_price'])
                except:
                    entry_data = {}
                
                self.position_stats[symbol] = {
                    'max_profit_pct': max(0.0, position_data.get('profit_pct', 0.0)),
                    'min_profit_pct': min(0.0, position_data.get('profit_pct', 0.0)),
                    'current_profit_pct': position_data.get('profit_pct', 0.0),
                    'half_closed': False,
                    'reached_10_percent': False,
                    'ten_percent_half_exit_count': 0,
                    'five_percent_exit_done': False,
                    'ten_percent_exit_done': False,
                    'bb600_exit_done': False,  # BB600 돌파 절반청산 완료 여부 (1회만)
                    'technical_exit_attempted': False,
                    'entry_time': get_korea_time(),
                    'entry_data': entry_data,
                    'sync_created': True  # 동기화로 생성된 포지션 표시
                }
            else:
                # 기존 stats 업데이트
                current_profit = position_data.get('profit_pct', 0.0)
                self.position_stats[symbol]['current_profit_pct'] = current_profit

                # 최대 수익률 업데이트
                if current_profit > self.position_stats[symbol].get('max_profit_pct', 0):
                    self.position_stats[symbol]['max_profit_pct'] = current_profit

                # 최저 수익률 업데이트
                if current_profit < self.position_stats[symbol].get('min_profit_pct', 0):
                    self.position_stats[symbol]['min_profit_pct'] = current_profit

    def _handle_missing_positions(self, active_exchange_positions, sync_stats):
        """누락된 포지션 처리"""
        missing_positions_report = []
        
        missing_positions = []
        for symbol in active_exchange_positions:
            if symbol not in self.active_positions:
                missing_positions.append(symbol)
        
        if missing_positions:
            print(f"[누락포지션] ⚠️ {len(missing_positions)}개 누락 포지션 발견:")
            for symbol in missing_positions:
                symbol_name = symbol.replace('/USDT:USDT', '')
                position_data = active_exchange_positions[symbol]
                
                print(f"   🆕 {symbol_name}: ${position_data['entry_price']:.4f}, "
                      f"{position_data['side']}, {abs(position_data['quantity']):.4f}")
                
                missing_positions_report.append({
                    'symbol': symbol,
                    'action': 'added',
                    'position_data': position_data
                })
            
            sync_stats['new_positions'] = len(missing_positions)
            print(f"[누락포지션] ✅ {len(missing_positions)}개 포지션 동기화 완료")
        # 누락된 포지션이 없을 때는 메시지 출력하지 않음
        
        return missing_positions_report

    def _handle_removed_positions(self, active_exchange_positions, sync_stats):
        """제거된 포지션 처리"""
        removed_positions_report = []
        
        # 로컬에는 있지만 거래소에는 없는 포지션들
        positions_to_remove = []
        for symbol in list(self.active_positions.keys()):
            if symbol not in active_exchange_positions:
                positions_to_remove.append(symbol)
        
        if positions_to_remove:
            print(f"[제거포지션] 🗑️ {len(positions_to_remove)}개 포지션 제거 필요:")
            for symbol in positions_to_remove:
                symbol_name = symbol.replace('/USDT:USDT', '')
                position_data = self.active_positions[symbol]
                
                print(f"   🗑️ {symbol_name}: ${position_data.get('entry_price', 0):.4f}, "
                      f"{position_data.get('side', 'unknown')}")
                
                # active_positions에서 제거
                del self.active_positions[symbol]
                
                # position_stats에서도 제거
                if symbol in self.position_stats:
                    del self.position_stats[symbol]
                
                removed_positions_report.append({
                    'symbol': symbol,
                    'action': 'removed',
                    'reason': 'not_found_on_exchange'
                })
            
            sync_stats['removed_positions'] = len(positions_to_remove)
            print(f"[제거포지션] ✅ {len(positions_to_remove)}개 포지션 정리 완료")
        # 제거할 포지션이 없을 때는 메시지 출력하지 않음
        
        return removed_positions_report

    def _generate_sync_summary_report(self, sync_stats, detailed_reports, quiet=False):
        """
        포괄적 동기화 요약 보고서 생성 (변경사항 있을 때만)

        Args:
            sync_stats: 동기화 통계
            detailed_reports: 상세 보고서
            quiet: True이면 중요 변경사항만 출력
        """
        # 변경사항이 있는지 확인
        has_changes = (
            sync_stats['total_exchange_positions'] > 0 or
            sync_stats['new_positions'] > 0 or
            sync_stats['updated_positions'] > 0 or
            sync_stats['removed_positions'] > 0 or
            sync_stats['price_corrections'] > 0 or
            sync_stats['dca_corrections'] > 0 or
            sync_stats['quantity_corrections'] > 0 or
            sync_stats['side_corrections'] > 0
        )

        # quiet 모드: 중요 변경사항(신규/제거)만 출력
        if quiet:
            if sync_stats['new_positions'] > 0 or sync_stats['removed_positions'] > 0:
                print(f"📊 포지션 변경: +{sync_stats['new_positions']}개, -{sync_stats['removed_positions']}개")
            return

        # 변경사항이 있을 때만 상세 보고서 출력
        if has_changes:
            print(f"\n{'='*60}")
            print(f"🔄 포지션 동기화 완료 보고서")
            print(f"{'='*60}")
            
            # 기본 통계
            print(f"📊 동기화 통계:")
            print(f"   ⏱️ 소요 시간: {sync_stats['sync_duration']:.2f}초")
            print(f"   📥 거래소 포지션: {sync_stats['total_exchange_positions']}개")
            print(f"   ✅ 동기화된 포지션: {sync_stats['synced_positions']}개")
            print(f"   🆕 신규 포지션: {sync_stats['new_positions']}개")
            print(f"   🔄 업데이트된 포지션: {sync_stats['updated_positions']}개")
            print(f"   🗑️ 제거된 포지션: {sync_stats['removed_positions']}개")
        
        # 교정 통계
        if any([sync_stats['price_corrections'], sync_stats['dca_corrections'], 
                sync_stats['quantity_corrections'], sync_stats['side_corrections']]):
            print(f"\n🔧 교정 통계:")
            if sync_stats['price_corrections'] > 0:
                print(f"   💰 가격 교정: {sync_stats['price_corrections']}건")
            if sync_stats['dca_corrections'] > 0:
                print(f"   🔧 DCA 시스템 교정: {sync_stats['dca_corrections']}건")
            if sync_stats['quantity_corrections'] > 0:
                print(f"   📊 수량 교정: {sync_stats['quantity_corrections']}건")
            if sync_stats['side_corrections'] > 0:
                print(f"   🔄 방향 교정: {sync_stats['side_corrections']}건")
        
        # 현재 포지션 요약 (로그 파일에만 기록)
        if self.active_positions:
            total_position_value = 0
            total_profit_amount = 0
            
            for symbol, position in self.active_positions.items():
                symbol_name = symbol.replace('/USDT:USDT', '')
                entry_price = position.get('entry_price', 0)
                current_price = position.get('current_price', entry_price)
                quantity = abs(position.get('quantity', 0))
                side = position.get('side', 'unknown')
                profit_pct = position.get('profit_pct', 0)
                leverage = position.get('leverage', 10)
                
                position_value = quantity * current_price / leverage
                profit_amount = position_value * (profit_pct / 100)
                
                total_position_value += position_value
                total_profit_amount += profit_amount
                
                side_emoji = "🟢" if side == "long" else "🔴" if side == "short" else "⚪"
                profit_emoji = "📈" if profit_pct > 0 else "📉" if profit_pct < 0 else "➖"
                
                self.logger.debug(f"   {side_emoji} {symbol_name:12} | "
                      f"${entry_price:8.4f} → ${current_price:8.4f} | "
                      f"{profit_emoji} {profit_pct:6.2f}% | "
                      f"{quantity:8.4f} | {leverage:2.0f}x")
            
            # 전체 포지션 요약
            total_profit_pct = (total_profit_amount / total_position_value * 100) if total_position_value > 0 else 0
            self.logger.debug(f"💼 포트폴리오 요약:")
            self.logger.debug(f"   💰 총 포지션 가치: ${total_position_value:.2f}")
            self.logger.debug(f"   📊 총 수익금액: ${total_profit_amount:.2f}")
            self.logger.debug(f"   📈 전체 수익률: {total_profit_pct:.2f}%")
        else:
            pass
        
        # DCA 시스템 상태
        if detailed_reports['dca_sync']:
            dca_managed_count = sum(1 for report in detailed_reports['dca_sync'] if report['has_dca_position'])
            if dca_managed_count > 0:
                print(f"\n🔧 DCA 시스템 상태:")
                print(f"   📊 DCA 관리 포지션: {dca_managed_count}개")
                
                for report in detailed_reports['dca_sync']:
                    if report['has_dca_position'] and report['dca_corrections_made']:
                        symbol_name = report['symbol'].replace('/USDT:USDT', '')
                        corrections = len(report['dca_corrections_made'])
                        print(f"   🔧 {symbol_name}: {corrections}건 교정")
        
            # 오류 및 경고
            if sync_stats['validation_errors'] > 0:
                print(f"\n⚠️ 검증 오류: {sync_stats['validation_errors']}건")
            
            print(f"{'='*60}")
            print(f"✅ 포지션 동기화 완료 - {get_korea_time().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}\n")
        # 변경사항이 없으면 아무것도 출력하지 않음

    def _apply_integrated_filtering(self, candidate_symbols):
        """⚡ 통합 필터링 로직: Top200 추출 → 15m 로드 → Surge 필터링 (가변 결과)"""
        try:
            print(f"🚀 통합 필터링 (Top200 → 15m Surge): {len(candidate_symbols)}개 심볼")

            # 1단계: 상승률 상위 100위권 추출 (IP 밴 방지를 위해 축소!)
            print("📊 1단계: 상승률 상위 100위권 추출 (IP 밴 방지)")
            candidate_symbols.sort(key=lambda x: x[1], reverse=True)
            top100_filtered = candidate_symbols[:100] if len(candidate_symbols) >= 100 else candidate_symbols
            top100_count = len(top100_filtered)
            print(f"✅ Top100 추출 완료: {top100_count}개 심볼 (안전 최우선)")

            if not top100_filtered:
                print("⚠️ Top100 추출 실패")
                return []

            # ⚡ 최적화: Stage 2-4 제거 (15m 데이터는 WebSocket 실시간 구독으로 자동 수집)
            # - Stage 2: 불필요한 load_history=True REST API 호출 제거 (100 symbols × 0.5-2s = 0.8-3.3분)
            # - Stage 3: 항상 0개 반환하는 15m Surge 필터 제거
            # - Stage 4: 불필요한 결과 조합 로직 제거 (top100_filtered를 그대로 반환하므로 의미 없음)
            print("ℹ️ 15m 데이터는 WebSocket 구독으로 실시간 수집됩니다 (즉시 반환)")

            return top100_filtered
            
        except Exception as e:
            print(f"⚠️ 통합 필터링 오류: {e}")
            import traceback
            print(f"🔍 DEBUG: 오류 스택: {traceback.format_exc()}")
            
            # 폴백으로 상위 100위권만 반환
            print("🔄 폴백으로 상위 100위권만 반환")
            return self._get_top100_symbols(candidate_symbols)

    def _apply_4h_filtering(self, candidate_symbols):
        """⚡ 최적화된 4시간봉 급등 필터링 - 0봉만 처리 + 기존 심볼 재사용

        최적화 전략:
        - 첫 실행: 전체 4봉 검사하여 캐시 구축
        - 이후 실행: 0봉(최신 캔들)만 검사 + 기존 통과 심볼 재사용
        - 4시간(240분)마다 전체 재검사로 캐시 갱신
        """
        try:
            import time
            current_time = time.time()
            
            # 캐시 초기화 (클래스 변수로 관리)
            if not hasattr(self, '_4h_filter_cache'):
                self._4h_filter_cache = {
                    'last_full_scan': 0,
                    'passed_symbols': set(),
                    'failed_symbols': set(),
                    'scan_count': 0
                }
            
            cache = self._4h_filter_cache
            time_since_full_scan = current_time - cache['last_full_scan']
            full_scan_interval = 4 * 60 * 60  # 4시간 = 14400초
            
            # 전체 스캔 조건: 첫 실행 또는 4시간 경과
            need_full_scan = (cache['last_full_scan'] == 0 or 
                             time_since_full_scan >= full_scan_interval)
            
            if need_full_scan:
                print(f"🚀 4h 필터링 [전체 스캔]: {len(candidate_symbols)}개 심볼")
                filtered_symbols = self._full_4h_filtering(candidate_symbols)
                
                # 캐시 업데이트
                cache['last_full_scan'] = current_time
                cache['passed_symbols'] = {s[0] for s in filtered_symbols}
                cache['failed_symbols'] = {s[0] for s in candidate_symbols if s not in filtered_symbols}
                cache['scan_count'] += 1
                
                print(f"   💾 캐시 갱신: 통과 {len(cache['passed_symbols'])}개, 실패 {len(cache['failed_symbols'])}개")
                return filtered_symbols
            
            else:
                print(f"🚀 4h 필터링 [증분 스캔]: {len(candidate_symbols)}개 심볼 (0봉만 검사)")
                filtered_symbols = self._incremental_4h_filtering(candidate_symbols, cache)
                
                cache['scan_count'] += 1
                print(f"   ⚡ 증분 처리 완료: {time_since_full_scan/60:.0f}분 전 전체 스캔 기준")
                return filtered_symbols

        except Exception as e:
            print(f"❌ 4시간봉 필터링 실패: {e}")
            import traceback
            print(f"🔍 DEBUG: 오류 스택: {traceback.format_exc()}")
            return []

    def _full_4h_filtering(self, candidate_symbols):
        """전체 4시간 필터링 - 4봉 이내 시가대비고가 3% 이상 급등"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time

        filtered_symbols = []
        batch_size = 10  # 20 → 10 축소 (Rate Limit 강력 방지)
        total_batches = (len(candidate_symbols) + batch_size - 1) // batch_size

        # 배치 생성
        batches = []
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(candidate_symbols))
            batches.append((batch_idx, candidate_symbols[start_idx:end_idx]))

        print(f"   📡 전체 4h 스캔: {len(candidate_symbols)}개 심볼을 {total_batches}개 배치로 병렬 처리")

        # 배치 처리 함수
        def process_full_4h_batch(batch_data):
            batch_idx, batch_symbols = batch_data
            batch_filtered = []
            batch_checked = 0

            for idx, symbol_data in enumerate(batch_symbols):
                try:
                    symbol = symbol_data[0]
                    batch_checked += 1

                    # WebSocket에서 4h 데이터 조회 (REST API 차단!)
                    ohlcv_df = self.get_ohlcv_data(symbol, '4h', limit=10)
                    if ohlcv_df is None or len(ohlcv_df) < 5:
                        continue

                    # DataFrame을 OHLCV 리스트 형식으로 변환
                    ohlcv = []
                    for _, row in ohlcv_df.iterrows():
                        ohlcv.append([
                            int(row['timestamp'].timestamp() * 1000),
                            row['open'],
                            row['high'],
                            row['low'],
                            row['close'],
                            row['volume']
                        ])

                    if not ohlcv or len(ohlcv) < 5:  # 최소 5개 필요 (4봉 + 1개)
                        continue

                    # 조건 1: 최근 4봉 중 시가대비고가 3% 이상 급등 1회 이상
                    surge_found = False
                    for i in range(-4, 0):
                        candle = ohlcv[i]
                        open_price = candle[1]
                        high_price = candle[2]

                        if open_price > 0:
                            surge_pct = ((high_price - open_price) / open_price) * 100
                            if surge_pct >= 4.0:  # 4% 급등 조건 (엄격한 필터링)
                                surge_found = True
                                break

                    # 조건 2: 4봉 전 시가 ~ 0봉 종가 전체 상승률 0% 이상
                    if surge_found:
                        first_candle_open = ohlcv[-4][1]  # 4봉 전 시가
                        last_candle_close = ohlcv[-1][4]  # 0봉 종가

                        if first_candle_open > 0:
                            total_change_pct = ((last_candle_close - first_candle_open) / first_candle_open) * 100
                            if total_change_pct >= 0:  # 전체 구간 0% 이상 상승이면 통과
                                batch_filtered.append(symbol_data)

                    # 🛡️ Rate Limit 보호: 0.33초 대기 (병렬 3워커 × 초당 3개 = 안전)
                    time.sleep(0.33)

                except Exception as e:
                    if "429" in str(e) or "rate limit" in str(e).lower():
                        time.sleep(1)
                    continue

            return batch_idx, batch_filtered, batch_checked

        # 병렬 처리 실행 (속도 개선)
        completed_batches = 0
        total_checked = 0
        with ThreadPoolExecutor(max_workers=5) as executor:  # 2 → 5 (WebSocket이므로 안전)
            future_to_batch = {executor.submit(process_full_4h_batch, batch): batch[0] for batch in batches}

            for future in as_completed(future_to_batch):
                try:
                    batch_idx, batch_filtered, batch_checked = future.result()
                    filtered_symbols.extend(batch_filtered)
                    total_checked += batch_checked
                    completed_batches += 1

                    if completed_batches % 2 == 0 or completed_batches == total_batches:
                        print(f"   ⏳ 배치 {completed_batches}/{total_batches} 완료 (처리: {total_checked}개, 통과: {len(filtered_symbols)}개)")

                except Exception as e:
                    self.logger.error(f"배치 처리 중 오류: {e}")
                    continue

        # 🕐 전체 스캔 시간 기록 (증분 스캔 기준점)
        self._last_full_scan_time = time.time()

        print(f"🔍 4h 전체 필터링 완료: {len(filtered_symbols)}/{total_checked}개 통과 (통과율: {len(filtered_symbols)/max(total_checked,1)*100:.1f}%)")
        return filtered_symbols

    def _incremental_4h_filtering(self, candidate_symbols, cache):
        """증분 4시간 필터링 - 경과 시간에 따라 동적으로 검사 범위 조정 + 캐시 활용"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time

        # 🕐 경과 시간 계산 및 검사 범위 결정
        if self._last_full_scan_time > 0:
            elapsed_hours = (time.time() - self._last_full_scan_time) / 3600

            # 경과 시간에 따라 검사할 봉 개수 결정
            if elapsed_hours < 4:
                candles_to_check = 1  # 0봉만
                check_range = "0봉"
                use_cache = True
            elif elapsed_hours < 8:
                candles_to_check = 2  # 0~1봉
                check_range = "0~1봉"
                use_cache = True
            elif elapsed_hours < 12:
                candles_to_check = 3  # 0~2봉
                check_range = "0~2봉"
                use_cache = True
            else:
                candles_to_check = 4  # 0~3봉 (전체)
                check_range = "0~3봉 (전체 권장)"
                use_cache = False  # 12시간 이상 경과시 캐시 무효화

            elapsed_str = f"{elapsed_hours:.1f}시간"
        else:
            # 첫 실행시 기본값
            candles_to_check = 1
            check_range = "0봉"
            elapsed_str = "최초"
            use_cache = True

        # 1. 캐시에서 기존 통과 심볼 우선 선택 (캐시 유효시)
        candidate_symbol_names = {s[0] for s in candidate_symbols}

        if use_cache:
            cached_passed = cache['passed_symbols'] & candidate_symbol_names
            cached_symbols = [s for s in candidate_symbols if s[0] in cached_passed]
            new_symbols = [s for s in candidate_symbols if s[0] not in cache['passed_symbols'] and s[0] not in cache['failed_symbols']]

            print(f"   ⏱️ 경과 시간: {elapsed_str} → 검사 범위: {check_range} (증분 모드)")
            print(f"   💾 캐시 활용: {len(cached_symbols)}개 기존 통과 심볼 재사용")
            print(f"   🔍 신규 검사: {len(new_symbols)}개 심볼의 {check_range} 검사")
        else:
            # 12시간 이상 경과: 캐시 무효화, 전체 재검사 권장
            cached_symbols = []
            new_symbols = candidate_symbols
            print(f"   ⏱️ 경과 시간: {elapsed_str} → 캐시 무효화 (전체 스캔 권장)")
            print(f"   ⚠️ 12시간 이상 경과: 전체 {len(new_symbols)}개 심볼 재검사")

        if not new_symbols:
            print(f"   ✅ 모든 심볼이 캐시됨 - 즉시 반환")
            return cached_symbols

        # 3. 새로운 심볼들의 동적 범위 검사
        new_filtered = []
        batch_size = 20  # 배치 크기 (50 → 20 축소, Rate Limit 안전성 강화)
        total_batches = (len(new_symbols) + batch_size - 1) // batch_size

        def process_incremental_batch(batch_data):
            batch_idx, batch_symbols = batch_data
            batch_filtered = []
            batch_checked = 0

            for symbol_data in batch_symbols:
                try:
                    symbol = symbol_data[0]
                    batch_checked += 1

                    # WebSocket에서 4h 데이터 조회 (REST API 차단!)
                    ohlcv_df = self.get_ohlcv_data(symbol, '4h', limit=5)
                    if ohlcv_df is None or len(ohlcv_df) < 5:
                        continue

                    # DataFrame을 OHLCV 리스트 형식으로 변환
                    ohlcv = []
                    for _, row in ohlcv_df.iterrows():
                        ohlcv.append([
                            int(row['timestamp'].timestamp() * 1000),
                            row['open'],
                            row['high'],
                            row['low'],
                            row['close'],
                            row['volume']
                        ])

                    if not ohlcv or len(ohlcv) < 5:
                        continue

                    # 🕐 동적 검사 범위: 경과 시간에 따라 조정
                    # candles_to_check 개수만큼만 검사 (최신 봉부터)
                    check_start = -candles_to_check

                    # 조건 1: 최근 N봉 중 시가대비고가 3% 이상 급등 1회 이상
                    surge_found = False
                    for i in range(check_start, 0):
                        candle = ohlcv[i]
                        open_price = candle[1]
                        high_price = candle[2]

                        if open_price > 0:
                            surge_pct = ((high_price - open_price) / open_price) * 100
                            if surge_pct >= 4.0:  # 4% 급등 조건 (엄격한 필터링)
                                surge_found = True
                                break

                    # 조건 2: 4봉 전 시가 ~ 0봉 종가 전체 상승률 0% 이상
                    if surge_found:
                        first_candle_open = ohlcv[-4][1]  # 4봉 전 시가 (index -4)
                        last_candle_close = ohlcv[-1][4]  # 0봉 종가 (index -1)

                        if first_candle_open > 0:
                            total_change_pct = ((last_candle_close - first_candle_open) / first_candle_open) * 100
                            if total_change_pct >= 0:  # 전체 구간 0% 이상 상승이면 통과
                                batch_filtered.append(symbol_data)
                                # 캐시에 추가
                                cache['passed_symbols'].add(symbol)

                    # 🛡️ Rate Limit 보호: 0.33초 대기 (병렬 처리 고려 안전 속도)
                    time.sleep(0.33)

                except Exception as e:
                    if "429" in str(e) or "rate limit" in str(e).lower():
                        time.sleep(0.5)
                    continue

            return batch_idx, batch_filtered, batch_checked

        # 배치 생성 및 처리
        batches = []
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(new_symbols))
            batches.append((batch_idx, new_symbols[start_idx:end_idx]))

        # 병렬 처리 (속도 개선)
        completed_batches = 0
        total_checked = 0
        with ThreadPoolExecutor(max_workers=5) as executor:  # 2 → 5 (WebSocket이므로 안전)
            future_to_batch = {executor.submit(process_incremental_batch, batch): batch[0] for batch in batches}

            for future in as_completed(future_to_batch):
                try:
                    batch_idx, batch_filtered, batch_checked = future.result()
                    new_filtered.extend(batch_filtered)
                    total_checked += batch_checked
                    completed_batches += 1

                except Exception as e:
                    self.logger.error(f"증분 배치 처리 중 오류: {e}")
                    continue

        # 4. 최종 결과 조합
        all_filtered = cached_symbols + new_filtered

        print(f"🔍 4h 증분 필터링 완료: 캐시 {len(cached_symbols)}개 + 신규 {len(new_filtered)}개 = 총 {len(all_filtered)}개")
        print(f"   💡 성능 향상: {len(new_symbols)}개 중 {total_checked}개만 검사 ({check_range})")

        # 증분 스캔 완료 시점 업데이트 (캐시 유지)
        if use_cache:
            print(f"   ⚡ 증분 처리 완료: {elapsed_str} 전 전체 스캔 기준")

        return all_filtered

    def _get_top100_symbols(self, candidate_symbols):
        """상승률 상위 100위권 심볼 추출"""
        try:
            if not candidate_symbols:
                return []
            
            # 변동률 기준으로 정렬 (높은 순)
            sorted_symbols = sorted(candidate_symbols, key=lambda x: x[1], reverse=True)
            
            # 상위 100개 추출
            top100 = sorted_symbols[:100]
            
            print(f"📈 상위 100위권 심볼 추출: {len(top100)}개")
            
            # 상위 10개 출력
            if top100:
                top10_info = [f"{s.replace('/USDT:USDT', '').replace('/USDT', '')}(+{c:.1f}%)"
                             for s, c, _, _ in top100[:10]]
                print(f"🔥 TOP 10: {', '.join(top10_info)}")
            
            return top100
            
        except Exception as e:
            print(f"⚠️ 상위 100위권 추출 실패: {e}")
            return []
    
    def _websocket_15m_filtering(self, candidate_symbols):
        """⚡ WebSocket 15분봉 데이터로 필터링 (4h 대체) - 성능 최적화된 제한적 처리"""
        filtered_symbols = []

        # 🚨 우선순위 정렬 제거: 모든 심볼을 동등하게 처리
        # 모든 후보 심볼을 그대로 처리 (순서 변경 없음)
        prioritized_symbols = candidate_symbols

        # 디버그 통계 초기화
        total_candidates = len(candidate_symbols)
        selected_for_processing = len(prioritized_symbols)
        symbols_with_15m_data = 0
        symbols_with_sufficient_candles = 0
        symbols_passed_surge_check = 0
        debug_details = []

        try:
            # 디버그 출력 제거됨 (사용자 요청)

            # WebSocket 버퍼 상태 확인
            if hasattr(self, '_websocket_kline_buffer'):
                all_15m_keys = [k for k in self._websocket_kline_buffer.keys() if k.endswith('_15m')]
            else:
                return []

            # 2. WebSocket 데이터 보유 심볼 우선 처리
            ws_symbols, non_ws_symbols = self._separate_websocket_symbols(prioritized_symbols)
            print(f"   📡 15m 버퍼 보유: {len(ws_symbols)}개 | 미보유: {len(non_ws_symbols)}개")

            # 3. WebSocket 데이터 심볼 우선 처리 (빠른 처리)
            processed_symbols = self._process_websocket_symbols(ws_symbols)
            filtered_symbols.extend(processed_symbols[0])
            symbols_with_15m_data += processed_symbols[1]
            symbols_with_sufficient_candles += processed_symbols[2]
            symbols_passed_surge_check += processed_symbols[3]

            print(f"   📊 15m 데이터: {symbols_with_15m_data}개 | 16봉 이상: {symbols_with_sufficient_candles}개 | Surge 통과: {symbols_passed_surge_check}개")

            # ⚡ WebSocket 전용 모드: REST API 호출 완전 제거 (속도 최적화)
            # WebSocket 데이터가 없는 심볼은 스킵
            if non_ws_symbols:
                print(f"   ⚠️ WebSocket 데이터 없는 심볼 {len(non_ws_symbols)}개는 스킵 (REST API 제거)")


            # 성능 최적화: 결과만 간단히 출력
            if len(filtered_symbols) > 0:
                print(f"🔍 15m 필터링 완료: {len(filtered_symbols)}/{total_candidates}개 통과")
            
            return filtered_symbols
            
        except Exception as e:
            print(f"⚠️ WebSocket 15분봉 필터링 오류: {e}")
            import traceback
            print(f"🔍 DEBUG: 오류 스택: {traceback.format_exc()}")
            return []

    def _prioritize_symbols_for_filtering(self, candidate_symbols, limit=None):
        """상위 변동률/거래량 기준으로 심볼 우선순위 정렬 (제한 없음)"""
        try:
            # 입력 데이터 정규화
            normalized_symbols = []
            for item in candidate_symbols:
                if isinstance(item, str):
                    normalized_symbols.append((item, 0.0, 0))
                elif isinstance(item, (list, tuple)) and len(item) >= 3:
                    normalized_symbols.append((item[0], float(item[1]), float(item[2])))
                else:
                    continue
            
            # 변동률과 거래량 기준으로 정렬 (변동률 70%, 거래량 30% 가중치)
            def priority_score(symbol_data):
                _, change_pct, volume_24h = symbol_data
                # 변동률 점수 (절대값 사용 - 상승과 하락 모두 고려)
                change_score = abs(change_pct) * 0.7
                # 거래량 점수 (로그 스케일로 정규화)
                volume_score = np.log10(max(volume_24h, 1)) * 0.3
                return change_score + volume_score
            
            # 우선순위 정렬
            sorted_symbols = sorted(normalized_symbols, key=priority_score, reverse=True)
            
            # 제한이 없으면 모든 심볼 반환, 있으면 상위 N개만 선별
            if limit is None:
                selected_symbols = sorted_symbols  # 모든 심볼
            else:
                selected_symbols = sorted_symbols[:limit]
            
            return selected_symbols
            
        except Exception as e:
            print(f"⚠️ 심볼 우선순위 선별 실패: {e}")
            if limit is None:
                return candidate_symbols  # 모든 심볼 반환
            else:
                return candidate_symbols[:limit]  # 폴백: 단순 앞에서부터 선별

    def _separate_websocket_symbols(self, prioritized_symbols):
        """WebSocket 데이터 보유 심볼과 REST API 필요 심볼 분리"""
        ws_symbols = []
        non_ws_symbols = []
        
        if not hasattr(self, '_websocket_kline_buffer'):
            return [], prioritized_symbols
        
        for symbol_data in prioritized_symbols:
            symbol = symbol_data[0]
            ws_symbol = symbol.replace('/USDT:USDT', '').replace('/', '')
            buffer_key_15m = f"{ws_symbol}_15m"

            if buffer_key_15m in self._websocket_kline_buffer:
                ws_symbols.append(symbol_data)
            else:
                non_ws_symbols.append(symbol_data)
        
        return ws_symbols, non_ws_symbols

    def _process_websocket_symbols(self, ws_symbols):
        """⚡ WebSocket 데이터 보유 심볼들의 15분봉 처리 (4h 대체)"""
        filtered_symbols = []
        symbols_with_15m_data = 0
        symbols_with_sufficient_candles = 0
        symbols_passed_surge_check = 0

        for symbol_data in ws_symbols:
            try:
                if len(symbol_data) == 3:
                    symbol, change_pct, volume_24h = symbol_data
                elif len(symbol_data) == 1:
                    symbol = symbol_data[0]
                    change_pct = 0.0
                    volume_24h = 0.0
                else:
                    continue
            except (TypeError, ValueError) as e:
                continue
            ws_symbol = symbol.replace('/USDT:USDT', '').replace('/', '')
            buffer_key_15m = f"{ws_symbol}_15m"

            if (hasattr(self, '_websocket_kline_buffer') and
                buffer_key_15m in self._websocket_kline_buffer):

                symbols_with_15m_data += 1
                kline_15m = self._websocket_kline_buffer[buffer_key_15m]

                # 15분봉 16봉 = 4시간
                if len(kline_15m) >= 16:
                    symbols_with_sufficient_candles += 1
                    recent_16_candles = kline_15m[-16:]

                    # Surge 조건 확인 (15분봉)
                    if self._check_15m_surge_condition(recent_16_candles):
                        symbols_passed_surge_check += 1
                        filtered_symbols.append((symbol, change_pct, volume_24h))

        return (filtered_symbols, symbols_with_15m_data, symbols_with_sufficient_candles, symbols_passed_surge_check)

    def _process_rest_api_symbols(self, non_ws_symbols, timeout_seconds):
        """REST API 필요 심볼들의 4시간봉 처리 (타임아웃 적용)"""
        filtered_symbols = []
        symbols_with_4h_data = 0
        symbols_with_sufficient_candles = 0
        symbols_passed_surge_check = 0
        
        start_time = time.time()
        
        for symbol_data in non_ws_symbols:
            # 타임아웃 체크
            if time.time() - start_time > timeout_seconds:
                print(f"   ⏰ REST API 처리 타임아웃 ({timeout_seconds}초) - {len(filtered_symbols)}개 결과로 종료")
                break
            
            # 🚨 데이터 언패킹 오류 수정: 길이 체크 추가
            try:
                if len(symbol_data) == 3:
                    symbol, change_pct, volume_24h = symbol_data
                elif len(symbol_data) == 4:
                    symbol, change_pct, volume_24h, ticker = symbol_data
                elif len(symbol_data) == 1:
                    symbol = symbol_data[0]
                    change_pct = 0.0
                    volume_24h = 0.0
                else:
                    continue  # 올바르지 않은 데이터 형식은 건너뛰기
            except (TypeError, ValueError) as e:
                continue  # 데이터 언패킹 실패시 건너뛰기
            ws_symbol = symbol.replace('/USDT:USDT', '').replace('/', '')
            
            try:
                # REST API로 4시간봉 데이터 조회
                api_4h_data = self.get_ohlcv_data(ws_symbol, '4h', 10)

                if api_4h_data is not None and len(api_4h_data) >= 4:
                    symbols_with_4h_data += 1
                    symbols_with_sufficient_candles += 1

                    # DataFrame을 kline 형태로 변환
                    kline_4h = []
                    for idx, row in api_4h_data.iterrows():
                        kline_4h.append({
                            'open': float(row['open']),
                            'high': float(row['high']),
                            'low': float(row['low']),
                            'close': float(row['close']),
                            'volume': float(row['volume'])
                        })

                    # WebSocket 버퍼에 캐시
                    buffer_key_4h = f"{ws_symbol}_4h"
                    if hasattr(self, '_websocket_kline_buffer'):
                        self._websocket_kline_buffer[buffer_key_4h] = kline_4h

                    # Surge 조건 확인
                    recent_4_candles = kline_4h[-4:]
                    if self._check_4h_surge_condition(recent_4_candles):
                        symbols_passed_surge_check += 1
                        filtered_symbols.append((symbol, change_pct, volume_24h))

            except Exception as api_e:
                pass  # 에러 발생 시 해당 심볼 스킵

            # 🛡️ Rate Limit 보호: 종목마다 0.33초 대기 (초당 3종목 안전 속도)
            time.sleep(0.33)
        
        return (filtered_symbols, symbols_with_4h_data, symbols_with_sufficient_candles, symbols_passed_surge_check)

    def _filter_15m_surge_from_top100(self, top100_symbols):
        """⚡ Top100 심볼 중 15m Surge 조건 통과한 것만 필터링"""
        filtered = []
        for symbol_data in top100_symbols:
            try:
                symbol = symbol_data[0]
                buffer_key = f"{symbol}_15m"

                # 15m 버퍼 확인
                if hasattr(self, '_websocket_kline_buffer') and buffer_key in self._websocket_kline_buffer:
                    kline_15m = self._websocket_kline_buffer[buffer_key]

                    # 최소 16개 캔들 필요
                    if len(kline_15m) >= 16:
                        recent_16_candles = kline_15m[-16:]

                        # Surge 조건 확인
                        if self._check_15m_surge_condition(recent_16_candles):
                            filtered.append(symbol_data)
            except Exception as e:
                continue

        return filtered

    def _check_15m_surge_condition(self, recent_16_candles):
        """⚡ 15분봉 16봉 이내 시가대비 고가 2% 이상 상승 확인 (4h 대체)"""
        # 15분봉 16봉 = 4시간 (4h 1봉과 동일한 시간대)
        for candle in recent_16_candles:
            try:
                if isinstance(candle, dict):
                    open_price = candle.get('open', 0)
                    high_price = candle.get('high', 0)
                else:
                    # 배열 형태인 경우 [timestamp, open, high, low, close, volume]
                    open_price = candle[1] if len(candle) > 1 else 0
                    high_price = candle[2] if len(candle) > 2 else 0

                if open_price <= 0:
                    continue

                # 2% 이상 움직임 체크
                if high_price >= open_price * 1.02:
                    return True
            except:
                continue
        return False

    def _fallback_1h_filtering(self, candidate_symbols):
        """1시간봉 기반 폴백 필터링"""
        filtered_symbols = []
        
        # 디버그 통계 초기화
        total_candidates = len(candidate_symbols)
        symbols_with_1h_data = 0
        symbols_with_sufficient_1h_candles = 0
        symbols_passed_1h_surge_check = 0
        
        try:
            # 조용한 1h 폴백 처리
            if hasattr(self, '_websocket_kline_buffer'):
                all_1h_keys = [k for k in self._websocket_kline_buffer.keys() if k.endswith('_1h')]
            
            for i, item in enumerate(candidate_symbols):
                # candidate_symbols 구조 확인 및 처리 (4개 요소: symbol, change_pct, volume_24h, ticker)
                if len(item) >= 3:
                    symbol = item[0]
                    change_pct = item[1]
                    volume_24h = item[2]
                else:
                    continue  # 구조가 맞지 않으면 스킵
                
                # WebSocket 1시간봉 데이터 확인 - 심볼 형식 변환 (BTC/USDT:USDT -> BTCUSDT)
                ws_symbol = symbol.replace('/USDT:USDT', '').replace('/', '')
                buffer_key_1h = f"{ws_symbol}_1h"
                
                if (hasattr(self, '_websocket_kline_buffer') and 
                    buffer_key_1h in self._websocket_kline_buffer):
                    
                    symbols_with_1h_data += 1
                    kline_1h = self._websocket_kline_buffer[buffer_key_1h]
                    
                    # 최근 8개 1시간봉으로 4시간봉 2개 대체
                    if len(kline_1h) >= 8:
                        symbols_with_sufficient_1h_candles += 1
                        recent_8h = kline_1h[-8:]
                        
                        has_valid_surge = False
                        
                        # 4시간 단위로 그룹핑 (2그룹)
                        for i in range(0, 8, 4):
                            group_4h = recent_8h[i:i+4]
                            if len(group_4h) == 4:
                                # 4시간 그룹의 시가와 최고가
                                if isinstance(group_4h[0], dict):
                                    group_open = group_4h[0].get('open', 0)
                                    group_high = max(candle.get('high', 0) for candle in group_4h)
                                else:
                                    # 배열 형태인 경우
                                    group_open = group_4h[0][1] if len(group_4h[0]) > 1 else 0
                                    group_high = max(candle[2] for candle in group_4h if len(candle) > 2)
                                
                                if group_open > 0:
                                    surge_pct = ((group_high - group_open) / group_open) * 100
                                    if surge_pct >= 2.0:
                                        has_valid_surge = True
                                        break
                        
                        if has_valid_surge:
                            symbols_passed_1h_surge_check += 1
                            filtered_symbols.append((symbol, change_pct, volume_24h))
                    else:
                        # 1시간봉 데이터도 부족한 경우 - 필터링에서 제외
                        self.logger.debug(f"DEBUG: {symbol}: 1시간봉 데이터 부족 - 필터링 제외")
                        continue
                else:
                    # WebSocket 데이터 없음 - 필터링에서 제외
                    self.logger.debug(f"DEBUG: {symbol}: WebSocket 1시간봉 데이터 없음 - 필터링 제외")
                    continue
            
            # 중요한 결과만 출력 (통과한 심볼이 있을 때만)
            if len(filtered_symbols) > 0:
                print(f"🎯 1h 폴백 완료: {len(filtered_symbols)}개 심볼 통과")
            # 아무것도 통과하지 않았을 때는 조용히 처리
            return filtered_symbols
            
        except Exception as e:
            print(f"❌ 1시간봉 폴백 필터링 오류: {e}")
            self.logger.error(f"1시간봉 폴백 필터링 오류: {e}")
            # 에러 발생시 빈 리스트 반환 (더 이상 전체 통과하지 않음)
            return []

    def _check_rate_limit_before_scan(self):
        """스캔 전 Rate Limit 여유 확인"""
        try:
            # 가벼운 테스트 호출
            test_ticker = self.exchange.fetch_ticker('BTC/USDT:USDT')
            if test_ticker:
                return True  # 정상
        except Exception as e:
            error_str = str(e).lower()
            if "418" in str(e) or "429" in str(e) or "rate limit" in error_str or "too many requests" in error_str:
                print("🚨 Rate Limit 감지 - 스캔 연기")
                self._api_rate_limited = True
                self._last_rate_limit_check = time.time()
                return False  # 차단됨
            # 다른 에러는 정상으로 간주
        return True

    def get_filtered_symbols(self, min_change_pct=1.0):  # 8% → 2% → 1%로 완화
        """WebSocket 전용 심볼 필터링 - REST API 완전 금지"""
        try:
            # 🛡️ Rate Limit 사전 체크 (REST API 사용 전)
            if not self._check_rate_limit_before_scan():
                print("⏳ Rate Limit 감지 - WebSocket 전용 모드로 전환")
                # WebSocket 데이터만 사용
                websocket_symbols = self._get_websocket_filtered_symbols()
                if websocket_symbols:
                    return websocket_symbols
                else:
                    print("❌ WebSocket 데이터 없음 - 1분 대기 후 재시도 권장")
                    return []

            # Rate limit 상태에서도 전체 심볼 필터링 수행 (주요 심볼 우선 제거)
            if hasattr(self, '_api_rate_limited') and self._api_rate_limited:
                print("🚨 Rate limit 모드 - WebSocket 데이터만 사용한 전체 심볼 필터링")
            
            # 🚀 전체 USDT 선물 심볼 조회 (캐시 사용으로 2-5초 → 0ms 단축)
            markets = self._get_cached_markets()
            usdt_symbols = [symbol for symbol, market in markets.items()
                           if (symbol.endswith('/USDT:USDT') or symbol.endswith('/USDT'))
                           and market['active'] and market['type'] == 'swap']

            print(f"📊 전체 USDT 선물 심볼: {len(usdt_symbols)}개")
            
            # WebSocket 데이터 우선 사용 
            websocket_symbols = self._get_websocket_filtered_symbols()
            
            # 🚨 Rate Limit 상태에서는 WebSocket 데이터가 있을 때만 사용
            if hasattr(self, '_api_rate_limited') and self._api_rate_limited:
                if websocket_symbols:
                    print(f"✅ Rate Limit 모드 - WebSocket 데이터 강제 사용: {len(websocket_symbols)}개 심볼")
                    return websocket_symbols
                else:
                    print("❌ Rate Limit 모드 - WebSocket 데이터도 없어서 스캔 불가")
                    return []
            
            # 정상 상태에서는 기존 로직 유지 (최소 10개 이상)
            if websocket_symbols and len(websocket_symbols) >= 10:
                print(f"✅ WebSocket 데이터 사용: {len(websocket_symbols)}개 심볼")
                return websocket_symbols
            
            # 웹소켓 데이터가 부족할 때 REST API 사용 (폴백)
            print("⚠️ WebSocket 데이터 부족 - REST API 폴백")
            
            # 1단계: 티커 데이터 수집
            candidate_symbols = []
            
            try:
                print("⚡ 전체 티커 일괄 조회 중...")
                all_tickers = self.exchange.fetch_tickers()

                # 1단계: 24시간 변동률로 빠른 사전 필터링 (상위 300개)
                temp_candidates = []
                for symbol in usdt_symbols:
                    if symbol in all_tickers:
                        ticker = all_tickers[symbol]
                        if ticker and 'percentage' in ticker:
                            change_24h = ticker.get('percentage', 0) or 0
                            volume_24h = ticker.get('quoteVolume', 0) or 0
                            temp_candidates.append((symbol, change_24h, volume_24h, ticker))

                # 24시간 변동률 기준으로 정렬하되 전체 심볼 사용
                temp_candidates.sort(key=lambda x: x[1], reverse=True)
                top_symbols = temp_candidates  # 전체 심볼 사용 (약 581개)
                print(f"📊 1단계 사전 필터링: 전체 {len(top_symbols)}개 심볼 사용")

                # 2단계: 전체 심볼에 대해 오늘 09:00 이후 변동률 계산
                from datetime import datetime, time as dt_time, timedelta, timezone

                # UTC 현재 시각
                now_utc = datetime.now(timezone.utc)

                # 한국 시간 (UTC+9)
                kst_offset = timedelta(hours=9)
                now_kst = now_utc + kst_offset

                # 오늘 09:00 KST 계산
                today_9am_kst = now_kst.replace(hour=9, minute=0, second=0, microsecond=0)

                # 현재 시각이 09:00 이전이면 어제 09:00 사용
                if now_kst < today_9am_kst:
                    today_9am_kst = today_9am_kst - timedelta(days=1)

                # UTC로 변환 (바이낸스 API는 UTC 사용)
                today_9am_utc = today_9am_kst - kst_offset
                since_timestamp = int(today_9am_utc.timestamp() * 1000)

                print(f"📅 변동률 기준 시각: {today_9am_kst.strftime('%Y-%m-%d %H:%M:%S KST')} (UTC: {today_9am_utc.strftime('%Y-%m-%d %H:%M:%S')})")
                print(f"🕐 현재 KST: {now_kst.strftime('%Y-%m-%d %H:%M:%S')}")

                # 전체 심볼에 대해 09:00 이후 변동률 재계산
                for idx, (symbol, _, volume_24h, ticker) in enumerate(top_symbols):
                    current_price = ticker.get('last', 0) or 0

                    # 오늘 09:00 이후 변동률 계산 (1시간봉 사용)
                    try:
                        hours_since_9am = int((datetime.now(timezone.utc).timestamp() * 1000 - since_timestamp) / (1000 * 3600)) + 2

                        # WebSocket에서 1h 데이터 조회 (REST API 차단!)
                        ohlcv_df = self.get_ohlcv_data(symbol, '1h', limit=min(hours_since_9am, 24))

                        # DataFrame을 OHLCV 리스트 형식으로 변환
                        ohlcv = []
                        if ohlcv_df is not None and len(ohlcv_df) > 0:
                            for _, row in ohlcv_df.iterrows():
                                ohlcv.append([
                                    int(row['timestamp'].timestamp() * 1000),
                                    row['open'],
                                    row['high'],
                                    row['low'],
                                    row['close'],
                                    row['volume']
                                ])

                        if ohlcv and len(ohlcv) > 0:
                            # 09:00 시각에 가장 가까운 캔들 찾기
                            base_price = None
                            for candle in ohlcv:
                                if candle[0] >= since_timestamp:
                                    base_price = candle[1]  # 시가
                                    break

                            if base_price is None and len(ohlcv) > 0:
                                base_price = ohlcv[0][1]  # 첫 캔들 시가

                            if base_price and base_price > 0:
                                change_pct_since_9am = ((current_price - base_price) / base_price) * 100
                            else:
                                change_pct_since_9am = 0
                        else:
                            change_pct_since_9am = 0

                    except Exception as e:
                        # 변동률 계산 실패시 0으로 처리
                        change_pct_since_9am = 0
                        # 디버깅: 처음 3개만 오류 출력
                        if idx < 3:
                            print(f"   ⚠️ [{symbol}] 09:00 변동률 계산 실패: {e}")

                    # 09:00 이후 변동률로 업데이트
                    candidate_symbols.append((symbol, change_pct_since_9am, volume_24h, ticker))

                    # 진행 상황 표시 (100개마다)
                    if (idx + 1) % 100 == 0:
                        print(f"   ⏳ 09:00 이후 변동률 계산 중... {idx + 1}/{len(top_symbols)}")

                    # 디버깅: 처음 3개 결과 출력
                    if idx < 3:
                        print(f"   🔍 [{symbol}] 현재가: ${current_price:.2f}, 09:00 이후 변동률: {change_pct_since_9am:.2f}%")

                    time.sleep(0.1)  # Rate limit 방지 (20ms → 100ms 증가)

                # 📊 09:00 이후 변동률 통계
                positive_count = sum(1 for _, change, _, _ in candidate_symbols if change > 0)
                negative_count = sum(1 for _, change, _, _ in candidate_symbols if change <= 0)

                print(f"✅ 2단계 완료: 09:00 이후 변동률 계산 완료 ({len(candidate_symbols)}개)")
                print(f"   📈 09:00 이후 > 0%: {positive_count}개 ({positive_count/len(candidate_symbols)*100:.1f}%)")
                print(f"   📉 09:00 이후 ≤ 0%: {negative_count}개 ({negative_count/len(candidate_symbols)*100:.1f}%)")

                # 🚫 임시 비활성화: 09:00 이후 > 0% 필터링 (새로운 종목 진입 허용)
                # candidate_symbols = [(s, c, v, t) for s, c, v, t in candidate_symbols if c > 0]
                print(f"   ⚠️ 09:00 이후 > 0% 필터링 비활성화 - 전체 {len(candidate_symbols)}개 종목 허용")

            except Exception as e:
                # Rate Limit 감지 및 처리 강화
                error_str = str(e).lower()
                if ("418" in str(e) or "429" in str(e) or 
                    "too many requests" in error_str or "rate limit" in error_str):
                    print(f"🚨 Rate Limit 감지 - 티커 조회 중단: {e}")
                    self._api_rate_limited = True
                    self._last_rate_limit_check = time.time()
                    return []  # 즉시 중단하여 추가 API 호출 방지
                
                print(f"⚠️ 전체 티커 조회 실패, 배치 처리로 전환: {e}")

                # 배치 처리로 fallback (Rate Limit 아닌 경우만)
                batch_size = 20  # 50 → 20으로 배치 크기 축소 (Rate Limit 안전성 강화)
                for i in range(0, len(usdt_symbols), batch_size):
                    # Rate Limit 재확인
                    if hasattr(self, '_api_rate_limited') and self._api_rate_limited:
                        print("🚨 배치 처리 중 Rate Limit 감지 - 중단")
                        break

                    batch_symbols = usdt_symbols[i:i+batch_size]

                    try:
                        tickers = self.exchange.fetch_tickers(batch_symbols)

                        for symbol, ticker in tickers.items():
                            if ticker and 'percentage' in ticker:
                                change_pct = ticker.get('percentage', 0) or 0
                                volume_24h = ticker.get('quoteVolume', 0) or 0
                                candidate_symbols.append((symbol, change_pct, volume_24h, ticker))

                        time.sleep(1.0)  # 0.2 → 1.0초로 대기 시간 증가 (배치 간 충분한 회복 시간)

                    except Exception as e:
                        # 배치 처리 중 Rate Limit 감지
                        error_str = str(e).lower()
                        if ("418" in str(e) or "429" in str(e) or 
                            "too many requests" in error_str or "rate limit" in error_str):
                            self.logger.warning(f"🚨 배치 {i//batch_size + 1} Rate Limit 감지 - 중단: {e}")
                            self._api_rate_limited = True
                            self._last_rate_limit_check = time.time()
                            break  # 즉시 중단
                        else:
                            self.logger.warning(f"배치 {i//batch_size + 1} 실패: {e}")
                            continue

            print(f"🔍 전체 USDT 심볼 수집: {len(candidate_symbols)}개")

            # 2단계: 4시간봉 급등 필터링 (4봉 이내 3% 이상)
            filtered_symbols = self._apply_4h_filtering(candidate_symbols)

            # 4h 필터링 결과가 없으면 폴백으로 통합 필터링 사용
            if not filtered_symbols or len(filtered_symbols) == 0:
                print("⚠️ 4h 필터링 결과 없음 → 통합 필터링으로 폴백")
                filtered_symbols = self._apply_integrated_filtering(candidate_symbols)

            # 변동률 순으로 정렬
            filtered_symbols.sort(key=lambda x: x[1], reverse=True)
            
            if filtered_symbols:
                # 상위 심볼 출력 - 다양한 데이터 구조 대응
                top_symbols = filtered_symbols[:10]
                symbol_info = []
                for item in top_symbols:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        symbol_name = item[0].replace('/USDT:USDT', '').replace('/USDT', '')
                        change_pct = item[1]
                        symbol_info.append(f"{symbol_name}(+{change_pct:.1f}%)")
                    else:
                        symbol_name = str(item).replace('/USDT:USDT', '').replace('/USDT', '')
                        symbol_info.append(symbol_name)

                # 전체 선별된 심볼 반환 (최대 150개) - 다양한 데이터 구조 대응
                result_symbols = []
                for item in filtered_symbols:
                    if isinstance(item, (list, tuple)) and len(item) >= 1:
                        result_symbols.append(item[0])  # 첫 번째 요소가 심볼
                    else:
                        result_symbols.append(item)
                return result_symbols
            else:
                # 통합 필터링 실패시 상위 변동률 심볼로 스캔 결과 제공
                print("⚠️ 통합 필터링 조건 미충족 - 상위 변동률 심볼로 스캔 진행")
                if candidate_symbols:
                    # 변동률 상위 20개 심볼로 제한하여 스캔 결과 제공
                    candidate_symbols.sort(key=lambda x: x[1], reverse=True)
                    top_candidates = candidate_symbols[:20]
                    top_symbols_list = [symbol for symbol, _, _, _ in top_candidates]
                    
                    symbol_info = [f"{s.replace('/USDT:USDT', '').replace('/USDT', '')}(+{c:.1f}%)"
                                  for s, c, _, _ in top_candidates[:10]]
                    print(f"📈 상위 변동률 기준 스캔: {', '.join(symbol_info)}")
                    
                    return top_symbols_list
                else:
                    return []  # 완전 실패시에만 빈 배열
            
        except Exception as e:
            self.logger.error(f"심볼 필터링 실패: {e}")
            import traceback
            self.logger.error(f"스택 트레이스: {traceback.format_exc()}")
            
            # 오류 시에도 빈 배열 반환
            print(f"⚠️ 오류 발생으로 스캔 중단 - 필터링 조건 엄격 적용")
            return []
    
    def _get_websocket_filtered_symbols(self):
        """WebSocket 데이터만 사용한 심볼 필터링 + 신뢰도 기반 품질 검증"""
        try:
            if not hasattr(self, '_websocket_kline_buffer') or not self._websocket_kline_buffer:
                print("⚠️ WebSocket 버퍼가 비어있음")
                return []

            print(f"📡 WebSocket 버퍼 심볼: {len(self._websocket_kline_buffer)}개")

            # WebSocket 버퍼에서 1분봉 데이터가 있는 심볼들 추출
            candidate_symbols = []
            quality_stats = {'total': 0, 'passed': 0, 'low_quality': 0, 'insufficient_data': 0}

            for buffer_key, kline_data in self._websocket_kline_buffer.items():
                if '_1m' not in buffer_key:
                    continue

                quality_stats['total'] += 1

                # 🔍 품질 검증 1: 최소 데이터 수 (3개 → 10개로 강화)
                if len(kline_data) < 10:
                    quality_stats['insufficient_data'] += 1
                    continue

                symbol = buffer_key.replace('_1m', '')

                # 안전한 가격 데이터 추출 (인덱스 오류 방지)
                try:
                    # 🔍 품질 검증 2: 데이터 구조 유효성 (최근 10개 캔들 검증)
                    valid_candles = 0
                    for i in range(-10, 0):
                        try:
                            if len(kline_data[i]) >= 6:  # [timestamp, open, high, low, close, volume]
                                valid_candles += 1
                        except (IndexError, TypeError):
                            pass

                    # 10개 중 최소 8개 이상 유효해야 통과 (80% 신뢰도)
                    if valid_candles < 8:
                        quality_stats['low_quality'] += 1
                        continue

                    # 최근 24시간 변동률 계산 (1440개 1분봉으로 근사)
                    if len(kline_data) >= 1440 and len(kline_data[-1]) > 4 and len(kline_data[-1440]) > 4:
                        current_price = float(kline_data[-1][4])  # 최신 종가
                        day_ago_price = float(kline_data[-1440][4])  # 24시간 전 종가

                        # 🔍 품질 검증 3: 가격 데이터 이상치 확인
                        if current_price <= 0 or day_ago_price <= 0:
                            quality_stats['low_quality'] += 1
                            continue

                        # 🔍 품질 검증 4: 급격한 가격 변동 (>1000%) 이상치 제거
                        price_change = abs((current_price - day_ago_price) / day_ago_price)
                        if price_change > 10.0:  # 1000% 이상 변동은 데이터 오류 가능성
                            quality_stats['low_quality'] += 1
                            continue

                        change_pct = ((current_price - day_ago_price) / day_ago_price) * 100
                    else:
                        # 데이터가 부족하면 가용한 모든 데이터로 변동률 추정
                        if len(kline_data) > 0 and len(kline_data[-1]) > 4:
                            current_price = float(kline_data[-1][4])
                            if len(kline_data[0]) > 4:
                                old_price = float(kline_data[0][4])
                            else:
                                old_price = current_price

                            # 가격 유효성 검증
                            if old_price <= 0 or current_price <= 0:
                                quality_stats['low_quality'] += 1
                                continue

                            change_pct = ((current_price - old_price) / old_price) * 100
                        else:
                            # 데이터 형식이 올바르지 않으면 건너뛰기
                            quality_stats['low_quality'] += 1
                            continue

                except (IndexError, ValueError, TypeError) as data_error:
                    # 데이터 형식 오류시 해당 심볼 건너뛰기
                    quality_stats['low_quality'] += 1
                    continue

                # 기본 거래량 (정확한 24h 거래량은 ticker에서만 가능)
                try:
                    available_candles = min(len(kline_data), 100)
                    volume_24h = 0
                    for candle in kline_data[-available_candles:]:
                        if len(candle) > 5:
                            volume_24h += float(candle[5])  # 안전한 거래량 접근

                    # 🔍 품질 검증 5: 거래량 최소값 (너무 낮은 거래량 제외)
                    if volume_24h < 100:  # 최소 거래량 기준
                        quality_stats['low_quality'] += 1
                        continue

                except (IndexError, ValueError, TypeError):
                    volume_24h = 1000000  # 기본값

                # ✅ 모든 품질 검증 통과
                quality_stats['passed'] += 1
                candidate_symbols.append((symbol, change_pct, volume_24h))

            # 📊 품질 통계 출력
            if quality_stats['total'] > 0:
                pass_rate = (quality_stats['passed'] / quality_stats['total']) * 100
                print(f"📊 WebSocket 데이터 품질 검증:")
                print(f"   • 총 심볼: {quality_stats['total']}개")
                print(f"   • 통과: {quality_stats['passed']}개 ({pass_rate:.1f}%)")
                print(f"   • 데이터 부족: {quality_stats['insufficient_data']}개")
                print(f"   • 품질 미달: {quality_stats['low_quality']}개")

            if not candidate_symbols:
                print("⚠️ WebSocket 품질 검증 통과 심볼 없음")
                return []

            # WebSocket 후보 심볼 처리 (조용한 스캔)
            
            # 2시간봉 필터링 (최적화된 버전 사용)
            if hasattr(self, 'optimized_filter') and self.optimized_filter:
                filtered_symbols = self.optimized_filter.fast_filter_symbols(candidate_symbols)
                
                if filtered_symbols:
                    # 변동률 순으로 정렬
                    filtered_symbols.sort(key=lambda x: x[1], reverse=True)
                    print(f"✅ WebSocket 필터링 통과: {len(filtered_symbols)}개 심볼")
                    
                    # 모든 필터링 통과 심볼 반환 (제한 없음)
                    return [symbol for symbol, _, _ in filtered_symbols]
                else:
                    print("⚠️ 2시간봉 필터링 통과 심볼 없음")
                    return []
            else:
                # 최적화 필터가 없으면 변동률만으로 필터링
                candidate_symbols.sort(key=lambda x: x[1], reverse=True)
                return [symbol for symbol, _, _ in candidate_symbols]  # 모든 후보 심볼
                
        except Exception as e:
            print(f"❌ WebSocket 필터링 실패: {e}")
            
            # 실패해도 기본 심볼들은 반환 (빈 배열 대신)
            if hasattr(self, '_websocket_kline_buffer') and self._websocket_kline_buffer:
                basic_symbols = []
                for buffer_key in list(self._websocket_kline_buffer.keys())[:20]:  # 상위 20개만
                    if '_1m' in buffer_key:
                        symbol = buffer_key.replace('_1m', '')
                        basic_symbols.append(symbol)
                
                if basic_symbols:
                    print(f"⚠️ 필터링 실패했지만 기본 WebSocket 심볼 사용: {len(basic_symbols)}개")
                    return basic_symbols
            
            return []
    
    def manual_dca_recovery(self, symbol: str = None):
        """수동 DCA 주문 복구"""
        if not hasattr(self, 'dca_recovery') or not self.dca_recovery:
            print("[DCA복구] ❌ DCA 복구 시스템이 초기화되지 않음")
            return
        
        try:
            if symbol:
                # USDT 접미사 추가 (필요시)
                if not symbol.endswith('USDT'):
                    symbol = f"{symbol}/USDT:USDT"
                elif not symbol.endswith('/USDT:USDT'):
                    symbol = f"{symbol}:USDT"
                
                # 특정 심볼 복구
                result = self.dca_recovery.manual_recovery_for_symbol(symbol)
                print(f"[DCA복구] {symbol} 복구 결과: {result}")
            else:
                # 전체 포지션 복구
                exchange_positions = {}
                for sym in self.active_positions.keys():
                    try:
                        positions = self.exchange.fetch_positions([sym])
                        if positions and positions[0].get('contracts', 0) > 0:
                            exchange_positions[sym] = {
                                'contracts': positions[0]['contracts'],
                                'markPrice': positions[0]['markPrice']
                            }
                    except Exception as e:
                        print(f"[DCA복구] ⚠️ {sym} 포지션 조회 실패: {e}")
                
                result = self.dca_recovery.enhanced_scan_and_recover(exchange_positions)
                print(f"[DCA복구] 전체 복구 결과: {result}")
                
        except Exception as e:
            print(f"[DCA복구] ❌ 수동 복구 실패: {e}")
    
    def get_dca_recovery_stats(self):
        """DCA 복구 시스템 통계 조회"""
        if not hasattr(self, 'dca_recovery') or not self.dca_recovery:
            return None
        
        return self.dca_recovery.get_recovery_stats()
    
    def get_trade_summary(self):
        """거래 요약 조회"""
        if not hasattr(self, 'trade_history_sync') or not self.trade_history_sync:
            return None
        
        return self.trade_history_sync.get_daily_summary()
    
    def force_trade_sync(self):
        """강제 거래 내역 동기화"""
        if not hasattr(self, 'trade_history_sync') or not self.trade_history_sync:
            print("[ERROR] 거래 내역 동기화 시스템이 초기화되지 않음")
            return False
        
        result = self.trade_history_sync.force_full_sync()
        print(f"[거래동기화] 강제 동기화 결과: {result}")
        return result
    
    # 🛡️ 강화된 DCA 복구 시스템 유틸리티 메소드들
    def emergency_dca_recovery(self, symbol: str = None):
        """긴급 DCA 복구 실행"""
        if hasattr(self, 'dca_recovery') and self.dca_recovery:
            print(f"🚨 긴급 DCA 복구 시작: {symbol or '전체 포지션'}")
            return self.dca_recovery.manual_emergency_recovery(symbol)
        elif hasattr(self, 'dca_recovery') and self.dca_recovery:
            print(f"🔧 기본 DCA 복구 시작: {symbol or '전체 포지션'}")
            if symbol:
                return self.dca_recovery.manual_recovery_for_symbol(symbol)
            else:
                # 전체 복구를 위한 간단한 구현
                exchange_positions = {}
                for sym in self.active_positions.keys():
                    try:
                        positions = self.exchange.fetch_positions([sym])
                        if positions and positions[0].get('contracts', 0) > 0:
                            exchange_positions[sym] = {
                                'contracts': positions[0]['contracts'],
                                'markPrice': positions[0]['markPrice']
                            }
                    except Exception as e:
                        print(f"[긴급복구] ⚠️ {sym} 포지션 조회 실패: {e}")
                return self.dca_recovery.enhanced_scan_and_recover(exchange_positions)
        else:
            print("[ERROR] DCA 복구 시스템이 초기화되지 않음")
            return None
    
    def get_dca_recovery_status(self):
        """DCA 복구 시스템 상태 조회"""
        status = {}
        
        if hasattr(self, 'dca_recovery') and self.dca_recovery:
            status['enhanced'] = self.dca_recovery.get_system_status()
            
        if hasattr(self, 'dca_recovery') and self.dca_recovery:
            status['basic'] = self.dca_recovery.get_recovery_stats()
            
        return status if status else None
    
    def force_enhanced_dca_scan(self):
        """강제 강화된 DCA 스캔 실행"""
        if not hasattr(self, 'dca_recovery') or not self.dca_recovery:
            print("[ERROR] 강화된 DCA 복구 시스템이 초기화되지 않음")
            return None
            
        try:
            # 현재 포지션 정보 수집
            exchange_positions = {}
            current_prices = {}
            
            for symbol in self.active_positions.keys():
                try:
                    positions = self.exchange.fetch_positions([symbol])
                    if positions and positions[0].get('contracts', 0) > 0:
                        mark_price = positions[0]['markPrice']
                        exchange_positions[symbol] = {
                            'contracts': positions[0]['contracts'],
                            'markPrice': mark_price
                        }
                        current_prices[symbol] = mark_price
                except Exception as e:
                    print(f"[강제스캔] ⚠️ {symbol} 포지션 조회 실패: {e}")
            
            if exchange_positions:
                print(f"🔍 강제 DCA 스캔 실행 - {len(exchange_positions)}개 포지션 검사")
                result = self.dca_recovery.enhanced_scan_and_recover(
                    exchange_positions, current_prices
                )
                
                print(f"📊 스캔 결과:")
                print(f"  - 검사한 포지션: {result.get('scanned_positions', 0)}개")
                print(f"  - 누락 주문 감지: {len(result.get('missing_orders_detected', []))}개")
                print(f"  - 복구 성공: {result.get('successful_recoveries', 0)}개")
                print(f"  - 복구 실패: {result.get('failed_recoveries', 0)}개")
                print(f"  - 스캔 시간: {result.get('scan_duration', 0):.2f}초")
                
                return result
            else:
                print("📭 활성 포지션 없음")
                return {'message': '활성 포지션 없음'}
                
        except Exception as e:
            print(f"[강제스캔] ❌ 실행 실패: {e}")
            return {'error': str(e)}
    
    def reconstruct_daily_stats(self):
        """청산된 DCA 포지션을 기반으로 일일 통계 재구성"""
        try:
            import json
            import os
            from datetime import datetime
            
            current_trading_day = self._get_trading_day()
            print(f"📊 일일 통계 재구성 시작 ({current_trading_day})")
            
            # DCA 포지션 파일에서 직접 읽기
            dca_file = 'dca_positions.json'
            if not os.path.exists(dca_file):
                print("❌ dca_positions.json 파일이 없습니다")
                return
            
            with open(dca_file, 'r', encoding='utf-8') as f:
                positions_data = json.load(f)
            
            # 오늘 청산된 포지션들 찾기
            today_closed_positions = []
            today_active_positions = []
            
            for symbol, position in positions_data.items():
                # updated_at 시간 확인하여 오늘 업데이트된 것만 포함
                try:
                    if position.get('updated_at'):
                        updated_str = position['updated_at']
                        if '+09:00' in updated_str:
                            # KST 시간으로 파싱
                            updated_date = datetime.fromisoformat(updated_str.replace('+09:00', '')).date()
                        else:
                            # UTC 시간으로 파싱 후 KST로 변환
                            updated_date = datetime.fromisoformat(updated_str.replace('Z', '+00:00'))
                            updated_date = (updated_date + timedelta(hours=9)).date()
                        
                        trading_day_date = datetime.strptime(current_trading_day, '%Y-%m-%d').date()
                        
                        if updated_date == trading_day_date:
                            if position.get('current_stage') == 'closed' and not position.get('is_active', True):
                                today_closed_positions.append((symbol, position))
                            elif position.get('is_active', False):
                                today_active_positions.append((symbol, position))
                except Exception as e:
                    print(f"  ⚠️ {symbol} 날짜 파싱 실패: {e}")
            
            print(f"  📈 오늘 청산된 포지션: {len(today_closed_positions)}개")
            
            # 통계 계산
            total_trades = len(today_closed_positions)
            wins = 0
            losses = 0
            total_pnl = 0.0
            trades_detail = []
            
            for symbol, position in today_closed_positions:
                try:
                    # 수익률 계산
                    max_profit_pct = position.get('max_profit_pct', 0.0)
                    total_amount = position.get('total_amount_usdt', 0.0)
                    
                    # 수익금 계산 (레버리지 고려)
                    profit_amount = total_amount * max_profit_pct
                    total_pnl += profit_amount
                    
                    # 수익/손실 분류
                    if max_profit_pct > 0:
                        wins += 1
                        result = "수익"
                    else:
                        losses += 1
                        result = "손실"
                    
                    trades_detail.append({
                        'symbol': symbol,
                        'profit_pct': max_profit_pct * 100,
                        'profit_amount': profit_amount,
                        'result': result,
                        'amount': total_amount
                    })
                    
                    print(f"    {symbol}: {result} {max_profit_pct*100:+.2f}% (${profit_amount:+.2f})")
                    
                except Exception as e:
                    print(f"  ⚠️ {symbol} 계산 실패: {e}")
            
            # 승률 계산
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
            
            # 통계 업데이트
            self.today_stats.update({
                'date': current_trading_day,
                'total_trades': total_trades,
                'wins': wins,
                'losses': losses,
                'total_pnl': total_pnl,
                'win_rate': win_rate,
                'trades_detail': trades_detail
            })
            
            # 통계 저장
            self._save_daily_stats()
            
            print(f"✅ 통계 재구성 완료:")
            print(f"  💰 총 거래: {total_trades}회")
            print(f"  ✅ 수익: {wins}회 | ❌ 손실: {losses}회")
            print(f"  📈 승률: {win_rate:.1f}%")
            print(f"  💵 총 손익: ${total_pnl:+.2f}")
            
        except Exception as e:
            print(f"❌ 통계 재구성 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def print_positions_summary(self):
        """모든 포지션을 테이블 형태로 요약 출력"""
        try:
            if not self.active_positions:
                print("📭 활성 포지션이 없습니다.")
                return
            
            print(f"\n{'='*120}")
            print(f"📊 포지션 요약 테이블 ({len(self.active_positions)}개)")
            print(f"{'='*120}")
            
            # 테이블 헤더
            header = f"{'심볼':<12} {'진입가':<12} {'현재가':<12} {'수익률':<10} {'투자금':<10} {'고점수익':<10} {'DCA단계':<12} {'상태':<8}"
            print(header)
            print("-" * 120)
            
            total_investment = 0.0
            total_current_value = 0.0
            total_pnl = 0.0
            
            # 각 포지션 정보 수집 및 출력
            for symbol, position_info in self.active_positions.items():
                try:
                    # 현재가 조회
                    current_price = self.get_current_price(symbol)
                    if current_price is None:
                        continue  # 가격 조회 실패시 해당 포지션 스킵
                    entry_price = position_info['entry_price']
                    
                    # 수익률 계산
                    profit_pct = ((current_price - entry_price) / entry_price) * 100
                    
                    # DCA 정보 가져오기
                    dca_position = None
                    investment_amount = 0.0
                    max_profit_pct = 0.0
                    dca_stage = "N/A"
                    
                    if hasattr(self, 'dca_manager') and self.dca_manager:
                        dca_position = self.dca_manager.positions.get(symbol)
                        if dca_position:
                            investment_amount = getattr(dca_position, 'total_amount_usdt', 0.0)
                            max_profit_pct = getattr(dca_position, 'max_profit_pct', 0.0) * 100
                            stage = getattr(dca_position, 'current_stage', 'unknown')
                            
                            # 단계 한글화
                            stage_map = {
                                'initial': '최초진입',
                                'first_dca': '1차추가',
                                'second_dca': '2차추가',
                                'closed': '청산완료'
                            }
                            dca_stage = stage_map.get(stage, stage)
                    
                    # 포지션 현재 가치 계산
                    quantity = position_info.get('quantity', 0)
                    leverage = position_info.get('leverage', 10)
                    if quantity == 0:
                        # quantity가 없으면 investment_amount와 entry_price로 역산
                        quantity = (investment_amount * leverage) / entry_price if entry_price > 0 else 0
                    
                    current_value = quantity * current_price / leverage if leverage > 0 else 0
                    
                    # 상태 표시
                    if profit_pct >= 3:
                        status = "🟢높음"
                    elif profit_pct >= 0:
                        status = "🟡수익"
                    elif profit_pct >= -5:
                        status = "🟠손실"
                    else:
                        status = "🔴위험"
                    
                    # 심볼명 정리 및 색상 적용
                    clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                    symbol_colored = f"\033[93m{clean_symbol:<10}\033[0m"  # 노랑색
                    
                    # 수익률에 색상 적용
                    if profit_pct >= 0:
                        profit_pct_colored = f"\033[92m{profit_pct:>+8.2f}%\033[0m"  # 초록색
                    else:
                        profit_pct_colored = f"\033[91m{profit_pct:>+8.2f}%\033[0m"  # 빨간색
                    
                    # 행 출력
                    row = f"{symbol_colored} ${entry_price:<11.4f} ${current_price:<11.4f} {profit_pct_colored} ${investment_amount:<9.1f} {max_profit_pct:>+8.2f}% {dca_stage:<12} {status:<8}"
                    print(row)
                    
                    # 합계 계산
                    total_investment += investment_amount
                    total_current_value += current_value
                    total_pnl += (current_value - investment_amount)
                    
                except Exception as e:
                    clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                    symbol_colored = f"\033[93m{clean_symbol:<10}\033[0m"  # 노랑색
                    print(f"{symbol_colored} {'오류':<12} {'오류':<12} {'N/A':<10} {'N/A':<10} {'N/A':<10} {'N/A':<12} {'❌오류':<8}")
            
            print("-" * 120)
            
            # 합계 출력
            total_profit_pct = ((total_current_value - total_investment) / total_investment * 100) if total_investment > 0 else 0
            profit_color = "🟢" if total_pnl >= 0 else "🔴"
            
            # 총합 라벨과 수익률에 색상 적용
            total_label_colored = f"\033[93m{'전체 합계':<10}\033[0m"  # 노랑색
            if total_profit_pct >= 0:
                total_profit_pct_colored = f"\033[92m{total_profit_pct:>+8.2f}%\033[0m"  # 초록색
                total_pnl_colored = f"\033[92m${total_pnl:+.2f}\033[0m"  # 초록색
            else:
                total_profit_pct_colored = f"\033[91m{total_profit_pct:>+8.2f}%\033[0m"  # 빨간색
                total_pnl_colored = f"\033[91m${total_pnl:+.2f}\033[0m"  # 빨간색
            
            print(f"{total_label_colored} {'':<12} {'':<12} {total_profit_pct_colored} ${total_investment:<9.1f} {'':<10} {'':<12} {profit_color}{total_pnl_colored}")
            print(f"{'='*120}")
            
            # 요약 정보
            print(f"\n💰 포트폴리오 요약:")
            print(f"   총 투자금액: ${total_investment:.2f}")
            print(f"   현재 가치: ${total_current_value:.2f}")
            print(f"   손익: {profit_color}${total_pnl:+.2f} ({total_profit_pct:+.2f}%)")
            
        except Exception as e:
            print(f"❌ 포지션 요약 출력 실패: {e}")
            import traceback
            traceback.print_exc()
    
    # 절반하락 청산 로직 삭제됨 (사용자 요청)
    
    # 절반하락 청산 모니터링 함수 삭제됨 (사용자 요청)
    
    def print_positions_table(self):
        """포지션 상세 테이블 출력 (메인 루프에서 분리)"""
        if not self.active_positions:
            return
            
        try:
            print(f"📊 [실시간데이터] 활성 포지션 모니터링...")
            print("="*120)
            print(f"{'심볼':<12} {'수익률(레버리지/원금)':<32} {'진입가':<14} {'현재가':<14} {'수익금':<20} {'투자금':<10}")
            print("-"*120)
            
            total_entry_amount = 0
            total_profit_amount = 0
            
            # 포지션 데이터 수집 및 수익률 계산
            position_data = []
            
            for symbol, pos_info in self.active_positions.items():
                clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                entry_amount = pos_info.get('entry_amount', 0)
                leverage = pos_info.get('leverage', self.leverage)
                
                # entry_amount가 0이거나 없으면 현재 포지션 크기로부터 역산하여 계산
                if entry_amount == 0:
                    quantity = abs(pos_info.get('quantity', 0))
                    entry_price = pos_info.get('entry_price', 0)
                    
                    if quantity > 0 and entry_price > 0 and leverage > 0:
                        position_value = quantity * entry_price
                        entry_amount = position_value / leverage
                
                # 현재가 조회 및 수익률 계산
                try:
                    current_price = self.get_current_price(symbol)
                    entry_price = pos_info.get('entry_price', 0)
                    
                    # DCA 시스템의 평균가 우선 사용 (동기화 개선)
                    if self.dca_manager and symbol in self.dca_manager.positions:
                        dca_position = self.dca_manager.positions[symbol]
                        if dca_position.is_active:
                            entry_price = dca_position.average_price
                            # DCA 시스템의 실제 투자금액 사용
                            entry_amount = dca_position.total_amount_usdt if hasattr(dca_position, 'total_amount_usdt') else entry_amount
                    
                    if current_price and entry_price:
                        # 포지션 방향 확인 (롱/숏)
                        position_side = pos_info.get('side', 'long')
                        quantity = pos_info.get('quantity', 0)
                        
                        # 수량의 부호로 포지션 방향 판단 (음수 = 숏, 양수 = 롱)
                        if quantity < 0:
                            position_side = 'short'
                        elif quantity > 0:
                            position_side = 'long'
                        
                        # 가격 변동률 계산 (포지션 방향 고려)
                        if position_side == 'short':
                            # 숏 포지션: 가격 하락시 수익
                            price_change_pct = ((entry_price - current_price) / entry_price) * 100
                        else:
                            # 롱 포지션: 가격 상승시 수익
                            price_change_pct = ((current_price - entry_price) / entry_price) * 100
                        
                        profit_pct = price_change_pct  # 원금 수익률
                        leverage_profit_pct = price_change_pct * leverage  # 레버리지 수익률
                        # 실제 손익 금액 계산 (레버리지 기준 - 화면 표시와 일치)
                        profit_amount = entry_amount * (leverage_profit_pct / 100)
                    else:
                        profit_pct = 0
                        leverage_profit_pct = 0
                        profit_amount = 0
                        current_price = entry_price
                except:
                    profit_pct = 0
                    leverage_profit_pct = 0
                    profit_amount = 0
                    current_price = pos_info.get('entry_price', 0)
                
                total_entry_amount += entry_amount
                total_profit_amount += profit_amount
                
                # 포지션 데이터 저장 (수익률 포함)
                position_data.append({
                    'clean_symbol': clean_symbol,
                    'profit_pct': profit_pct,
                    'leverage_profit_pct': leverage_profit_pct,
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'profit_amount': profit_amount,
                    'entry_amount': entry_amount
                })
            
            # 레버리지 수익률 기준 내림차순 정렬 (수익률이 큰 순서대로)
            position_data.sort(key=lambda x: x['leverage_profit_pct'], reverse=True)
            
            # 정렬된 순서대로 출력
            for pos_data in position_data:
                clean_symbol = pos_data['clean_symbol']
                profit_pct = pos_data['profit_pct']
                leverage_profit_pct = pos_data['leverage_profit_pct']
                entry_price = pos_data['entry_price']
                current_price = pos_data['current_price']
                profit_amount = pos_data['profit_amount']
                entry_amount = pos_data['entry_amount']
                
                # 수익률 표시 (레버리지수익률(원금수익률) 형태)
                if leverage_profit_pct >= 0:
                    profit_str = f"\033[92m✅{leverage_profit_pct:+.1f}%({profit_pct:+.2f}%)\033[0m"  # 밝은 초록색
                else:
                    profit_str = f"\033[91m❌{leverage_profit_pct:+.1f}%({profit_pct:+.2f}%)\033[0m"   # 밝은 빨간색
                
                # 진입가와 현재가 표시 (간결하게)
                entry_price_str = f"${entry_price:.4f}" if entry_price < 1 else f"${entry_price:.2f}"
                current_price_str = f"${current_price:.4f}" if current_price < 1 else f"${current_price:.2f}"
                
                # 심볼명과 수익금에 색상 코드 추가 (가독성 향상)
                symbol_str = f"\033[93m{clean_symbol:<10}\033[0m"  # 밝은 노랑색
                
                # 수익금에도 색상 적용
                if profit_amount >= 0:
                    profit_amount_str = f"\033[92m${profit_amount:+7.2f}\033[0m"  # 초록색
                else:
                    profit_amount_str = f"\033[91m${profit_amount:+7.2f}\033[0m"  # 빨간색
                
                # 한 줄에 모든 정보 표시
                print(f"{symbol_str} {profit_str:<32} {entry_price_str:<14} {current_price_str:<14} {profit_amount_str:<20} ${entry_amount:>10.2f}")

            print("-"*120)
            # 레버리지 기준 총합 수익률 계산
            total_leverage_profit_pct = (total_profit_amount / total_entry_amount * 100) if total_entry_amount > 0 else 0
            total_original_profit_pct = total_leverage_profit_pct / self.leverage  # 원금 수익률
            
            # 레버리지 수익률(원금 수익률) 형태로 표시
            if total_profit_amount >= 0:
                total_color_str = f"\033[92m✅{total_leverage_profit_pct:+.1f}%({total_original_profit_pct:+.2f}%)\033[0m"  # 밝은 초록색
                total_profit_amount_str = f"\033[92m${total_profit_amount:+7.2f}\033[0m"  # 초록색
            else:
                total_color_str = f"\033[91m❌{total_leverage_profit_pct:+.1f}%({total_original_profit_pct:+.2f}%)\033[0m"   # 밝은 빨간색
                total_profit_amount_str = f"\033[91m${total_profit_amount:+7.2f}\033[0m"  # 빨간색
            
            # 총합 라벨도 노랑색으로 표시
            total_symbol_str = f"\033[93m{'총합':<10}\033[0m"  # 밝은 노랑색
            print(f"{total_symbol_str} {total_color_str:<32}   {'총계':<14} {'총계':<14} {total_profit_amount_str:<20} ${total_entry_amount:>10.2f}")
            print("="*120)
            
        except Exception as e:
            self.logger.error(f"포지션 테이블 출력 실패: {e}")
    
    def print_account_status(self):
        """계좌 상황 출력"""
        try:
            # 계좌 잔고 조회
            balance = self.exchange.fetch_balance()
            usdt_balance = balance['USDT']['total']
            usdt_free = balance['USDT']['free']
            usdt_used = usdt_balance - usdt_free
            
            # 선물 포지션 조회
            futures_positions = self.exchange.fetch_positions()
            open_positions = [pos for pos in futures_positions if pos['contracts'] > 0]
            
            print("\n" + "=" * 80)
            print(f"📊 계좌 상황 - {get_korea_time().strftime('%H:%M:%S')}")
            print("=" * 80)
            
            print(f"💰 USDT: 총 ${usdt_balance:.2f} | 가용 ${usdt_free:.2f} | 사용중 ${usdt_used:.2f}")
            print(f"📈 포지션: {len(open_positions)}개 활성")
            
            if open_positions:
                # 수익률 기준 정렬
                open_positions.sort(key=lambda x: x.get('percentage', 0) or 0, reverse=True)
                
                total_pnl = sum(pos.get('unrealizedPnl', 0) or 0 for pos in open_positions)
                
                # 상위 3개 포지션만 표시
                print(f"🏆 상위포지션: ", end="")
                for i, pos in enumerate(open_positions[:3]):
                    symbol = pos['symbol'].replace('/USDT:USDT', '')
                    pnl_percent = pos.get('percentage', 0) or 0
                    print(f"{symbol} {pnl_percent:+.1f}%", end=" | " if i < 2 else "")
                print()
                
                # 계좌 총 수익률
                account_pnl_percent = (total_pnl / usdt_balance) * 100 if usdt_balance > 0 else 0
                print(f"💎 총 수익: ${total_pnl:+.2f} ({account_pnl_percent:+.2f}%)")
            
            print("=" * 80)
            
        except Exception as e:
            self.logger.error(f"계좌 상황 출력 실패: {e}")
    
    def get_current_price(self, symbol):
        """현재가 조회"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            # 안전한 데이터 접근: 딕셔너리인지 확인
            if isinstance(ticker, dict) and 'last' in ticker:
                return ticker['last']
            elif isinstance(ticker, (list, tuple)) and len(ticker) > 0:
                # 리스트/튜플 형태인 경우 첫 번째 요소가 가격이라고 가정
                return float(ticker[0]) if ticker[0] is not None else None
            else:
                self.logger.warning(f"Unexpected ticker data structure for {symbol}: {type(ticker)}")
                return None
        except Exception as e:
            self.logger.warning(f"Failed to get current price for {symbol}: {e}")
            return None

    def _find_golden_cross(self, df, ma1_col, ma2_col, recent_n=30):
        """골든크로스 탐지 함수 (최근 n봉 내에서)"""
        try:
            if df is None or len(df) < 2:
                return False
            
            # 최근 n봉만 검사
            check_length = min(recent_n, len(df))
            recent_df = df.tail(check_length)
            
            if len(recent_df) < 2:
                return False
            
            # 각 인접한 캔들 쌍에서 골든크로스 찾기
            for i in range(len(recent_df) - 1):
                curr_idx = i
                next_idx = i + 1
                
                curr_row = recent_df.iloc[curr_idx]
                next_row = recent_df.iloc[next_idx]
                
                # 모든 값이 유효한지 확인
                if (pd.notna(curr_row[ma1_col]) and pd.notna(curr_row[ma2_col]) and
                    pd.notna(next_row[ma1_col]) and pd.notna(next_row[ma2_col])):
                    
                    # 골든크로스: 이전봉에서 ma1 < ma2, 다음봉에서 ma1 > ma2
                    if (curr_row[ma1_col] < curr_row[ma2_col] and 
                        next_row[ma1_col] > next_row[ma2_col]):
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"골든크로스 탐지 오류: {e}")
            return False

    def _find_dead_cross(self, df, ma1_col, ma2_col, recent_n=20):
        """데드크로스 탐지 함수 (최근 n봉 내에서)"""
        try:
            if df is None or len(df) < 2:
                return False
            
            # 최근 n봉만 검사
            check_length = min(recent_n, len(df))
            recent_df = df.tail(check_length)
            
            if len(recent_df) < 2:
                return False
            
            # 각 인접한 캔들 쌍에서 데드크로스 찾기
            for i in range(len(recent_df) - 1):
                curr_idx = i
                next_idx = i + 1
                
                curr_row = recent_df.iloc[curr_idx]
                next_row = recent_df.iloc[next_idx]
                
                # 모든 값이 유효한지 확인
                if (pd.notna(curr_row[ma1_col]) and pd.notna(curr_row[ma2_col]) and
                    pd.notna(next_row[ma1_col]) and pd.notna(next_row[ma2_col])):
                    
                    # 데드크로스: 이전봉에서 ma1 > ma2, 다음봉에서 ma1 < ma2
                    if (curr_row[ma1_col] > curr_row[ma2_col] and 
                        next_row[ma1_col] < next_row[ma2_col]):
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"데드크로스 탐지 오류: {e}")
            return False

    def on_websocket_kline_update(self, symbol: str, current_price: float, kline_data: dict, timeframe: str = '1m'):
        """
        WebSocket Kline 업데이트 콜백 함수 (멀티 타임프레임 지원)
        
        Args:
            symbol: 심볼명
            current_price: 현재가
            kline_data: Kline 데이터 딕셔너리
            timeframe: 타임프레임 (1m, 3m, 5m, 15m, 1h, 4h, 1d)
        """
        try:
            # WebSocket 버퍼가 없으면 초기화
            if not hasattr(self, '_websocket_kline_buffer'):
                self._websocket_kline_buffer = {}
            
            # 버퍼 키 생성 (symbol_timeframe)
            buffer_key = f"{symbol}_{timeframe}"
            
            # 해당 심볼-타임프레임 버퍼 초기화
            if buffer_key not in self._websocket_kline_buffer:
                self._websocket_kline_buffer[buffer_key] = []
            
            # 새로운 kline 데이터 추가
            self._websocket_kline_buffer[buffer_key].append(kline_data)
            
            # 타임프레임별 최대 보관 수량 설정 (4h는 REST API 필터링 전용)
            max_candles = {
                '1m': 1500,  # 1분봉: 25시간
                '3m': 500,   # 3분봉: 25시간
                '5m': 300,   # 5분봉: 25시간
                '15m': 200,  # 15분봉: 50시간
                '1h': 100,   # 1시간봉: 4일
                '1d': 30     # 일봉: 1개월
            }
            
            # 버퍼 크기 제한
            max_size = max_candles.get(timeframe, 500)
            if len(self._websocket_kline_buffer[buffer_key]) > max_size:
                self._websocket_kline_buffer[buffer_key] = self._websocket_kline_buffer[buffer_key][-max_size:]
            
            # 실시간 가격 모니터링 콜백 (1분봉만)
            if timeframe == '1m' and self.realtime_monitor:
                self.realtime_monitor.update_price(symbol, current_price, kline_data)
        
        except Exception as e:
            self.logger.error(f"WebSocket Kline 업데이트 실패 {symbol} {timeframe}: {e}")

    def get_websocket_kline_data(self, symbol: str, timeframe: str, limit: int = 1000):
        """
        WebSocket 버퍼에서 특정 심볼-타임프레임 데이터 조회 (python-binance WebSocket 전용)

        Args:
            symbol: 심볼명 (예: 'BTC/USDT:USDT')
            timeframe: 타임프레임
            limit: 최대 개수

        Returns:
            pandas.DataFrame: Kline 데이터 프레임
        """
        try:
            # ⚡ python-binance WebSocket 매니저에서 데이터 조회
            if not self.ws_kline_manager:
                return None

            # 심볼 형식 변환 (BTC/USDT:USDT -> BTCUSDT)
            ws_symbol = symbol.replace('/USDT:USDT', '').replace('/', '')
            if not ws_symbol.endswith('USDT'):
                ws_symbol = ws_symbol + 'USDT'

            # WebSocket 매니저에서 데이터 가져오기
            kline_data = self.ws_kline_manager.get_kline_buffer(ws_symbol, timeframe, limit)

            # DataFrame인 경우 처리
            if isinstance(kline_data, pd.DataFrame):
                if not kline_data.empty and len(kline_data) >= 1:  # 테스트용: 최소 1개만 있으면 사용
                    return kline_data
                else:
                    return None
            # 리스트인 경우 처리 (이전 방식과의 호환성)
            elif kline_data and len(kline_data) >= min(limit, 3):
                # DataFrame 형태로 변환 (기존 방식과 호환)
                df_data = []
                for candle in kline_data:
                    if isinstance(candle, dict):
                        df_data.append([
                            candle['timestamp'],
                            candle['open'],
                            candle['high'],
                            candle['low'],
                            candle['close'],
                            candle['volume']
                        ])
                    else:
                        # 배열 형태인 경우
                        df_data.append(candle)

                df = pd.DataFrame(df_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

                return df

            return None

        except Exception as e:
            self.logger.error(f"WebSocket 데이터 조회 실패 {symbol} {timeframe}: {e}")
            return None


def main():
    """메인 실행 함수 - invincible_surge_entry_strategy.py와 동일한 스캔 방식"""
    logger = setup_logging()
    
    # 바이낸스 설정
    api_key = BinanceConfig.API_KEY if HAS_BINANCE_CONFIG else None
    secret_key = BinanceConfig.SECRET_KEY if HAS_BINANCE_CONFIG else None
    
    # 전략 초기화
    strategy = OneMinuteSurgeEntryStrategy(api_key, secret_key, sandbox=False)
    
    
    try:
        last_position_monitor = time.time()
        
        while True:
            kst_now = get_korea_time()
            current_time = kst_now.strftime('%H:%M:%S')
            
            print(f"\n" + "="*60)
            print(f"🔍 [1분봉 급등 초입 전략] 시장 스캔 시작 - {current_time}")
            print("="*60)
            
            # 🔄 실시간 포지션 동기화 (매 스캔마다)
            try:
                strategy.sync_positions_with_exchange()
            except Exception as e:
                print(f"⚠️ 포지션 동기화 실패: {e}")
            
            # 📋 DCA 지정가 주문 상태 확인 및 업데이트
            try:
                if strategy.dca_manager:
                    limit_order_result = strategy.dca_manager.check_and_update_limit_orders()
                    if limit_order_result.get('success') and limit_order_result.get('updated_count', 0) > 0:
                        print(f"✅ DCA 지정가 주문 {limit_order_result['updated_count']}개 업데이트됨")
            except Exception as e:
                print(f"⚠️ DCA 지정가 주문 확인 실패: {e}")
            
            # 현재 계좌 포지션 간략 정보만 표시 (상세 테이블은 주기적으로 표시)
            if strategy.active_positions:
                print(f"📊 [포지션 현황] {len(strategy.active_positions)}개 활성")
                # 최초 실행이거나 10초마다 상세 테이블 출력
                if not hasattr(strategy, '_first_run_done'):
                    strategy._first_run_done = True
                    strategy.print_positions_table()
            else:
                print(f"📊 [계좌포지션] 보유중: 없음")
            
            # 심볼 필터링 및 배치 스캔
            # 🚨 디버그: 메인 루프 실행 확인
            symbols = strategy.get_filtered_symbols()
            
            if not symbols:
                pass  # 메시지는 get_filtered_symbols()에서 이미 출력됨
            else:
                # 🎯 필터링된 심볼들을 동적으로 WebSocket에 구독
                print(f"🔄 [메인루프] 구독 업데이트 호출 시작: {len(symbols)}개 심볼")
                strategy.update_websocket_subscriptions(symbols)
                print(f"✅ [메인루프] 구독 업데이트 호출 완료")

                # 🚀 최적화된 WebSocket 스캔 또는 기존 스캔 선택
                print(f"⚡ 스캔 시작: {len(symbols)}개 심볼")
                
                # 🔍 임시 디버깅: 스캔 상태 확인
                scan_count = 0
                skip_count = 0

                try:
                    # WebSocket 스캐너를 기본으로 사용 (IP 밴 방지 및 최대 성능)
                    # WebSocket 매니저가 있으면 항상 WebSocket 모드 사용
                    if strategy.ws_kline_manager:
                        # ⚡ WebSocket 전용 모드: 15m 필터링 사용 (4h 대체, REST API 제거)
                        # 3m, 5m, 15m, 1d 데이터로만 스캔
                        print("⚡ WebSocket 전용 스캔 모드 (15m 필터링 사용)")
                        all_signals = strategy.scan_symbols(symbols)
                        print(f"✅ WebSocket 스캔 완료: {len(all_signals)}개 신호 발견")
                    else:
                        # WebSocket 스캐너 비활성화 시에만 기존 방식 사용
                        print("⚠️ WebSocket 스캐너 비활성화 - 기존 API 스캔 사용 (IP 밴 위험)")
                        all_signals = strategy.scan_symbols(symbols)
                        print(f"✅ API 스캔 완료: {len(all_signals)}개 신호 발견")
                        
                except Exception as e:
                    print(f"❌ 스캔 실패: {e}")
                    all_signals = []
            
            # 실시간 포지션 모니터링 (5초마다 - 긴급청산용)
            current_time_seconds = time.time()
            if strategy.active_positions:  # 활성 포지션이 있을 때만
                if (current_time_seconds - last_position_monitor) >= 3:  # 3초마다 실시간 체크
                    strategy.monitor_positions_realtime()
                    last_position_monitor = current_time_seconds
                
                # 10초마다 상세 모니터링 (기술적 분석 포함)
                if int(current_time_seconds) % 10 == 0:
                    strategy.monitor_positions_detailed()
            else:
                # 포지션 없을 때는 1분마다만 체크
                if (current_time_seconds - last_position_monitor) >= 60:
                    last_position_monitor = current_time_seconds
            
            # 🎯 DCA 지정가 주문 모니터링 (check_pending_limit_orders()로 자동 처리됨)
            # DCA 주문 체결 확인은 각 포지션 모니터링 시 check_pending_limit_orders()에서 자동으로 처리
            
            # 절반하락 청산 시스템 제거됨 (사용자 요청)
            
            # 주기적 출력을 위한 타이머 초기화
            if not hasattr(strategy, '_last_stats_time'):
                strategy._last_stats_time = 0
                strategy._last_positions_table_time = 0
                strategy._last_account_status_time = 0
            
            # 250ms 모드: 통계는 5초마다만 출력 (화면 안정성)
            if current_time_seconds - strategy._last_stats_time >= 5:
                strategy.print_daily_stats()
                strategy._last_stats_time = current_time_seconds
            
            # 포지션 상세 테이블은 10초마다 출력 
            if strategy.active_positions and (current_time_seconds - strategy._last_positions_table_time >= 10):
                strategy.print_positions_table()
                strategy._last_positions_table_time = current_time_seconds
            
            # 계좌 요약 상황은 30초마다 출력
            elif current_time_seconds - strategy._last_account_status_time >= 30:
                strategy.print_account_status()
                strategy._last_account_status_time = current_time_seconds
            
            # 다음 스캔까지 대기 (웹소켓 기반 250ms 초고속 모드)
            print(f"\n🚀 다음 스캔까지 250ms 대기...")
            time.sleep(0.25)  # 250ms 대기 (웹소켓 기반 극한 속도)
                
    except KeyboardInterrupt:
        print("\n🛑 전략 종료됨 (Ctrl+C)")

    except Exception as e:
        print(f"❌ 전략 실행 중 오류: {e}")

    finally:
        # 🚀 WebSocket 시스템 종료
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            try:
                print("[WebSocket] 종료 중...")
                strategy.ws_kline_manager.shutdown()
                print("[WebSocket] ✅ 정상 종료 완료")
            except Exception as ws_shutdown_error:
                print(f"[WebSocket] ⚠️ 종료 중 오류: {ws_shutdown_error}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()