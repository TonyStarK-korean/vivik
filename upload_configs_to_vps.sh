#!/bin/bash
# ==================================================================
# VPS Config File Upload Script (English Only)
# ==================================================================
# This script creates binance_config.py and telegram_config.py
# Copy and paste this entire script into your VPS SSH terminal
# ==================================================================

echo "===================================================================="
echo "Creating Binance and Telegram config files..."
echo "===================================================================="
echo ""

# Navigate to project directory
cd ~/vivik

# Create binance_config.py
echo "Creating binance_config.py..."
cat > binance_config.py << 'BINANCE_EOF'
# 바이낸스 API 설정
class BinanceConfig:
    # API 키 설정
    API_KEY = "Ljyd55VX6OZEY3pdqM2KlJk8g5cHmRDmOs7HBwzPfby4Njfg7Vs24exv3nZrw1m3"
    SECRET_KEY = "Jl1hPQYfXcYfVijELwbejgHID9tLq3IXmtSkWxxtMLhtni8XvAJU1oV0ouREXbgE"
    SECRET = SECRET_KEY  # 호환성을 위한 별칭

    # 거래 설정
    LEVERAGE = 5  # 레버리지 (기본 5배)
    POSITION_SIZE_PCT = 5  # 포지션 크기 비율 (5%)

    # 안전 설정
    TESTNET = False  # True: 테스트넷, False: 실제 거래
    USE_TESTNET = TESTNET  # 호환성을 위한 별칭

    # API 제한 설정
    ENABLE_RATE_LIMIT = True

    @classmethod
    def get_config(cls):
        """API 설정 딕셔너리 반환"""
        return {
            'apiKey': cls.API_KEY,
            'secret': cls.SECRET_KEY,
            'sandbox': cls.TESTNET,
            'enableRateLimit': cls.ENABLE_RATE_LIMIT,
            'options': {
                'defaultType': 'swap'  # 선물 거래
            }
        }

    @classmethod
    def get_api_credentials(cls):
        """API 자격증명 반환"""
        return {
            'apiKey': cls.API_KEY,
            'secret': cls.SECRET_KEY,
            'sandbox': cls.TESTNET,
            'enableRateLimit': cls.ENABLE_RATE_LIMIT
        }

    @classmethod
    def validate_config(cls):
        """API 설정 유효성 검증"""
        try:
            # API 키와 시크릿 키가 설정되어 있는지 확인
            if not cls.API_KEY or not cls.SECRET_KEY:
                return False, "API 키 또는 시크릿 키가 설정되지 않았습니다"

            # 키 길이 검증 (바이낸스 API 키는 보통 64자)
            if len(cls.API_KEY) < 10 or len(cls.SECRET_KEY) < 10:
                return False, "API 키 또는 시크릿 키가 너무 짧습니다"

            return True, "API 설정이 유효합니다"

        except Exception as e:
            return False, f"설정 검증 중 오류: {e}"
BINANCE_EOF

echo "✅ binance_config.py created"

# Create telegram_config.py
echo "Creating telegram_config.py..."
cat > telegram_config.py << 'TELEGRAM_EOF'
# 텔레그램 봇 설정
TELEGRAM_BOT_TOKEN = "7956902168:AAG23yyVuByGDthMUVmdDkO2oBD3ODDftnA"  # BotFather에서 받은 봇 토큰
TELEGRAM_CHAT_ID = "7213415516"     # 메시지를 받을 채팅방 ID
TELEGRAM_EOF

echo "✅ telegram_config.py created"
echo ""

# Verify files exist
echo "===================================================================="
echo "Verifying files..."
echo "===================================================================="
ls -lh binance_config.py telegram_config.py
echo ""

# Test Python import
echo "Testing Python import..."
python3 << 'PYTHON_TEST_EOF'
try:
    from binance_config import BinanceConfig
    import telegram_config
    print("✅ binance_config.py imported successfully")
    print("✅ telegram_config.py imported successfully")
    print(f"   Binance API Key: {BinanceConfig.API_KEY[:10]}...")
    print(f"   Telegram Bot Token: {telegram_config.TELEGRAM_BOT_TOKEN[:10]}...")
except Exception as e:
    print(f"❌ Import failed: {e}")
    exit(1)
PYTHON_TEST_EOF

echo ""
echo "===================================================================="
echo "✅ Config files uploaded successfully!"
echo "===================================================================="
echo ""

# Ask to restart bot
echo "Do you want to restart the trading bot? (y/n)"
read -r RESTART

if [ "$RESTART" = "y" ] || [ "$RESTART" = "Y" ]; then
    echo ""
    echo "Stopping bot..."
    pkill -f one_minute_surge_entry_strategy.py
    sleep 2

    echo "Starting bot..."
    nohup python3 one_minute_surge_entry_strategy.py > trading_bot.log 2>&1 &
    echo "Bot started (PID: $!)"

    echo ""
    echo "Showing recent logs (Ctrl+C to exit)..."
    sleep 2
    tail -f trading_bot.log
else
    echo ""
    echo "Manual restart commands:"
    echo "  pkill -f one_minute_surge_entry_strategy.py"
    echo "  nohup python3 one_minute_surge_entry_strategy.py > trading_bot.log 2>&1 &"
    echo "  tail -f trading_bot.log"
fi

echo ""
echo "===================================================================="
echo "Setup complete!"
echo "===================================================================="
