# -*- coding: utf-8 -*-
"""
MA480 수정 테스트
"""
import sys
import os
import ccxt
import pandas as pd

# 스크립트 디렉토리 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

def test_problematic_symbols():
    """문제가 되었던 심볼들 테스트"""
    
    # 문제 심볼들
    symbols = ["METIS", "TRADOOR", "MUBARAK", "MELANIA", "APR", "BLUAI"]
    
    print("=== MA480 수정 테스트 ===")
    print("15분봉에서 직접 MA480 계산")
    print()
    
    try:
        exchange = ccxt.binance()
        
        for symbol in symbols:
            try:
                print(f"--- {symbol} ---")
                
                # 15분봉 데이터 600개 가져오기 (MA480을 위해 충분한 데이터)
                ohlcv = exchange.fetch_ohlcv(f'{symbol}/USDT', '15m', limit=600)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
                print(f"데이터 개수: {len(df)}")
                
                if len(df) < 480:
                    print(f"❌ 데이터 부족: {len(df)}개 (480개 필요)")
                    continue
                
                # MA 계산
                df['ma5'] = df['close'].rolling(window=5).mean()
                df['ma80'] = df['close'].rolling(window=80).mean()
                df['ma480'] = df['close'].rolling(window=480).mean()
                
                # 현재 값들
                current_price = df['close'].iloc[-1]
                ma5 = df['ma5'].iloc[-1]
                ma80 = df['ma80'].iloc[-1]
                ma480 = df['ma480'].iloc[-1]
                
                print(f"현재가: {current_price:.6f}")
                print(f"MA5: {ma5:.6f}")
                print(f"MA80: {ma80:.6f}")
                print(f"MA480: {ma480:.6f}")
                
                # 전제조건 체크
                ma80_vs_ma480 = pd.notna(ma80) and pd.notna(ma480) and ma80 < ma480
                ma5_vs_ma480 = pd.notna(ma5) and pd.notna(ma480) and ma5 < ma480
                basic_condition = ma80_vs_ma480 and ma5_vs_ma480
                
                print(f"MA80 < MA480: {ma80_vs_ma480}")
                print(f"MA5 < MA480: {ma5_vs_ma480}")
                print(f"전제조건 통과: {basic_condition}")
                
                if not basic_condition:
                    print("❌ A전략 진입 불가 - 전제조건 차단")
                else:
                    print("✅ A전략 진입 가능 - 전제조건 통과")
                
                print()
                
            except Exception as e:
                print(f"❌ {symbol} 테스트 실패: {e}")
                print()
                
    except Exception as e:
        print(f"테스트 실패: {e}")

if __name__ == "__main__":
    test_problematic_symbols()