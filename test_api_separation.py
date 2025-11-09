# -*- coding: utf-8 -*-
"""
API 분리 테스트 스크립트
"""
import os
import sys
import ccxt

# 스크립트 디렉토리를 Python 경로에 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from binance_config import BinanceConfig
    HAS_BINANCE_CONFIG = True
except ImportError:
    print("[INFO] binance_config.py 없음 - 공개 API만 사용")
    class BinanceConfig:
        API_KEY = ""
        SECRET_KEY = ""
    HAS_BINANCE_CONFIG = False

def test_api_separation():
    """API 분리 테스트"""
    print("[INFO] API 분리 테스트 시작...")
    
    # 공개 API 테스트 (스캔용)
    print("\n[TEST] 1. 공개 API 테스트 (마켓 데이터 조회)")
    try:
        public_exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
        # 마켓 데이터 로드 (공개 API)
        markets = public_exchange.load_markets()
        usdt_futures = [symbol for symbol, market in markets.items() 
                       if symbol.endswith('/USDT:USDT') and market.get('active', False)]
        
        print(f"   [SUCCESS] 공개 API 작동 - USDT 선물: {len(usdt_futures)}개")
        
        # 실시간 가격 조회 테스트 (첫 5개 심볼)
        test_symbols = usdt_futures[:5]
        for symbol in test_symbols:
            try:
                ticker = public_exchange.fetch_ticker(symbol)
                clean_symbol = symbol.replace('/USDT:USDT', '')
                price = ticker['last']
                print(f"   [DATA] {clean_symbol}: ${price:,.4f}")
            except Exception as e:
                print(f"   [SKIP] {clean_symbol} 가격 조회 실패: {e}")
                
    except Exception as e:
        print(f"   [ERROR] 공개 API 실패: {e}")
        return False
    
    # 프라이빗 API 테스트 (거래용)
    print("\n[TEST] 2. 프라이빗 API 테스트")
    if not HAS_BINANCE_CONFIG or not BinanceConfig.API_KEY:
        print("   [SKIP] API 키 없음 - 프라이빗 API 테스트 건너뛰기")
        return True
        
    try:
        private_exchange = ccxt.binance({
            'apiKey': BinanceConfig.API_KEY,
            'secret': BinanceConfig.SECRET_KEY,
            'sandbox': False,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        
        print("   [INFO] 프라이빗 API 초기화 완료")
        
        # 잔고 조회 테스트
        try:
            balance = private_exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {})
            free_balance = usdt_balance.get('free', 0)
            total_balance = usdt_balance.get('total', 0)
            
            print(f"   [SUCCESS] 잔고 조회 성공")
            print(f"   [BALANCE] 가용 잔고: ${free_balance:.2f} USDT")
            print(f"   [BALANCE] 총 잔고: ${total_balance:.2f} USDT")
            
        except Exception as e:
            if "-2015" in str(e):
                print(f"   [ERROR] API 권한 오류 (-2015): {e}")
                print("   [INFO] API 키에 선물 거래 권한이 없거나 IP 제한이 있을 수 있습니다.")
                return False
            else:
                print(f"   [ERROR] 잔고 조회 실패: {e}")
                return False
        
        # 포지션 조회 테스트
        try:
            positions = private_exchange.fetch_positions()
            active_positions = [p for p in positions if p['contracts'] > 0]
            
            print(f"   [SUCCESS] 포지션 조회 성공")
            print(f"   [POSITIONS] 활성 포지션: {len(active_positions)}개")
            
            if active_positions:
                for position in active_positions[:3]:  # 최대 3개만 출력
                    symbol = position['symbol'].replace('/USDT:USDT', '')
                    size = position['contracts']
                    pnl_pct = position['percentage'] or 0
                    print(f"   [POSITION] {symbol}: {size:.6f} ({pnl_pct:+.2f}%)")
                    
        except Exception as e:
            print(f"   [ERROR] 포지션 조회 실패: {e}")
            return False
            
        print("   [SUCCESS] 프라이빗 API 모든 테스트 통과")
        return True
        
    except Exception as e:
        print(f"   [ERROR] 프라이빗 API 초기화 실패: {e}")
        return False

def main():
    """메인 함수"""
    print("="*60)
    print("15분봉 초필살기 전략 - API 분리 테스트")
    print("="*60)
    
    result = test_api_separation()
    
    print("\n" + "="*60)
    if result:
        print("[RESULT] 모든 테스트 성공 - API 분리 정상 작동")
        print("[INFO] 15분봉 초필살기 전략을 실행할 수 있습니다.")
    else:
        print("[RESULT] 테스트 실패 - API 설정 또는 권한 문제")
        print("[INFO] binance_config.py의 API 키와 권한을 확인하세요.")
    print("="*60)

if __name__ == "__main__":
    main()