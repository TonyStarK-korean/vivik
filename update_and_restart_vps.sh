#!/bin/bash
# VPS 업데이트 및 안전한 재시작 스크립트
# systemd 서비스를 고려한 완전 종료 및 재시작

set -e  # 에러 발생시 스크립트 중단

echo "========================================"
echo "🔄 Alpha-Z VPS 업데이트 및 재시작"
echo "========================================"
echo ""

# 1. 프로젝트 디렉토리로 이동
cd /root/vivik || { echo "❌ 디렉토리 없음: /root/vivik"; exit 1; }
echo "📂 현재 디렉토리: $(pwd)"
echo ""

# 2. systemd 서비스 중지
echo "⏸️  systemd 서비스 중지 중..."
if systemctl is-active --quiet alpha_z_trading.service 2>/dev/null; then
    systemctl stop alpha_z_trading.service
    echo "   ✅ alpha_z_trading.service 중지됨"
else
    echo "   ℹ️  alpha_z_trading.service 실행 중 아님"
fi
echo ""

# 3. 모든 프로세스 강제 종료
echo "🛑 모든 alpha_z 프로세스 강제 종료 중..."
pkill -9 -f "alpha_z_triple_strategy" 2>/dev/null || echo "   (실행 중인 프로세스 없음)"
pkill -9 -f "one_minute_surge_entry_strategy" 2>/dev/null || echo "   (실행 중인 프로세스 없음)"
sleep 2
echo ""

# 4. 프로세스 종료 확인
REMAINING=$(ps aux | grep -E "[a]lpha_z" | wc -l)
if [ $REMAINING -gt 0 ]; then
    echo "⚠️  일부 프로세스가 남아있습니다. 다시 시도합니다..."
    killall -9 python3 2>/dev/null || true
    sleep 2
fi
echo "   ✅ 모든 프로세스 종료 완료"
echo ""

# 5. Git 상태 확인
echo "📊 현재 Git 상태:"
git status --short
echo ""

# 6. 로컬 변경사항 백업 (혹시 모를 경우 대비)
if [ -n "$(git status --porcelain)" ]; then
    echo "⚠️  로컬 변경사항이 있습니다. 백업 중..."
    BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    git diff > "$BACKUP_DIR/local_changes.patch"
    echo "   ✅ 변경사항 백업됨: $BACKUP_DIR/local_changes.patch"
    echo ""
fi

# 7. GitHub에서 최신 변경사항 가져오기
echo "⬇️  GitHub에서 최신 변경사항 가져오기..."
git fetch origin

# 8. 현재 브랜치 확인 및 pull
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "   현재 브랜치: $CURRENT_BRANCH"

# main 또는 master 브랜치에서 pull
if [ "$CURRENT_BRANCH" = "main" ]; then
    git pull origin main
elif [ "$CURRENT_BRANCH" = "master" ]; then
    git pull origin master
else
    echo "⚠️  브랜치가 main/master가 아닙니다. main으로 전환합니다..."
    git checkout main 2>/dev/null || git checkout master
    git pull
fi

if [ $? -eq 0 ]; then
    echo "   ✅ 업데이트 성공!"
else
    echo "❌ 업데이트 실패. 수동으로 확인하세요."
    exit 1
fi
echo ""

# 9. 주요 파일 확인
echo "🔍 주요 파일 확인:"
if [ -f "alpha_z_triple_strategy.py" ]; then
    echo "   ✅ alpha_z_triple_strategy.py ($(stat -c%s alpha_z_triple_strategy.py | numfmt --to=iec))"
else
    echo "   ❌ alpha_z_triple_strategy.py 없음!"
    exit 1
fi

if [ -f "improved_dca_position_manager.py" ]; then
    echo "   ✅ improved_dca_position_manager.py ($(stat -c%s improved_dca_position_manager.py | numfmt --to=iec))"
else
    echo "   ⚠️  improved_dca_position_manager.py 없음 (DCA 기능 제한됨)"
