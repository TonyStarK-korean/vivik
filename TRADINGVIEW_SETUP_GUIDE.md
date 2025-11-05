# TradingView Webhook 설정 가이드

## 📋 목차
1. [시스템 개요](#시스템-개요)
2. [서버 설정](#서버-설정)
3. [TradingView 설정](#tradingview-설정)
4. [Pine Script 코드](#pine-script-코드)
5. [테스트 방법](#테스트-방법)
6. [문제 해결](#문제-해결)

---

## 🎯 시스템 개요

### 구조
```
TradingView (Pine Script)
    ↓ Webhook 신호
웹훅 서버 (Flask)
    ↓ 매매 실행
기존 전략 시스템 (DCA + 텔레그램)
    ↓ 주문 전송
바이낸스 거래소
```

### 지원 기능
- ✅ 진입 신호 (BUY)
- ✅ 청산 신호 (SELL/CLOSE)
- ✅ DCA 시스템 연동
- ✅ 텔레그램 알림
- ✅ 전략C/D 분류
- ✅ 최대 포지션 수 제한
- ✅ 보안 서명 검증

---

## 🔧 서버 설정

### 1단계: 필수 패키지 설치
```bash
pip install flask
```

### 2단계: 설정 파일 수정 (webhook_config.json)
```json
{
    "security": {
        "enabled": true,
        "secret_key": "mySecretKey12345!@#$%"  // ⚠️ 반드시 변경!
    },
    "trading": {
        "enabled": true,        // false로 하면 시뮬레이션 모드
        "test_mode": false,     // true로 하면 테스트넷 사용
        "max_positions": 5      // 최대 동시 포지션 수
    },
    "telegram": {
        "enabled": true,
        "send_webhook_alerts": true
    },
    "server": {
        "host": "0.0.0.0",      // 외부 접속 허용
        "port": 5000,           // 포트 번호
        "debug": false          // 프로덕션에서는 false
    }
}
```

### 3단계: 서버 실행
```bash
python tradingview_strategy_executor.py
```

**실행 확인**:
```
🚀 TradingView Webhook Strategy System
==================================================
📊 1단계: 기존 전략 시스템 초기화 중...
✅ 전략 시스템 초기화 완료

📡 2단계: 웹훅 실행기 초기화 중...
✅ 웹훅 실행기 초기화 완료

🌐 3단계: 웹훅 서버 시작 중...
==================================================
🚀 TradingView Webhook Server Starting...
📡 Listening on http://0.0.0.0:5000/webhook
💊 Health check: http://0.0.0.0:5000/health
📊 Status: http://0.0.0.0:5000/status
==================================================
```

### 4단계: 외부 접속 설정 (필수!)

#### A. 로컬 테스트 (같은 PC)
```
웹훅 URL: http://localhost:5000/webhook
```

#### B. 같은 네트워크 (공유기 내부)
```
1. 내 IP 확인: ipconfig (Windows) 또는 ifconfig (Mac/Linux)
2. 웹훅 URL: http://192.168.0.XXX:5000/webhook
```

#### C. 인터넷을 통한 접속 ⭐ (권장)

**방법 1: ngrok 사용 (가장 쉬움)**
```bash
# ngrok 설치: https://ngrok.com/download
ngrok http 5000

# 출력 예시:
# Forwarding: https://abc123.ngrok.io -> http://localhost:5000
# 웹훅 URL: https://abc123.ngrok.io/webhook
```

**방법 2: 포트 포워딩**
```
1. 공유기 관리 페이지 접속 (보통 192.168.0.1 또는 192.168.1.1)
2. 포트 포워딩 설정
   - 외부 포트: 5000
   - 내부 IP: 내 PC IP
   - 내부 포트: 5000
3. 공인 IP 확인: https://www.whatismyip.com/
4. 웹훅 URL: http://공인IP:5000/webhook
```

**방법 3: AWS/GCP/Azure 서버**
```
1. 클라우드 서버에서 실행
2. 보안 그룹에서 포트 5000 허용
3. 웹훅 URL: http://서버IP:5000/webhook
```

---

## 📈 TradingView 설정

### 1단계: Pine Script 작성

#### 전략C 예시 (3분봉)
```pinescript
//@version=5
strategy("전략C - 3분봉 시세 초입 포착", overlay=true)

// ===== 파라미터 =====
webhook_url = input.string("https://abc123.ngrok.io/webhook", "웹훅 URL")

// ===== 전략C 조건 (예시) =====
// 실제 전략 로직은 기존 전략 그대로 사용
ma5 = ta.sma(close, 5)
ma20 = ta.sma(close, 20)

// 진입 조건 (예시: MA5 > MA20 골든크로스)
longCondition = ta.crossover(ma5, ma20)

// 청산 조건 (예시: MA5 < MA20 데드크로스)
exitCondition = ta.crossunder(ma5, ma20)

// ===== 진입 신호 =====
if longCondition
    strategy.entry("Long", strategy.long)

    // 웹훅 메시지 (JSON 형식)
    alert_message = '{\n' +
         '  "symbol": "' + syminfo.ticker + '",\n' +
         '  "action": "buy",\n' +
         '  "strategy": "strategy_c",\n' +
         '  "price": ' + str.tostring(close) + ',\n' +
         '  "timestamp": "' + str.tostring(time) + '"\n' +
         '}'

    alert(alert_message, alert.freq_once_per_bar_close)

// ===== 청산 신호 =====
if exitCondition
    strategy.close("Long")

    // 웹훅 메시지
    alert_message = '{\n' +
         '  "symbol": "' + syminfo.ticker + '",\n' +
         '  "action": "sell",\n' +
         '  "strategy": "strategy_c",\n' +
         '  "price": ' + str.tostring(close) + ',\n' +
         '  "timestamp": "' + str.tostring(time) + '"\n' +
         '}'

    alert(alert_message, alert.freq_once_per_bar_close)
```

#### 전략D 예시 (5분봉)
```pinescript
//@version=5
strategy("전략D - 5분봉 초강력 타점", overlay=true)

webhook_url = input.string("https://abc123.ngrok.io/webhook", "웹훅 URL")

// 전략D 조건 (예시)
rsi = ta.rsi(close, 14)
longCondition = ta.crossover(rsi, 30)  // RSI 과매도 탈출
exitCondition = ta.crossunder(rsi, 70)  // RSI 과매수

if longCondition
    strategy.entry("Long", strategy.long)

    alert_message = '{\n' +
         '  "symbol": "' + syminfo.ticker + '",\n' +
         '  "action": "buy",\n' +
         '  "strategy": "strategy_d",\n' +
         '  "price": ' + str.tostring(close) + ',\n' +
         '  "timestamp": "' + str.tostring(time) + '"\n' +
         '}'

    alert(alert_message, alert.freq_once_per_bar_close)

if exitCondition
    strategy.close("Long")

    alert_message = '{\n' +
         '  "symbol": "' + syminfo.ticker + '",\n' +
         '  "action": "sell",\n' +
         '  "strategy": "strategy_d",\n' +
         '  "price": ' + str.tostring(close) + ',\n' +
         '  "timestamp": "' + str.tostring(time) + '"\n' +
         '}'

    alert(alert_message, alert.freq_once_per_bar_close)
```

### 2단계: 알림 생성

#### 1. Pine Script 추가
- 차트에 Pine Script 추가
- 저장

#### 2. 알림 설정
```
1. 차트 우측 상단 "알람" 아이콘 클릭
2. "조건" 탭에서 설정:
   - 조건: [스크립트 이름] - alert() 함수 호출
   - 옵션: "알람이 실행될 때마다"

3. "알림 동작" 탭에서 설정:
   - Webhook URL: https://abc123.ngrok.io/webhook
   - 메시지: {{strategy.order.alert_syntax}}

4. "만들기" 클릭
```

#### 📝 중요 포인트
- ✅ **메시지**: `{{strategy.order.alert_syntax}}` 사용 (Pine Script의 alert_message 전달)
- ✅ **빈도**: "알람이 실행될 때마다" 선택
- ✅ **만료**: "열려 있는 시간 동안" 또는 원하는 기간 설정

---

## 🧪 테스트 방법

### 1단계: 서버 상태 확인
```bash
# Health Check
curl http://localhost:5000/health

# 정상 응답:
{
  "status": "healthy",
  "timestamp": "2025-01-04T12:00:00",
  "trading_enabled": true,
  "version": "1.0.0"
}
```

### 2단계: 수동 테스트 (Postman/cURL)
```bash
# 진입 신호 테스트
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "action": "buy",
    "strategy": "strategy_c",
    "price": 50000.0,
    "timestamp": "2025-01-04T12:00:00Z"
  }'

# 정상 응답:
{
  "success": true,
  "message": "Signal received and processing",
  "symbol": "BTC/USDT:USDT",
  "action": "buy"
}
```

### 3단계: TradingView 테스트
```
1. Paper Trading (모의 거래)로 테스트
2. 작은 금액으로 실전 테스트
3. 로그 확인: tradingview_webhook.log
```

---

## 🔍 로그 확인

### 서버 로그 (터미널)
```
📥 웹훅 요청 수신: 1.2.3.4
📦 수신 데이터: {
  "symbol": "BTCUSDT",
  "action": "buy",
  "strategy": "strategy_c"
}
✅ 알림 파싱 완료: BTC/USDT:USDT BUY (strategy_c)
🔄 매매 실행 시작: BTC/USDT:USDT buy
🎯 [진입] BTC - 전략C: 3분봉 시세 초입 포착
✅ BTC DCA 진입 성공: $50000.000000
```

### 파일 로그 (tradingview_webhook.log)
```bash
tail -f tradingview_webhook.log
```

---

## 🚨 문제 해결

### 문제 1: 웹훅이 도달하지 않음
```
✅ 체크리스트:
- [ ] 서버가 실행 중인가? (터미널 확인)
- [ ] 방화벽에서 포트 5000 허용했는가?
- [ ] ngrok 실행 중인가? (ngrok 사용 시)
- [ ] TradingView 웹훅 URL이 정확한가?
- [ ] 인터넷 연결 상태는 정상인가?

🔧 해결:
1. 서버 재시작
2. ngrok 재실행 (URL 변경 시 TradingView 알림도 수정!)
3. 로컬 테스트 먼저 (localhost:5000)
```

### 문제 2: 401 Unauthorized (서명 오류)
```
✅ 원인: 보안 서명 불일치

🔧 해결:
1. webhook_config.json에서 security.enabled를 false로 설정 (테스트용)
2. 또는 TradingView에서 X-Webhook-Signature 헤더 전송 (고급)
```

### 문제 3: 매매가 실행되지 않음
```
✅ 체크리스트:
- [ ] webhook_config.json에서 trading.enabled가 true인가?
- [ ] API 키가 유효한가?
- [ ] 거래소 계좌 잔고가 충분한가?
- [ ] 최대 포지션 수에 도달했는가?

🔧 해결:
1. /status 엔드포인트로 상태 확인
2. 로그에서 오류 메시지 확인
3. 시뮬레이션 모드로 먼저 테스트
```

### 문제 4: 포지션이 두 번 열림
```
✅ 원인: TradingView 알림이 중복 발송됨

🔧 해결:
1. Pine Script에서 alert.freq_once_per_bar_close 사용
2. 포지션 추적 로직 확인 (self.positions)
```

---

## 📊 JSON 메시지 형식 (참고)

### 진입 신호
```json
{
  "symbol": "BTCUSDT",
  "action": "buy",
  "strategy": "strategy_c",
  "price": 50000.0,
  "timestamp": "2025-01-04T12:00:00Z"
}
```

### 청산 신호
```json
{
  "symbol": "BTCUSDT",
  "action": "sell",
  "strategy": "strategy_c",
  "price": 51000.0,
  "timestamp": "2025-01-04T13:00:00Z"
}
```

### 전략 타입
- `strategy_c`: 전략C (3분봉 시세 초입 포착)
- `strategy_d`: 전략D (5분봉 초입 초강력 타점)
- `strategy_cd`: 전략C+D (복합 진입)

---

## ⚙️ 고급 설정

### 보안 강화 (HMAC 서명)
```python
# TradingView에서 웹훅 전송 시 서명 추가 (고급 사용자용)
import hmac
import hashlib

secret_key = "mySecretKey12345"
payload = '{"symbol":"BTCUSDT","action":"buy"}'
signature = hmac.new(secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()

# 헤더에 추가: X-Webhook-Signature: {signature}
```

### HTTPS 사용 (SSL)
```bash
# Certbot으로 SSL 인증서 발급
sudo certbot certonly --standalone -d yourdomain.com

# Flask에서 SSL 사용
app.run(ssl_context=('cert.pem', 'key.pem'))
```

---

## 📞 지원

문제가 계속되면:
1. 로그 파일 확인 (`tradingview_webhook.log`)
2. GitHub Issues 등록
3. 텔레그램/Discord 커뮤니티 문의

**Happy Trading! 🚀**
