#!/bin/bash
# Alpha-Z Trading Bot 24/7 서비스 설정 스크립트

echo "=================================="
echo "🚀 Alpha-Z 24/7 서비스 설정 시작"
echo "=================================="

# 1. 로그 디렉토리 생성
echo ""
echo "📁 로그 디렉토리 생성..."
mkdir -p /root/vivik/logs
chmod 755 /root/vivik/logs

# 2. 기존 프로세스 종료
echo ""
echo "⏸️  기존 프로세스 종료..."
pkill -f "python.*alpha_z_triple_strategy" || echo "   (실행 중인 프로세스 없음)"
sleep 2

# 3. systemd 서비스 파일 생성
echo ""
echo "📝 systemd 서비스 파일 생성..."
cat > /etc/systemd/system/alpha_z_trading.service << 'EOF'
[Unit]
Description=Alpha-Z Triple Strategy Trading Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/vivik
ExecStart=/usr/bin/python3 /root/vivik/alpha_z_triple_strategy.py --scan
Restart=always
RestartSec=10
StandardOutput=append:/root/vivik/logs/alpha_z_trading.log
StandardError=append:/root/vivik/logs/alpha_z_error.log

# 환경 변수
Environment="PYTHONUNBUFFERED=1"

# 리소스 제한
MemoryLimit=2G
CPUQuota=80%

[Install]
WantedBy=multi-user.target
EOF

# 4. systemd 리로드
echo ""
echo "🔄 systemd 설정 리로드..."
systemctl daemon-reload

# 5. 서비스 활성화 (부팅시 자동 시작)
echo ""
echo "✅ 서비스 활성화 (부팅시 자동 시작)..."
systemctl enable alpha_z_trading.service

# 6. 서비스 시작
echo ""
echo "🚀 서비스 시작..."
systemctl start alpha_z_trading.service

# 7. 서비스 상태 확인
sleep 3
echo ""
echo "📊 서비스 상태:"
systemctl status alpha_z_trading.service --no-pager -l

# 8. 최근 로그 확인
echo ""
echo "📋 최근 로그 (10줄):"
tail -10 /root/vivik/logs/alpha_z_trading.log

echo ""
echo "=================================="
echo "✅ 24/7 서비스 설정 완료!"
echo "=================================="
echo ""
echo "📌 유용한 명령어:"
echo ""
echo "   서비스 상태 확인:"
echo "   systemctl status alpha_z_trading"
echo ""
echo "   서비스 재시작:"
echo "   systemctl restart alpha_z_trading"
echo ""
echo "   서비스 중지:"
echo "   systemctl stop alpha_z_trading"
echo ""
echo "   서비스 로그 실시간 확인:"
echo "   journalctl -u alpha_z_trading -f"
echo ""
echo "   또는:"
echo "   tail -f /root/vivik/logs/alpha_z_trading.log"
echo ""
echo "   서비스 자동시작 해제:"
echo "   systemctl disable alpha_z_trading"
echo ""
