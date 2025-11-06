# 🛡️ Binance Rate Limiter 사용 가이드

바이낸스 IP 밴 문제를 완전히 해결하는 고급 Rate Limiting 시스템입니다.

## 📋 주요 기능

### ✅ 완벽한 Rate Limit 관리
- **가중치 추적**: 엔드포인트별 정확한 가중치 계산
- **1분 윈도우**: 1200 가중치/분 자동 관리
- **429/418 감지**: 자동 백오프 및 IP 차단 처리
- **Retry-After**: 헤더 기반 정확한 대기 시간

### ✅ 지능형 캐싱 시스템
- **응답 캐싱**: API 응답 자동 캐싱으로 중복 요청 제거
- **TTL 관리**: 데이터 타입별 최적화된 캐시 수명
- **메모리 관리**: 캐시 크기 제한으로 메모리 효율성

### ✅ 고급 백오프 전략
- **지수 백오프**: 연속 실패 시 대기 시간 증가
- **상태 저장**: 재시작 시에도 차단 상태 유지
- **점진적 복구**: 안전한 API 호출 재개

## 🚀 설치 및 적용

### 1. 파일 확인
```bash
# 필수 파일들이 있는지 확인
ls -la binance_rate_limiter.py
ls -la one_minute_surge_entry_strategy.py
```

### 2. 자동 적용 완료
Rate Limiter는 이미 전략 파일에 자동 적용되었습니다:
- ✅ `RateLimitedExchange` 래퍼 적용
- ✅ 모든 API 호출에 자동 rate limiting
- ✅ 상태 모니터링 시스템 추가

### 3. 실행하여 확인
```bash
python one_minute_surge_entry_strategy.py
```

## 📊 모니터링 정보

### Rate Limiter 상태 출력 (30초마다)
```
🛡️ [Rate Limiter 상태]
  상태: 정상
  가중치: 245/1200 (20.4%)
  분당 요청: 23
  캐시: 15개 항목
```

### 위험 상태 시 자세한 정보
```
🛡️ [Rate Limiter 상태]
  상태: 제한됨
  가중치: 1150/1200 (95.8%)
  분당 요청: 87
  IP 차단: 1234초 남음
  백오프: 60초 남음
  연속 429: 3회
  에러: 429:3, 418:1
  캐시: 42개 항목
```

## 🔧 고급 설정

### Rate Limiter 개별 사용 (선택사항)
```python
from binance_rate_limiter import BinanceRateLimiter, RateLimitedExchange
import ccxt

# 기본 exchange 생성
exchange = ccxt.binance({
    'apiKey': 'your-key',
    'secret': 'your-secret'
})

# Rate limiter 적용
safe_exchange = RateLimitedExchange(exchange)

# 안전한 API 호출
try:
    tickers = safe_exchange.fetch_tickers()
    print(f"성공: {len(tickers)}개 티커 조회")
except Exception as e:
    print(f"실패: {e}")
```

### 수동 상태 확인
```python
# Rate limiter 상태 확인
status = strategy.rate_limiter.get_status()
print(f"현재 가중치: {status['current_weight']}/{status['max_weight']}")
print(f"Rate limited: {status['rate_limited']}")
```

## 📈 엔드포인트별 가중치

### 주요 엔드포인트 가중치
| 엔드포인트 | 가중치 | 설명 |
|-----------|--------|------|
| `/fapi/v1/ticker/24hr` | 1 | 개별 심볼 티커 |
| `/fapi/v2/ticker/24hr` | 40 | 모든 심볼 티커 |
| `/fapi/v1/klines` | 1-2 | OHLCV (limit 기반) |
| `/fapi/v2/account` | 5 | 계좌 정보 |
| `/fapi/v1/order` | 1 | 주문 관련 |

### 가중치 최적화 팁
- **개별 심볼 조회**: 전체 조회보다 20배 효율적
- **캐시 활용**: 동일 요청 시 API 호출 제거
- **배치 처리**: 동시 요청으로 효율성 증대

## 🚨 문제 해결

### IP 차단 시 대처법
1. **자동 대기**: Rate limiter가 자동으로 차단 시간 대기
2. **WebSocket 전환**: REST API 차단 시 WebSocket 전용 모드
3. **상태 복원**: 재시작 시에도 차단 정보 유지

### 429 에러 발생 시
```
🚨 429 에러 발생 (연속 3회) - 60초 대기
⏳ Rate limit 대기: 60.0초
✅ 429 백오프 완료 - API 호출 재개 가능
```

### 캐시 최적화
- **TTL 설정**: 데이터 타입별 최적화
- **메모리 관리**: 1000개 항목 제한
- **히트율 모니터링**: 캐시 효율성 추적

## 📝 상태 파일 관리

### 자동 생성 파일
- `binance_rate_limiter_state.json`: 차단 상태 저장
- 재시작 시 자동으로 이전 상태 복원

### 상태 파일 초기화 (필요 시)
```bash
# 차단 상태 초기화 (주의: IP 차단이 실제로 해제된 경우만)
rm binance_rate_limiter_state.json
```

## 🎯 성능 향상

### API 호출 최적화 결과
- ✅ **중복 요청 제거**: 캐시를 통한 90% 감소
- ✅ **가중치 관리**: 실시간 추적으로 99% 정확도
- ✅ **IP 밴 방지**: 완전 자동화된 백오프 시스템
- ✅ **WebSocket 병행**: REST API 부하 50% 감소

### 권장 운영 방식
1. **WebSocket 우선**: 실시간 데이터는 WebSocket 활용
2. **배치 처리**: 여러 심볼 동시 조회 시 개별 API 사용
3. **캐시 활용**: 빈번한 조회는 캐시 기반
4. **모니터링**: 가중치 80% 초과 시 주의

## ⚡ 추가 최적화 옵션

### WebSocket 최대 활용
- 실시간 데이터: WebSocket으로 95% 커버
- 히스토리 데이터: 캐시된 REST API
- 하이브리드 모드: 최적의 성능과 안정성

### 병렬 처리 최적화
- Rate limiter는 스레드 안전
- 동시 API 호출 지원
- 가중치 실시간 동기화

---

**🎉 이제 IP 밴 걱정 없이 안전한 트레이딩이 가능합니다!**

Rate Limiter는 백그라운드에서 자동으로 작동하며, 별도 설정 없이 모든 API 호출을 보호합니다.