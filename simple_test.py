# -*- coding: utf-8 -*-
import ccxt
import pandas as pd

# 간단한 테스트
exchange = ccxt.binance()

# APR 15분봉 데이터 가져오기
ohlcv = exchange.fetch_ohlcv('APR/USDT', '15m', limit=500)
df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

# MA 계산
df['ma80'] = df['close'].rolling(window=80).mean()
df['ma480'] = df['close'].rolling(window=480).mean()
df['ma5'] = df['close'].rolling(window=5).mean()

# 현재 MA 값
ma80 = df['ma80'].iloc[-1]
ma480 = df['ma480'].iloc[-1]
ma5 = df['ma5'].iloc[-1]

print(f"APR - MA80: {ma80:.4f}, MA480: {ma480:.4f}, MA5: {ma5:.4f}")
print(f"MA80 < MA480: {ma80 < ma480}")
print(f"MA5 < MA480: {ma5 < ma480}")
print(f"전제조건: {ma80 < ma480 and ma5 < ma480}")