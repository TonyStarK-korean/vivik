#!/bin/bash

# Alpha-Z Trading System 24시간 가동 스크립트
PROJECT_DIR="/root/alpha_z_trading"
LOG_DIR="${PROJECT_DIR}/logs"
SCREEN_NAME="alpha_z_trading"

echo "🚀 Alpha-Z Trading System 24시간 가동 시작..."

# 프로젝트 디렉토리로 이동
cd ${PROJECT_DIR}

# 로그 디렉토리 확인
mkdir -p ${LOG_DIR}

# 기존 screen 세션 종료 (있는 경우)
if screen -list | grep -q "${SCREEN_NAME}"; then
    echo "🔄 기존 세션 종료 중..."
    screen -S ${SCREEN_NAME} -X quit
    sleep 2
fi

# 새로운 screen 세션에서 트레이딩 시스템 시작
echo "🎯 새로운 트레이딩 세션 시작..."
screen -dmS ${SCREEN_NAME} bash -c "
    cd ${PROJECT_DIR}
    source venv/bin/activate
    
    # 무한 재시작 루프
    while true; do
        echo '\$(date): Alpha-Z Trading System 시작' >> ${LOG_DIR}/system.log
        python one_minute_surge_entry_strategy.py 2>&1 | tee -a ${LOG_DIR}/trading_\$(date +%Y%m%d).log
        
        echo '\$(date): 시스템 중단됨, 10초 후 재시작...' >> ${LOG_DIR}/system.log
        sleep 10
    done
"

echo "✅ Alpha-Z Trading System 24시간 가동 시작 완료!"
echo ""
echo "📋 관리 명령어:"
echo "   세션 확인: screen -list"
echo "   세션 접속: screen -r ${SCREEN_NAME}"
echo "   세션 종료: screen -S ${SCREEN_NAME} -X quit"
echo "   로그 확인: tail -f ${LOG_DIR}/trading_\$(date +%Y%m%d).log"
echo "   시스템 로그: tail -f ${LOG_DIR}/system.log"