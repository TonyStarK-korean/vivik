# 바이낸스 자동 매매 봇 (Alpha-Z Trading System)

자동화된 암호화폐 선물 거래 봇 (Strategy C + D 복합 전략, 고급 DCA 시스템)

## 📊 주요 기능

### 🎯 진입 전략
- ✅ **Strategy C**: 3분봉 시세 초입 포착 전략
  - BB200-BB480 골든크로스 (200봉 이내)
  - MA5-MA20 패턴 조건
  - 3분봉 SuperTrend(10-3) 진입 시그널
- ✅ **Strategy D**: 5분봉 초강력 타점 전략
  - 15분봉 MA80 < MA480
  - 5분봉 SuperTrend(10-3) 진입 시그널
  - MA80-MA480 골든크로스 또는 이격도 5% 이내
  - MA480 우하향 + BB200 상단선 골든크로스
  - 10봉 이내 MA5-MA20 골든크로스
- ✅ **1분봉 진입 타이밍**: MA5-MA120 골든크로스 또는 이격도 조건
- ✅ **4시간봉 필터링**: 3% 이상 급등 확인

### 💰 포지션 관리
- ✅ **초기 진입**: 자본의 0.8% × 레버리지 10배
- ✅ **1차 DCA**: -3% 하락 시 자본의 2% × 레버리지 10배 (지정가 자동 등록)
- ✅ **2차 DCA**: -6% 하락 시 자본의 2.5% × 레버리지 10배 (지정가 자동 등록)
- ✅ **최대 포지션**: 10종목 동시 보유
- ✅ **종목당 최대 비중**: 5.3% (모든 DCA 포함)

### 📉 청산 시스템 (5가지 방법)
1. **SuperTrend 청산**: 3분봉 SuperTrend 매도 신호 시 즉시 전량 청산
2. **단계별 청산**: 손실 구간에서 평단가 최적화를 위한 부분 청산
3. **수익 구간 청산**: 10% 수익 또는 BB600 상단 돌파 시 50% 청산
4. **적응형 손절**: 단계별 변동성 기반 손절
   - 초기 진입: -10%
   - 1차 DCA 후: -7%
   - 2차 DCA 후: -5%
5. **트레일링 스톱**: 수익률별 차등 하락 허용
   - 20% 이상: 15% 하락 허용
   - 15~20%: 20% 하락 허용
   - 10~15%: 25% 하락 허용
   - 5~10%: 50% 하락 시 전량 청산
   - 3~5%: 손실 전환 직전 청산

### ⚡ 시스템 최적화
- ✅ **WebSocket 실시간 데이터**: 레이턴시 0.05초 (REST 대비 36배 향상)
- ✅ **병렬 처리**: 521개 심볼 5-10초 내 스캔 완료
- ✅ **캐시 시스템**: OHLCV 데이터 1200초 캐싱
- ✅ **텔레그램 알림**: 진입/청산/DCA 체결 실시간 알림
- ✅ **Rate Limiter**: IP 밴 방지 시스템

## 📖 상세 문서

전략 조건, DCA 시스템, 청산 로직 등 상세한 내용은 [TRADING_SYSTEM_DOCUMENTATION.md](TRADING_SYSTEM_DOCUMENTATION.md)를 참고하세요.

## VPS 설치 가이드

### 1. 프로젝트 클론

```bash
git clone https://github.com/TonyStarK-korean/vivik.git
cd vivik
```

### 2. Python 환경 설정

```bash
# Python 3.8+ 필요
python3 --version

# 가상환경 생성 (선택사항)
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate  # Windows
```

### 3. 패키지 설치

```bash
pip install -r requirements.txt
```

### 4. API 설정 (중요!)

#### binance_config.py 생성
```bash
cp binance_config.example.py binance_config.py
nano binance_config.py  # 또는 vi, vim
```

실제 API 키 입력:
```python
API_KEY = "여기에_실제_바이낸스_API_키"
SECRET_KEY = "여기에_실제_바이낸스_시크릿_키"
```

#### telegram_config.py 생성
```bash
cp telegram_config.example.py telegram_config.py
nano telegram_config.py
```

