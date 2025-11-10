#!/bin/bash
# VPS에서 GitHub 최신 변경사항 가져오기 및 재시작 스크립트

echo "=================================="
echo "🔄 VPS 업데이트 시작"
echo "=================================="

# 1. 프로젝트 디렉토리로 이동
cd /root/vivik || { echo "❌ 디렉토리 없음: /root/vivik"; exit 1; }

echo ""
echo "📂 현재 디렉토리: $(pwd)"

# 2. 실행 중인 Python 프로세스 확인 및 종료
echo ""
echo "⏸️  실행 중인 트레이딩 봇 종료..."
pkill -f "python.*alpha_z_triple_strategy.py" || echo "   (실행 중인 봇 없음)"
pkill -f "python.*one_minute_surge_entry_strategy.py" || echo "   (실행 중인 봇 없음)"
sleep 2

# 3. Git 상태 확인
echo ""
echo "📊 현재 Git 상태:"
git status

# 4. GitHub에서 최신 변경사항 가져오기
echo ""
echo "⬇️  GitHub에서 최신 변경사항 가져오기..."
git fetch origin
git pull origin master

if [ $? -eq 0 ]; then
    echo "✅ 업데이트 성공!"
else
    echo "❌ 업데이트 실패. 수동으로 확인하세요."
    exit 1
fi

# 5. alpha_z_triple_strategy.py 파일 확인
echo ""
echo "🔍 주요 파일 확인:"
if [ -f "alpha_z_triple_strategy.py" ]; then
    echo "   ✅ alpha_z_triple_strategy.py 존재"
    ls -lh alpha_z_triple_strategy.py
else
    echo "   ❌ alpha_z_triple_strategy.py 없음!"
    exit 1
fi

# 6. Python 패키지 업데이트 (필요시)
echo ""
echo "📦 Python 패키지 확인..."
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt --quiet
    echo "   ✅ 패키지 업데이트 완료"
else
    echo "   ⚠️  requirements.txt 없음 (건너뜀)"
fi

# 7. 백그라운드로 봇 재시작
echo ""
echo "🚀 Alpha-Z Triple Strategy 봇 시작..."
nohup python3 alpha_z_triple_strategy.py --scan > alpha_z_trading.log 2>&1 &
BOT_PID=$!

sleep 3

# 8. 프로세스 확인
if ps -p $BOT_PID > /dev/null; then
    echo "   ✅ 봇 시작 성공! (PID: $BOT_PID)"
else
    echo "   ❌ 봇 시작 실패. 로그 확인:"
    tail -20 alpha_z_trading.log
    exit 1
fi

# 9. 로그 출력
echo ""
echo "📋 최근 로그 (5초 후):"
sleep 5
tail -30 alpha_z_trading.log

echo ""
echo "=================================="
echo "✅ VPS 업데이트 완료!"
echo "=================================="
echo ""
echo "📌 유용한 명령어:"
echo "   로그 실시간 확인: tail -f alpha_z_trading.log"
echo "   봇 상태 확인: ps aux | grep alpha_z"
echo "   봇 종료: pkill -f alpha_z_triple_strategy"
echo ""
