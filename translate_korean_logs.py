# -*- coding: utf-8 -*-
"""
Korean to English Log Message Translator
Translates ALL Korean log messages in Python trading bot files
"""

import re
import os

# Korean to English translation mapping
TRANSLATIONS = {
    # Common phrases
    "초기화 완료": "Initialization complete",
    "초기화 실패": "Initialization failed",
    "시작": "Starting",
    "완료": "Complete",
    "실패": "Failed",
    "성공": "Success",
    "오류": "Error",
    "경고": "Warning",
    "정보": "Info",
    "디버그": "Debug",

    # WebSocket related
    "WebSocket 연결 시도": "WebSocket connection attempt",
    "WebSocket 시작 성공": "WebSocket start success",
    "WebSocket 시작 실패": "WebSocket start failed",
    "WebSocket 종료 오류": "WebSocket shutdown error",
    "WebSocket 연결 최종 실패": "WebSocket connection final failure",
    "WebSocket 미시작": "WebSocket not started",
    "WebSocket 연결 종료 중": "Closing WebSocket connection",
    "구독 시도": "Subscription attempt",
    "구독 성공": "Subscription success",
    "구독 실패": "Subscription failed",
    "이미 구독됨": "Already subscribed",
    "구독 해제": "Unsubscribe",
    "구독 예외": "Subscription exception",
    "상세 오류": "Detailed error",
    "스트림 중지 오류": "Stream stop error",
    "콜백 처리 오류": "Callback processing error",
    "Kline 데이터 저장 실패": "Kline data save failed",
    "Kline 버퍼 조회 실패": "Kline buffer query failed",
    "상위 타임프레임 생성 실패": "Higher timeframe generation failed",
    "타임스탬프 정렬 실패": "Timestamp alignment failed",

    # Subscription and data loading
    "배치 구독 시작": "Batch subscription start",
    "타임프레임": "Timeframe",
    "심볼": "Symbol",
    "일괄 구독 완료": "Batch subscription complete",
    "일괄 구독 해제": "Batch unsubscribe complete",
    "초기 데이터 로딩 시작": "Initial data loading start",
    "진행": "Progress",
    "초기 데이터 로딩 완료": "Initial data loading complete",
    "실패한 심볼": "Failed symbols",
    "버퍼 초기화 완료": "Buffer initialization complete",
    "WebSocket 연결 끊김 감지": "WebSocket connection loss detected",
    "재연결 준비": "Reconnection preparation",
    "재연결 시도": "Reconnection attempt",
    "재연결 성공": "Reconnection success",
    "재연결 실패": "Reconnection failed",
    "수동 개입 필요": "Manual intervention required",
    "구독 상태 저장": "Subscription state saved",
    "구독 상태 복구": "Subscription state restored",
    "상태 저장 실패": "State save failed",
    "상태 복구 실패": "State recovery failed",

    # Position and trading
    "진입": "Entry",
    "청산": "Exit",
    "이미 포지션 보유 중": "Position already held",
    "진입 스킵": "Entry skipped",
    "최대 포지션 수": "Maximum positions",
    "도달": "Reached",
    "진입 시도": "Entry attempt",
    "가격 조회 실패": "Price query failed",
    "DCA 시스템으로 진입 시도": "DCA system entry attempt",
    "DCA 진입 성공": "DCA entry success",
    "DCA 진입 실패": "DCA entry failed",
    "기존 방식으로 진입 시도": "Legacy entry attempt",
    "주문 실패": "Order failed",
    "진입 실행 오류": "Entry execution error",
    "포지션 없음": "No position",
    "청산 스킵": "Exit skipped",
    "DCA 시스템으로 청산": "DCA system exit",
    "DCA 청산 성공": "DCA exit success",
    "DCA 청산 실패": "DCA exit failed",
    "기존 방식으로 청산": "Legacy exit",
    "청산 주문 실패": "Exit order failed",
    "청산 실행 오류": "Exit execution error",

    # DCA system
    "DCA 지정가 주문 자동 생성 시작": "DCA limit order auto-generation start",
    "진입가": "Entry price",
    "현재가 확인": "Current price check",
    "현재가 조회 실패": "Current price query failed",
    "DCA 주문 건너뜀": "DCA order skipped",
    "DCA 지정가 주문 등록": "DCA limit order placed",
    "DCA 지정가 주문 실패": "DCA limit order failed",
    "DCA 지정가 주문 자동 생성 완료": "DCA limit order auto-generation complete",
    "DCA 지정가 주문 자동 생성 실패": "DCA limit order auto-generation failed",
    "DCA 재주문 검토 시작": "DCA re-order review start",
    "순환매": "Cyclic trading",
    "회": "times",
    "재주문 건너뜀": "Re-order skipped",
    "재주문 등록": "Re-order placed",
    "재주문 실패": "Re-order failed",
    "재주문 처리 실패": "Re-order processing failed",
    "DCA 재주문 완료": "DCA re-order complete",
    "개 주문 등록": "orders placed",
    "DCA 재주문 실패": "DCA re-order failed",

    # Position management
    "거래소와 DCA 시스템 초기 동기화 시작": "Exchange and DCA system initial sync start",
    "개선된 DCA 시스템 초기화 완료": "Improved DCA system initialization complete",
    "활성 포지션": "Active positions",
    "개": "count",
    "평단가 급격한 변화 감지": "Drastic average price change detected",
    "변화": "change",
    "기존": "Previous",
    "신규": "New",
    "평단가 업데이트": "Average price update",
    "평단가 업데이트 실패": "Average price update failed",
    "포지션 데이터 로드 완료": "Position data load complete",
    "포지션 파일 없음": "Position file not found",
    "새로 시작": "Starting fresh",
    "포지션 데이터 로드 실패": "Position data load failed",
    "백업 파일에서 복구 완료": "Backup file recovery complete",
    "백업 파일 복구 실패": "Backup file recovery failed",
    "제한 데이터 로드 완료": "Limit data load complete",
    "제한 데이터 로드 실패": "Limit data load failed",
    "데이터 저장 완료": "Data save complete",
    "데이터 저장 실패": "Data save failed",

    # Synchronization
    "거래소와 DCA 시스템 동기화 시작": "Exchange and DCA system sync start",
    "고아 포지션": "Orphan position",
    "정리 완료": "Cleanup complete",
    "기존 포지션 등록": "Existing position registered",
    "고아 포지션 정리": "Orphan position cleanup",
    "동기화 완료": "Sync complete",
    "신규감지": "New detected",
    "동기화 실패": "Sync failed",
    "Rate limit 상태": "Rate limit status",
    "포지션 조회 건너뛰기": "Position query skipped",
    "현재 계좌에 포지션 없음": "No positions in current account",
    "활성 포지션 없음": "No active positions",
    "모두 0 수량": "All zero quantity",
    "포지션 조회 시도": "Position query attempt",
    "포지션 조회 실패": "Position query failed",
    "포지션 없음으로 처리": "Treated as no position",

    # Position updates
    "기존 포지션 등록": "Existing position registration",
    "수량": "Quantity",
    "기존 포지션 등록 실패": "Existing position registration failed",
    "고아 포지션 미체결 주문 취소": "Orphan position pending order cancel",
    "고아 포지션 정리": "Orphan position cleanup",
    "메인 전략 포지션도 정리": "Main strategy position also cleaned",
    "고아 포지션 정리 실패": "Orphan position cleanup failed",
    "포지션 축소 동기화": "Position reduction sync",
    "단계": "Stage",
    "평단가": "Average price",
    "포지션 수량 동기화": "Position quantity sync",
    "포지션 업데이트 실패": "Position update failed",
    "이미 활성 포지션 존재": "Active position already exists",
    "새 포지션 추가": "New position added",
    "포지션 추가 실패": "Position add failed",

    # Exits and triggers
    "복합 기술적 청산 트리거": "Composite technical exit trigger",
    "신호 개수": "Signal count",
    "평균 강도": "Average strength",
    "손절 트리거 확인 실패": "Stop loss trigger check failed",
    "SuperClaude 기본 청산 트리거": "SuperClaude basic exit trigger",
    "청산 타입": "Exit type",
    "청산 비율": "Exit ratio",
    "익절 트리거": "Take profit trigger",
    "수익률": "Profit ratio",
    "청산비율": "Exit ratio",
    "트레일링 스톱 트리거": "Trailing stop trigger",
    "최고가": "Highest price",
    "트레일링가": "Trailing price",
    "트레일링": "Trailing",
    "수익 청산 트리거 확인 실패": "Profit exit trigger check failed",
    "DCA 부분청산": "DCA partial exit",
    "진입가 회복": "Entry price recovery",
    "최초 진입가 회복": "Initial entry price recovery",
    "순환매 제한 초과": "Cyclic trading limit exceeded",
    "순환매 재진입 트리거": "Cyclic trading re-entry trigger",
    "회차": "Round",
    "하락률": "Drop rate",
    "순환매 체크 실패": "Cyclic trading check failed",

    # Exit execution
    "미체결 주문 취소": "Pending order cancel",
    "개 주문 취소": "orders cancelled",
    "청산할 포지션 없음": "No position to exit",
    "실제 포지션": "Actual position",
    "실제 포지션 기준 청산": "Exit based on actual position",
    "실제 포지션 조회 실패": "Actual position query failed",
    "백업": "Backup",
    "DCA 기록": "DCA record",
    "긴급 청산 실패": "Emergency exit failed",
    "청산 메시지 생성 실패": "Exit message generation failed",
    "부분 청산할 수량 없음": "No quantity for partial exit",
    "체결된 수량": "Filled quantity",
    "엔트리": "Entry",
    "부분 청산 후 평단가 재계산": "Average price recalculation after partial exit",
    "이전 평단가": "Previous avg price",
    "새 평단가": "New avg price",
    "이전 수량": "Previous quantity",
    "새 수량": "New quantity",
    "잔여 엔트리": "Remaining entries",
    "부분청산 후 포지션 유지": "Position maintained after partial exit",
    "추가 모니터링 계속": "Continue additional monitoring",
    "전량 청산 완료": "Full exit complete",
    "새로운 청산 시스템 상태 초기화": "New exit system state initialization",
    "부분 청산 완료": "Partial exit complete",
    "청산": "Exit",
    "사유": "Reason",
    "부분 청산 실패": "Partial exit failed",

    # Stage-based exits
    "단계별 청산 대상 없음": "No stage-based exit target",
    "단계별 청산 불가": "Stage-based exit impossible",
    "단계별 청산 수량 조정": "Stage-based exit quantity adjustment",
    "대상 단계": "Target stage",
    "기록상 수량": "Recorded quantity",
    "실제 보유": "Actual holding",
    "청산 수량": "Exit quantity",
    "백업 청산량 사용": "Using backup exit quantity",
    "단계별 청산 후 평단가 재계산": "Average price recalculation after stage-based exit",
    "청산 단계": "Exit stage",
    "단계별 청산 완료": "Stage-based exit complete",
    "단계별 청산 실패": "Stage-based exit failed",

    # Rate limiting
    "Rate Limit 추적 시스템 초기화 완료": "Rate Limit tracking system initialization complete",
    "분당": "per minute",
    "가중치": "weight",
    "주문 기록 동기화 시스템 초기화 완료": "Order history sync system initialization complete",
    "주문 기록 동기화 시스템 초기화 실패": "Order history sync system initialization failed",
    "Rate limit 복구 시도": "Rate limit recovery attempt",
    "경과": "Elapsed",
    "API 호출 재개": "API calls resumed",
    "WebSocket 데이터 없음": "No WebSocket data",
    "REST API 차단": "REST API blocked",
    "WebSocket 데이터 부족": "Insufficient WebSocket data",
    "REST API 폴백": "REST API fallback",
    "REST API 폴백 실패": "REST API fallback failed",
    "데이터 조회 실패": "Data query failed",
    "Rate limit 감지": "Rate limit detected",
    "API 호출 중단": "API calls stopped",

    # WebSocket data management
    "웹소켓 kline 데이터 업데이트 실패": "WebSocket kline data update failed",
    "타임프레임 생성 실패": "Timeframe generation failed",
    "타임프레임 변환 실패": "Timeframe conversion failed",
    "WebSocket 조회 실패": "WebSocket query failed",
    "병렬 조회 중단": "Parallel query stopped",
    "병렬 조회 중 Rate Limit 감지": "Rate limit detected during parallel query",
    "병렬조회": "Parallel query",
    "WebSocket 충분": "WebSocket sufficient",
    "응답": "Response",
    "WebSocket 스캔 콜백 실패": "WebSocket scan callback failed",
    "WebSocket 버퍼 프리로딩 실패": "WebSocket buffer preloading failed",

    # Subscription management
    "WebSocket 구독": "WebSocket subscription",
    "WebSocket 구독 업데이트 실패": "WebSocket subscription update failed",
    "초기 심볼 구독 실패": "Initial symbol subscription failed",

    # Indicators and technical analysis
    "지표 계산 실패": "Indicator calculation failed",
    "데이터 부족": "Insufficient data",
    "길이": "Length",
    "필요": "Required",
    "지표 계산 시도": "Indicator calculation attempt",
    "SuperTrend 계산 실패": "SuperTrend calculation failed",
    "골든크로스 탐지 오류": "Golden cross detection error",
    "데드크로스 탐지 오류": "Dead cross detection error",

    # Strategy execution
    "전략C": "Strategy C",
    "전략D": "Strategy D",
    "전략 조건 충족": "Strategy conditions met",
    "전략저장": "Strategy save",
    "저장 완료": "Save complete",
    "데이터 컬럼 접근 오류": "Data column access error",
    "Rate limit 감지": "Rate limit detected",
    "API 호출 중단 모드 활성화": "API call stop mode activated",
    "진입 조건 체크 건너뛰기": "Entry condition check skipped",
    "전략C/D 진입 조건 체크 실패": "Strategy C/D entry condition check failed",
    "잘못된 심볼 데이터": "Invalid symbol data",

    # Analysis and scanning
    "데이터 조회 실패": "Data query failed",
    "REST API 데이터 로드 실패": "REST API data load failed",
    "티커 변동률 사용": "Using ticker change rate",
    "결과 없음": "No results",
    "타입 오류": "Type error",
    "FALLBACK": "FALLBACK",
    "기본 WATCHLIST로 분류": "Classified as default WATCHLIST",
    "분석 실패": "Analysis failed",
    "작업 제출 실패": "Task submission failed",
    "예상치 못한 결과 타입": "Unexpected result type",
    "스캔 타임아웃": "Scan timeout",
    "초과": "Exceeded",
    "스킵": "Skip",
    "스캔 중 오류": "Error during scan",
    "스캔 통계": "Scan statistics",
    "개 분석": "analyzed",
    "개 결과": "results",
    "개 최종": "final",
    "결과 샘플": "Result sample",
    "처음": "First",
    "타입": "Type",
    "내용": "Content",
    "결과 타입 통계": "Result type statistics",
    "기타": "Other",
    "all_results가 비어있음": "all_results is empty",

    # Entry and exit alerts
    "진입 알림 전송 실패": "Entry alert send failed",
    "DCA 트리거 알림 전송 실패": "DCA trigger alert send failed",
    "DCA주문확인": "DCA order confirmation",
    "DCA 지정가 주문": "DCA limit order",
    "배치 완료": "Deployment complete",
    "DCA 지정가 주문 일부만 배치됨": "DCA limit order partially deployed",
    "예상": "Expected",
    "DCA 지정가 주문이 배치되지 않았습니다": "DCA limit order not deployed",
    "지정가 주문 확인 실패": "Limit order confirmation failed",
    "WebSocket 구독 실패": "WebSocket subscription failed",

    # Position monitoring
    "DCA 청산 완료": "DCA exit complete",
    "타입": "Type",
    "최대수익률": "Max profit rate",
    "BB600 부분청산 기록 초기화": "BB600 partial exit record initialization",
    "재진입 시 재실행 가능": "Re-executable on re-entry",
    "DCA 청산 통지 실패": "DCA exit notification failed",
    "전량청산 완료": "Full exit complete",
    "DCA 지정가 주문": "DCA limit order",
    "자동 취소": "Auto cancel",
    "DCA 주문 자동 취소 실패": "DCA order auto cancel failed",
    "WebSocket 구독 해제 실패": "WebSocket unsubscribe failed",
    "청산 완료": "Exit complete",
    "수익금": "Profit amount",
    "청산 알림 전송 실패": "Exit alert send failed",
    "DCA 청산 통지 실패 (fallback)": "DCA exit notification failed (fallback)",

    # Partial exit accumulation
    "부분청산 누적": "Partial exit accumulation",
    "기존방식": "Legacy method",
    "손익": "P&L",
    "누적": "Cumulative",
    "총 손익": "Total P&L",
    "부분청산 합산": "Partial exit aggregation",
    "전량청산 기록": "Full exit record",
    "부분청산 누적 데이터 정리 완료": "Partial exit accumulation data cleanup complete",
    "일일통계 업데이트": "Daily stats update",
    "거래": "Trade",

    # DCA order management
    "DCA 주문 점검 오류": "DCA order inspection error",
    "포지션체크": "Position check",
    "로컬 캐시에 포지션 존재": "Position exists in local cache",
    "중복 진입 차단": "Duplicate entry blocked",
    "API 키 없음": "No API key",
    "세션 캐시만 사용": "Using session cache only",
    "세션 내 이미 신호 발송됨": "Signal already sent in session",
    "실시간 조회": "Real-time query",
    "크기": "Size",
    "포지션": "Position",
    "세션 캐시 동기화": "Session cache sync",
    "포지션 존재": "Position exists",
    "세션 캐시 정리": "Session cache cleanup",
    "확인 실패": "Confirmation failed",
    "안전하게 진입 차단": "Entry blocked safely",

    # Market and ticker
    "마켓 캐시 조회 실패": "Market cache query failed",
    "가격 회복으로 본절보호청산 취소": "Capital protection exit cancelled due to price recovery",
    "청산 신호 체크 실패": "Exit signal check failed",
    "BB600 부분청산 이미 실행됨": "BB600 partial exit already executed",
    "시간": "Time",
    "BB600 부분청산 실행 기록됨": "BB600 partial exit execution recorded",
    "BB600 돌파 체크 실패": "BB600 breakout check failed",
    "SuperTrend 청산 시그널 체크 실패": "SuperTrend exit signal check failed",

    # SuperTrend analysis
    "SuperTrend 컬럼 없음": "No SuperTrend column",
    "조건 우회": "Condition bypass",
    "SuperTrend 5봉조건 체크": "SuperTrend 5-candle condition check",
    "현재방향": "Current direction",
    "컬럼": "Column",
    "SuperTrend 방향값들": "SuperTrend direction values",
    "SuperTrend 5봉조건 통과": "SuperTrend 5-candle condition passed",
    "현재 상승추세": "Currently in uptrend",
    "전환신호 발견": "Conversion signal found",
    "SuperTrend 조건3 체크": "SuperTrend condition 3 check",
    "현재가": "Current price",
    "ST값": "ST value",
    "SuperTrend 조건3 스킵": "SuperTrend condition 3 skipped",
    "supertrend 컬럼 없음": "No supertrend column",
    "SuperTrend 5봉조건 실패": "SuperTrend 5-candle condition failed",
    "모든 조건 미충족": "All conditions not met",
    "분봉 SuperTrend 진입 시그널 체크 실패": "SuperTrend entry signal check failed",

    # Strategy conditions
    "급등 조건 체크 실패": "Surge condition check failed",
    "제외": "Excluded",
    "분봉": "minute candles",
    "봉내": "within candles",
    "시가대비고가": "High vs Open",
    "이상 급등 감지": "Surge detected above",

    # Strategy C and D debugging
    "전략C 시작": "Strategy C start",
    "있음": "Present",
    "없음": "Absent",
    "전략C": "Strategy C",
    "전략D": "Strategy D",
    "REST API 로드 실패 예시": "REST API load failure example",

    # Signal reporting
    "SIGNAL": "SIGNAL",
    "진입신호": "Entry signal",
    "3분봉 시세 초입 포착": "3m candle early entry capture",
    "5분봉 초입 초강력 타점": "5m candle ultra-strong entry point",

    # Debugging and logging
    "디버깅 로그 설정 실패": "Debug logging setup failed",
    "DEBUG": "DEBUG",

    # WebSocket modes
    "하이브리드 모드": "Hybrid mode",
    "메인 스캔": "Main scan",
    "필터링": "Filtering",
    "스마트 하이브리드": "Smart hybrid",
    "실시간": "Real-time",
    "초기 데이터": "Initial data",
    "kline 웹소켓": "kline websocket",
    "극한 스캔 모드 활성화": "Extreme scan mode activated",
    "동적 WebSocket 구독 시스템 활성화됨": "Dynamic WebSocket subscription system activated",
    "필터링된 심볼만 동적으로 구독됩니다": "Only filtered symbols subscribed dynamically",
    "초기화 실패": "Initialization failed",
    "메인 스캔도 REST API 사용": "Main scan also uses REST API",
    "WebSocket 모듈 미설치": "WebSocket module not installed",
    "기존": "Legacy",
    "폴링 방식 사용": "Polling method used",
    "초기화 실패": "Initialization failed",
    "기존 방식으로 fallback": "Fallback to legacy method",
    "공개 API 모드": "Public API mode",
    "시장 데이터 수신 활성화": "Market data reception activated",
    "REST API 전용 모드 사용": "REST API only mode used",
    "WebSocket 전용 스캔 모드 활성화됨": "WebSocket-only scan mode activated",
    "Rate limit 회복됨": "Rate limit recovered",
    "API 호출 재개": "API calls resumed",

    # WebSocket subscription updates
    "WebSocket 구독 업데이트 시작": "WebSocket subscription update start",
    "필터링된 심볼": "Filtered symbols",
    "WebSocket 매니저가 없음": "No WebSocket manager",
    "구독 불가": "Subscription impossible",
    "동적 구독 시스템이 비활성화됨": "Dynamic subscription system disabled",
    "WebSocket 매니저와 동적 구독 시스템 확인됨": "WebSocket manager and dynamic subscription system confirmed",
    "심볼 형식 변환 완료": "Symbol format conversion complete",
    "대상 심볼": "Target symbols",
    "현재 구독 중인 심볼": "Currently subscribed symbols",
    "새로 구독할 심볼": "Symbols to newly subscribe",
    "구독 해제할 심볼": "Symbols to unsubscribe",
    "새로운": "New",
    "WebSocket 구독 시작": "WebSocket subscription start",
    "안정화 배치 처리": "Stabilized batch processing",
    "고속 모드": "High-speed mode",
    "배치당": "Per batch",
    "연결": "Connections",
    "히스토리 병렬 로드": "History parallel load",
    "배치": "Batch",
    "예상 소요 시간": "Estimated time",
    "약": "Approx",
    "병렬 처리": "Parallel processing",
    "완료": "Complete",
    "배치 구독 실패": "Batch subscription failed",
    "무시하고 계속": "Ignore and continue",
    "배치 완전 실패": "Batch completely failed",
    "WebSocket 구독 완료": "WebSocket subscription complete",
    "총 구독 심볼": "Total subscribed symbols",
    "새로 구독할 심볼이 없음": "No new symbols to subscribe",
    "WebSocket 구독 해제 및 캐시 제거 완료": "WebSocket unsubscribe and cache removal complete",
    "항목": "Items",
    "심볼 추적 업데이트 완료": "Symbol tracking update complete",
    "캐시": "Cache",
    "WebSocket 매니저가 없음": "No WebSocket manager",
    "초기 구독 불가": "Initial subscription impossible",
    "WebSocket 매니저 초기화 완료": "WebSocket manager initialization complete",
    "필터링된 심볼만 동적 구독 방식": "Dynamic subscription method for filtered symbols only",
    "WebSocket 매니저 준비 완료": "WebSocket manager ready",
    "지원 타임프레임": "Supported timeframes",
    "동적 구독 방식": "Dynamic subscription method",
    "필터링 통과 심볼만 구독": "Subscribe only to symbols passing filter",
    "버퍼 초기화 완료": "Buffer initialization complete",
    "초 후 WebSocket 버퍼 상태": "WebSocket buffer status after seconds",
    "버퍼링 중": "Buffering",
    "데이터가 있는 버퍼": "Buffers with data",

    # Data validation
    "데이터 부족하지만": "Insufficient data but",
    "개로 지표 계산 시도": "Attempting indicator calculation with count",

    # Miscellaneous
    "새로운": "New",
    "청산 방식 활성화": "Exit methods activated",
    "약수익보호": "Weak profit protection",
    "약상승후급락리스크회피": "Weak rise then sharp drop risk avoidance",
    "DCA순환매": "DCA cyclic trading",

    # Additional WebSocket manager messages
    "python-binance WebSocket 시작 성공": "python-binance WebSocket start success",
    "구독 관리": "Subscription management",
    "신규 심볼 없음": "No new symbols",
    "현재": "Current",
    "신규 구독": "New subscription",
    "활성": "Active",
    "구독 완료": "Subscription complete",
    "BulkWebSocketKlineManager 초기화 완료": "BulkWebSocketKlineManager initialization complete",
    "강제 재구독": "Forced re-subscription",
    "전체 재등록": "Full re-registration",
    "구독 관리": "Subscription management",
    "UNSUBSCRIBE 비활성화": "UNSUBSCRIBE disabled",
    "유지": "Maintain",
    "초기 데이터 로딩 시작": "Initial data loading start",
    "Rate Limit 보호": "Rate Limit protection",
    "심볼당": "Per symbol",
    "delay": "delay",
    "API 호출": "API calls",
    "바이낸스 제한": "Binance limit",
    "대비": "vs",
    "사용": "Usage",
    "IP 밴 위험 거의 0%": "IP ban risk almost 0%",
    "Rate Limit 보호": "Rate Limit protection",
    "다음 심볼로 넘어가기 전 안전 delay": "Safe delay before next symbol",
    "분당 API 호출": "API calls per minute",
    "로 제한": "Limited to",
    "초기 데이터 로드 실패": "Initial data load failed",
    "성공률": "Success rate",
    "조회 실패": "Query failed",
    "최신 캔들 조회 실패": "Latest candle query failed",
    "강제 close 실패": "Force close failed",

    # Defense system
    "WebSocket Defense System 초기화 완료": "WebSocket Defense System initialization complete",
    "방어 시스템이 이미 실행 중입니다": "Defense system already running",
    "스레드 시작": "Thread start",
    "WebSocket Defense System 가동 완료": "WebSocket Defense System startup complete",
    "개 스레드": "threads",
    "WebSocket Defense System 중지됨": "WebSocket Defense System stopped",
    "Heartbeat Monitor 시작": "Heartbeat Monitor start",
    "Heartbeat 끊김": "Heartbeat disconnected",
    "무응답": "No response",
    "임계값": "Threshold",
    "Heartbeat Monitor 에러": "Heartbeat Monitor error",
    "Data Sync Check 시작": "Data Sync Check start",
    "데이터 지연": "Data delay",
    "Data Sync Check 에러": "Data Sync Check error",
    "Stream Flush Detection 시작": "Stream Flush Detection start",
    "close 이벤트 누락": "close event missing",
    "Stream Flush Detection 에러": "Stream Flush Detection error",
    "Flush 감지 실패": "Flush detection failed",
    "캔들 강제 close 처리": "Candle forced close processing",
    "스캔 트리거 실패": "Scan trigger failed",

    # TradingView webhook messages
    "TradingView 전략 실행기 초기화 완료": "TradingView strategy executor initialization complete",
    "TradingView 청산 신호": "TradingView exit signal",
    "청산 실패": "Exit failed",
    "포지션 없음?": "No position?",
    "매매 실행 오류": "Trade execution error",
    "웹훅 요청 수신": "Webhook request received",
    "수신 데이터": "Received data",
    "서명 검증 실패": "Signature verification failed",
    "알림 파싱 완료": "Alert parsing complete",
    "알 수 없는 액션": "Unknown action",
    "알림 파싱 실패": "Alert parsing failed",
    "매매 비활성화됨": "Trading disabled",
    "시뮬레이션 모드": "Simulation mode",
    "매매 미실행": "Trade not executed",
    "전략 실행기가 초기화되지 않음": "Strategy executor not initialized",
    "전략 실행기 미초기화": "Strategy executor uninitialized",
    "매매 실행 시작": "Trade execution start",
    "웹훅 엔드포인트": "Webhook endpoint",
    "JSON 파싱 실패": "JSON parsing failed",
    "웹훅 처리 오류": "Webhook processing error",
    "전략 실행기 초기화 완료": "Strategy executor initialization complete",
    "설정 로드 완료": "Configuration load complete",
    "기본 설정 파일 생성됨": "Default config file created",
    "SECRET_KEY를 반드시 변경하세요": "SECRET_KEY must be changed",
    "SECRET_KEY가 기본값입니다": "SECRET_KEY is default value",
    "보안 위험": "Security risk",
    "테스트 모드": "Test mode",
    "전략 실행기 없이 서버만 시작": "Starting server only without strategy executor",
    "실제 사용 시에는 tradingview_strategy_executor.py를 실행하세요": "For actual use, run tradingview_strategy_executor.py",
}

