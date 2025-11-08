#!/bin/bash
# VPS Trading Bot Automatic Update and Restart Script
# Usage: ./update_and_restart.sh

echo "========================================="
echo "📦 VPS Trading Bot Update Script"
echo "========================================="
echo ""

# 프로젝트 경로 설정 (필요시 수정)
PROJECT_DIR=~/vivik
cd $PROJECT_DIR || { echo "❌ Project directory not found: $PROJECT_DIR"; exit 1; }

echo "📁 Project directory: $PROJECT_DIR"
echo ""

# 백업 생성
BACKUP_DIR=~/vivik_backup_$(date +%Y%m%d_%H%M%S)
echo "💾 Creating backup: $BACKUP_DIR"
cp -r . $BACKUP_DIR
echo "✅ Backup created successfully"
echo ""

# 봇 중지
echo "🛑 Stopping trading bot..."
BOT_STOPPED=false

# systemd 서비스 확인 및 중지
if systemctl is-active --quiet trading-bot 2>/dev/null; then
    sudo systemctl stop trading-bot
    echo "✅ Trading bot stopped (systemd)"
    BOT_STOPPED=true
else
    echo "ℹ️  Trading bot is not running via systemd"
fi

# 프로세스 직접 종료 (이중 확인)
if pgrep -f one_minute_surge_entry_strategy.py > /dev/null; then
    echo "🔍 Found running bot process, killing..."
    pkill -f one_minute_surge_entry_strategy.py
    sleep 2
    BOT_STOPPED=true
    echo "✅ Bot process killed"
fi

if [ "$BOT_STOPPED" = false ]; then
    echo "ℹ️  No running bot detected"
fi
echo ""

# Git 업데이트
echo "📥 Pulling latest changes from GitHub..."
git fetch origin

# 충돌 체크
if git diff --quiet HEAD origin/main; then
    echo "ℹ️  Already up to date"
else
    echo "🔄 Updates available, pulling..."
    git pull origin main

    if [ $? -eq 0 ]; then
        echo "✅ Git pull successful"
    else
        echo "❌ Git pull failed"
        echo "ℹ️  You may need to resolve conflicts manually"
        echo "ℹ️  Or use: git stash && git pull origin main && git stash pop"
        exit 1
    fi
fi
echo ""

# 변경사항 확인
echo "📝 Recent changes:"
git log -3 --oneline --decorate
echo ""

# Python 패키지 확인
echo "🔍 Checking Python dependencies..."
if [ -f requirements.txt ]; then
    pip3 install -r requirements.txt --quiet
    echo "✅ Dependencies checked"
else
    echo "⚠️  requirements.txt not found"
fi
echo ""

# 봇 재시작
echo "🚀 Starting trading bot..."
BOT_STARTED=false

# systemd 서비스가 있으면 사용
if [ -f /etc/systemd/system/trading-bot.service ]; then
    sudo systemctl start trading-bot
    sleep 3

    if systemctl is-active --quiet trading-bot; then
        echo "✅ Trading bot started via systemd"
        BOT_STARTED=true
    else
        echo "❌ systemd start failed, trying direct execution..."
    fi
fi

# systemd가 없거나 실패한 경우 직접 실행
if [ "$BOT_STARTED" = false ]; then
    nohup python3 one_minute_surge_entry_strategy.py > trading_bot.log 2>&1 &
    sleep 3

    if pgrep -f one_minute_surge_entry_strategy.py > /dev/null; then
        echo "✅ Trading bot started in background (PID: $(pgrep -f one_minute_surge_entry_strategy.py))"
        BOT_STARTED=true
    else
        echo "❌ Failed to start trading bot"
        echo "ℹ️  Check logs: tail -50 trading_bot.log"
    fi
fi
echo ""

# 상태 확인
echo "========================================="
echo "📊 Status Check"
echo "========================================="

if systemctl is-active --quiet trading-bot 2>/dev/null; then
    echo "✅ Trading bot is running (systemd)"
    sudo systemctl status trading-bot --no-pager | head -15
elif pgrep -f one_minute_surge_entry_strategy.py > /dev/null; then
    echo "✅ Trading bot is running (background)"
    echo "   PID: $(pgrep -f one_minute_surge_entry_strategy.py)"
    echo "   Check logs: tail -f trading_bot.log"
else
    echo "❌ Trading bot is NOT running"
    echo ""
    echo "🔍 Troubleshooting:"
    echo "   1. Check logs: tail -50 trading_bot.log"
    echo "   2. Check errors: grep -i error trading_bot.log"
    echo "   3. Manual start: python3 one_minute_surge_entry_strategy.py"
fi

echo ""
echo "========================================="
echo "✅ Update completed!"
echo "========================================="
echo ""
echo "📝 Next steps:"
echo "   1. Monitor logs: tail -f trading_bot.log"
echo "   2. Check Telegram notifications"
echo "   3. Verify positions/trading activity"
echo ""
echo "🔄 Rollback if needed:"
echo "   1. Stop bot: sudo systemctl stop trading-bot"
echo "   2. Restore: rm -rf ~/vivik && mv $BACKUP_DIR ~/vivik"
echo "   3. Restart: sudo systemctl start trading-bot"
echo ""
