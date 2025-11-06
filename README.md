# 바이낸스 자동 매매 봇 (1분봉 급등 진입 전략)

자동화된 암호화폐 선물 거래 봇 (전략 C, D, DCA 시스템 포함)

## 주요 기능

- ✅ 1분봉 기반 급등 진입 전략
- ✅ SuperTrend(10-3) + 이동평균 복합 전략
- ✅ DCA(Dollar Cost Averaging) 시스템
- ✅ WebSocket 실시간 데이터 수신
- ✅ 5가지 청산 방법 (본절보호, SuperTrend, BB600 등)
- ✅ 텔레그램 알림 지원
- ✅ Rate Limiter 및 IP 밴 방지

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

## 필수 파일

- `one_minute_surge_entry_strategy.py` - 메인 전략 파일
- `indicators.py` - 기술적 지표 계산
- `cache_manager.py` - 캐시 관리
- `bulk_websocket_kline_manager.py` - WebSocket 관리
- `websocket_defense_system.py` - WebSocket 방어 시스템
- `binance_websocket_kline_manager.py` - 바이낸스 WebSocket
- `binance_rate_limiter.py` - Rate Limiter

## 보안 주의사항

⚠️ **절대로 GitHub에 실제 API 키를 올리지 마세요!**

- `binance_config.py` - Git에서 제외됨
- `telegram_config.py` - Git에서 제외됨
- VPS에서 직접 설정 파일 생성 필요

## 성능 최적화

- WebSocket: 0 API calls/min (bootstrap 후)
- 레이턴시: 0.05초 (REST 대비 36배 향상)
- 가격 캡처율: 100% (실시간)

## 문의

문제가 있으면 GitHub Issues에 등록해주세요.

## 라이선스

개인 사용 목적
