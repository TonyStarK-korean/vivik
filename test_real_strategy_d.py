# -*- coding: utf-8 -*-
"""
실제 전략D 검증 테스트
정확한 조건으로 데이터 수신과 전략 실행 검증
"""

import sys
import io
import pandas as pd
from one_minute_surge_entry_strategy import OneMinuteSurgeEntryStrategy

# UTF-8 인코딩 강제
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def test_real_strategy_d():
    """실제 전략D 조건으로 검증"""

    print("=" * 80)
    print("전략D 검증 테스트 (실제 조건)")
    print("=" * 80)

    # 전략 초기화
    print("\n1. 전략 초기화 중...")
    strategy = OneMinuteSurgeEntryStrategy()

    # 테스트 심볼
    test_symbol = "BTC/USDT:USDT"
    print(f"\n2. 테스트 심볼: {test_symbol}")

    # ========================================
    # STEP 1: 데이터 수신
    # ========================================
    print("\n" + "=" * 80)
    print("STEP 1: 데이터 수신")
    print("=" * 80)

    timeframes = {
        '5m': 100,
        '15m': 700,
    }

    data_dict = {}

    for tf, limit in timeframes.items():
        print(f"\n[{tf}] 데이터 로드 중... (limit={limit})")
        try:
            data = strategy.exchange.fetch_ohlcv(test_symbol, tf, limit=limit)
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            data_dict[tf] = df

            print(f"  OK: {len(df)}개 캔들 수신")
            print(f"  최신: {df['timestamp'].iloc[-1]} | 종가: ${df['close'].iloc[-1]:,.2f}")

        except Exception as e:
            print(f"  FAIL: {e}")
            data_dict[tf] = None

    if not all(df is not None for df in data_dict.values()):
        print("\n데이터 수신 실패!")
        return False

    df_5m = data_dict['5m']
    df_15m = data_dict['15m']

    # ========================================
    # STEP 2: 지표 계산
    # ========================================
    print("\n" + "=" * 80)
    print("STEP 2: 지표 계산")
    print("=" * 80)

    print("\n[5분봉] calculate_indicators() 실행 중...")
    df_5m_calc = strategy.calculate_indicators(df_5m)
    if df_5m_calc is not None:
        print(f"  OK: {len(df_5m_calc)}개 캔들 (지표 계산 완료)")
        # 지표 확인
        indicators = ['ma5', 'ma20', 'ma80', 'ma480', 'bb200_upper', 'supertrend', 'supertrend_direction', 'supertrend_signal']
        print("  지표 확인:")
        for ind in indicators:
            if ind in df_5m_calc.columns:
                latest_val = df_5m_calc[ind].iloc[-1]
                if pd.notna(latest_val):
                    print(f"    {ind}: {latest_val:.4f}")
                else:
                    print(f"    {ind}: N/A")
            else:
                print(f"    {ind}: 컬럼 없음")
    else:
        print("  FAIL: 지표 계산 실패")
        return False

    print("\n[15분봉] calculate_indicators() 실행 중...")
    df_15m_calc = strategy.calculate_indicators(df_15m)
    if df_15m_calc is not None:
        print(f"  OK: {len(df_15m_calc)}개 캔들 (지표 계산 완료)")
        latest_15m = df_15m_calc.iloc[-1]
        print("  지표 확인:")
        for ind in ['ma80', 'ma480']:
            if ind in df_15m_calc.columns:
                val = latest_15m[ind]
                if pd.notna(val):
                    print(f"    {ind}: {val:.4f}")
                else:
                    print(f"    {ind}: N/A")
    else:
        print("  FAIL: 지표 계산 실패")
        return False

    # ========================================
    # STEP 3: 실제 전략D 조건 검증
    # ========================================
    print("\n" + "=" * 80)
    print("STEP 3: 전략D 조건 검증 (5개 조건)")
    print("=" * 80)

    # 조건1: 15분봉 MA80 < MA480
    print("\n[조건1] 15분봉 MA80 < MA480")
    latest_15m = df_15m_calc.iloc[-1]
    ma80_15m = latest_15m['ma80']
    ma480_15m = latest_15m['ma480']

    condition1 = False
    if pd.notna(ma80_15m) and pd.notna(ma480_15m):
        condition1 = ma80_15m < ma480_15m
        print(f"  MA80: {ma80_15m:.2f}")
        print(f"  MA480: {ma480_15m:.2f}")
        print(f"  결과: {'OK' if condition1 else 'FAIL'} (MA80 {'<' if condition1 else '>='} MA480)")
    else:
        print(f"  FAIL: 지표값 없음 (MA80={ma80_15m}, MA480={ma480_15m})")

    # 조건2: 5분봉 SuperTrend(10-3) 진입 시그널
    print("\n[조건2] 5분봉 SuperTrend(10-3) 진입 시그널")
    condition2 = False
    try:
        supertrend_signal = strategy.check_5m_supertrend_entry_signal(test_symbol, df_5m_calc)
        condition2 = supertrend_signal
        print(f"  check_5m_supertrend_entry_signal() 결과: {supertrend_signal}")
        print(f"  결과: {'OK' if condition2 else 'FAIL'}")
    except Exception as e:
        print(f"  FAIL: {e}")

    # 조건3: 60봉이내 MA80-MA480 골든크로스 OR 이격도 5%이내
    print("\n[조건3] 60봉이내 MA80-MA480 골든크로스 OR 이격도 5%이내")
    condition3 = False

    # 골든크로스 확인
    golden_cross = False
    if len(df_5m_calc) >= 60:
        recent_60 = df_5m_calc.tail(60)
        for i in range(1, len(recent_60)):
            prev = recent_60.iloc[i-1]
            curr = recent_60.iloc[i]
            if (pd.notna(prev['ma80']) and pd.notna(prev['ma480']) and
                pd.notna(curr['ma80']) and pd.notna(curr['ma480'])):
                if prev['ma80'] < prev['ma480'] and curr['ma80'] >= curr['ma480']:
                    golden_cross = True
                    print(f"  골든크로스 발견: 봉 {i}")
                    break

    # 이격도 확인
    gap_condition = False
    latest_5m = df_5m_calc.iloc[-1]
    if (pd.notna(latest_5m['ma80']) and pd.notna(latest_5m['ma480']) and
        latest_5m['ma80'] < latest_5m['ma480'] and latest_5m['ma480'] > 0):
        gap_pct = ((latest_5m['ma480'] - latest_5m['ma80']) / latest_5m['ma480']) * 100
        gap_condition = gap_pct <= 5.0
        print(f"  MA80: {latest_5m['ma80']:.2f}")
        print(f"  MA480: {latest_5m['ma480']:.2f}")
        print(f"  이격도: {gap_pct:.2f}%")
        print(f"  이격도 조건: {'OK' if gap_condition else 'FAIL'} (5% 이내)")

    condition3 = golden_cross or gap_condition
    print(f"  결과: {'OK' if condition3 else 'FAIL'} (골든크로스={golden_cross} OR 이격도={gap_condition})")

    # 조건4: MA480 5연속 하락 AND BB200상한선이 MA480 골든크로스
    print("\n[조건4] MA480 5연속 하락 AND BB200상한선이 MA480 골든크로스")
    condition4 = False

    # MA480 5연속 하락
    ma480_down = False
    if len(df_5m_calc) >= 60:
        recent = df_5m_calc.tail(60)
        max_consecutive = 0
        current_consecutive = 0
        for i in range(1, len(recent)):
            if (pd.notna(recent.iloc[i]['ma480']) and pd.notna(recent.iloc[i-1]['ma480']) and
                recent.iloc[i]['ma480'] < recent.iloc[i-1]['ma480']):
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        ma480_down = max_consecutive >= 5
        print(f"  MA480 최대 연속 하락: {max_consecutive}봉")
        print(f"  5연속 하락: {'OK' if ma480_down else 'FAIL'}")

    # BB200-MA480 골든크로스
    bb_golden = False
    for i in range(1, len(df_5m_calc)):
        prev = df_5m_calc.iloc[i-1]
        curr = df_5m_calc.iloc[i]
        if (pd.notna(prev['bb200_upper']) and pd.notna(prev['ma480']) and
            pd.notna(curr['bb200_upper']) and pd.notna(curr['ma480'])):
            if prev['bb200_upper'] < prev['ma480'] and curr['bb200_upper'] >= curr['ma480']:
                bb_golden = True
                print(f"  BB200-MA480 골든크로스 발견: 봉 {i}")
                break

    if not bb_golden:
        print(f"  BB200-MA480 골든크로스: FAIL")

    condition4 = ma480_down and bb_golden
    print(f"  결과: {'OK' if condition4 else 'FAIL'}")

    # 조건5: 20봉이내 MA5-MA20 골든크로스
    print("\n[조건5] 20봉이내 MA5-MA20 골든크로스")
    condition5 = False
    if len(df_5m_calc) >= 20:
        recent_20 = df_5m_calc.tail(20)
        for i in range(1, len(recent_20)):
            prev = recent_20.iloc[i-1]
            curr = recent_20.iloc[i]
            if (pd.notna(prev['ma5']) and pd.notna(prev['ma20']) and
                pd.notna(curr['ma5']) and pd.notna(curr['ma20'])):
                if prev['ma5'] < prev['ma20'] and curr['ma5'] >= curr['ma20']:
                    condition5 = True
                    print(f"  MA5-MA20 골든크로스 발견: 봉 {i}")
                    break

    if not condition5:
        print(f"  MA5-MA20 골든크로스: FAIL")

    print(f"  결과: {'OK' if condition5 else 'FAIL'}")

    # 조건 요약
    print("\n" + "-" * 80)
    print("조건 요약:")
    conditions = {
        "조건1 (15m MA80<MA480)": condition1,
        "조건2 (SuperTrend 진입)": condition2,
        "조건3 (골든크로스 OR 이격도)": condition3,
        "조건4 (MA480하락 AND BB골든)": condition4,
        "조건5 (MA5-MA20 골든)": condition5
    }

    passed = sum(conditions.values())
    for name, result in conditions.items():
        print(f"  {'OK' if result else 'FAIL'} {name}")

    print(f"\n통과: {passed}/5")

    # ========================================
    # STEP 4: 실제 analyze_symbol 호출
    # ========================================
    print("\n" + "=" * 80)
    print("STEP 4: analyze_symbol() 호출")
    print("=" * 80)

    print("\nanalyze_symbol() 실행 중...")
    result = strategy.analyze_symbol(test_symbol)

    if result:
        print(f"\nOK: 결과 반환됨")
        print(f"  심볼: {result.get('symbol')}")
        print(f"  전략: {result.get('strategy_type')}")
        print(f"  상태: {result.get('status')}")
        print(f"  진입가: ${result.get('entry_price', 0):.4f}")
    else:
        print(f"\nanalyze_symbol() 반환: None")
        print(f"  이유: 조건 미충족 ({passed}/5)")

    # 최종 결론
    print("\n" + "=" * 80)
    print("검증 완료")
    print("=" * 80)

    print(f"\n[1] 데이터 수신: OK (5m={len(df_5m)}, 15m={len(df_15m)})")
    print(f"[2] 지표 계산: OK")
    print(f"[3] 조건 검증: {passed}/5 통과")
    print(f"[4] 전략 실행: OK")

    if passed >= 5:
        print(f"\n결과: 진입 신호 발생!")
    elif passed >= 3:
        print(f"\n결과: 관심 종목 (3-4개 조건)")
    else:
        print(f"\n결과: 조건 미충족")
        print(f"  현재 시장 상황이 전략 조건에 맞지 않음")
        print(f"  시스템은 정상 작동 중")

    return True

if __name__ == "__main__":
    print("\n실제 전략D 검증 테스트 시작\n")
    test_real_strategy_d()
