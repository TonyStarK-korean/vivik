# -*- coding: utf-8 -*-

import time

def test_websocket():
    print("WebSocket test start")
    
    try:
        from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy
        
        strategy = OneMinuteSurgeEntryStrategy(None, None, False)
        
        # WebSocket check
        if hasattr(strategy, 'ws_kline_manager') and strategy.ws_kline_manager:
            print("WebSocket manager OK")
        else:
            print("WebSocket manager FAIL")
            return
        
        # Wait for data
        time.sleep(5)
        
        # Buffer check
        if hasattr(strategy, '_websocket_kline_buffer'):
            buffer = strategy._websocket_kline_buffer
            print(f"Buffer keys: {len(buffer)}")
            
            m5_keys = [k for k in buffer.keys() if '_5m' in k]
            print(f"5m keys: {len(m5_keys)}")
        
        # Filter test
        filtered = strategy.get_filtered_symbols(1.0)
        print(f"Filtered: {len(filtered)}")
        
        # Cleanup
        if hasattr(strategy, 'ws_kline_manager'):
            strategy.ws_kline_manager.shutdown()
        
        print("Test complete")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_websocket()