#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 키 권한 문제 진단 및 해결
"""

import ccxt
import time

def test_api_permissions():
    """API 키 권한 테스트"""
    try:
        from binance_config import BinanceConfig
        
        print("=== API 키 권한 테스트 ===")
        
        # 거래소 객체 생성
        exchange = ccxt.binance({
            'apiKey': BinanceConfig.API_KEY,
            'secret': BinanceConfig.SECRET_KEY,
            'sandbox': False,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # 선물 거래
            }
        })
        
        print("1. 기본 연결 테스트...")
        markets = exchange.load_markets()
        print(f"   ✅ 마켓 로드 성공: {len(markets)}개 마켓")
        
        print("2. 계좌 정보 테스트...")
        try:
            balance = exchange.fetch_balance()
            usdt_balance = balance.get('USDT', {}).get('free', 0)
            print(f"   ✅ 잔고 조회 성공: {usdt_balance:.2f} USDT")
        except Exception as e:
            if "2015" in str(e):
                print("   ❌ 계좌 정보 권한 없음 - 바이낸스에서 권한 활성화 필요")
                print("   💡 해결 방법: 바이낸스 API 관리에서 'Spot & Margin Trading' 권한 활성화")
            else:
                print(f"   ❌ 계좌 정보 오류: {e}")
        
        print("3. 선물 권한 테스트...")
        try:
            positions = exchange.fetch_positions()
            print(f"   ✅ 선물 포지션 조회 성공: {len(positions)}개 포지션")
        except Exception as e:
            if "2015" in str(e):
                print("   ❌ 선물 거래 권한 없음 - 바이낸스에서 권한 활성화 필요")
                print("   💡 해결 방법: 바이낸스 API 관리에서 'Futures' 권한 활성화")
            else:
                print(f"   ❌ 선물 권한 오류: {e}")
        
        print("4. 현재가 조회 테스트 (권한 불필요)...")
        try:
            ticker = exchange.fetch_ticker('BTC/USDT:USDT')
            price = ticker['last']
            print(f"   ✅ 현재가 조회 성공: BTC ${price:,.2f}")
        except Exception as e:
            print(f"   ❌ 현재가 조회 실패: {e}")
            
        return True
        
    except Exception as e:
        print(f"❌ API 테스트 실패: {e}")
        if "2015" in str(e):
            print("\n🔧 API 키 권한 문제 해결 방법:")
            print("1. 바이낸스 로그인 → API Management")
            print("2. 해당 API 키 클릭 → Edit")
            print("3. 다음 권한들 활성화:")
            print("   ✅ Enable Reading")
            print("   ✅ Enable Spot & Margin Trading")  
            print("   ✅ Enable Futures")
            print("4. IP 제한이 있다면 제거하거나 현재 IP 추가")
            print("5. 저장 후 5분 대기")
        return False

def main():
    test_api_permissions()

if __name__ == "__main__":
    main()