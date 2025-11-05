# -*- coding: utf-8 -*-
"""
데이터 가용성 확인 스크립트
"""

import ccxt
import pandas as pd
import time

def check_data_availability():
    """데이터 가용성 확인"""
    print("=== 데이터 가용성 확인 ===")
    
    try:
        # 거래소 초기화
        exchange = ccxt.binance({
            'apiKey': None,
            'secret': None,
            'sandbox': False,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'  # futures 거래소 사용
            }
        })
        
        # 테스트 심볼들
        test_symbols = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'BNB/USDT:USDT']
        
        for symbol in test_symbols:
            print(f"\n--- {symbol} 데이터 확인 ---")
            
            # 1일봉 데이터 확인
            try:
                daily_data = exchange.fetch_ohlcv(symbol, '1d', limit=500)
                print(f"1일봉: {len(daily_data)}개 ({len(daily_data) >= 480})")
                
                if daily_data:
                    df_daily = pd.DataFrame(daily_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df_daily['timestamp'] = pd.to_datetime(df_daily['timestamp'], unit='ms')
                    
                    # MA480 계산 가능 여부
                    ma480_possible = len(df_daily) >= 480
                    print(f"MA480 계산 가능: {ma480_possible}")
                    
                    if ma480_possible:
                        df_daily['ma480'] = df_daily['close'].rolling(window=480).mean()
                        valid_ma480 = df_daily['ma480'].notna().sum()
                        print(f"유효한 MA480: {valid_ma480}개")
                
            except Exception as e:
                print(f"1일봉 오류: {e}")
            
            # 4시간봉 데이터 확인
            try:
                h4_data = exchange.fetch_ohlcv(symbol, '4h', limit=100)
                print(f"4시간봉: {len(h4_data)}개")
                
                if h4_data:
                    recent_4 = h4_data[-4:]
                    surge_count = 0
                    
                    for candle in recent_4:
                        open_price = candle[1]
                        high_price = candle[2]
                        if open_price > 0:
                            surge_pct = ((high_price - open_price) / open_price) * 100
                            if surge_pct >= 2.0:
                                surge_count += 1
                    
                    print(f"최근 4봉 중 2% 이상 급등: {surge_count}개")
                
            except Exception as e:
                print(f"4시간봉 오류: {e}")
            
            # 1시간봉 데이터 확인
            try:
                h1_data = exchange.fetch_ohlcv(symbol, '1h', limit=500)
                print(f"1시간봉: {len(h1_data)}개")
                
                if h1_data:
                    df_h1 = pd.DataFrame(h1_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    
                    # MA80 계산 가능 여부
                    ma80_possible = len(df_h1) >= 80
                    print(f"MA80 계산 가능: {ma80_possible}")
                
            except Exception as e:
                print(f"1시간봉 오류: {e}")
            
            time.sleep(0.5)  # Rate Limit 방지
        
        # 티커 데이터 확인
        print(f"\n--- 티커 데이터 확인 ---")
        try:
            tickers = exchange.fetch_tickers(['BTC/USDT:USDT', 'ETH/USDT:USDT'])
            for symbol, ticker in tickers.items():
                change_pct = ticker.get('percentage', 0)
                volume = ticker.get('quoteVolume', 0)
                print(f"{symbol}: 변동률 {change_pct:.2f}%, 거래량 {volume:,.0f}")
        except Exception as e:
            print(f"티커 데이터 오류: {e}")
        
        print("\n=== 확인 완료 ===")
        
    except Exception as e:
        print(f"❌ 확인 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_data_availability()