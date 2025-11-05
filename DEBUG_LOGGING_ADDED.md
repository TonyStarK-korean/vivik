# 디버그 로깅 추가 완료

## 🎯 문제 상황

사용자 보고: **"위에꺼 전혀 아무것도 안뜬다고"**
- 디버그 로그가 전혀 출력되지 않음
- 관심목록 0개, 신호 0개
- 이전에 추가한 전략C/D 디버그 로그도 보이지 않음

## 🔍 추가된 디버그 로깅

### 1. 메인 루프 실행 확인 (Line 9328-9330)
```python
# 🚨 디버그: 메인 루프 실행 확인
print(f"\n{'='*80}")
print(f"🚨 [DEBUG] 메인 루프 실행중 - get_filtered_symbols() 호출 직전")
print(f"{'='*80}\n")
symbols = strategy.get_filtered_symbols()
```

**목적**: 메인 루프가 실제로 실행되고 있는지 확인

### 2. 심볼 필터링 시작 확인 (Line 8340-8342)
```python
def get_filtered_symbols(self, min_change_pct=8.0):
    """WebSocket 전용 심볼 필터링 - REST API 완전 금지"""
    # 🚨 디버그: 함수 호출 확인
    print(f"\n{'='*80}")
    print(f"🚨 [DEBUG] get_filtered_symbols() 호출됨!")
    print(f"{'='*80}\n")
    try:
        # ... rest of function
```

**목적**: `get_filtered_symbols()` 함수가 호출되는지 확인

### 3. 스캔 시작 확인 (Line 3209-3212)
```python
def scan_symbols(self, symbols):
    """심볼들 병렬 스캔 (Rate Limit 고려) - 버그 수정된 안전 버전"""
    # 🚨 디버그: 함수 호출 확인
    print(f"\n{'='*80}")
    print(f"🚨 [DEBUG] scan_symbols() 호출됨! symbols 개수: {len(symbols)}")
    print(f"🚨 [DEBUG] 첫 5개 심볼: {symbols[:5] if symbols else '없음'}")
    print(f"{'='*80}\n")
    # ... rest of function
```

**목적**:
- `scan_symbols()` 함수가 호출되는지 확인
- 전달된 심볼 개수 확인
- 심볼 리스트 샘플 확인

### 4. 개별 심볼 분석 시작 확인 (Line 2699-2704)
```python
def analyze_symbol(self, symbol, cached_ticker=None):
    """개별 심볼 분석 (invincible_surge_entry_strategy.py와 동일한 구조)"""
    # 🚨 디버그: 함수 호출 확인 (매우 짧게)
    if hasattr(self, '_first_analyze_call') and self._first_analyze_call:
        pass  # 첫 호출 이후는 스킵
    else:
        print(f"🚨 [DEBUG] analyze_symbol() 첫 호출: {symbol}")
        self._first_analyze_call = True
    # ... rest of function
```

**목적**:
- `analyze_symbol()` 함수가 호출되는지 확인
- 첫 번째 심볼만 출력 (로그 스팸 방지)

---

## 📊 예상되는 출력 패턴

### 정상 실행시 출력 순서:

```
📊 [계좌포지션] 보유중: 없음

================================================================================
🚨 [DEBUG] 메인 루프 실행중 - get_filtered_symbols() 호출 직전
================================================================================

================================================================================
🚨 [DEBUG] get_filtered_symbols() 호출됨!
================================================================================

📊 전체 USDT 선물 심볼: 531개
⚠️ WebSocket 버퍼가 비어있음
⚠️ WebSocket 데이터 부족 - REST API 폴백
⚡ 전체 티커 일괄 조회 중...
🔍 전체 USDT 심볼 수집: 531개
🚀 4h 필터링 시작: 531개 심볼
✅ REST API 병렬 배치 처리 완료: 521개 심볼 체크됨
🔍 4h 필터링 완료: XXX/531개 통과

================================================================================
🚨 [DEBUG] scan_symbols() 호출됨! symbols 개수: XXX
🚨 [DEBUG] 첫 5개 심볼: ['BTC/USDT:USDT', 'ETH/USDT:USDT', ...]
================================================================================

🔍 스캔 시작: XXX개 심볼 분석 예정
📊 티커 데이터 수집 중...
✅ 티커 데이터 수집 완료: XXX개/XXX개
⚡ 병렬 분석 시작: XXX개 심볼 (스레드: 30개)

🚨 [DEBUG] analyze_symbol() 첫 호출: BTC/USDT:USDT

🔍 [전략C 시작] BTC: df_3m=있음, len=480
🔍 [전략C] BTC: failed=5, status=watchlist
...
```

---

## 🔍 진단 시나리오

### 시나리오 A: 아무것도 안 뜬다
**증상**: 위의 디버그 로그 중 **하나도** 보이지 않음

