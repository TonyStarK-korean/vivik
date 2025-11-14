#!/bin/bash

echo "========================================="
echo "🔍 실시간 청산 시스템 확인"
echo "========================================="
echo ""

# 1. 봇 실행 상태 확인
echo "1️⃣ 봇 실행 상태:"
if systemctl is-active --quiet alpha_z_trading; then
    echo "✅ 봇이 실행 중입니다"
    systemctl status alpha_z_trading | grep "Active:"
else
    echo "❌ 봇이 실행되지 않았습니다"
    exit 1
fi
echo ""

# 2. 최근 청산 체크 로그 확인 (최근 5분)
echo "2️⃣ 최근 5분간 청산 체크 로그:"
if [ -f /root/vivik/alpha_z_trading.log ]; then
    tail -1000 /root/vivik/alpha_z_trading.log | grep "청산 조건 체크" | tail -10
    echo ""
    echo "📊 청산 체크 횟수: $(tail -1000 /root/vivik/alpha_z_trading.log | grep -c "청산 조건 체크")"
else
    echo "⚠️ 로그 파일을 찾을 수 없습니다"
fi
echo ""

# 3. 실제 청산 발생 확인
echo "3️⃣ 실제 청산 발생 내역:"
if [ -f /root/vivik/alpha_z_trading.log ]; then
    tail -2000 /root/vivik/alpha_z_trading.log | grep -E "청산 신호|손절 트리거|Trailing Stop" | tail -5
    echo ""
    echo "📊 청산 발생 횟수: $(tail -2000 /root/vivik/alpha_z_trading.log | grep -c "청산 신호")"
else
    echo "⚠️ 로그 파일을 찾을 수 없습니다"
fi
echo ""

# 4. 현재 활성 포지션 수
echo "4️⃣ 현재 활성 포지션:"
if [ -f /root/vivik/data/dca_positions.json ]; then
    python3 -c "
import json
try:
    with open('/root/vivik/data/dca_positions.json', 'r') as f:
        data = json.load(f)
        active = [k for k, v in data.items() if v.get('is_active', False)]
        print(f'활성 포지션: {len(active)}개')
        for symbol in active:
            print(f'  - {symbol}')
except:
    print('포지션 파일 읽기 실패')
"
else
    echo "⚠️ 포지션 파일을 찾을 수 없습니다"
fi
echo ""

# 5. 실시간 로그 모니터링 시작
echo "5️⃣ 실시간 로그 모니터링 (Ctrl+C로 종료):"
echo "========================================="
tail -f /root/vivik/alpha_z_trading.log | grep --line-buffered -E "청산|exit|Exit|손절|Trailing"

