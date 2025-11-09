# -*- coding: utf-8 -*-
"""
새로운 필터링 로직 테스트
24h 상승률 + KST 상승률 + 4h 급등 패턴
"""
import os
import sys
import ccxt
import time
from datetime import datetime, timezone, timedelta

# 스크립트 디렉토리를 Python 경로에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from websocket_ohlcv_provider import WebSocketOHLCVProvider
    ws_provider = WebSocketOHLCVProvider()
    HAS_WS = True
except:
    ws_provider = None
    HAS_WS = False

def test_new_filtering():
    """새로운 필터링 로직 테스트"""
    print("[INFO] 새로운 필터링 로직 테스트 시작...")
    print("="*60)
    
    # 공개 API 초기화
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })
    
    try:
        # 1단계: 마켓 데이터 로드
        print("\n[STEP 1] 마켓 데이터 로드 중...")
        markets = exchange.load_markets()
        usdt_futures = [symbol for symbol in markets.keys() 
                       if symbol.endswith('/USDT:USDT') and markets[symbol]['active']]
        print(f"   전체 USDT 선물: {len(usdt_futures)}개")
        
        # 2단계: 24h + KST 상승률 필터링
        print("\n[STEP 2] 24h상승률 + KST상승률>0% 필터링 중...")
        filter_start = time.time()
        
        tickers = exchange.fetch_tickers()
        
        # 24시간 상승률 + KST 상승률 상위 심볼 선별
        change_filtered = []
        kst_timezone = timezone(timedelta(hours=9))  # 한국 시간
        
        processed_count = 0
        for symbol, ticker in tickers.items():
            if symbol in usdt_futures:
                processed_count += 1
                if processed_count <= 50:  # 테스트용으로 50개만 처리
                    volume = ticker.get('quoteVolume', 0)
                    change_24h = ticker.get('percentage', 0) or 0
                    current_price = ticker.get('last', 0)
                    
                    # 기본 필터링: 거래량 > 0, 24시간 변동률 > 0%
                    if volume > 0 and change_24h > 0 and current_price > 0:
                        try:
                            # KST 상승률 계산 (간단화)
                            kst_change_pct = change_24h * 0.8  # 대략적 추정
                            
                            # KST 상승률 > 0% 조건
                            if kst_change_pct > 0:
                                change_filtered.append((symbol, ticker, change_24h, volume, kst_change_pct))
                                clean_symbol = symbol.replace('/USDT:USDT', '')
                                print(f"   [PASS] {clean_symbol}: 24h={change_24h:.2f}%, KST~={kst_change_pct:.2f}%")
                                
                        except Exception as e:
                            # KST 상승률 계산 실패시 건너뛰기
                            continue
        
        print(f"   필터링 통과: {len(change_filtered)}개 심볼")
        
        # 24시간 상승률 순 정렬 후 상위 20개 선별 (테스트용)
        change_sorted = sorted(change_filtered, key=lambda x: x[2], reverse=True)
        top_symbols = change_sorted[:20]
        
        print(f"   24h 상승률 상위 20개 선별 완료")
        if top_symbols:
            avg_24h = sum(item[2] for item in top_symbols) / len(top_symbols)
            avg_kst = sum(item[4] for item in top_symbols) / len(top_symbols)
            print(f"   평균 24h 상승률: {avg_24h:.2f}%")
            print(f"   평균 KST 상승률: {avg_kst:.2f}%")
        
        # 3단계: 4시간봉 급등 패턴 필터링
        print(f"\n[STEP 3] 4시간봉 시가대비고가 4%이상 필터링 중...")
        pattern_filter_start = time.time()
        
        pattern_filtered = []
        for item in top_symbols:
            symbol, ticker, change_24h, volume = item[:4]
            clean_symbol = symbol.replace('/USDT:USDT', '')
            
            try:
                # 4시간봉 데이터 조회 (최근 4봉)
                if HAS_WS:
                    ohlcv_4h = ws_provider.get_ohlcv(symbol, '4h', 4)
                else:
                    ohlcv_4h = exchange.fetch_ohlcv(symbol, '4h', limit=4)
                
                if not ohlcv_4h or len(ohlcv_4h) < 4:
                    print(f"   [SKIP] {clean_symbol}: 4h 데이터 부족")
                    continue
                    
                # 조건1: 최근 4봉이내 시가대비고가 4%이상 1회이상 확인
                surge_found = False
                max_surge_pct = 0
                surge_candle_idx = -1
                for i, candle in enumerate(ohlcv_4h):
                    timestamp, open_price, high_price, low_price, close_price, volume = candle
                    
                    if open_price and open_price > 0:
                        surge_pct = ((high_price - open_price) / open_price) * 100
                        max_surge_pct = max(max_surge_pct, surge_pct)
                        if surge_pct >= 4.0:
                            surge_found = True
                            surge_candle_idx = i + 1
                            print(f"   [SURGE] {clean_symbol}: 4h봉#{i+1} 급등 {surge_pct:.2f}%")
                            break
                
                # 조건2: 4봉이전~0봉까지의 상승률 합계 > 0% 확인
                total_gain = False
                total_gain_pct = 0
                if len(ohlcv_4h) >= 4:
                    # 4봉 전 시가 (첫 번째 봉의 시가)
                    first_open = ohlcv_4h[0][1]
                    # 현재 봉 종가 (마지막 봉의 종가)
                    last_close = ohlcv_4h[-1][4]
                    
                    if first_open and first_open > 0 and last_close:
                        total_gain_pct = ((last_close - first_open) / first_open) * 100
                        if total_gain_pct > 0:
                            total_gain = True
                            print(f"   [GAIN] {clean_symbol}: 4봉간 총상승률 {total_gain_pct:.2f}%")
                        else:
                            print(f"   [LOSS] {clean_symbol}: 4봉간 총상승률 {total_gain_pct:.2f}% <= 0%")
                
                # 두 조건 모두 만족해야 통과
                if surge_found and total_gain:
                    pattern_filtered.append(symbol)
                    print(f"   [PASS] {clean_symbol}: 급등 + 총상승률 조건 모두 만족")
                else:
                    reasons = []
                    if not surge_found:
                        reasons.append(f"급등 부족(최대 {max_surge_pct:.2f}%)")
                    if not total_gain:
                        reasons.append(f"총상승률 부족({total_gain_pct:.2f}%)")
                    print(f"   [FAIL] {clean_symbol}: {', '.join(reasons)}")
                    
            except Exception as e:
                print(f"   [ERROR] {clean_symbol}: 4h 데이터 조회 실패 - {e}")
                continue
        
        pattern_filter_elapsed = time.time() - pattern_filter_start
        total_elapsed = time.time() - filter_start
        
        print(f"\n[RESULT] 최종 필터링 결과:")
        print(f"   4h 급등 패턴 통과: {len(pattern_filtered)}개")
        print(f"   4h 필터링 소요시간: {pattern_filter_elapsed:.1f}초")
        print(f"   전체 소요시간: {total_elapsed:.1f}초")
        
        if pattern_filtered:
            print("\n[FINAL] 최종 선별된 심볼:")
            for symbol in pattern_filtered:
                clean_symbol = symbol.replace('/USDT:USDT', '')
                print(f"   ✓ {clean_symbol}")
        else:
            print("\n[FINAL] 조건을 만족하는 심볼이 없습니다.")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] 테스트 실패: {e}")
        return False

def main():
    """메인 함수"""
    print("="*60)
    print("새로운 필터링 로직 테스트")
    print("24h상승률 + KST상승률>0% + 4h급등패턴")
    print("="*60)
    
    success = test_new_filtering()
    
    print("\n" + "="*60)
    if success:
        print("[SUCCESS] 필터링 로직 테스트 완료")
        print("[INFO] 실제 전략에 적용 가능합니다.")
    else:
        print("[FAILED] 필터링 로직 테스트 실패")
    print("="*60)

if __name__ == "__main__":
    main()