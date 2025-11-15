# -*- coding: utf-8 -*-
"""
Binance API Rate Limiter
완전한 바이낸스 API 율제한 관리 시스템

Rate Limits:
- IP 기준: 1per minute 1200 요청 (weight 곱셈 적용)
- UID 기준: 독립적 관리
- 429 Response: 백오프 의무화
- 418 Response: IP 차단 (2분~3일)

Features:
- 요청 weight 자동 추적
- 429/418 자동 감지 및 백오프
- Retry-After 헤더 Process
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
    """바이낸스 API 율제한 Admin"""
    
    # 엔드포인트별 weight Info (주요 엔드포인트)
    ENDPOINT_WEIGHTS = {
        # 티커 관련
        '/fapi/v1/ticker/24hr': 1,  # count별 Symbol
        '/fapi/v2/ticker/24hr': 40,  # 모든 Symbol
        '/fapi/v1/ticker/price': 1,  # count별 Symbol
        '/fapi/v2/ticker/price': 2,  # 모든 Symbol
        
        # OHLCV 관련
        '/fapi/v1/klines': 1,  # 기본 weight
        '/fapi/v1/continuousKlines': 1,
        
        # 계좌 Info
        '/fapi/v2/account': 5,
        '/fapi/v2/positionRisk': 5,
        '/fapi/v1/openOrders': 1,
        
        # 주문 관련
        '/fapi/v1/order': 1,  # GET/POST/DELETE
        '/fapi/v1/allOpenOrders': 1,  # 특정 Symbol
        '/fapi/v1/openOrder': 1,
        
        # 기본값
        'default': 1
    }
    
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        
        # Rate limit status
        self._rate_limited = False
        self._ban_until = None  # IP 차단 Release Time
        self._last_429_time = None
        self._retry_after = 0
        
        # 요청 기록 (1분 윈도우) - 더 엄격한 제한
        self._request_times = deque()
        self._weight_history = deque()
        self._current_weight = 0
        self._max_weight_per_minute = 1000  # 1200 → 1000으로 더 보수적 설정
        
        # 백오프 관리
        self._consecutive_429s = 0
        self._backoff_multiplier = 1.0
        
        # 스레드 안전성
        self._lock = threading.RLock()
        
        # 에러 통계
        self._error_stats = defaultdict(int)
        self._last_reset = time.time()
        
        # Cache 관리
        self._response_cache = {}
        self._cache_ttl = {}
        
        # Status Save/Load
        self._state_file = 'binance_rate_limiter_state.json'
        self._load_state()
        
        self.logger.info("🛡️ Binance Rate Limiter Initialization complete")
    
    def _get_endpoint_weight(self, endpoint_path: str, params: dict = None) -> int:
        """엔드포인트별 요청 weight 계산"""
        # 파라미터 기반 weight 조정
        weight = self.ENDPOINT_WEIGHTS.get(endpoint_path, self.ENDPOINT_WEIGHTS['default'])
        
        # klines는 limit 기반으로 weight 조정
        if '/klines' in endpoint_path and params:
            limit = params.get('limit', 500)
            # limit에 따른 weight 증가
            if limit > 1000:
                weight = 2
            elif limit > 500:
                weight = 1
        
        # 모든 Symbol 조times는 높은 weight
        if params and not params.get('symbol'):
            weight *= 20  # 전체 Symbol 조times 패널티
        
        return weight
    
    def _clean_old_requests(self):
        """1분 이전 요청 기록 정리"""
        current_time = time.time()
        cutoff_time = current_time - 60
        
        # 오래된 요청 Remove
        while self._request_times and self._request_times[0] < cutoff_time:
            self._request_times.popleft()
            if self._weight_history:
                self._weight_history.popleft()
        
        # Current weight 재계산
        self._current_weight = sum(self._weight_history)
    
    def _update_rate_limit_state(self, response_headers: dict):
        """Response 헤더에서 rate limit Status Update"""
        try:
            # 서버에서 제공하는 rate limit Info
            if 'x-mbx-used-weight-1m' in response_headers:
                server_weight = int(response_headers['x-mbx-used-weight-1m'])
                # 서버 weight와 Sync
                if abs(self._current_weight - server_weight) > 100:
                    self.logger.warning(f"weight Sync: 로컬({self._current_weight}) vs 서버({server_weight})")
                    self._current_weight = server_weight
            
            # Retry-After 헤더 Process
            if 'retry-after' in response_headers:
                self._retry_after = int(response_headers['retry-after'])
                self.logger.warning(f"Retry-After Received: {self._retry_after}초")
        except (ValueError, KeyError) as e:
            self.logger.debug(f"헤더 파싱 Error: {e}")
    
    def _handle_rate_limit_error(self, status_code: int, response_headers: dict):
        """Rate limit 에러 Process"""
        current_time = time.time()
        
        if status_code == 429:
            # Too Many Requests
            self._consecutive_429s += 1
            self._last_429_time = current_time
            self._error_stats['429'] += 1
            
            # Retry-After 헤더에서 대기 Time 가져오기 (더 보수적)
            retry_after = int(response_headers.get('retry-after', 180))  # 기본 3분 대기
            self._retry_after = max(retry_after, 120)  # 최소 2분 대기
            
            # 백오프 배율 증가 (더 공격적)
            self._backoff_multiplier = min(self._backoff_multiplier * 2.0, 20.0)
            
            self.logger.error(f"🚨 429 Error 발생 (연속 {self._consecutive_429s}times) - {retry_after}초 Waiting")
            
            # 임시 rate limit Active화
            self._rate_limited = True
            
        elif status_code == 418:
            # IP 차단
            self._error_stats['418'] += 1
            retry_after = int(response_headers.get('retry-after', 3600))  # 기본 1Time
            self._ban_until = current_time + retry_after
            self._rate_limited = True
            
            self.logger.critical(f"🔒 IP 차단 (418) - {retry_after}초 차단됨 (Release: {datetime.fromtimestamp(self._ban_until)})")
            
            # Status Save
            self._save_state()
    
    def is_rate_limited(self) -> bool:
        """Current rate limit Status Confirm"""
        current_time = time.time()
        
        # IP 차단 Confirm
        if self._ban_until and current_time < self._ban_until:
            remaining = int(self._ban_until - current_time)
            self.logger.debug(f"IP 차단 중 (남은 Time: {remaining}초)")
            return True
        elif self._ban_until and current_time >= self._ban_until:
            # 차단 Release
            self.logger.info("🔓 IP 차단 Release됨")
            self._ban_until = None
            self._rate_limited = False
            self._consecutive_429s = 0
            self._backoff_multiplier = 1.0
        
        # 429 에러 후 백오프 Confirm
        if self._last_429_time and self._retry_after > 0:
            elapsed = current_time - self._last_429_time
            if elapsed < self._retry_after:
                remaining = int(self._retry_after - elapsed)
                self.logger.debug(f"429 백오프 중 (남은 Time: {remaining}초)")
                return True
            else:
                # 백오프 Complete
                self.logger.info("✅ 429 백오프 Complete - API calls 재count 가능")
                self._rate_limited = False
                self._retry_after = 0
                self._consecutive_429s = max(0, self._consecutive_429s - 1)
        
        # weight 기반 제한 Confirm (더 보수적으로 60%에서 제한)
        with self._lock:
            self._clean_old_requests()
            if self._current_weight >= self._max_weight_per_minute * 0.60:  # 60% Reached시 제한
                self.logger.warning(f"weight 한계 근접 (60%): {self._current_weight}/{self._max_weight_per_minute}")
                return True
        
        return False
    
    def wait_if_needed(self, endpoint_path: str, params: dict = None) -> bool:
        """Required시 대기 후 요청 허용 여부 반환"""
        if self.is_rate_limited():
            # 대기 Time 계산
            wait_time = self._calculate_wait_time()
            if wait_time > 0:
                self.logger.info(f"⏳ Rate limit Waiting: {wait_time:.1f}초")
                time.sleep(wait_time)
            
            # 대기 후 재검사
            if self.is_rate_limited():
                self.logger.error("⛔ Rate limit 지속됨 - 요청 거부")
                return False
        
        # weight 예Approx
        weight = self._get_endpoint_weight(endpoint_path, params)
        with self._lock:
            self._clean_old_requests()
            # 요청 후 weight가 한계를 Exceeded하는지 Confirm
            if self._current_weight + weight > self._max_weight_per_minute:
                self.logger.warning(f"weight 한계 Exceeded Expected: {self._current_weight + weight}/{self._max_weight_per_minute}")
                return False
        
        return True
    
    def _calculate_wait_time(self) -> float:
        """적절한 대기 Time 계산"""
        current_time = time.time()
        
        # IP 차단 대기 Time
        if self._ban_until and current_time < self._ban_until:
            return self._ban_until - current_time
        
        # 429 백오프 대기 Time
        if self._last_429_time and self._retry_after > 0:
            elapsed = current_time - self._last_429_time
            remaining = self._retry_after - elapsed
            if remaining > 0:
                return remaining * self._backoff_multiplier
        
        # weight 기반 대기 Time (가장 오래된 요청이 만료될 때까지)
        if self._request_times:
            oldest_request = self._request_times[0]
            wait_until = oldest_request + 60  # 1분 후 만료
            wait_time = max(0, wait_until - current_time)
            return wait_time
        
        return 0
    
    def record_request(self, endpoint_path: str, params: dict = None, response_headers: dict = None):
        """요청 기록 및 weight Add"""
        current_time = time.time()
        weight = self._get_endpoint_weight(endpoint_path, params)
        
        with self._lock:
            self._request_times.append(current_time)
            self._weight_history.append(weight)
            self._current_weight += weight
            self._clean_old_requests()
        
        # Response 헤더 Process
        if response_headers:
            self._update_rate_limit_state(response_headers)
        
        self.logger.debug(f"요청 기록: {endpoint_path} (weight: {weight}, 총합: {self._current_weight})")
    
    def record_error(self, status_code: int, response_headers: dict = None):
        """에러 Response 기록"""
        if status_code in [429, 418]:
            self._handle_rate_limit_error(status_code, response_headers or {})
        else:
            self._error_stats[str(status_code)] += 1
    
    def get_cache(self, cache_key: str) -> Optional[Any]:
        """Cache에서 데이터 조times"""
        if cache_key in self._response_cache:
            data, cached_time, ttl = self._response_cache[cache_key]
            if time.time() - cached_time < ttl:
                self.logger.debug(f"Cache 히트: {cache_key}")
                return data
            else:
                # 만료된 Cache Delete
                del self._response_cache[cache_key]
        return None
    
    def set_cache(self, cache_key: str, data: Any, ttl: int = 60):
        """Cache에 데이터 Save"""
        self._response_cache[cache_key] = (data, time.time(), ttl)
        self.logger.debug(f"Cache Save: {cache_key} (TTL: {ttl}초)")
        
        # Cache Size 제한 (메모리 관리)
        if len(self._response_cache) > 1000:
            # 가장 오래된 Cache 10count Delete
            oldest_keys = sorted(self._response_cache.keys(), 
                               key=lambda k: self._response_cache[k][1])[:10]
            for key in oldest_keys:
                del self._response_cache[key]
    
    def get_status(self) -> dict:
        """Current rate limiter Status 반환"""
        current_time = time.time()
        
        # IP 차단 Status
        ban_status = "차단됨" if self._ban_until and current_time < self._ban_until else "정상"
        ban_remaining = max(0, self._ban_until - current_time) if self._ban_until else 0
        
        # 429 백오프 Status
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
        """Current Status를 File로 Save"""
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
            
            self.logger.debug("Rate limiter Status Save됨")
        except Exception as e:
            self.logger.error(f"State save failed: {e}")
    
    def _load_state(self):
        """File에서 Status Load"""
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
                
                self.logger.info("Rate limiter Status 복원됨")
        except Exception as e:
            self.logger.error(f"Status Load Failed: {e}")


class RateLimitedExchange:
    """Rate Limiter가 적용된 Exchange 래퍼"""
    
    def __init__(self, exchange, logger=None):
        self.exchange = exchange
        self.rate_limiter = BinanceRateLimiter(logger)
        self.logger = logger or logging.getLogger(__name__)
    
    def _safe_api_call(self, method_name: str, *args, **kwargs):
        """Rate limit을 고려한 안전한 API calls"""
        # 엔드포인트 경로 추정
        endpoint_path = self._get_endpoint_path(method_name, args, kwargs)
        params = self._extract_params(args, kwargs)
        
        # Cache Confirm
        cache_args = str(sorted(args)) if args else ""
        cache_kwargs = str(sorted(kwargs.items())) if kwargs else ""
        cache_key = f"{method_name}:{hash(cache_args + cache_kwargs)}"
        cached_result = self.rate_limiter.get_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        # Rate limit Confirm 및 대기
        if not self.rate_limiter.wait_if_needed(endpoint_path, params):
            raise Exception(f"Rate limit Exceeded로 요청 거부됨: {method_name}")
        
        try:
            # 실제 API calls
            method = getattr(self.exchange, method_name)
            result = method(*args, **kwargs)
            
            # Success시 요청 기록
            self.rate_limiter.record_request(endpoint_path, params)
            
            # Cache Save (Response Type에 따라 TTL 조정)
            ttl = self._get_cache_ttl(method_name)
            self.rate_limiter.set_cache(cache_key, result, ttl)
            
            return result
            
        except Exception as e:
            # 에러 Response Process
            status_code = getattr(e, 'response', {}).get('status_code') or \
                         getattr(e, 'status_code', 0)
            
            response_headers = getattr(e, 'response', {}).get('headers', {})
            
            if status_code:
                self.rate_limiter.record_error(status_code, response_headers)
            
            # Rate limit 에러는 별도 Process
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
        """API calls 파라미터 추출"""
        params = {}
        
        # args에서 Symbol 추출 (첫 번째 인자가 보통 Symbol)
        if args:
            params['symbol'] = args[0]
        
        # kwargs에서 주요 파라미터 추출
        for key in ['symbol', 'limit', 'since', 'timeframe']:
            if key in kwargs:
                params[key] = kwargs[key]
        
        return params
    
    def _get_cache_ttl(self, method_name: str) -> int:
        """메서드별 Cache TTL Settings (API 호출 최소화)"""
        ttl_mapping = {
            'fetch_ticker': 5,      # 5초 (빠른 change)
            'fetch_tickers': 10,    # 10초 
            'fetch_ohlcv': 30,      # 30초 (OHLCV 데이터)
            'fetch_balance': 60,    # 1분 (계좌 Info) - 더 긴 캐시
            'fetch_positions': 30,  # 30초 (Position Info) - 더 긴 캐시
            'fetch_orders': 120,    # 2분 (주문 내역)
            'fetch_open_orders': 60, # 1분 (열린 주문)
            'market': 600,          # 10분 (마켓 정보는 변경 빈도 낮음)
        }
        return ttl_mapping.get(method_name, 45)  # 기본 45초
    
    def __getattr__(self, name):
        """Exchange 메서드에 대한 프록시"""
        if hasattr(self.exchange, name):
            # API calls 메서드인지 Confirm
            method = getattr(self.exchange, name)
            if callable(method) and (name.startswith('fetch_') or 
                                   name.startswith('create_') or 
                                   name.startswith('cancel_') or
                                   name.startswith('edit_') or
                                   name == 'market' or
                                   'order' in name.lower() or
                                   'position' in name.lower() or
                                   'balance' in name.lower() or
                                   'account' in name.lower()):
                # Rate limit이 적용된 래퍼 반환
                def rate_limited_method(*args, **kwargs):
                    return self._safe_api_call(name, *args, **kwargs)
                return rate_limited_method
            else:
                # 일반 속성/메서드는 그대로 반환
                return method
        else:
            raise AttributeError(f"'{type(self.exchange).__name__}' object has no attribute '{name}'")


# Usage 예시 및 Test
if __name__ == "__main__":
    import ccxt
    
    # 로깅 Settings
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Rate limiter Test
    rate_limiter = BinanceRateLimiter(logger)
    
    # Status 출력
    status = rate_limiter.get_status()
    print("Rate Limiter Status:")
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    # Exchange 래퍼 Test
    try:
        exchange = ccxt.binance({
            'apiKey': 'your-api-key',
            'secret': 'your-secret',
            'sandbox': True,  # Test넷 Usage
        })
        
        rate_limited_exchange = RateLimitedExchange(exchange, logger)
        
        # Test 호출
        # tickers = rate_limited_exchange.fetch_tickers()
        # print(f"티커 수: {len(tickers)}")
        
    except Exception as e:
        print(f"Exchange Test Failed: {e}")