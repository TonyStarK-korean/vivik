# -*- coding: utf-8 -*-
"""
Cache Manager Module
캐시 관리 전용 모듈

주요 기능:
- 범용 데이터 캐싱 (TTL 60초)
- 마켓 정보 캐싱 (TTL 1시간)
- 잔고 캐싱 (TTL 5분)
- 변동률 필터 캐싱 (TTL 10분)
- API 심볼 캐싱 (TTL 5분)
- 자동 만료 및 크기 제한
"""

import time
from typing import Any, Optional, List, Dict


class CacheManager:
    """통합 캐시 관리 시스템"""

    def __init__(self, logger=None):
        """
        Args:
            logger: 로거 인스턴스 (선택)
        """
        self.logger = logger

        # 범용 데이터 캐시
        self._data_cache: Dict[str, tuple] = {}
        self._cache_ttl = 60  # 60초

        # 마켓 정보 캐시
        self._market_cache = None
        self._market_cache_time = 0
        self._market_cache_ttl = 3600  # 1시간

        # 잔고 캐시
        self._balance_cache = None
        self._balance_cache_time = 0
        self._balance_cache_ttl = 300  # 5분

        # 변동률 필터 캐시
        self._change_filter_cache: Dict[str, Dict] = {}
        self._change_filter_ttl = 600  # 10분

        # API 심볼 캐시
        self._api_symbol_cache: List[str] = []
        self._api_cache_time = 0
        self._api_cache_ttl = 300  # 5분

        # OHLCV 캐시 (WebSocket 전용)
        self._ohlcv_cache_ttl = 300  # 5분

    def get_cached_data(self, cache_key: str) -> Optional[Any]:
        """
        범용 캐시 데이터 조회

        Args:
            cache_key: 캐시 키

        Returns:
            캐시된 데이터 또는 None (만료/없음)
        """
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

    def set_cached_data(self, cache_key: str, data: Any):
        """
        데이터를 캐시에 저장

        Args:
            cache_key: 캐시 키
            data: 저장할 데이터
        """
        try:
            self._data_cache[cache_key] = (data, time.time())
            # 캐시 크기 제한 (100개 이상이면 오래된 것부터 제거)
            if len(self._data_cache) > 100:
                oldest_key = min(self._data_cache.keys(),
                                key=lambda k: self._data_cache[k][1])
                del self._data_cache[oldest_key]
        except Exception:
            pass

    def get_cached_markets(self, exchange) -> Optional[Dict]:
        """
        마켓 정보 캐시 조회 (1시간 TTL)

        Args:
            exchange: ccxt exchange 객체

        Returns:
            마켓 정보 딕셔너리 또는 None
        """
        try:
            current_time = time.time()

            # 캐시가 유효한지 확인
            if (self._market_cache is not None and
                current_time - self._market_cache_time < self._market_cache_ttl):
                return self._market_cache

            # 캐시가 없거나 만료됨 → API 호출
            self._market_cache = exchange.load_markets()
            self._market_cache_time = current_time

            return self._market_cache

        except Exception as e:
            if self.logger:
                self.logger.error(f"마켓 캐시 조회 실패: {e}")
            # 실패시 기존 캐시라도 반환 (만료되었더라도)
            if self._market_cache is not None:
                return self._market_cache
            # 캐시도 없으면 직접 호출
            return exchange.load_markets()

    def get_cached_balance(self) -> Optional[float]:
        """
        잔고 캐시 조회 (5분 TTL)

        Returns:
            캐시된 잔고 또는 None
        """
        try:
            cache_age = time.time() - self._balance_cache_time
            if cache_age < self._balance_cache_ttl:
                return self._balance_cache
            return None
        except Exception:
            return None

    def cache_balance(self, balance: float):
        """
        잔고 캐싱

        Args:
            balance: 잔고 금액
        """
        try:
            self._balance_cache = balance
            self._balance_cache_time = time.time()
        except Exception:
            pass

    def get_cached_change_filter(self, min_change_pct: float) -> Optional[List[str]]:
        """
        변동률 필터링 캐시 조회 (10분 TTL)

        Args:
            min_change_pct: 최소 변동률

        Returns:
            필터링된 심볼 리스트 또는 None
        """
        try:
            cache_key = f"change_{min_change_pct}"
            if cache_key in self._change_filter_cache:
                cache_data = self._change_filter_cache[cache_key]
                cache_age = time.time() - cache_data['timestamp']

                if cache_age < self._change_filter_ttl:
                    return cache_data['symbols']

            return None
        except:
            return None

    def cache_change_filter(self, symbols: List[str], min_change_pct: float):
        """
        변동률 필터링 결과 캐싱

        Args:
            symbols: 필터링된 심볼 리스트
            min_change_pct: 최소 변동률
        """
        try:
            cache_key = f"change_{min_change_pct}"
            self._change_filter_cache[cache_key] = {
                'symbols': symbols,
                'timestamp': time.time()
            }
        except:
            pass

    def get_cached_api_symbols(self) -> List[str]:
        """
        API 심볼 캐시 조회 (5분 TTL)

        Returns:
            캐시된 심볼 리스트 (빈 리스트 가능)
        """
        try:
            cache_age = time.time() - self._api_cache_time
            if cache_age < self._api_cache_ttl:
                return self._api_symbol_cache
            return []
        except:
            return []

    def cache_api_symbols(self, symbols: List[str]):
        """
        API 심볼 캐싱

        Args:
            symbols: 심볼 리스트
        """
        try:
            self._api_symbol_cache = symbols
            self._api_cache_time = time.time()
        except:
            pass

    def clear_all_caches(self):
        """모든 캐시 초기화"""
        try:
            self._data_cache.clear()
            self._market_cache = None
            self._market_cache_time = 0
            self._balance_cache = None
            self._balance_cache_time = 0
            self._change_filter_cache.clear()
            self._api_symbol_cache = []
            self._api_cache_time = 0

            if self.logger:
                self.logger.info("✅ 모든 캐시 초기화 완료")
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ 캐시 초기화 실패: {e}")

    def clear_expired_caches(self):
        """만료된 캐시만 정리"""
        try:
            current_time = time.time()

            # 범용 데이터 캐시 정리
            expired_keys = [
                key for key, (_, timestamp) in self._data_cache.items()
                if current_time - timestamp >= self._cache_ttl
            ]
            for key in expired_keys:
                del self._data_cache[key]

            # 변동률 필터 캐시 정리
            expired_filter_keys = [
                key for key, data in self._change_filter_cache.items()
                if current_time - data['timestamp'] >= self._change_filter_ttl
            ]
            for key in expired_filter_keys:
                del self._change_filter_cache[key]

            # 마켓 캐시 정리
            if (self._market_cache is not None and
                current_time - self._market_cache_time >= self._market_cache_ttl):
                self._market_cache = None
                self._market_cache_time = 0

            # 잔고 캐시 정리
            if (self._balance_cache is not None and
                current_time - self._balance_cache_time >= self._balance_cache_ttl):
                self._balance_cache = None
                self._balance_cache_time = 0

            # API 심볼 캐시 정리
            if current_time - self._api_cache_time >= self._api_cache_ttl:
                self._api_symbol_cache = []
                self._api_cache_time = 0

            if self.logger:
                self.logger.debug(f"✅ 만료 캐시 정리 완료: {len(expired_keys) + len(expired_filter_keys)}개 항목")

        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ 만료 캐시 정리 실패: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        current_time = time.time()
        return {
            'data_cache_size': len(self._data_cache),
            'market_cache_age': int(current_time - self._market_cache_time) if self._market_cache else None,
            'balance_cache_age': int(current_time - self._balance_cache_time) if self._balance_cache else None,
            'change_filter_cache_size': len(self._change_filter_cache),
            'api_symbols_cache_age': int(current_time - self._api_cache_time) if self._api_symbol_cache else None,
            'api_symbols_count': len(self._api_symbol_cache)
        }


# 사용 예시
if __name__ == "__main__":
    import logging

    # 로깅 설정
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # CacheManager 생성
    cache_mgr = CacheManager(logger)

    # 데이터 캐싱
    cache_mgr.set_cached_data("test_key", {"price": 50000})
    data = cache_mgr.get_cached_data("test_key")
    print(f"캐시된 데이터: {data}")

    # 잔고 캐싱
    cache_mgr.cache_balance(10000.0)
    balance = cache_mgr.get_cached_balance()
    print(f"캐시된 잔고: ${balance}")

    # 캐시 통계
    stats = cache_mgr.get_cache_stats()
    print(f"\n캐시 통계:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
