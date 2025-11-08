# VPS 업데이트 가이드 (Log Translation Update)

## 📋 업데이트 내용

이번 업데이트에서는 **모든 로그 메시지가 영어로 번역**되었습니다.

### 변경된 파일 (11개)
1. `one_minute_surge_entry_strategy.py` - 메인 전략 파일
2. `improved_dca_position_manager.py` - DCA 관리 시스템
3. `telegram_bot.py` - 텔레그램 알림
4. `websocket_user_data_stream.py` - WebSocket 사용자 데이터
5. `bulk_websocket_kline_manager.py` - WebSocket K라인 관리자
6. `binance_rate_limiter.py` - Rate Limiter
7. `cache_manager.py` - 캐시 관리자
8. `indicators.py` - 기술적 지표
9. `advanced_exit_system.py` - 고급 청산 시스템
10. `basic_exit_system.py` - 기본 청산 시스템
11. `websocket_defense_system.py` - WebSocket 방어 시스템

### 추가된 문서
- `WEBSOCKET_COMPLETE_MIGRATION_GUIDE.md` - WebSocket 마이그레이션 가이드
- `strategy_conditions_comprehensive_guide.md` - 전략 조건 상세 가이드
- `apply_websocket_user_data_stream.py` - WebSocket 적용 헬퍼

---

## 🚀 VPS에서 업데이트하는 방법

### 방법 1: SSH로 직접 업데이트 (권장)

```bash
# 1. VPS에 SSH 접속
ssh your_username@your_vps_ip

# 2. 프로젝트 디렉토리로 이동
cd ~/vivik  # 또는 프로젝트가 설치된 경로

# 3. 현재 실행 중인 봇 중지 (systemd 사용 시)
sudo systemctl stop trading-bot

# 4. 또는 직접 실행 중인 경우
# ps aux | grep one_minute_surge_entry_strategy.py
# kill -9 [프로세스 ID]

# 5. 백업 생성 (안전을 위해)
cp -r . ../vivik_backup_$(date +%Y%m%d_%H%M%S)

# 6. 최신 코드 가져오기
git fetch origin
git pull origin main

# 7. 변경사항 확인
git log -3 --oneline

# 8. 봇 재시작 (systemd 사용 시)
sudo systemctl start trading-bot

# 9. 또는 직접 실행
# nohup python3 one_minute_surge_entry_strategy.py > trading_bot.log 2>&1 &

# 10. 로그 확인 (영어로 출력되는지 확인)
tail -f trading_bot.log
# 또는
sudo journalctl -u trading-bot -f
```

---

### 방법 2: 자동 업데이트 스크립트 사용

VPS에서 다음 스크립트를 실행하세요:

```bash
#!/bin/bash
# update_and_restart.sh

echo "========================================="
echo "VPS Trading Bot Update Script"
echo "========================================="

# 프로젝트 경로 설정
PROJECT_DIR=~/vivik
cd $PROJECT_DIR

# 백업 생성
BACKUP_DIR=~/vivik_backup_$(date +%Y%m%d_%H%M%S)
echo "Creating backup: $BACKUP_DIR"
cp -r . $BACKUP_DIR

# 봇 중지
echo "Stopping trading bot..."
if systemctl is-active --quiet trading-bot; then
    sudo systemctl stop trading-bot
    echo "Trading bot stopped"
else
    echo "Trading bot is not running via systemd"
    # 프로세스 직접 종료
    pkill -f one_minute_surge_entry_strategy.py
fi

# Git 업데이트
echo "Pulling latest changes from GitHub..."
git fetch origin
git pull origin main

# 변경사항 확인
echo "Recent changes:"
git log -3 --oneline

# 봇 재시작
echo "Starting trading bot..."
if [ -f /etc/systemd/system/trading-bot.service ]; then
    sudo systemctl start trading-bot
    echo "Trading bot started via systemd"
else
    nohup python3 one_minute_surge_entry_strategy.py > trading_bot.log 2>&1 &
    echo "Trading bot started in background"
fi

# 상태 확인
sleep 3
if systemctl is-active --quiet trading-bot; then
    echo "✅ Trading bot is running"
    sudo systemctl status trading-bot --no-pager
else
    echo "❌ Trading bot failed to start"
    echo "Check logs: tail -50 trading_bot.log"
fi

echo "========================================="
echo "Update completed!"
echo "========================================="
```

**스크립트 실행 방법:**
```bash
# 스크립트에 실행 권한 부여
chmod +x update_and_restart.sh

# 실행
./update_and_restart.sh
```

---

## 📝 업데이트 후 확인사항

### 1. 로그 확인
```bash
# 실시간 로그 확인
tail -f trading_bot.log

# 또는 systemd 로그
sudo journalctl -u trading-bot -f --since "5 minutes ago"
```

**확인할 내용:**
- ✅ 로그 메시지가 영어로 출력되는지
- ✅ 에러 없이 정상 실행되는지
- ✅ WebSocket 연결이 정상인지

### 2. 봇 상태 확인
```bash
# systemd 사용 시
sudo systemctl status trading-bot

# 프로세스 직접 확인
ps aux | grep one_minute_surge_entry_strategy.py
```

### 3. 텔레그램 알림 확인
- 봇이 정상적으로 시작되면 텔레그램으로 알림이 옵니다
- 로그 메시지가 영어로 표시되는지 확인하세요

---

## 🔄 롤백 방법 (문제 발생 시)

문제가 발생하면 백업으로 복원할 수 있습니다:

```bash
# 1. 봇 중지
sudo systemctl stop trading-bot
# 또는
pkill -f one_minute_surge_entry_strategy.py

# 2. 백업 확인
ls -la ~/vivik_backup*

# 3. 백업으로 복원 (가장 최근 백업 사용)
cd ~
rm -rf vivik
mv vivik_backup_YYYYMMDD_HHMMSS vivik  # 실제 백업 디렉토리 이름 입력

# 4. 봇 재시작
cd vivik
sudo systemctl start trading-bot
# 또는
nohup python3 one_minute_surge_entry_strategy.py > trading_bot.log 2>&1 &
```

---

## 🆘 문제 해결

### 문제 1: Git pull 실패
```bash
# 로컬 변경사항이 있는 경우
git stash
git pull origin main
git stash pop
```

### 문제 2: 봇이 시작되지 않음
```bash
# 로그 확인
tail -100 trading_bot.log

# Python 경로 확인
which python3
python3 --version

# 필요한 패키지 재설치
pip3 install -r requirements.txt
```

### 문제 3: 권한 오류
```bash
# 파일 소유권 확인 및 수정
sudo chown -R $USER:$USER ~/vivik
chmod +x *.py
```

### 문제 4: systemd 서비스 재로드 필요
```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-bot
sudo systemctl start trading-bot
```

---

## 📞 추가 지원

문제가 계속되면 GitHub Issues에 등록하거나 로그 파일을 확인하세요:

```bash
# 전체 로그 확인
cat trading_bot.log

# 에러만 확인
grep -i error trading_bot.log
grep -i fail trading_bot.log
```

---

## ✅ 업데이트 체크리스트

- [ ] VPS에 SSH 접속 완료
- [ ] 백업 생성 완료
- [ ] 봇 중지 완료
- [ ] Git pull 완료
- [ ] 봇 재시작 완료
- [ ] 로그 확인 (영어로 출력됨)
- [ ] 텔레그램 알림 정상 작동
- [ ] 포지션/트레이딩 정상 작동

---

*업데이트 일자: 2024년 11월 7일*
*버전: Log Translation v1.0*
