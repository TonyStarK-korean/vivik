#!/bin/bash
# systemd 서비스 설치 및 활성화 스크립트

set -e

echo "========================================"
echo "🔧 systemd 서비스 설정"
echo "========================================"
echo ""

# 1. 프로젝트 디렉토리 확인
cd /root/vivik || { echo "❌ 디렉토리 없음: /root/vivik"; exit 1; }

# 2. 기존 프로세스 종료
echo "🛑 기존 프로세스 종료 중..."
if systemctl is-active --quiet alpha_z_trading.service 2>/dev/null; then
    systemctl stop alpha_z_trading.service
    echo "   ✅ 서비스 중지됨"
fi
pkill -9 -f alpha_z_triple_strategy 2>/dev/null || true
sleep 2
echo ""

# 3. 서비스 파일 복사
echo "📋 서비스 파일 설치 중..."
if [ -f "alpha_z_trading.service" ]; then
    cp alpha_z_trading.service /etc/systemd/system/
    echo "   ✅ 서비스 파일 복사됨: /etc/systemd/system/alpha_z_trading.service"
else
    echo "❌ alpha_z_trading.service 파일 없음!"
    exit 1
fi
echo ""

# 4. systemd 리로드
echo "🔄 systemd 리로드 중..."
systemctl daemon-reload
echo "   ✅ 리로드 완료"
echo ""

# 5. 서비스 활성화 (재부팅 시 자동 시작)
echo "✅ 서비스 활성화 중..."
systemctl enable alpha_z_trading.service
echo "   ✅ 재부팅 시 자동 시작 설정됨"
echo ""

# 6. 서비스 시작
echo "🚀 서비스 시작 중..."
systemctl start alpha_z_trading.service
sleep 3
echo ""

# 7. 상태 확인
echo "📊 서비스 상태:"
systemctl status alpha_z_trading.service --no-pager -l
echo ""

# 8. 프로세스 확인
echo "🔍 실행 중인 프로세스:"
ps aux | grep "[a]lpha_z_triple_strategy"
echo ""

# 9. 로그 확인
echo "📋 최근 로그 (5초 후):"
sleep 5
tail -30 alpha_z_trading.log
echo ""

echo "========================================"
echo "✅ systemd 서비스 설정 완료!"
echo "========================================"
echo ""
echo "📌 유용한 명령어:"
echo "   서비스 상태: systemctl status alpha_z_trading.service"
echo "   서비스 로그: journalctl -u alpha_z_trading.service -f"
echo "   서비스 재시작: systemctl restart alpha_z_trading.service"
echo "   서비스 중지: systemctl stop alpha_z_trading.service"
echo "   서비스 비활성화: systemctl disable alpha_z_trading.service"
echo "   파일 로그: tail -f /root/vivik/alpha_z_trading.log"
echo ""
