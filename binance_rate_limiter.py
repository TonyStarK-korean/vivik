# -*- coding: utf-8 -*-
"""
Binance API Rate Limiter
완전한 바이낸스 API 율제한 관리 시스템

Rate Limits:
- IP 기준: 1분당 1200 요청 (weight 곱셈 적용)
- UID 기준: 독립적 관리
- 429 응답: 백오프 의무화
- 418 응답: IP 차단 (2분~3일)

Features:
- 요청 가중치 자동 추적
- 429/418 자동 감지 및 백오프
- Retry-After 헤더 처리
- 지수 백오프 시스템
- 캐싱 최적화
"""

import time
import logging
from datetime import datetime, timedelta
from collections import deque, defaultdict
from typing import Dict, Optional, Callable, Any
import threading
import json
import os


class BinanceRateLimiter:
    """바이낸스 API 율제한 관리자"""
    
    # 엔드포인트별 가중치 정보 (주요 엔드포인트)
    ENDPOINT_WEIGHTS = {
        # 티커 관련
        '/fapi/v1/ticker/24hr': 1,  # 개별 심볼
        '/fapi/v2/ticker/24hr': 40,  # 모든 심볼
        '/fapi/v1/ticker/price': 1,  # 개별 심볼
        '/fapi/v2/ticker/price': 2,  # 모든 심볼
        
        # OHLCV 관련
        '/fapi/v1/klines': 1,  # 기본 weight
        '/fapi/v1/continuousKlines': 1,
        
        # 계좌 정보
        '/fapi/v2/account': 5,
        '/fapi/v2/positionRisk': 5,
        '/fapi/v1/openOrders': 1,
        
        # 주문 관련
        '/fapi/v1/order': 1,  # GET/POST/DELETE
        '/fapi/v1/allOpenOrders': 1,  # 특정 심볼
        '/fapi/v1/openOrder': 1,
        
        # 기본값
        'default': 1
    }
    
    def __init__(self, logger=None, premium_mode=False, custom_limits=None):
        self.logger = logger or logging.getLogger(__name__)
        
        # 프리미엄 모드 설정
        self._premium_mode = premium_mode
        
        # Rate limit 상태
        self._rate_limited = False
        self._ban_until = None  # IP 차단 해제 시간
        self._last_429_time = None
        self._retry_after = 0
        
        # 요청 기록 (1분 윈도우)
        self._request_times = deque()
        self._weight_history = deque()
        self._current_weight = 0
        
        # 🚀 프리미엄 모드별 한계 설정
        if custom_limits:
            self._max_weight_per_minute = custom_limits.get('weight_per_minute', 1200)
            self._max_orders_per_second = custom_limits.get('orders_per_second', 10)
            self._max_orders_per_day = custom_limits.get('orders_per_day', 200000)
        elif premium_mode:
            # 프리미엄 API 한계 (실제 한계보다 안전 마진 적용)
            self._max_weight_per_minute = 5400  # 6000의 90%
            self._max_orders_per_second = 90    # 100의 90%
            self._max_orders_per_day = 1800000  # 2M의 90%
            self.logger.info("🌟 프리미엄 모드 활성화 - 5배 향상된 Rate Limit")
        else:
            # 기본 API 한계 - 극도로 보수적 설정 (IP 밴 완전 방지)
            self._max_weight_per_minute = 200   # 1200의 16% (극도로 보수적)
            self._max_orders_per_second = 2     # 10의 20%
            self._max_orders_per_day = 40000    # 200K의 20%
        
        # 백오프 관리
        self._consecutive_429s = 0
        self._backoff_multiplier = 1.0
        
        # 스레드 안전성
        self._lock = threading.RLock()
        
        # 에러 통계
        self._error_stats = defaultdict(int)
        self._last_reset = time.time()
        
        # 캐시 관리
        self._response_cache = {}
        self._cache_ttl = {}
        
        # 상태 저장/로드
        self._state_file = 'binance_rate_limiter_state.json'
        self._load_state()
        
        # 프리미엄 모드별 최적화 설정
        if self._premium_mode:
            # 프리미엄 모드: 더 공격적인 캐싱과 배치 처리
            self._cache_ttl_multiplier = 0.5  # 캐시 TTL 50% 단축 (더 실시간)
            self._safety_margin = 0.95  # 95% 사용 (더 공격적)
            self.logger.info("🌟 프리미엄 최적화: 실시간성↑, 처리량 5배↑")
        else:
            # 기본 모드: 보수적 설정
            self._cache_ttl_multiplier = 1.0
            self._safety_margin = 0.90  # 90% 사용 (안전)
        
        mode_str = "프리미엄" if self._premium_mode else "기본"
        self.logger.info(f"🛡️ Binance Rate Limiter 초기화 완료 ({mode_str} 모드)")
    
    def _get_endpoint_weight(self, endpoint_path: str, params: dict = None) -> int:
        """엔드포인트별 요청 가중치 계산"""
        # 파라미터 기반 가중치 조정
        weight = self.ENDPOINT_WEIGHTS.get(endpoint_path, self.ENDPOINT_WEIGHTS['default'])
        
        # klines는 limit 기반으로 가중치 조정
        if '/klines' in endpoint_path and params:
            limit = params.get('limit', 500)
            # limit에 따른 가중치 증가
            if limit > 1000:
                weight = 2
            elif limit > 500:
                weight = 1
        
        # 모든 심볼 조회는 높은 가중치
        if params and not params.get('symbol'):
            weight *= 20  # 전체 심볼 조회 패널티
        
        return weight
    
    def _clean_old_requests(self):
        """1분 이전 요청 기록 정리"""
        current_time = time.time()
        cutoff_time = current_time - 60
        
        # 오래된 요청 제거
        while self._request_times and self._request_times[0] < cutoff_time:
            self._request_times.popleft()
            if self._weight_history:
                self._weight_history.popleft()
        
        # 현재 가중치 재계산
        self._current_weight = sum(self._weight_history)
    
    def _update_rate_limit_state(self, response_headers: dict):
        """응답 헤더에서 rate limit 상태 업데이트"""
        try:
            # 서버에서 제공하는 rate limit 정보
            if 'x-mbx-used-weight-1m' in response_headers:
                server_weight = int(response_headers['x-mbx-used-weight-1m'])
                # 서버 가중치와 동기화
                if abs(self._current_weight - server_weight) > 100:
                    self.logger.warning(f"가중치 동기화: 로컬({self._current_weight}) vs 서버({server_weight})")
                    self._current_weight = server_weight
            
            # Retry-After 헤더 처리
            if 'retry-after' in response_headers:
                self._retry_after = int(response_headers['retry-after'])
                self.logger.warning(f"Retry-After 수신: {self._retry_after}초")
        except (ValueError, KeyError) as e:
            self.logger.debug(f"헤더 파싱 오류: {e}")
    
    def _handle_rate_limit_error(self, status_code: int, response_headers: dict):
        """Rate limit 에러 처리"""
        current_time = time.time()
        
        if status_code == 429:
            # Too Many Requests
            self._consecutive_429s += 1
            self._last_429_time = current_time
            self._error_stats['429'] += 1
            
            # Retry-After 헤더에서 대기 시간 가져오기
            retry_after = int(response_headers.get('retry-after', 60))
            self._retry_after = retry_after
            
            # 백오프 배율 증가
            self._backoff_multiplier = min(self._backoff_multiplier * 1.5, 10.0)
            
            self.logger.error(f"🚨 429 에러 발생 (연속 {self._consecutive_429s}회) - {retry_after}초 대기")
            
            # 임시 rate limit 활성화
            self._rate_limited = True
            
        elif status_code == 418:
            # IP 차단
            self._error_stats['418'] += 1
            retry_after = int(response_headers.get('retry-after', 3600))  # 기본 1시간
            self._ban_until = current_time + retry_after
            self._rate_limited = True
            
            self.logger.critical(f"🔒 IP 차단 (418) - {retry_after}초 차단됨 (해제: {datetime.fromtimestamp(self._ban_until)})")
            
            # 상태 저장
            self._save_state()
    
    def is_rate_limited(self) -> bool:
        """현재 rate limit 상태 확인"""
        current_time = time.time()
        
        # IP 차단 확인
        if self._ban_until and current_time < self._ban_until:
            remaining = int(self._ban_until - current_time)
            self.logger.debug(f"IP 차단 중 (남은 시간: {remaining}초)")
            return True
        elif self._ban_until and current_time >= self._ban_until:
            # 차단 해제
            self.logger.info("🔓 IP 차단 해제됨")
            self._ban_until = None
            self._rate_limited = False
            self._consecutive_429s = 0
            self._backoff_multiplier = 1.0
        
        # 429 에러 후 백오프 확인
        if self._last_429_time and self._retry_after > 0:
            elapsed = current_time - self._last_429_time
            if elapsed < self._retry_after:
                remaining = int(self._retry_after - elapsed)
                self.logger.debug(f"429 백오프 중 (남은 시간: {remaining}초)")
                return True
            else:
                # 백오프 완료
                self.logger.info("✅ 429 백오프 완료 - API 호출 재개 가능")
                self._rate_limited = False
                self._retry_after = 0
                self._consecutive_429s = max(0, self._consecutive_429s - 1)
        
        # 가중치 기반 제한 확인
        with self._lock:
            self._clean_old_requests()
            if self._current_weight >= self._max_weight_per_minute * 0.9:  # 90% 도달시 제한
                self.logger.warning(f"가중치 한계 근접: {self._current_weight}/{self._max_weight_per_minute}")
                return True
        
        return False
    
    def wait_if_needed(self, endpoint_path: str, params: dict = None) -> bool:
        """필요시 대기 후 요청 허용 여부 반환"""
        if self.is_rate_limited():
            # 대기 시간 계산
            wait_time = self._calculate_wait_time()
            if wait_time > 0:
                self.logger.info(f"⏳ Rate limit 대기: {wait_time:.1f}초")
                time.sleep(wait_time)
            
            # 대기 후 재검사
            if self.is_rate_limited():
                self.logger.error("⛔ Rate limit 지속됨 - 요청 거부")
                return False
        
        # 가중치 예약
        weight = self._get_endpoint_weight(endpoint_path, params)
        with self._lock:
            self._clean_old_requests()
            # 요청 후 가중치가 한계를 초과하는지 확인
            if self._current_weight + weight > self._max_weight_per_minute:
                self.logger.warning(f"가중치 한계 초과 예상: {self._current_weight + weight}/{self._max_weight_per_minute}")
                return False
        
        return True
    
    def _calculate_wait_time(self) -> float:
        """적절한 대기 시간 계산"""
        current_time = time.time()
        
        # IP 차단 대기 시간
        if self._ban_until and current_time < self._ban_until:
            return self._ban_until - current_time
        
        # 429 백오프 대기 시간
        if self._last_429_time and self._retry_after > 0:
            elapsed = current_time - self._last_429_time
            remaining = self._retry_after - elapsed
            if remaining > 0:
                return remaining * self._backoff_multiplier
        
        # 가중치 기반 대기 시간 (가장 오래된 요청이 만료될 때까지)
        if self._request_times:
            oldest_request = self._request_times[0]
            wait_until = oldest_request + 60  # 1분 후 만료
            wait_time = max(0, wait_until - current_time)
            return wait_time
        
        return 0
    
    def record_request(self, endpoint_path: str, params: dict = None, response_headers: dict = None):
        """요청 기록 및 가중치 추가"""
        current_time = time.time()
        weight = self._get_endpoint_weight(endpoint_path, params)
        
        with self._lock:
            self._request_times.append(current_time)
            self._weight_history.append(weight)
            self._current_weight += weight
            self._clean_old_requests()
        
        # 응답 헤더 처리
        if response_headers:
            self._update_rate_limit_state(response_headers)
        
        self.logger.debug(f"요청 기록: {endpoint_path} (weight: {weight}, 총합: {self._current_weight})")
    
    def record_error(self, status_code: int, response_headers: dict = None):
        """에러 응답 기록"""
        if status_code in [429, 418]:
            self._handle_rate_limit_error(status_code, response_headers or {})
        else:
            self._error_stats[str(status_code)] += 1
    
    def get_cache(self, cache_key: str) -> Optional[Any]:
        """캐시에서 데이터 조회"""
        if cache_key in self._response_cache:
            data, cached_time, ttl = self._response_cache[cache_key]
            if time.time() - cached_time < ttl:
                self.logger.debug(f"캐시 히트: {cache_key}")
                return data
            else:
                # 만료된 캐시 삭제
                del self._response_cache[cache_key]
        return None
    
    def set_cache(self, cache_key: str, data: Any, ttl: int = 60):
        """캐시에 데이터 저장"""
        self._response_cache[cache_key] = (data, time.time(), ttl)
        self.logger.debug(f"캐시 저장: {cache_key} (TTL: {ttl}초)")
        
        # 캐시 크기 제한 (메모리 관리)
        if len(self._response_cache) > 1000:
            # 가장 오래된 캐시 10개 삭제
            oldest_keys = sorted(self._response_cache.keys(), 
                               key=lambda k: self._response_cache[k][1])[:10]
            for key in oldest_keys:
                del self._response_cache[key]
    
    def get_status(self) -> dict:
        """현재 rate limiter 상태 반환"""
        current_time = time.time()
        
        # IP 차단 상태
        ban_status = "차단됨" if self._ban_until and current_time < self._ban_until else "정상"
        ban_remaining = max(0, self._ban_until - current_time) if self._ban_until else 0
        
        # 429 백오프 상태
        backoff_remaining = 0
        if self._last_429_time and self._retry_after > 0:
            elapsed = current_time - self._last_429_time
            backoff_remaining = max(0, self._retry_after - elapsed)
        
        with self._lock:
            self._clean_old_requests()
            
            return {
                'rate_limited': self.is_rate_limited(),
                'current_weight': self._current_weight,
                'max_weight': self._max_weight_per_minute,
                'weight_usage_pct': (self._current_weight / self._max_weight_per_minute) * 100,
                'requests_per_minute': len(self._request_times),
                'ban_status': ban_status,
                'ban_remaining_seconds': int(ban_remaining),
                'backoff_remaining_seconds': int(backoff_remaining),
                'consecutive_429s': self._consecutive_429s,
                'backoff_multiplier': self._backoff_multiplier,
                'error_stats': dict(self._error_stats),
                'cache_size': len(self._response_cache)
            }
    
    def reset_stats(self):
        """통계 리셋"""
        with self._lock:
            self._error_stats.clear()
            self._last_reset = time.time()
        self.logger.info("📊 Rate limiter 통계 리셋됨")
    
    def _save_state(self):
        """현재 상태를 파일로 저장"""
        try:
            state = {
                'ban_until': self._ban_until,
                'last_429_time': self._last_429_time,
                'retry_after': self._retry_after,
                'consecutive_429s': self._consecutive_429s,
                'backoff_multiplier': self._backoff_multiplier,
                'error_stats': dict(self._error_stats)
            }
            
            with open(self._state_file, 'w') as f:
                json.dump(state, f)
            
            self.logger.debug("Rate limiter 상태 저장됨")
        except Exception as e:
            self.logger.error(f"상태 저장 실패: {e}")
    
    def _load_state(self):
        """파일에서 상태 로드"""
        try:
            if os.path.exists(self._state_file):
                with open(self._state_file, 'r') as f:
                    state = json.load(f)
                
                self._ban_until = state.get('ban_until')
                self._last_429_time = state.get('last_429_time')
                self._retry_after = state.get('retry_after', 0)
                self._consecutive_429s = state.get('consecutive_429s', 0)
                self._backoff_multiplier = state.get('backoff_multiplier', 1.0)
                self._error_stats.update(state.get('error_stats', {}))
                
                self.logger.info("Rate limiter 상태 복원됨")
        except Exception as e:
            self.logger.error(f"상태 로드 실패: {e}")


