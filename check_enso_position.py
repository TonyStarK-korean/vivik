#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ccxt
import json
from binance_config import BinanceConfig

# 바이낸스 연결
exchange = ccxt.binance({
    'apiKey': BinanceConfig.API_KEY,
    'secret': BinanceConfig.SECRET_KEY,
    'sandbox': False,
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

# ENSO 현재가 확인
ticker = exchange.fetch_ticker('ENSO/USDT:USDT')
current_price = ticker['last']
print(f"ENSO 현재가: {current_price} USDT")

# 포지션 확인
positions = exchange.fetch_positions(['ENSO/USDT:USDT'])
print(f"전체 포지션 정보: {positions}")

for pos in positions:
    print(f"포지션 항목: {pos}")
    if float(pos.get('contracts', 0)) != 0:
        pnl_pct = pos.get('percentage', 0)
        print(f"포지션 수량: {pos.get('contracts', 0)}")
        print(f"평단가: {pos.get('markPrice', 0)}")
        print(f"현재 수익률: {pnl_pct:.2f}%")
        print(f"미실현 손익: {pos.get('unrealizedPnl', 0)} USDT")

        # 긴급 청산 실행
        if pnl_pct < -60:  # -60% 이하면 긴급 청산
            print("🚨 긴급 청산 실행!")
            try:
                order = exchange.create_market_sell_order('ENSO/USDT:USDT', abs(float(pos['contracts'])))
                print(f"청산 주문 성공: {order}")
            except Exception as e:
                print(f"청산 주문 실패: {e}")
                
print("포지션 정보가 없거나 이미 청산된 것 같습니다.")