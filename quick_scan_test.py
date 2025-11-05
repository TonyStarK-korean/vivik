# 간단한 스캔 테스트
import time

def test_scan():
    print("간단한 스캔 테스트 시작")
    
    try:
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        
        strategy = OneMinuteSurgeEntryStrategy(None, None, False)
        
        # 간단한 심볼 리스트로 테스트
        test_symbols = ['AVAAI/USDT:USDT', 'SQD/USDT:USDT']
        
        print(f"테스트 심볼: {test_symbols}")
        print("스캔 시작...")
        
        # 스캔 실행
        strategy.scan_symbols(test_symbols)
        
        # 정리
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            strategy.ws_kline_manager.shutdown()
        
        print("테스트 완료")
        
    except Exception as e:
        print(f"테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_scan()