class RateLimitedExchange:
    """Rate Limiter가 적용된 Exchange 래퍼"""
    
    def __init__(self, exchange, logger=None):
        self.exchange = exchange
        self.rate_limiter = BinanceRateLimiter(logger)
        self.logger = logger or logging.getLogger(__name__)
    
    def _safe_api_call(self, method_name: str, *args, **kwargs):
        """Rate limit을 고려한 안전한 API 호출"""
        # 엔드포인트 경로 추정
        endpoint_path = self._get_endpoint_path(method_name, args, kwargs)
        params = self._extract_params(args, kwargs)
        
        # 캐시 확인
        cache_args = str(sorted(args)) if args else ""
        cache_kwargs = str(sorted(kwargs.items())) if kwargs else ""
        cache_key = f"{method_name}:{hash(cache_args + cache_kwargs)}"
        cached_result = self.rate_limiter.get_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        # Rate limit 확인 및 대기
        if not self.rate_limiter.wait_if_needed(endpoint_path, params):
            raise Exception(f"Rate limit 초과로 요청 거부됨: {method_name}")
        
        try:
            # 실제 API 호출
            method = getattr(self.exchange, method_name)
            result = method(*args, **kwargs)
            
            # 성공시 요청 기록
            self.rate_limiter.record_request(endpoint_path, params)
            
            # 캐시 저장 (응답 타입에 따라 TTL 조정)
            ttl = self._get_cache_ttl(method_name)
            self.rate_limiter.set_cache(cache_key, result, ttl)
            
            return result
            
        except Exception as e:
            # 에러 응답 처리
            status_code = getattr(e, 'response', {}).get('status_code') or \
                         getattr(e, 'status_code', 0)
            
            response_headers = getattr(e, 'response', {}).get('headers', {})
            
            if status_code:
                self.rate_limiter.record_error(status_code, response_headers)
            
            # Rate limit 에러는 별도 처리
            if status_code in [429, 418]:
                error_msg = f"Rate limit 에러 ({status_code}): {e}"
                self.logger.error(error_msg)
                raise Exception(error_msg)
            
            # 다른 에러는 그대로 전파
            raise e
    
    def _get_endpoint_path(self, method_name: str, args, kwargs) -> str:
        """메서드명으로부터 엔드포인트 경로 추정"""
        endpoint_mapping = {
            'fetch_ohlcv': '/fapi/v1/klines',
            'fetch_ticker': '/fapi/v1/ticker/24hr',
            'fetch_tickers': '/fapi/v2/ticker/24hr',
            'fetch_order_book': '/fapi/v1/depth',
            'fetch_trades': '/fapi/v1/aggTrades',
            'fetch_balance': '/fapi/v2/account',
            'fetch_positions': '/fapi/v2/positionRisk',
            'fetch_orders': '/fapi/v1/allOrders',
            'fetch_open_orders': '/fapi/v1/openOrders',
            'create_order': '/fapi/v1/order',
            'cancel_order': '/fapi/v1/order',
        }
        return endpoint_mapping.get(method_name, 'default')
    
    def _extract_params(self, args, kwargs) -> dict:
        """API 호출 파라미터 추출"""
        params = {}
        
        # args에서 심볼 추출 (첫 번째 인자가 보통 심볼)
        if args:
            params['symbol'] = args[0]
        
        # kwargs에서 주요 파라미터 추출
        for key in ['symbol', 'limit', 'since', 'timeframe']:
            if key in kwargs:
                params[key] = kwargs[key]
        
        return params
    
    def _get_cache_ttl(self, method_name: str) -> int:
        """메서드별 캐시 TTL 설정"""
        ttl_mapping = {
            'fetch_ticker': 5,      # 5초 (빠른 변화)
            'fetch_tickers': 10,    # 10초 
            'fetch_ohlcv': 30,      # 30초 (OHLCV 데이터)
            'fetch_balance': 60,    # 60초 (계좌 정보)
            'fetch_positions': 30,  # 30초 (포지션 정보)
            'fetch_orders': 120,    # 2분 (주문 내역)
        }
        return ttl_mapping.get(method_name, 60)  # 기본 60초
    
    def __getattr__(self, name):
        """Exchange 메서드에 대한 프록시"""
        if hasattr(self.exchange, name):
            # API 호출 메서드인지 확인
            method = getattr(self.exchange, name)
            if callable(method) and (name.startswith('fetch_') or 
                                   name.startswith('create_') or 
                                   name.startswith('cancel_') or
                                   name.startswith('edit_')):
                # Rate limit이 적용된 래퍼 반환
                def rate_limited_method(*args, **kwargs):
                    return self._safe_api_call(name, *args, **kwargs)
                return rate_limited_method
            else:
                # 일반 속성/메서드는 그대로 반환
                return method
        else:
            raise AttributeError(f"'{type(self.exchange).__name__}' object has no attribute '{name}'")


# 사용 예시 및 테스트
if __name__ == "__main__":
    import ccxt
    
    # 로깅 설정
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Rate limiter 테스트
    rate_limiter = BinanceRateLimiter(logger)
    
    # 상태 출력
    status = rate_limiter.get_status()
    print("Rate Limiter 상태:")
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    # Exchange 래퍼 테스트
    try:
        exchange = ccxt.binance({
            'apiKey': 'your-api-key',
            'secret': 'your-secret',
            'sandbox': True,  # 테스트넷 사용
        })
        
        rate_limited_exchange = RateLimitedExchange(exchange, logger)
        
        # 테스트 호출
        # tickers = rate_limited_exchange.fetch_tickers()
        # print(f"티커 수: {len(tickers)}")
        
    except Exception as e:
        print(f"Exchange 테스트 실패: {e}")