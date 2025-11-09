#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VPN 연결 후 바이낸스 접근 테스트
"""

import requests
import time

def test_binance_with_vpn():
    """VPN 연결 후 바이낸스 API 테스트"""
    print("=== VPN 연결 후 바이낸스 테스트 ===")
    
    # 1. 현재 IP 확인
    try:
        print("1. 현재 IP 주소 확인...")
        ip_response = requests.get("https://api.ipify.org", timeout=10)
        current_ip = ip_response.text
        print(f"   현재 IP: {current_ip}")
    except Exception as e:
        print(f"   IP 확인 실패: {e}")
    
    # 2. 바이낸스 접근 테스트
    print("\n2. 바이낸스 API 접근 테스트...")
    try:
        response = requests.get("https://fapi.binance.com/fapi/v1/ping", timeout=10)
        
        if response.status_code == 200:
            print("   ✅ 성공! 바이낸스 접근 가능!")
            print("   🎉 IP 밴 해제 완료!")
            return True
        elif response.status_code == 418:
            print("   ❌ 여전히 IP 밴 상태")
            print("   💡 다른 VPN 서버로 변경해보세요")
            return False
        elif response.status_code == 429:
            print("   ⚠️ Rate Limit - 잠시 후 재시도")
            return False
        else:
            print(f"   ❓ 알 수 없는 응답: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   🌐 네트워크 오류: {e}")
        return False
    
    # 3. 거래소 연결 테스트
    print("\n3. 거래소 마켓 데이터 테스트...")
    try:
        response = requests.get("https://fapi.binance.com/fapi/v1/ticker/24hr?symbol=BTCUSDT", timeout=10)
        if response.status_code == 200:
            data = response.json()
            price = float(data['lastPrice'])
            change = float(data['priceChangePercent'])
            print(f"   ✅ BTC 가격: ${price:,.2f} ({change:+.2f}%)")
            print("   🚀 마켓 데이터 정상 수신!")
            return True
        else:
            print(f"   ❌ 마켓 데이터 오류: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ 마켓 데이터 실패: {e}")
        return False

def main():
    print("ProtonVPN 연결 후 이 스크립트를 실행하세요!")
    print("-" * 50)
    
    # 연결 대기
    input("ProtonVPN에 연결되면 Enter를 누르세요...")
    
    # 테스트 실행
    success = test_binance_with_vpn()
    
    if success:
        print("\n🎉 모든 테스트 통과!")
        print("이제 트레이딩 봇을 안전하게 실행할 수 있습니다!")
        print("\n다음 단계:")
        print("1. 트레이딩 봇 재시작")
        print("2. 정상 작동 확인")
        print("3. VPN 연결 유지")
    else:
        print("\n❌ 아직 문제가 있습니다")
        print("해결 방법:")
        print("1. ProtonVPN에서 다른 서버로 변경")
        print("2. 앱 재시작 후 다시 연결")
        print("3. 5분 후 재테스트")

if __name__ == "__main__":
    main()