실제 토큰 입력:
```python
TELEGRAM_BOT_TOKEN = "여기에_텔레그램_봇_토큰"
TELEGRAM_CHAT_ID = "여기에_채팅방_ID"
```

### 5. 실행

```bash
# 직접 실행
python one_minute_surge_entry_strategy.py

# 백그라운드 실행
nohup python one_minute_surge_entry_strategy.py > trading_bot.log 2>&1 &

# 로그 확인
tail -f trading_bot.log
```

## VPS 업데이트 방법

### 자동 업데이트 (권장)

```bash
cd ~/vivik
git pull origin main
chmod +x update_and_restart.sh
./update_and_restart.sh
```

### 강제 업데이트 (로컬 변경사항 무시)

⚠️ **주의**: VPS의 모든 로컬 변경사항이 삭제되고 GitHub 최신 버전으로 덮어씁니다!

```bash
cd ~/vivik
git pull origin main
chmod +x force_update_vps.sh
./force_update_vps.sh
```

**강제 업데이트는 다음 경우에 사용:**
- Git 충돌로 일반 업데이트가 안 될 때
- 로컬 변경사항을 버리고 GitHub 버전으로 되돌릴 때
- 완전히 깨끗한 상태로 재설치하고 싶을 때

상세한 내용은 [VPS_UPDATE_GUIDE.md](VPS_UPDATE_GUIDE.md) 참고

### 6. systemd로 자동 실행 (권장)

```bash
sudo nano /etc/systemd/system/trading-bot.service
```

내용:
```ini
[Unit]
Description=Binance Trading Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/vivik
ExecStart=/usr/bin/python3 one_minute_surge_entry_strategy.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

시작:
```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-bot
sudo systemctl start trading-bot
sudo systemctl status trading-bot
```

## 핵심 파일 구조

### 전략 실행 파일
- `one_minute_surge_entry_strategy.py` - 메인 전략 파일 (Strategy C + D)
- `alpha_z_triple_strategy.py` - Triple 전략 (A, B, C)

### 시스템 구성 파일
- `improved_dca_position_manager.py` - 고급 DCA 포지션 관리
- `indicators.py` - 기술적 지표 계산
- `cache_manager.py` - 캐시 관리
- `bulk_websocket_kline_manager.py` - WebSocket 관리
- `websocket_defense_system.py` - WebSocket 방어 시스템
- `binance_websocket_kline_manager.py` - 바이낸스 WebSocket
- `binance_rate_limiter.py` - Rate Limiter

### 문서 파일
- `TRADING_SYSTEM_DOCUMENTATION.md` - 전체 시스템 상세 문서
- `DCA_SYSTEM_IMPROVEMENTS.md` - DCA 시스템 개선 내역
- `WEBSOCKET_OPTIMIZATION_GUIDE.md` - WebSocket 최적화 가이드

## 보안 주의사항

⚠️ **절대로 GitHub에 실제 API 키를 올리지 마세요!**

- `binance_config.py` - Git에서 제외됨
- `telegram_config.py` - Git에서 제외됨
- VPS에서 직접 설정 파일 생성 필요

## 성능 지표

- **WebSocket**: 0 API calls/min (bootstrap 후)
- **레이턴시**: 0.05초 (REST 대비 36배 향상)
- **가격 캡처율**: 100% (실시간)
- **스캔 속도**: 521개 심볼 5-10초 내 처리

## 운영 가이드

### 시작 전 체크리스트
1. ✅ API 키 설정 확인
2. ✅ 텔레그램 봇 토큰 설정
3. ✅ 자본금 설정 확인
4. ✅ WebSocket 연결 확인

### 위험 관리
- 최대 10개 포지션 제한
- 포지션당 최대 5.3% 자본 투입 (모든 DCA 포함)
- 단계별 손절 시스템 활성화 (-10% / -7% / -5%)
- 수익 구간별 트레일링 스톱

## ⚠️ 주의사항

1. **실거래 전 시뮬레이션 권장**
2. **네트워크 안정성 필수**
3. **자본금 대비 적정 포지션 유지**
4. **정기적인 로그 모니터링**
5. **급변동 시장에서 주의 운영**

## 문의

문제가 있으면 GitHub Issues에 등록해주세요.

## 라이선스

개인 사용 목적
