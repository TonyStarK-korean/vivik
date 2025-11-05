#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
실제 시장 데이터로 4시간봉 필터링 테스트
"""
import time
import sys
import os

def test_real_market_filtering():
    """실제 시장에서 4시간봉 필터링 테스트"""
    try:
        print("=== 실제 시장 4시간봉 필터링 테스트 ===")
        
        # 전략 임포트
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        
        # 전략 초기화 (간단한 로그만)
        print("전략 초기화 중...")
        strategy = OneMinuteSurgeEntryStrategy(
            api_key=None,
            secret_key=None,
            sandbox=False
        )
        
        # 10초 대기 후 실제 심볼 가져오기
        print("WebSocket 데이터 수집 및 실제 심볼 조회... (10초)")
        time.sleep(10)
        
        print("\n=== 실제 시장 데이터 조회 ===")
        
        # 실제 거래소에서 심볼 리스트 가져오기
        if hasattr(strategy, 'exchange') and strategy.exchange:
            try:
                markets = strategy.exchange.load_markets()
                
                # USDT 무기한 선물 필터링
                usdt_futures = []
                for symbol, market in markets.items():
                    if (market.get('type') == 'swap' and 
                        market.get('quote') == 'USDT' and 
                        market.get('active', True)):
                        usdt_futures.append(symbol)
                
                print(f"✅ 총 USDT 무기한 선물: {len(usdt_futures)}개")
                
                # 상위 20개 심볼로 테스트 (API 호출 부담 줄이기)
                test_symbols = usdt_futures[:20]
                print(f"테스트 대상: {len(test_symbols)}개")
                
                # ticker 정보 가져오기
                tickers = strategy.exchange.fetch_tickers(test_symbols)
                
                # (심볼, 변동률, 거래량) 형태로 변환
                candidate_symbols = []
                for symbol in test_symbols:
                    if symbol in tickers:
                        ticker = tickers[symbol]
                        change_pct = ticker.get('percentage', 0) or 0
                        volume_24h = ticker.get('quoteVolume', 0) or 0
                        candidate_symbols.append((symbol, change_pct, volume_24h))
                
                print(f"Ticker 데이터 수집 완료: {len(candidate_symbols)}개")
                
                # 샘플 심볼 표시
                for i, (symbol, change_pct, volume_24h) in enumerate(candidate_symbols[:5]):
                    print(f"  [{i+1}] {symbol}: {change_pct:+.2f}%, 거래량: ${volume_24h:,.0f}")
                
            except Exception as e:
                print(f"❌ 거래소 데이터 조회 실패: {e}")
                # 폴백: 하드코딩된 테스트 심볼
                candidate_symbols = [
                    ('BTC/USDT:USDT', 1.5, 1000000),
                    ('ETH/USDT:USDT', 2.2, 800000),
                    ('BNB/USDT:USDT', 0.8, 600000),
                    ('SOL/USDT:USDT', 3.1, 500000),
                    ('ADA/USDT:USDT', 1.9, 400000),
                    ('XRP/USDT:USDT', 2.5, 700000),
                    ('AVAX/USDT:USDT', 1.2, 300000),
                    ('DOT/USDT:USDT', 0.7, 200000),
                    ('LINK/USDT:USDT', 1.8, 250000),
                    ('UNI/USDT:USDT', 2.1, 180000)
                ]
                print(f"폴백 테스트 심볼 사용: {len(candidate_symbols)}개")
        else:
            print("❌ 거래소 연결 없음, 폴백 심볼 사용")
            candidate_symbols = [
                ('BTC/USDT:USDT', 1.5, 1000000),
                ('ETH/USDT:USDT', 2.2, 800000),
                ('BNB/USDT:USDT', 0.8, 600000),
                ('SOL/USDT:USDT', 3.1, 500000),
                ('ADA/USDT:USDT', 1.9, 400000)
            ]
        
        print(f"\n=== 4시간봉 필터링 실행 ===")
        print(f"입력 심볼: {len(candidate_symbols)}개")
        
        # 4시간봉 필터링 실행
        filtered_4h = strategy._websocket_4h_filtering(candidate_symbols)
        
        print(f"\n=== 필터링 결과 ===")
        print(f"✅ 4시간봉 통과: {len(filtered_4h)}개")
        
        if filtered_4h:
            print("통과한 심볼들:")
            for symbol, change_pct, volume_24h in filtered_4h:
                print(f"  🎯 {symbol}: {change_pct:+.2f}%, ${volume_24h:,.0f}")
        else:
            print("⚠️ 현재 시점에 2% Surge 조건을 만족하는 심볼이 없습니다.")
            print("   (정상적인 상황일 수 있음 - 시장 상황에 따라 달라짐)")
        
        # 정리
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            strategy.ws_kline_manager.shutdown()
        
        print(f"\n=== 테스트 완료 ===")
        
        # 결과 반환
        return len(filtered_4h) > 0
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_real_market_filtering()
    sys.exit(0 if success else 1)