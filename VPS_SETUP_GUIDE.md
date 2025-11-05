# 🚀 VPS 서버 설정 가이드

## 📋 순서대로 실행하세요

### 1️⃣ 시스템 업데이트 및 Python 설치

```bash
# Ubuntu/Debian 기준
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip git screen
```

### 2️⃣ 프로젝트 다운로드

```bash
# 홈 디렉토리로 이동
cd ~

# Git에서 프로젝트 클론
git clone https://github.com/TonyStarK-korean/vivik.git

# 프로젝트 폴더로 이동
cd vivik
```

### 3️⃣ Python 패키지 설치

```bash
# 필수 패키지 설치
pip3 install ccxt pandas numpy ta flask requests websockets urllib3
```

또는 requirements.txt가 있다면:

```bash
pip3 install -r requirements.txt
```

### 4️⃣ 파일 확인

```bash
# 필수 파일 확인
ls -la one_minute_surge_entry_strategy.py
ls -la pattern_optimizations.py
ls -la binance_config.py
ls -la fix_ssl_connection.py
```

### 5️⃣ 빠른 테스트

```bash
# 진단 스크립트 실행
python3 quick_test_vps.py
```

### 6️⃣ 봇 실행

**방법 1: SSL 우회 스크립트 사용 (권장)**

```bash
# Screen 세션으로 백그라운드 실행
screen -S trading_bot

# SSL 우회 버전 실행
python3 fix_ssl_connection.py

# 또는 메인 스크립트 직접 실행
python3 one_minute_surge_entry_strategy.py

# Screen 세션 종료: Ctrl+A, D (세션은 계속 실행됨)
```

**방법 2: 직접 실행**

```bash
python3 one_minute_surge_entry_strategy.py
```

### 7️⃣ 로그 확인

```bash
# 실시간 로그 확인
tail -f strategy.log

# 또는 improved_dca_system.log
tail -f improved_dca_system.log
```

### 8️⃣ Screen 관리 명령어

```bash
# Screen 세션 목록 보기
screen -ls

# Screen 세션 다시 연결
screen -r trading_bot

# Screen 세션 종료 (세션 내부에서)
exit
# 또는 Ctrl+D

# Screen 세션 종료하지 않고 나가기
# Ctrl+A, D
```

### 9️⃣ 프로세스 관리

```bash
# Python 프로세스 확인
ps aux | grep python

# 프로세스 종료 (필요시)
pkill -f one_minute_surge_entry_strategy.py
```

---

## 🔧 문제 해결

### SSL 연결 오류가 발생하면

```bash
# SSL 우회 스크립트 사용
python3 fix_ssl_connection.py
```

### Import 오류가 발생하면

```bash
# 패키지 재설치
pip3 install --upgrade ccxt pandas numpy ta
```

### 권한 오류가 발생하면

```bash
# 실행 권한 부여
chmod +x *.py
```

---

## 📊 상태 확인

```bash
# 1. 프로세스 실행 여부
ps aux | grep one_minute_surge_entry_strategy

# 2. 로그 실시간 확인
tail -f strategy.log

# 3. 네트워크 연결 확인
curl -I https://api.binance.com

# 4. Python 버전 확인
python3 --version
```

---

## 🛑 봇 중지

```bash
# Screen 세션 내부에서
Ctrl+C

# 또는 외부에서 강제 종료
pkill -f one_minute_surge_entry_strategy.py
```

---

## 🔄 업데이트

```bash
# 프로젝트 폴더로 이동
cd ~/vivik

# 최신 코드 가져오기
git pull origin main

# Screen 세션 재시작
screen -S trading_bot
python3 one_minute_surge_entry_strategy.py
```

---

## ⚠️ 중요 사항

1. **API 키 보안**: GitHub에 올라간 API 키는 즉시 삭제하고 새로 발급받으세요!
2. **백업**: 주기적으로 데이터 파일 백업 (`*.json`, `*.log`)
3. **모니터링**: 텔레그램 알림 설정 권장
4. **VPN**: 일부 지역에서는 VPN 필요 (vpn_guide.txt 참고)

---

## 📞 지원

문제가 발생하면:
1. `strategy.log` 확인
2. `python3 quick_test_vps.py` 실행
3. GitHub Issues에 로그와 함께 문의
