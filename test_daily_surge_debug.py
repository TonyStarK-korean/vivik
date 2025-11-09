# -*- coding: utf-8 -*-
"""
일봉 급등 조건 직접 테스트 스크립트
"""
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

def test_daily_surge_condition(symbol, debug=True):
    """
    일봉상 60봉이내 시가대비고가 10%이상 상승 조건 직접 테스트
    """
    try:
        # Binance Exchange 객체 생성
        exchange = ccxt.binance({
            'sandbox': False,
            'rateLimit': 1200,
            'enableRateLimit': True,
        })
        
        print(f"\n[DEBUG] [{symbol}] 일봉 급등 조건 테스트 시작...")
        
        # 일봉 데이터 조회 (60봉 + 5봉 여유분)
        ohlcv = exchange.fetch_ohlcv(symbol, '1d', limit=65)
        
        if not ohlcv or len(ohlcv) < 60:
            print(f"[ERROR] [{symbol}] 일봉 데이터 부족: {len(ohlcv) if ohlcv else 0}개")
            return False, "일봉 데이터 부족"
        
        # DataFrame 변환
        df_1d = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # 최근 60봉 체크
        recent_60_candles = df_1d.tail(60)
        
        surge_found = False
        max_surge = 0
        surge_details = []
        qualifying_surges = []  # 10% 이상 급등 기록
        
        # 심볼명 정리
        clean_symbol = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
        
        print(f"[INFO] [{clean_symbol}] 최근 60일간 일봉 데이터 분석 중...")
        
        for i, row in recent_60_candles.iterrows():
            open_price = row['open']
            high_price = row['high']
            low_price = row['low']
            close_price = row['close']
            timestamp = row['timestamp']
            
            # 날짜 변환
            date_str = datetime.fromtimestamp(timestamp/1000, tz=timezone.utc).strftime('%Y-%m-%d')
            
            if open_price > 0:
                surge_pct = ((high_price - open_price) / open_price) * 100
                max_surge = max(max_surge, surge_pct)
                
                # 상위 급등들을 기록 (5% 이상)
                if surge_pct >= 5.0:
                    surge_details.append(f"{date_str}:{surge_pct:.1f}%")
                
                # 10% 이상 급등 기록
                if surge_pct >= 10.0:
                    qualifying_surges.append(f"{date_str}:{surge_pct:.1f}%")
                    surge_found = True
        
        # 결과 출력
        if surge_found:
            print(f"[SUCCESS] [{clean_symbol}] 일봉 급등 조건 충족!")
            print(f"   10%+ 급등일: {', '.join(qualifying_surges)}")
            print(f"   5%+ 급등일: {', '.join(surge_details[:10])}...")  # 최대 10개만
            return True, f"일봉 급등 조건 충족 (60봉내)"
        else:
            print(f"[FAIL] [{clean_symbol}] 일봉 급등 조건 미충족")
            print(f"   최대 급등률: {max_surge:.1f}%")
            if surge_details:
                print(f"   5%+ 급등일: {', '.join(surge_details)}")
            else:
                print(f"   5% 이상 급등일 전혀 없음")
            
            return False, f"60봉내 일봉 10% 급등 없음 (최대: {max_surge:.1f}%)"
            
    except Exception as e:
        print(f"[ERROR] [{symbol}] 오류: {e}")
        return False, f"일봉 데이터 조회 실패: {e}"

def main():
    """메인 테스트 함수"""
    print("=== 일봉 급등 조건 디버깅 테스트 ===")
    
    # 테스트할 심볼들 (다양한 종류로)
    test_symbols = [
        'BTC/USDT:USDT',   # 대형주
        'ETH/USDT:USDT',   # 대형주
        'ADA/USDT:USDT',   # 중형주
        'LINK/USDT:USDT',  # 중형주
        'DOGE/USDT:USDT',  # 밈코인
        'SHIB/USDT:USDT',  # 밈코인
        # 신규상장/소형주 (이론적으로 급등 가능성 높음)
        'NEIRO/USDT:USDT',
        'HMSTR/USDT:USDT',
        'CATI/USDT:USDT',
        'TON/USDT:USDT',
    ]
    
    passed_count = 0
    total_count = 0
    
    for symbol in test_symbols:
        try:
            total_count += 1
            passed, msg = test_daily_surge_condition(symbol)
            if passed:
                passed_count += 1
        except Exception as e:
            print(f"[ERROR] [{symbol}] 테스트 실패: {e}")
        
        print("-" * 80)
    
    print(f"\n[SUMMARY] 테스트 결과 요약:")
    print(f"   총 테스트: {total_count}개")
    print(f"   조건 통과: {passed_count}개")
    print(f"   통과율: {passed_count/total_count*100:.1f}%" if total_count > 0 else "0%")
    
    if passed_count == 0:
        print("\n[DIAGNOSIS] 문제 진단:")
        print("   - 현재 10% 급등 조건이 너무 까다로울 수 있습니다")
        print("   - 최근 시장이 횡보/하락세일 가능성이 있습니다")
        print("   - 조건을 5%로 완화하거나 기간을 늘리는 것을 고려해보세요")

if __name__ == "__main__":
    main()