# Files to process
FILES = [
    "advanced_exit_system.py",
    "apply_websocket_user_data_stream.py",
    "basic_exit_system.py",
    "binance_rate_limiter.py",
    "binance_websocket_kline_manager.py",
    "bulk_websocket_kline_manager.py",
    "improved_dca_position_manager.py",
    "indicators.py",
    "one_minute_surge_entry_strategy.py",
    "tradingview_strategy_executor.py",
    "tradingview_webhook_server.py",
    "websocket_defense_system.py",
]

def translate_log_messages(content):
    """Translate Korean log messages to English"""
    for korean, english in TRANSLATIONS.items():
        # Escape special regex characters
        korean_escaped = re.escape(korean)
        content = re.sub(korean_escaped, english, content)
    return content

def process_file(filepath):
    """Process a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        translated_content = translate_log_messages(content)

        if original_content != translated_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(translated_content)
            return True, "Translated"
        else:
            return True, "No changes needed"

    except Exception as e:
        return False, str(e)

def main():
    """Main execution"""
    print("=" * 70)
    print("Korean to English Log Message Translator")
    print("=" * 70)

    results = []

    for filename in FILES:
        filepath = os.path.join(os.getcwd(), filename)

        if not os.path.exists(filepath):
            results.append((filename, False, "File not found"))
            continue

        print(f"\nProcessing: {filename}...", end=" ")
        success, message = process_file(filepath)
        results.append((filename, success, message))
        print(message)

    # Summary
    print("\n" + "=" * 70)
    print("Translation Summary:")
    print("=" * 70)

    success_count = sum(1 for _, success, _ in results if success)
    total_count = len(results)

    for filename, success, message in results:
        status = "✅" if success else "❌"
        print(f"{status} {filename}: {message}")

    print(f"\n{success_count}/{total_count} files processed successfully")
    print("=" * 70)

    # Syntax verification
    print("\nVerifying Python syntax...")
    syntax_errors = []

    for filename in FILES:
        filepath = os.path.join(os.getcwd(), filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    compile(f.read(), filepath, 'exec')
                print(f"✅ {filename}: Syntax OK")
            except SyntaxError as e:
                syntax_errors.append((filename, str(e)))
                print(f"❌ {filename}: Syntax Error - {e}")

    if syntax_errors:
        print(f"\n⚠️  {len(syntax_errors)} file(s) with syntax errors!")
    else:
        print("\n✅ All files syntax-verified successfully!")

if __name__ == "__main__":
    main()
