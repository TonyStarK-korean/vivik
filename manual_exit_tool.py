# -*- coding: utf-8 -*-
"""
수동 청산 도구 - 긴급 포지션 청산용
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from improved_dca_position_manager import ImprovedDCAPositionManager
from binance_config import BinanceConfig
import ccxt

def main():
    """수동 청산 실행"""
    try:
        # 거래소 연결
        exchange = ccxt.binance({
            'apiKey': BinanceConfig.API_KEY,
            'secret': BinanceConfig.SECRET_KEY,
            'sandbox': BinanceConfig.TESTNET,
            'options': {'defaultType': 'future'}
        })
        
        # DCA 매니저 초기화
        dca_manager = ImprovedDCAPositionManager(
            exchange=exchange,
            telegram_bot=None
        )
        
        # 현재 활성 포지션 표시
        print("=== 현재 활성 Position ===")
        positions = dca_manager.load_data()
        
        active_positions = {k: v for k, v in positions.items() if v.get('is_active', False)}
        
        if not active_positions:
            print("활성 Position이 없습니다.")
            return
        
        for i, (symbol, pos) in enumerate(active_positions.items(), 1):
            print(f"{i}. {symbol}")
            print(f"   Entry가: ${pos['initial_entry_price']:.6f}")
            print(f"   Average price: ${pos['average_price']:.6f}")
            print(f"   수량: {pos['total_quantity']}")
            print(f"   단계: {pos['current_stage']}")
            
            # 현재가 조회
            try:
                ticker = exchange.fetch_ticker(symbol)
                current_price = ticker['last']
                profit_pct = (current_price - pos['average_price']) / pos['average_price'] * 100
                print(f"   현재가: ${current_price:.6f}")
                print(f"   Profit rate: {profit_pct:+.2f}%")
            except:
                print("   현재가: Retrieval Failed")
            print()
        
        # 청산할 포지션 선택
        try:
            choice = input("청산할 포지션 번호 (q=종료): ")
            if choice.lower() == 'q':
                return
            
            choice = int(choice) - 1
            symbol = list(active_positions.keys())[choice]
            position = active_positions[symbol]
            
            print(f"\n선택된 Position: {symbol}")
            confirm = input("정말로 전량 청산하시겠습니까? (yes/no): ")
            
            if confirm.lower() != 'yes':
                print("Exit이 Cancelled되었습니다.")
                return
            
            # 현재가 조회
            ticker = exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            
            # 긴급 청산 실행
            success = dca_manager._execute_emergency_exit(
                dca_manager.positions[symbol], 
                current_price, 
                "manual_exit"
            )
            
            if success:
                print(f"✅ {symbol} 전량 Exit Complete!")
            else:
                print(f"❌ {symbol} Exit Failed")
                
        except (ValueError, IndexError):
            print("잘못된 times호입니다.")
        except KeyboardInterrupt:
            print("\nExit이 Cancelled되었습니다.")
            
    except Exception as e:
        print(f"Error 발생: {e}")

if __name__ == "__main__":
    main()