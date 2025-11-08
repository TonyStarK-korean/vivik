#!/bin/bash
# VPS 강제 업데이트 스크립트
# 로컬 변경사항을 무시하고 GitHub 최신 버전으로 강제 업데이트
# Usage: ./force_update_vps.sh

echo "========================================="
echo "⚠️  VPS 강제 업데이트 스크립트"
echo "========================================="
echo ""
echo "⚠️  경고: 이 스크립트는 VPS의 모든 로컬 변경사항을 삭제하고"
echo "         GitHub의 최신 버전으로 강제 덮어쓰기합니다!"
echo ""

# 프로젝트 경로 설정
PROJECT_DIR=~/vivik
cd $PROJECT_DIR || { echo "❌ 프로젝트 디렉토리를 찾을 수 없습니다: $PROJECT_DIR"; exit 1; }

echo "📁 프로젝트 경로: $PROJECT_DIR"
echo ""

# 5초 대기 (취소 가능)
echo "⏰ 5초 후 강제 업데이트를 시작합니다..."
echo "   취소하려면 Ctrl+C를 누르세요!"
for i in 5 4 3 2 1; do
    echo "   $i..."
    sleep 1
done
echo ""

# 백업 생성
BACKUP_DIR=~/vivik_backup_force_$(date +%Y%m%d_%H%M%S)
echo "💾 백업 생성 중: $BACKUP_DIR"
cp -r . $BACKUP_DIR
echo "✅ 백업 완료"
echo ""

# 봇 중지
echo "🛑 봇 중지 중..."
if systemctl is-active --quiet trading-bot 2>/dev/null; then
    sudo systemctl stop trading-bot
    echo "✅ systemd 봇 중지 완료"
else
    pkill -f one_minute_surge_entry_strategy.py 2>/dev/null
    echo "✅ 백그라운드 봇 중지 완료"
fi
sleep 2
echo ""

# Git 상태 확인
echo "📊 현재 Git 상태:"
git status --short
echo ""

# 로컬 변경사항 모두 버리기
echo "🗑️  로컬 변경사항 삭제 중..."
git fetch origin
git reset --hard origin/main
git clean -fd
echo "✅ 로컬 변경사항 삭제 완료"
echo ""

# 최신 코드 가져오기
echo "📥 GitHub에서 최신 코드 가져오기..."
git pull origin main
echo "✅ 최신 코드 업데이트 완료"
echo ""

# 변경사항 확인
echo "📝 최근 커밋 3개:"
git log -3 --oneline --decorate
echo ""

# Python 패키지 확인
echo "🔍 Python 패키지 확인 중..."
if [ -f requirements.txt ]; then
    pip3 install -r requirements.txt --quiet --upgrade
    echo "✅ 패키지 업데이트 완료"
else
    echo "⚠️  requirements.txt 파일 없음"
fi
echo ""

# Config 파일 확인
echo "🔍 설정 파일 확인..."
if [ ! -f binance_config.py ]; then
    echo "⚠️  binance_config.py 파일이 없습니다!"
    echo "   백업에서 복사하거나 새로 생성해야 합니다."
    if [ -f $BACKUP_DIR/binance_config.py ]; then
        echo "   백업에서 복사 중..."
        cp $BACKUP_DIR/binance_config.py .
        echo "✅ binance_config.py 복사 완료"
    fi
fi

if [ ! -f telegram_config.py ]; then
    echo "⚠️  telegram_config.py 파일이 없습니다!"
    if [ -f $BACKUP_DIR/telegram_config.py ]; then
        echo "   백업에서 복사 중..."
        cp $BACKUP_DIR/telegram_config.py .
        echo "✅ telegram_config.py 복사 완료"
    fi
fi
echo ""

# 봇 재시작
echo "🚀 봇 재시작 중..."
if [ -f /etc/systemd/system/trading-bot.service ]; then
    sudo systemctl start trading-bot
    sleep 3

    if systemctl is-active --quiet trading-bot; then
        echo "✅ systemd로 봇 시작 완료"
    else
        echo "❌ systemd 시작 실패, 직접 실행 시도..."
        nohup python3 one_minute_surge_entry_strategy.py > trading_bot.log 2>&1 &
    fi
else
    nohup python3 one_minute_surge_entry_strategy.py > trading_bot.log 2>&1 &
    echo "✅ 백그라운드로 봇 시작 완료"
fi
sleep 2
echo ""

# 상태 확인
echo "========================================="
echo "📊 최종 상태"
echo "========================================="
echo ""

# 봇 실행 상태
if systemctl is-active --quiet trading-bot 2>/dev/null; then
    echo "✅ 봇 실행 중 (systemd)"
    sudo systemctl status trading-bot --no-pager | head -10
elif pgrep -f one_minute_surge_entry_strategy.py > /dev/null; then
    echo "✅ 봇 실행 중 (백그라운드)"
    echo "   PID: $(pgrep -f one_minute_surge_entry_strategy.py)"
else
    echo "❌ 봇이 실행되지 않음!"
    echo ""
    echo "🔍 문제 해결:"
    echo "   tail -50 trading_bot.log"
fi
echo ""

# Git 상태
echo "📌 현재 Git 상태:"
git log -1 --oneline
git status --short
echo ""

echo "========================================="
echo "✅ 강제 업데이트 완료!"
echo "========================================="
echo ""
echo "📝 다음 단계:"
echo "   1. 로그 확인: tail -f trading_bot.log"
echo "   2. 텔레그램 알림 확인"
echo "   3. 포지션/거래 확인"
echo ""
echo "🔄 롤백이 필요하면:"
echo "   cd ~ && rm -rf vivik && mv $BACKUP_DIR vivik"
echo "   cd vivik && sudo systemctl start trading-bot"
echo ""
