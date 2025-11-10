#!/bin/bash
# Alpha-Z Trading Dashboard 설정 스크립트

echo "=================================="
echo "🚀 Alpha-Z Dashboard 설정 시작"
echo "=================================="

# 1. 패키지 설치
echo ""
echo "📦 Python 패키지 설치..."
pip3 install flask flask-cors python-binance python-dotenv

# 2. 로그 디렉토리 생성
echo ""
echo "📁 로그 디렉토리 생성..."
mkdir -p /root/vivik/logs
chmod 755 /root/vivik/logs

# 3. 기존 프로세스 종료
echo ""
echo "⏸️  기존 프로세스 종료..."
pkill -f "python.*dashboard_api" || echo "   (실행 중인 프로세스 없음)"
sleep 2

# 4. systemd 서비스 파일 생성
echo ""
echo "📝 systemd 서비스 파일 생성..."
cat > /etc/systemd/system/dashboard_api.service << 'EOF'
[Unit]
Description=Alpha-Z Trading Dashboard API Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/vivik
ExecStart=/usr/bin/python3 /root/vivik/dashboard_api.py
Restart=always
RestartSec=10
StandardOutput=append:/root/vivik/logs/dashboard_api.log
StandardError=append:/root/vivik/logs/dashboard_api_error.log

# 환경 변수
Environment="PYTHONUNBUFFERED=1"

# 리소스 제한
MemoryLimit=1G
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF

# 5. systemd 리로드
echo ""
echo "🔄 systemd 설정 리로드..."
systemctl daemon-reload

# 6. 서비스 활성화 (부팅시 자동 시작)
echo ""
echo "✅ 서비스 활성화 (부팅시 자동 시작)..."
systemctl enable dashboard_api.service

# 7. 서비스 시작
echo ""
echo "🚀 서비스 시작..."
systemctl start dashboard_api.service

# 8. 서비스 상태 확인
sleep 3
echo ""
echo "📊 서비스 상태:"
systemctl status dashboard_api.service --no-pager -l

# 9. 방화벽 포트 개방 (필요시)
echo ""
echo "🔓 방화벽 포트 5000 개방..."
if command -v ufw &> /dev/null; then
    ufw allow 5000/tcp
    echo "   UFW: 포트 5000 개방됨"
elif command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=5000/tcp
    firewall-cmd --reload
    echo "   firewalld: 포트 5000 개방됨"
else
    echo "   (방화벽이 설치되지 않음)"
fi

echo ""
echo "=================================="
echo "✅ Dashboard 설정 완료!"
echo "=================================="
echo ""
echo "📌 대시보드 접속:"
echo ""
echo "   http://158.247.193.81:5000"
echo ""
echo "📌 유용한 명령어:"
echo ""
echo "   서비스 상태 확인:"
echo "   systemctl status dashboard_api"
echo ""
echo "   서비스 재시작:"
echo "   systemctl restart dashboard_api"
echo ""
echo "   서비스 중지:"
echo "   systemctl stop dashboard_api"
echo ""
echo "   서비스 로그 실시간 확인:"
echo "   journalctl -u dashboard_api -f"
echo ""
echo "   또는:"
echo "   tail -f /root/vivik/logs/dashboard_api.log"
echo ""
