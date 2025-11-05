# TradingView Webhook 빠른 시작 ⚡

## 5분 안에 시작하기

### 1️⃣ 설치 (1분)
```bash
pip install flask
```

### 2️⃣ 서버 실행 (1분)
```bash
python tradingview_strategy_executor.py
```

**✅ 성공 메시지 확인:**
```
🚀 TradingView Webhook Server Starting...
📡 Listening on http://0.0.0.0:5000/webhook
```

### 3️⃣ ngrok으로 외부 접속 (1분)
```bash
# ngrok 다운로드: https://ngrok.com/download
ngrok http 5000

# 출력에서 URL 복사:
# https://abc123.ngrok.io
```

### 4️⃣ TradingView 설정 (2분)

#### Pine Script 예시 (복사해서 사용)
```pinescript
//@version=5
strategy("전략C 웹훅", overlay=true)

// MA 크로스오버 예시
ma5 = ta.sma(close, 5)
ma20 = ta.sma(close, 20)

longCondition = ta.crossover(ma5, ma20)
exitCondition = ta.crossunder(ma5, ma20)

// 진입
if longCondition
    strategy.entry("Long", strategy.long)

    alert('{"symbol":"' + syminfo.ticker + '","action":"buy","strategy":"strategy_c","price":' + str.tostring(close) + '}', alert.freq_once_per_bar_close)

// 청산
if exitCondition
    strategy.close("Long")

    alert('{"symbol":"' + syminfo.ticker + '","action":"sell","strategy":"strategy_c","price":' + str.tostring(close) + '}', alert.freq_once_per_bar_close)
```

#### 알림 생성
```
1. 차트에 Pine Script 추가
2. 알람 아이콘 클릭 → 조건: [스크립트] - alert()
3. Webhook URL: https://abc123.ngrok.io/webhook
4. 메시지: {{strategy.order.alert_syntax}}
5. "만들기" 클릭
```

### ✅ 완료!

---

## 🧪 테스트

### 서버 상태 확인
```bash
curl http://localhost:5000/health
```

### 수동 신호 전송 (테스트)
```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTCUSDT","action":"buy","strategy":"strategy_c","price":50000}'
```

---

## 📊 결과 확인

### 1. 터미널 로그
```
📥 웹훅 요청 수신: 1.2.3.4
✅ 알림 파싱 완료: BTC/USDT:USDT BUY
🔄 매매 실행 시작...
✅ BTC 진입 성공: $50000
```

### 2. 텔레그램 알림
```
🎯 [최초 진입] BTC
━━━━━━━━━━━━━━━━━━━━━━
💰 진입가: $50000.00
📦 수량: 0.01
🔧 전략: 🎯 전략C: 3분봉 시세 초입 포착
```

### 3. 바이낸스 주문 체결
- 선물 계좌에서 주문 확인

---

## ⚙️ 설정 (선택사항)

### webhook_config.json
```json
{
    "trading": {
        "enabled": true,        // 실제 매매 ON/OFF
        "max_positions": 5      // 최대 포지션 수
    }
}
```

---

## 🚨 문제 해결

| 문제 | 해결 |
|------|------|
| 웹훅 안 옴 | ngrok 재시작, URL 재설정 |
| 401 오류 | `webhook_config.json`에서 `security.enabled: false` |
| 매매 안 됨 | API 키 확인, 잔고 확인 |

---

## 📚 상세 가이드
더 자세한 내용은 `TRADINGVIEW_SETUP_GUIDE.md` 참고

**Happy Trading! 🚀**
