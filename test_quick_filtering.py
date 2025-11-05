# -*- coding: utf-8 -*-
"""
빠른 통합 필터링 테스트
"""

def test_data_structure():
    """데이터 구조 테스트"""
    print("=== 데이터 구조 테스트 ===")
    
    # 테스트 데이터 - 4개 요소 구조 (candidate_symbols)
    test_data_4 = [
        ('BTC/USDT:USDT', -0.1, 1000000, {'extra': 'data'}),
        ('ETH/USDT:USDT', 5.2, 500000, {'extra': 'data'}),
        ('ZK/USDT:USDT', 57.4, 100000, {'extra': 'data'})
    ]
    
    # 테스트 데이터 - 3개 요소 구조 (_websocket_4h_filtering)
    test_data_3 = [
        ('DASH/USDT:USDT', 34.4, 200000),
        ('AIOT/USDT:USDT', 34.2, 150000)
    ]
    
    # 통합 테스트
    combined = test_data_4 + test_data_3
    print(f"통합 데이터: {len(combined)}개")
    
    # 심볼 추출 테스트 (수정된 로직)
    result_symbols = []
    for item in combined:
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            result_symbols.append(item[0])  # 첫 번째 요소가 심볼
        else:
            result_symbols.append(item)
    
    print(f"추출된 심볼: {result_symbols}")
    
    # 상위 심볼 출력 테스트
    print("\n상위 심볼 정보:")
    for item in combined[:3]:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            symbol_name = item[0].replace('/USDT:USDT', '').replace('/USDT', '')
            change_pct = item[1]
            print(f"  {symbol_name}(+{change_pct:.1f}%)")
        else:
            symbol_name = str(item).replace('/USDT:USDT', '').replace('/USDT', '')
            print(f"  {symbol_name}")
    
    print("\n✅ 데이터 구조 테스트 완료")

if __name__ == "__main__":
    test_data_structure()