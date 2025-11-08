#!/bin/bash

# VPS 배포 스크립트
VPS_IP="158.247.193.81"
VPS_USER="root"
PROJECT_DIR="/root/alpha_z_trading"

echo "🚀 Alpha-Z Trading System VPS 배포 시작..."

# VPS에 프로젝트 디렉토리 생성 및 코드 업로드
echo "📁 VPS 프로젝트 디렉토리 설정..."
ssh ${VPS_USER}@${VPS_IP} "mkdir -p ${PROJECT_DIR}"

# 핵심 파일들 업로드
echo "📦 핵심 파일 업로드 중..."
scp one_minute_surge_entry_strategy.py ${VPS_USER}@${VPS_IP}:${PROJECT_DIR}/
scp improved_dca_position_manager.py ${VPS_USER}@${VPS_IP}:${PROJECT_DIR}/
scp binance_config.py ${VPS_USER}@${VPS_IP}:${PROJECT_DIR}/

# 추가 필요 파일들 업로드 (있는 경우)
echo "📦 추가 파일 확인 및 업로드..."
if [ -f "telegram_bot.py" ]; then
    scp telegram_bot.py ${VPS_USER}@${VPS_IP}:${PROJECT_DIR}/
fi

if [ -f "binance_rate_limiter.py" ]; then
    scp binance_rate_limiter.py ${VPS_USER}@${VPS_IP}:${PROJECT_DIR}/
fi

if [ -f "requirements.txt" ]; then
    scp requirements.txt ${VPS_USER}@${VPS_IP}:${PROJECT_DIR}/
fi

# VPS에서 환경 설정
echo "🔧 VPS 환경 설정 중..."
ssh ${VPS_USER}@${VPS_IP} << EOF
cd ${PROJECT_DIR}

# Python 및 pip 업데이트
apt update
apt install -y python3 python3-pip python3-venv git screen

# 가상환경 생성
python3 -m venv venv
source venv/bin/activate

# 필수 패키지 설치
pip install --upgrade pip
pip install ccxt pandas numpy requests python-binance websockets ta-lib

# requirements.txt가 있으면 설치
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

# 로그 디렉토리 생성
mkdir -p logs data

# 권한 설정
chmod +x one_minute_surge_entry_strategy.py

echo "✅ VPS 환경 설정 완료"
EOF

echo "✅ VPS 배포 완료!"
echo "📍 VPS 정보:"
echo "   IP: ${VPS_IP}"
echo "   디렉토리: ${PROJECT_DIR}"
echo "   실행 명령: cd ${PROJECT_DIR} && source venv/bin/activate && python one_minute_surge_entry_strategy.py"