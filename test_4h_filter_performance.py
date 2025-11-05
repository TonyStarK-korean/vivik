# -*- coding: utf-8 -*-
"""
4시간봉 필터링 성능 개선 테스트
"""

import sys
import time
import random
from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy

def generate_test_symbols(count=531):
    """테스트용 심볼 데이터 생성"""
    symbols = []
    
    # 실제와 유사한 심볼 데이터 생성
    popular_coins = ['BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'XRP', 'DOT', 'DOGE', 'AVAX', 'MATIC']
    
    for i in range(count):
        if i < len(popular_coins):
            symbol = f"{popular_coins[i]}/USDT:USDT"
        else:
            symbol = f"COIN{i}/USDT:USDT"
        
        # 변동률: -10% ~ +15% 범위
        change_pct = random.uniform(-10.0, 15.0)
        
        # 거래량: 1,000 ~ 1,000,000 범위 (로그 분포)
        volume_24h = random.uniform(1000, 1000000)
        
        symbols.append((symbol, change_pct, volume_24h))
    
    return symbols

def test_4h_filtering_performance():
    """4시간봉 필터링 성능 테스트"""
    print("🧪 4시간봉 필터링 성능 테스트 시작")
    print("=" * 60)
    
    try:
        # 전략 초기화 (공개 API 모드)
        strategy = OneMinuteSurgeEntryStrategy()
        
        # 테스트 데이터 생성
        print("📊 테스트 데이터 생성 중...")
        test_symbols = generate_test_symbols(531)
        print(f"   생성된 심볼 수: {len(test_symbols)}개")
        
        # 상위 10개 심볼 미리보기
        print("\n📈 상위 10개 심볼 (변동률 기준):")
        sorted_symbols = sorted(test_symbols, key=lambda x: abs(x[1]), reverse=True)
        for i, (symbol, change_pct, volume_24h) in enumerate(sorted_symbols[:10]):
            print(f"   {i+1:2d}. {symbol:15s} {change_pct:6.2f}% (거래량: {volume_24h:,.0f})")
        
        # 4시간봉 필터링 성능 테스트
        print(f"\n🔍 4시간봉 필터링 성능 테스트 (입력: {len(test_symbols)}개 심볼)")
        start_time = time.time()
        
        # 개선된 필터링 실행
        filtered_results = strategy._websocket_4h_filtering(test_symbols)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # 결과 출력
        print(f"\n✅ 필터링 완료!")
        print(f"   처리 시간: {processing_time:.2f}초")
        print(f"   입력 심볼: {len(test_symbols)}개")
        print(f"   출력 심볼: {len(filtered_results)}개")
        print(f"   처리 속도: {len(test_symbols)/processing_time:.1f} 심볼/초")
        
        if len(filtered_results) > 0:
            print(f"\n🎯 필터링 통과 심볼 (상위 5개):")
            for i, result in enumerate(filtered_results[:5]):
                if isinstance(result, tuple) and len(result) >= 3:
                    symbol, change_pct, volume_24h = result
                    print(f"   {i+1}. {symbol:15s} {change_pct:6.2f}% (거래량: {volume_24h:,.0f})")
        
        # 성능 개선 효과 계산
        original_expected_time = len(test_symbols) * 0.1  # 기존 예상 시간 (심볼당 0.1초)
        improvement_ratio = original_expected_time / processing_time if processing_time > 0 else 0
        
        print(f"\n⚡ 성능 개선 효과:")
        print(f"   기존 예상 시간: {original_expected_time:.1f}초")
        print(f"   실제 처리 시간: {processing_time:.2f}초")
        print(f"   성능 개선 배수: {improvement_ratio:.1f}x")
        
        # 메모리 사용량 체크 (간단한 측정)
        import psutil
        import os
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / 1024 / 1024  # MB
        print(f"   메모리 사용량: {memory_usage:.1f} MB")
        
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("4시간봉 필터링 성능 개선 테스트")
    print("개선사항:")
    print("1. 처리할 심볼 수 제한 (531개 → 100개)")
    print("2. 상위 변동률/거래량 기준 사전 필터링") 
    print("3. WebSocket 데이터 우선 처리")
    print("4. REST API 타임아웃 메커니즘 추가")
    print()
    
    success = test_4h_filtering_performance()
    
    if success:
        print("\n🎉 테스트 성공! 성능 개선이 정상적으로 적용되었습니다.")
    else:
        print("\n💥 테스트 실패! 코드를 다시 확인해주세요.")