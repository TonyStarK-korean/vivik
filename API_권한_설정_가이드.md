# 🔑 바이낸스 API 권한 설정 가이드

## ❌ 현재 상태
- **공개 API**: ✅ 정상 작동 (마켓 데이터 조회 가능)
- **프라이빗 API**: ❌ 권한 오류 (-2015 에러)

## 🔧 해결 방법

### 1. 바이낸스 계정 접속
- https://www.binance.com 로그인
- [API Management] 메뉴 접속

### 2. API 키 권한 확인 및 수정

#### 현재 API 키 권한 확인:
```
API_KEY: Ljyd55VX6OZEY3pdqM2KlJk8g5cHmRDmOs7HBwzPfby4Njfg7Vs24exv3nZrw1m3
```

#### 필요한 권한 설정:
- [x] **Enable Reading** (읽기 권한)
- [x] **Enable Futures** (선물 거래 권한) ← **반드시 체크**
- [x] **Enable Spot & Margin Trading** (현물 거래 권한)

### 3. IP 제한 확인
- **옵션 1**: IP 제한 없음 (Unrestricted) - 권장하지 않음
- **옵션 2**: 현재 IP 주소 추가
- **옵션 3**: VPN 사용시 VPN IP 주소 추가

### 4. 2FA 인증 확인
- Google Authenticator 또는 SMS 인증 활성화 필요
- API 키 생성/수정시 2FA 인증 요구됨

## 🔄 설정 완료 후 테스트

### API 권한 수정 후 다음 명령어로 재테스트:
```bash
python test_api_separation.py
```

### 성공시 다음과 같이 표시됨:
```
[SUCCESS] 잔고 조회 성공
[BALANCE] 가용 잔고: $1,000.00 USDT
[SUCCESS] 포지션 조회 성공
[POSITIONS] 활성 포지션: 0개
[SUCCESS] 프라이빗 API 모든 테스트 통과
```

## ⚠️ 주의사항

1. **테스트넷 vs 실거래**
   - 현재 설정: 실거래 모드 (TESTNET = False)
   - 실제 자금이 사용됩니다

2. **리스크 관리**
   - 포지션 크기: 1% (레버리지 20배로 20% 노출)
   - 최대 손실: 6% (시드 기준)
   - DCA 시스템: -3%, -6%에서 추가 진입

3. **백업 계획**
   - API 권한 문제 지속시 새 API 키 생성 권장
   - 기존 키 삭제 후 새 키로 binance_config.py 업데이트

## 📞 추가 도움이 필요한 경우

1. 바이낸스 고객지원 문의
2. API 권한 설정 스크린샷 확인
3. IP 주소 제한 문제 해결

---
**✅ API 권한 설정 완료 후 15분봉 초필살기 전략을 정상 실행할 수 있습니다.**