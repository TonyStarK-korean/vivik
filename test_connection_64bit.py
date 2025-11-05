import ccxt
import sys

print(f"Python 버전: {sys.version}")
print(f"비트: {sys.maxsize > 2**32 and '64-bit' or '32-bit'}")
print()

try:
    print("Binance API 연결 테스트 중...")
    ex = ccxt.binance()
    ticker = ex.fetch_ticker('BTC/USDT')
    print(f"✅ 성공! BTC 현재가: ${ticker['last']:,.2f}")
    print()
    print("🎉 64비트 Python으로 Binance API 연결 성공!")
except Exception as e:
    print(f"❌ 실패: {e}")
    sys.exit(1)