**원인**:
1. 메인 루프가 실행되지 않음
2. 프로그램이 초기화 단계에서 멈춤
3. 다른 부분에서 무한 대기 중

**해결책**: 프로그램 시작 로그 확인 필요

---

### 시나리오 B: "메인 루프 실행중"만 보임
**증상**:
```
🚨 [DEBUG] 메인 루프 실행중 - get_filtered_symbols() 호출 직전
```
이후 아무것도 안 뜸

**원인**: `get_filtered_symbols()` 함수 호출이 블로킹되거나 크래시

**해결책**:
- `get_filtered_symbols()` 함수 내부 try-except 체크
- API 호출 타임아웃 가능성

---

### 시나리오 C: "get_filtered_symbols() 호출됨!"까지만 보임
**증상**:
```
🚨 [DEBUG] get_filtered_symbols() 호출됨!
```
이후 아무것도 안 뜸

**원인**:
- Line 8349 `_get_cached_markets()` 호출에서 블로킹
- Line 8357 `_get_websocket_filtered_symbols()` 호출에서 블로킹
- 어딘가에서 예외 발생했지만 로그 없음

**해결책**: 추가 디버그 로깅 필요

---

### 시나리오 D: "WebSocket 버퍼 비어있음" → "심볼 수집 0개"
**증상**:
```
⚠️ WebSocket 버퍼가 비어있음
🔍 전체 USDT 심볼 수집: 0개
```

**원인**:
- 티커 조회 실패 (Rate Limit 또는 API 에러)
- Line 8367 또는 8389에서 빈 배열 반환

**해결책**: Rate Limit 상태 확인

---

### 시나리오 E: "4h 필터링 완료: 0/531개"
**증상**:
```
🔍 4h 필터링 완료: 0/531개 통과
```

**원인**: 4h 필터링이 모든 심볼을 제외

**해결책**: 4h 필터링 조건 완화 (2% → 1.5% 또는 1%)

---

### 시나리오 F: scan_symbols() 호출 안 됨
**증상**:
```
🔍 4h 필터링 완료: XXX/531개 통과
```
이후 `scan_symbols()` 디버그 로그 없음

**원인**:
- Line 9333: `if not symbols:` 조건으로 스캔 스킵
- `get_filtered_symbols()`가 빈 배열 반환

**해결책**: 필터링 결과 확인

---

### 시나리오 G: analyze_symbol() 호출 안 됨
**증상**:
```
🚨 [DEBUG] scan_symbols() 호출됨! symbols 개수: 100
⚡ 병렬 분석 시작: 100개 심볼 (스레드: 30개)
```
이후 `analyze_symbol()` 디버그 로그 없음

**원인**:
- 병렬 처리가 타임아웃
- 모든 심볼 분석이 3초 내에 완료 안 됨
- WebSocket 데이터 부족

**해결책**: 타임아웃 증가 또는 WebSocket 연결 확인

---

### 시나리오 H: 전략C/D 로그 안 나옴
**증상**:
```
🚨 [DEBUG] analyze_symbol() 첫 호출: BTC/USDT:USDT
```
이후 전략C/D 디버그 로그 없음

**원인**:
- df_3m, df_5m 데이터 없음
- 전략C/D 조건 체크 전에 리턴
- `is_data_insufficient` 플래그로 스킵

**해결책**: WebSocket 데이터 버퍼 확인

---

## 🚀 다음 단계

### 1. 프로그램 재시작
```bash
python one_minute_surge_entry_strategy.py
```

### 2. 첫 30초 로그 캡처
프로그램 시작 후 처음 30초간 출력되는 **모든 메시지**를 복사해주세요.

특히 다음 메시지들을 주의 깊게 확인:
- ✅ 초기 배치 구독: ...
- ✅ MultiplexedWebSocketManager 초기화 완료
- 🚨 [DEBUG] 로 시작하는 모든 메시지

### 3. 로그 분석
위의 **진단 시나리오**를 참고하여 어느 시점에서 멈추는지 확인

### 4. 보고
다음 정보를 제공해주세요:
1. 마지막으로 출력된 디버그 메시지
2. 그 이후 멈춘 시간 (예: 10초 대기 중)
3. 전체 로그 (가능하면)

---

## 📝 변경 파일 요약

**수정된 파일**: `one_minute_surge_entry_strategy.py`

**수정 위치**:
1. Line 9328-9330: 메인 루프 디버그 로그
2. Line 8340-8342: `get_filtered_symbols()` 진입 로그
3. Line 3209-3212: `scan_symbols()` 진입 로그
4. Line 2699-2704: `analyze_symbol()` 첫 호출 로그

**변경 내용**: 디버그 로깅 추가 (기능 변경 없음)

---

**작성일**: 2025-11-03
**목적**: 신호 미출력 원인 진단
**상태**: ✅ 테스트 준비 완료