fi
echo ""

# 10. Python 패키지 업데이트 (필요시)
echo "📦 Python 패키지 확인..."
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt --quiet --upgrade
    echo "   ✅ 패키지 업데이트 완료"
else
    echo "   ℹ️  requirements.txt 없음 (건너뜀)"
fi
echo ""

# 11. 로그 파일 백업
if [ -f "alpha_z_trading.log" ]; then
    LOG_BACKUP="alpha_z_trading_backup_$(date +%Y%m%d_%H%M%S).log"
    mv alpha_z_trading.log "$LOG_BACKUP"
    echo "   ✅ 기존 로그 백업: $LOG_BACKUP"
fi
touch alpha_z_trading.log
echo ""

# 12. systemd 서비스 재시작
echo "🚀 Alpha-Z Trading Bot 재시작 중..."
if systemctl is-enabled --quiet alpha_z_trading.service 2>/dev/null; then
    systemctl start alpha_z_trading.service
    sleep 3

    if systemctl is-active --quiet alpha_z_trading.service; then
        echo "   ✅ systemd 서비스로 시작됨"
        BOT_PID=$(systemctl show -p MainPID alpha_z_trading.service | cut -d= -f2)
        echo "   📌 PID: $BOT_PID"
    else
        echo "   ❌ systemd 서비스 시작 실패"
        systemctl status alpha_z_trading.service --no-pager
        exit 1
    fi
else
    # systemd 서비스가 없으면 직접 실행
    echo "   ℹ️  systemd 서비스 없음 - 직접 실행합니다"
    nohup python3 alpha_z_triple_strategy.py --scan > alpha_z_trading.log 2>&1 &
    BOT_PID=$!
    sleep 3

    if ps -p $BOT_PID > /dev/null; then
        echo "   ✅ 봇 시작 성공! (PID: $BOT_PID)"
    else
        echo "   ❌ 봇 시작 실패. 로그 확인:"
        tail -20 alpha_z_trading.log
        exit 1
    fi
fi
echo ""

# 13. 프로세스 확인
echo "🔍 실행 중인 프로세스:"
ps aux | grep "[a]lpha_z_triple_strategy" | head -5
echo ""

# 14. 로그 출력 (DCA 매니저 초기화 확인)
echo "📋 초기 로그 (5초 후):"
sleep 5
echo "----------------------------------------"
tail -50 alpha_z_trading.log | grep -E "DCA|초기화|Trading Bot|ERROR|Exception" || tail -30 alpha_z_trading.log
echo "----------------------------------------"
echo ""

# 15. 최종 상태 확인
echo "========================================"
echo "✅ VPS 업데이트 및 재시작 완료!"
echo "========================================"
echo ""
echo "📊 현재 상태:"

if systemctl is-active --quiet alpha_z_trading.service 2>/dev/null; then
    echo "   서비스: ✅ 실행 중 (systemd)"
    systemctl status alpha_z_trading.service --no-pager -l | head -10
else
    PROCESS_COUNT=$(ps aux | grep "[a]lpha_z_triple_strategy" | wc -l)
    if [ $PROCESS_COUNT -eq 1 ]; then
        echo "   프로세스: ✅ 실행 중 (1개)"
    elif [ $PROCESS_COUNT -gt 1 ]; then
        echo "   프로세스: ⚠️  중복 실행 ($PROCESS_COUNT개)"
    else
        echo "   프로세스: ❌ 실행 안됨"
    fi
fi
echo ""

echo "📌 유용한 명령어:"
echo "   실시간 로그: tail -f alpha_z_trading.log"
echo "   서비스 상태: systemctl status alpha_z_trading.service"
echo "   서비스 로그: journalctl -u alpha_z_trading.service -f"
echo "   프로세스 확인: ps aux | grep alpha_z"
echo "   서비스 재시작: systemctl restart alpha_z_trading.service"
echo "   서비스 중지: systemctl stop alpha_z_trading.service"
echo ""
