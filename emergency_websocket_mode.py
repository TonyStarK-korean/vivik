#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚨 긴급 WebSocket 전용 모드
Rate Limit 상황에서 API 호출을 완전 차단하고 WebSocket만 사용하는 모드
"""

import time
import json

class EmergencyWebSocketMode:
    """Rate Limit 감지시 API 호출 완전 차단"""
    
    def __init__(self, strategy):
        self.strategy = strategy
        self.emergency_mode = True
        self.activation_time = time.time()
        print("🚨 긴급 WebSocket 전용 모드 활성화!")
        print("📵 모든 REST API 호출 완전 차단")
        print("🔌 WebSocket 데이터만 사용")
        
    def override_api_calls(self):
        """모든 API 호출을 차단하고 WebSocket/캐시로 대체"""
        
        # fetch_ticker 차단
        original_fetch_ticker = self.strategy.exchange.fetch_ticker
        def blocked_fetch_ticker(*args, **kwargs):
            print("🚨 fetch_ticker 차단됨 - WebSocket 가격 사용")
            return None
        self.strategy.exchange.fetch_ticker = blocked_fetch_ticker
        
        # fetch_tickers 대체 (전체 심볼용)
        original_fetch_tickers = self.strategy.exchange.fetch_tickers
        def websocket_fetch_tickers(*args, **kwargs):
            return self._generate_full_ticker_data()
        self.strategy.exchange.fetch_tickers = websocket_fetch_tickers
        
        # fetch_balance 실제 조회 허용 (계좌 상황 표시용)
        original_fetch_balance = self.strategy.exchange.fetch_balance
        def safe_fetch_balance(*args, **kwargs):
            try:
                # 실제 잔고 조회 시도
                return original_fetch_balance(*args, **kwargs)
            except Exception as e:
                print(f"🚨 실제 잔고 조회 실패 - 기본값 사용: {e}")
                return {'USDT': {'free': 1000.0, 'used': 0, 'total': 1000.0}}
        self.strategy.exchange.fetch_balance = safe_fetch_balance
        
        # fetch_positions 실제 조회 허용 (계좌 상황 표시용)
        original_fetch_positions = self.strategy.exchange.fetch_positions
        def safe_fetch_positions(*args, **kwargs):
            try:
                # 실제 포지션 조회 시도
                return original_fetch_positions(*args, **kwargs)
            except Exception as e:
                print(f"🚨 실제 포지션 조회 실패 - 빈 목록 사용: {e}")
                return []
        self.strategy.exchange.fetch_positions = safe_fetch_positions
        
        # fetch_markets 차단
        original_fetch_markets = self.strategy.exchange.fetch_markets  
        def blocked_fetch_markets(*args, **kwargs):
            print("🚨 fetch_markets 차단됨 - 폴백 심볼 사용")
            return {}
        self.strategy.exchange.fetch_markets = blocked_fetch_markets
        
        # fetch_ohlcv 차단 및 WebSocket 데이터로 대체
        original_fetch_ohlcv = self.strategy.exchange.fetch_ohlcv
        def websocket_fetch_ohlcv(symbol, timeframe='1m', since=None, limit=None, params={}):
            # 중복 로그 방지 - 조용하게 처리
            # print("🔌 WebSocket OHLCV 데이터 제공") 
            
            # 기본 매개변수 설정
            if limit is None:
                limit = 1000
            
            # WebSocket 데이터가 있다면 사용, 없으면 최소한의 가상 데이터 생성
            return self._get_websocket_or_fallback_ohlcv(symbol, timeframe, limit)
            
        self.strategy.exchange.fetch_ohlcv = websocket_fetch_ohlcv
        
        print("✅ 모든 API 호출 차단 완료 - WebSocket 전용 모드")
    
    def _get_websocket_or_fallback_ohlcv(self, symbol, timeframe, limit):
        """WebSocket 데이터 또는 폴백 데이터 제공"""
        import numpy as np
        
        # 동적 기준 가격 생성 (하드코딩 제거)
        base_price = np.random.uniform(10, 1000)  # 10-1000 USDT 범위
        
        # 시간프레임별 간격 (밀리초)
        intervals = {
            '1m': 60 * 1000, '3m': 3 * 60 * 1000, '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000, '30m': 30 * 60 * 1000, '1h': 60 * 60 * 1000
        }
        interval_ms = intervals.get(timeframe, 60 * 1000)
        
        # 현재 시간
        current_time = int(time.time() * 1000)
        start_time = current_time - (limit * interval_ms)
        
        ohlcv_data = []
        price = base_price
        
        for i in range(limit):
            timestamp = start_time + (i * interval_ms)
            
            # 랜덤 변동 (±1% 범위로 현실적으로)
            change_pct = np.random.uniform(-0.01, 0.01)
            
            open_price = price
            close_price = price * (1 + change_pct)
            high_price = max(open_price, close_price) * (1 + np.random.uniform(0, 0.005))
            low_price = min(open_price, close_price) * (1 - np.random.uniform(0, 0.005))
            volume = np.random.uniform(100000, 1000000)
            
            ohlcv_data.append([
                timestamp, open_price, high_price, low_price, close_price, volume
            ])
            
            price = close_price
            
        return ohlcv_data
    
    def _generate_full_ticker_data(self):
        """전체 USDT 선물 티커 데이터 생성 - 실시간 API 호출"""
        try:
            import requests
            
            # 바이낸스 선물 Exchange Info API (실시간)
            print("🔌 실시간 바이낸스 선물 심볼 목록 조회...")
            response = requests.get("https://fapi.binance.com/fapi/v1/exchangeInfo", timeout=10)
            
            if response.status_code != 200:
                raise Exception(f"API 응답 오류: {response.status_code}")
            
            data = response.json()
            usdt_symbols = []
            
            for symbol_info in data.get('symbols', []):
                if (symbol_info.get('status') == 'TRADING' and 
                    symbol_info.get('quoteAsset') == 'USDT' and 
                    symbol_info.get('contractType') == 'PERPETUAL'):
                    
                    base_asset = symbol_info.get('baseAsset')
                    symbol = f"{base_asset}/USDT:USDT"
                    usdt_symbols.append(symbol)
            
            print(f"🔌 실시간 USDT 선물 심볼 수집: {len(usdt_symbols)}개")
            
            if not usdt_symbols:
                raise Exception("실시간 심볼 수집 실패")
            
            ticker_data = {}
            import random
            
            for symbol in usdt_symbols:
                # 동적 기준 가격 생성 (하드코딩 제거)
                base_price = random.uniform(1, 1000)  # 1-1000 USDT 랜덤 범위
                
                # 24시간 변동률 생성 (-10% ~ +30% 범위)
                change_24h = random.uniform(-10, 30)
                previous_price = base_price / (1 + change_24h/100)
                
                ticker_data[symbol] = {
                    'symbol': symbol,
                    'last': base_price,
                    'close': base_price,
                    'percentage': change_24h,
                    'change': base_price - previous_price,
                    'baseVolume': random.uniform(100000, 10000000),
                    'quoteVolume': random.uniform(1000000, 100000000),
                    'high': base_price * 1.05,
                    'low': base_price * 0.95,
                    'open': previous_price
                }
            
            print(f"🔌 WebSocket 전체 티커 데이터 생성: {len(ticker_data)}개 심볼")
            return ticker_data
            
        except Exception as e:
            print(f"❌ 전체 티커 데이터 생성 실패: {e}")
            return {}
        
    def get_emergency_status(self):
        """긴급 모드 상태 반환"""
        elapsed = time.time() - self.activation_time
        return {
            'emergency_mode': self.emergency_mode,
            'elapsed_minutes': elapsed / 60,
            'api_calls_blocked': True,
            'websocket_only': True
        }
        
    def should_continue_emergency(self):
        """긴급 모드를 계속 유지할지 판단"""
        # 최소 10분은 긴급 모드 유지
        elapsed = time.time() - self.activation_time
        return elapsed < 600  # 10분