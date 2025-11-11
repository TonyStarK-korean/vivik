#!/bin/bash
# 자동 업데이트 및 재시작 스크립트

set -e

echo "========================================"
echo "🔄 자동 업데이트 및 재시작"
echo "========================================"
echo ""

# 1. 프로젝트 디렉토리 확인
cd /root/vivik || { echo "❌ 디렉토리 없음: /root/vivik"; exit 1; }

# 2. 현재 브랜치 및 커밋 확인
echo "📌 현재 상태:"
git branch
git log -1 --oneline
echo ""

# 3. 변경사항 확인 (stash 필요 여부)
if ! git diff-index --quiet HEAD --; then
    echo "⚠️ 로컬 변경사항 감지 - stash 저장 중..."
    git stash save "Auto-stash before update $(date '+%Y-%m-%d %H:%M:%S')"
    echo "   ✅ stash 저장됨"
    echo ""
fi

# 4. 최신 코드 가져오기
echo "⬇️ GitHub에서 최신 코드 가져오는 중..."
git pull origin main
echo "   ✅ 업데이트 완료"
echo ""

# 5. 업데이트된 커밋 확인
echo "📋 최신 커밋:"
git log -3 --oneline
echo ""

# 6. 서비스 재시작
echo "🔄 서비스 재시작 중..."
systemctl restart alpha_z_trading.service
echo "   ✅ 재시작 명령 실행됨"
sleep 3
echo ""

# 7. 서비스 상태 확인
echo "📊 서비스 상태:"
systemctl status alpha_z_trading.service --no-pager -l | head -20
echo ""

# 8. 프로세스 확인
echo "🔍 실행 중인 프로세스:"
ps aux | grep "[a]lpha_z_triple_strategy"
echo ""

# 9. 최근 로그 확인
echo "📋 최근 로그 (20줄):"
tail -20 alpha_z_trading.log
echo ""

echo "========================================"
echo "✅ 업데이트 및 재시작 완료!"
echo "========================================"
echo ""
echo "📌 실시간 로그 확인:"
echo "   tail -f alpha_z_trading.log"
echo ""
echo "📌 서비스 로그 확인:"
echo "   journalctl -u alpha_z_trading.service -f"
echo ""
