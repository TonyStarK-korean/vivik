#!/bin/bash

# VPS 업데이트 스크립트 (VPS 경로: /root/vivik)
VPS_HOST="158.247.193.81"
VPS_USER="root"
VPS_PROJECT_DIR="/root/vivik"

echo "🚀 VPS 업데이트 시작..."
echo "VPS: ${VPS_USER}@${VPS_HOST}"
echo "프로젝트 폴더: ${VPS_PROJECT_DIR}"

# VPS에서 실행될 명령어들
ssh ${VPS_USER}@${VPS_HOST} << 'ENDSSH'

# 프로젝트 디렉토리로 이동
cd /root/vivik

echo "📦 최신 변경사항 가져오기..."
git pull origin master

echo "🔄 서비스 상태 확인..."
# 기존 프로세스 종료
pkill -f "one_minute_surge_entry_strategy.py" || true
screen -ls | grep alpha_z_trading && screen -S alpha_z_trading -X quit || true

echo "⏳ 잠시 대기..."
sleep 3

echo "🛠️ 의존성 업데이트..."
# 가상환경 활성화 및 패키지 업데이트 (있는 경우)
if [ -d "venv" ]; then
    source venv/bin/activate
    pip install --upgrade -r requirements.txt
else
    # 가상환경이 없으면 전역에 설치
    pip3 install --upgrade -r requirements.txt
fi

echo "📁 필요한 디렉토리 생성..."
mkdir -p logs data

echo "🔧 실행 권한 설정..."
chmod +x start_trading.sh one_minute_surge_entry_strategy.py

echo "🚀 트레이딩 시스템 시작..."
# 24시간 실행 스크립트 시작
if [ -f "start_trading.sh" ]; then
    ./start_trading.sh
else
    # 백그라운드에서 직접 실행
    nohup python3 one_minute_surge_entry_strategy.py > logs/trading_$(date +%Y%m%d).log 2>&1 &
fi

echo "📊 프로세스 상태 확인..."
sleep 2
ps aux | grep -v grep | grep python

echo "📋 로그 파일 생성 확인..."
ls -la logs/

echo "✅ VPS 배포 완료!"
echo ""
echo "📋 관리 명령어:"
echo "   실시간 로그: tail -f logs/trading_$(date +%Y%m%d).log"
echo "   프로세스 확인: ps aux | grep python"
echo "   Screen 세션: screen -list"
echo "   재시작: ./start_trading.sh"

ENDSSH

echo "✅ VPS 업데이트 완료!"