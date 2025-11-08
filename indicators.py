# -*- coding: utf-8 -*-
"""
Technical Indicators Module
기술적 지표 계산 전용 모듈

주요 기능:
- 이동평균(MA5, MA20, MA80, MA480)
- 볼린저 밴드(BB20, BB80, BB200, BB480, BB600)
- SuperTrend(10-3)
- 일목균형표(Ichimoku)
- 골든크로스/데드크로스 탐지
"""

import pandas as pd
import numpy as np
from typing import Optional


# 전략 조건 상세 설명 (format_condition_result에서 Usage)
STRATEGY_CONDITION_DETAILS = {
    # 전략 C 조건들
    'C1': {
        'name': '조건1',
        'description': 'BB200상단-BB480상단 골든크로스',
        'detail': '200봉이내 볼린저밴드 상단선 골든크로스 발생'
    },
    'C2A': {
        'name': '조건2A',
        'description': 'MA5-MA20 데드크로스 Confirm',
        'detail': '100봉이내 MA5-MA20 데드크로스 발생'
    },
    'C2B': {
        'name': '조건2B',
        'description': 'MA1-MA5 골든크로스',
        'detail': '10봉이내 MA1-MA5 골든크로스 발생'
    },
    'C2C': {
        'name': '조건2C',
        'description': 'MA5<MA20 또는 이격도 2%이내',
        'detail': 'MA5가 MA20 아래 또는 MA5-MA20 이격도 2%이내'
    },
    'C_ST': {
        'name': 'SuperTrend',
        'description': '5minute candles SuperTrend 매수신호',
        'detail': '5minute candles SuperTrend(10-3) 하락→상승 전환'
    },

    # 전략 D 조건들
    'D1': {
        'name': '조건D1',
        'description': '15minute candles MA80<MA480',
        'detail': '15minute candles에서 MA80이 MA480 아래 위치'
    },
    'D2': {
        'name': '조건D2',
        'description': '5minute candles SuperTrend 매수신호',
        'detail': '5minute candles SuperTrend(10-3) 하락→상승 전환'
    },
    'D3': {
        'name': '조건D3',
        'description': 'MA80-MA480 골든크로스 OR 이격도 5%이내',
        'detail': '200봉이내 골든크로스 또는 Current 이격도 5%이내'
    },
    'D4': {
        'name': '조건D4',
        'description': 'MA480 하락+BB200-MA480 골든',
        'detail': 'MA480 5연속 하락 + BB200상단-MA480 골든크로스'
    },
    'D5': {
        'name': '조건D5',
        'description': 'MA5-MA20 골든크로스',
        'detail': '20봉이내 MA5-MA20 골든크로스 발생'
    }
}


def calculate_indicators(df: pd.DataFrame, logger=None) -> Optional[pd.DataFrame]:
    """
    기술적 지표 계산

    Args:
        df: OHLCV 데이터프레임
        logger: 로거 인스턴스 (선택)

    Returns:
        지표가 Add된 데이터프레임 또는 None
    """
    try:
        if df is None:
            return None

        # 완화된 데이터 요구사항 - WebSocket 실Time 데이터에 맞춰 조정
        if len(df) >= 300:
            min_required = 100
        elif len(df) >= 200:
            min_required = 80
        elif len(df) >= 100:
            min_required = 50
        else:
            min_required = 30

        if len(df) < min_required:
            if logger:
                logger.debug(f"지표 계산 Failed: Insufficient data (Length:{len(df)}, Required:{min_required})")
            # 극한 완화 - 최소 20count만 있어도 계산 Attempt
            if len(df) >= 20:
                if logger:
                    logger.warning(f"⚠️ Insufficient data하지만 {len(df)}count로 Indicator calculation attempt")
            else:
                return None

        # 이동평균 (Length에 따라 적응적 계산)
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma20'] = df['close'].rolling(window=min(20, len(df))).mean()
        df['ma80'] = df['close'].rolling(window=min(80, len(df))).mean()

        # MA480은 데이터가 충분할 때만 계산
        if len(df) >= 480:
            df['ma480'] = df['close'].rolling(window=480).mean()
        else:
            # 데이터가 부족하면 MA200 또는 최대 가능한 Length로 대체
            ma_window = min(200, len(df) // 2) if len(df) > 20 else len(df) // 2
            if ma_window > 0:
                df['ma480'] = df['close'].rolling(window=ma_window).mean()
            else:
                df['ma480'] = df['close']

        # 볼린저 밴드 (적응적 계산)
        for period in [20, 80, 200]:
            actual_period = min(period, len(df))
            if actual_period >= 5:
                rolling_mean = df['close'].rolling(window=actual_period).mean()
                rolling_std = df['close'].rolling(window=actual_period).std()
                df[f'bb{period}_upper'] = rolling_mean + (rolling_std * 2)
                df[f'bb{period}_lower'] = rolling_mean - (rolling_std * 2)
            else:
                df[f'bb{period}_upper'] = df['close']
                df[f'bb{period}_lower'] = df['close']

        # BB480과 BB600은 충분한 데이터가 있을 때만 계산
        for period in [480, 600]:
            if len(df) >= period:
                rolling_mean = df['close'].rolling(window=period).mean()
                rolling_std = df['close'].rolling(window=period).std()
                df[f'bb{period}_upper'] = rolling_mean + (rolling_std * 2)
                df[f'bb{period}_lower'] = rolling_mean - (rolling_std * 2)
            else:
                # count선된 대체 계산: 가용 데이터로 최대한 계산
                max_window = min(len(df) - 5, max(20, len(df) // 2))
                if max_window >= 20:
                    rolling_mean = df['close'].rolling(window=max_window).mean()
                    rolling_std = df['close'].rolling(window=max_window).std()
                    # BB600은 더 넓은 밴드를 가지도록 조정
                    std_multiplier = 2.5 if period == 600 else 2.2
                    df[f'bb{period}_upper'] = rolling_mean + (rolling_std * std_multiplier)
                    df[f'bb{period}_lower'] = rolling_mean - (rolling_std * std_multiplier)
                elif f'bb200_upper' in df.columns:
                    # BB200 기반 확장
                    expansion_factor = 1.3 if period == 600 else 1.2
                    df[f'bb{period}_upper'] = df['bb200_upper'] * expansion_factor
                    df[f'bb{period}_lower'] = df['bb200_lower'] * (2 - expansion_factor)
                else:
                    # MA 기반 최후 대안
                    expansion_factor = 1.15 if period == 600 else 1.1
                    df[f'bb{period}_upper'] = df['ma480'] * expansion_factor
                    df[f'bb{period}_lower'] = df['ma480'] * (2 - expansion_factor)

        # 일목균형표
        df['ichimoku_base'] = (df['high'].rolling(window=26).max() + df['low'].rolling(window=26).min()) / 2
        df['ichimoku_conversion'] = (df['high'].rolling(window=9).max() + df['low'].rolling(window=9).min()) / 2

        # SuperTrend 지표 Add
        if len(df) >= 20:
            try:
                # ATR 계산
                df['tr'] = np.maximum(
                    df['high'] - df['low'],
                    np.maximum(
                        abs(df['high'] - df['close'].shift(1)),
                        abs(df['low'] - df['close'].shift(1))
                    )
                )
                df['atr'] = df['tr'].rolling(window=10).mean()

                # SuperTrend 계산 (10-3 Settings)
                hl2 = (df['high'] + df['low']) / 2
                multiplier = 3.0
                df['upper_band'] = hl2 + (multiplier * df['atr'])
                df['lower_band'] = hl2 - (multiplier * df['atr'])

                # SuperTrend 라인과 방향 계산
                df['supertrend'] = 0.0
                df['supertrend_direction'] = 0  # 1: 상승, -1: 하락
                df['supertrend_signal'] = 0    # 별칭 (호환성)

                for i in range(10, len(df)):
                    prev_close = df['close'].iloc[i-1]
                    curr_close = df['close'].iloc[i]
                    upper_band = df['upper_band'].iloc[i]
                    lower_band = df['lower_band'].iloc[i]
                    prev_supertrend = df['supertrend'].iloc[i-1] if i > 10 else upper_band
                    prev_direction = df['supertrend_direction'].iloc[i-1] if i > 10 else -1

                    # SuperTrend 계산 로직
                    if prev_direction == 1:  # 이전이 상승 트렌드
                        if curr_close < lower_band:
                            df.loc[df.index[i], 'supertrend'] = upper_band
                            df.loc[df.index[i], 'supertrend_direction'] = -1
                            df.loc[df.index[i], 'supertrend_signal'] = -1
                        else:
                            df.loc[df.index[i], 'supertrend'] = max(lower_band, prev_supertrend)
                            df.loc[df.index[i], 'supertrend_direction'] = 1
                            df.loc[df.index[i], 'supertrend_signal'] = 1
                    else:  # 이전이 하락 트렌드
                        if curr_close > upper_band:
                            df.loc[df.index[i], 'supertrend'] = lower_band
                            df.loc[df.index[i], 'supertrend_direction'] = 1
                            df.loc[df.index[i], 'supertrend_signal'] = 1
                        else:
                            df.loc[df.index[i], 'supertrend'] = min(upper_band, prev_supertrend)
                            df.loc[df.index[i], 'supertrend_direction'] = -1
                            df.loc[df.index[i], 'supertrend_signal'] = -1

            except Exception as st_error:
                if logger:
                    logger.warning(f"SuperTrend 계산 Failed: {st_error}")
                # SuperTrend Failed시 기본값 Settings
                df['supertrend'] = df['close']
                df['supertrend_direction'] = 1
                df['supertrend_signal'] = 1

        # 최소 데이터 Verification (더 관대한 기준)
        recent_check = df.tail(10)

        # 기본 지표 Verification
        ma20_valid = recent_check['ma20'].notna().sum()
        ma80_valid = recent_check['ma80'].notna().sum()

        if ma20_valid < 3 or ma80_valid < 3:
            if logger:
                logger.debug(f"지표 계산 Failed: 기본 MA Insufficient data (MA20:{ma20_valid}/10, MA80:{ma80_valid}/10)")
            return None

        # MA480은 조건부 Verification
        if len(df) >= 480:
            ma480_valid = recent_check['ma480'].notna().sum()
            if ma480_valid < 3:
                if logger:
                    logger.debug(f"지표 계산 Failed: MA480 Insufficient data (유효:{ma480_valid}/10)")
                return None

        # BB600 Verification: 원래 계산 또는 대체 계산 모두 허용
        if 'bb600_upper' in df.columns:
            bb600_valid = recent_check['bb600_upper'].notna().sum()
            if bb600_valid < 1:
                if logger:
                    logger.debug(f"지표 계산 Failed: BB600 Insufficient data (유효:{bb600_valid}/1)")
                return None
            # 대체 계산 Usage 시 Debug Info
            if len(df) < 600 and logger:
                logger.debug(f"[INFO] BB600 대체계산 Usage: 데이터{len(df)}count로 추정계산")

        return df

    except Exception as e:
        if logger:
            logger.error(f"지표 계산 Failed: {e}")
        return None


def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0, logger=None) -> Optional[pd.DataFrame]:
    """
    SuperTrend 지표 계산

    Args:
        df: OHLCV 데이터프레임
        period: ATR 기간 (기본값: 10)
        multiplier: ATR 배수 (기본값: 3.0)
        logger: 로거 인스턴스 (선택)

    Returns:
        SuperTrend 지표가 Add된 데이터프레임 또는 None
    """
    try:
        if df is None or len(df) < period:
            return None

        # ATR 계산
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(window=period).mean()

        # SuperTrend 계산
        hl2 = (df['high'] + df['low']) / 2
        df['upper_band'] = hl2 + (multiplier * df['atr'])
        df['lower_band'] = hl2 - (multiplier * df['atr'])

        # SuperTrend 라인 계산
        df['supertrend'] = 0.0
        df['supertrend_direction'] = 0  # 1: 상승, -1: 하락

        for i in range(period, len(df)):
            prev_close = df['close'].iloc[i-1]
            curr_close = df['close'].iloc[i]
            upper_band = df['upper_band'].iloc[i]
            lower_band = df['lower_band'].iloc[i]
            prev_supertrend = df['supertrend'].iloc[i-1] if i > period else upper_band
            prev_direction = df['supertrend_direction'].iloc[i-1] if i > period else -1

            # SuperTrend 계산 로직
            if prev_direction == 1:  # 이전이 상승 트렌드
                if curr_close < lower_band:
                    df.loc[df.index[i], 'supertrend'] = upper_band
                    df.loc[df.index[i], 'supertrend_direction'] = -1
                else:
                    df.loc[df.index[i], 'supertrend'] = max(lower_band, prev_supertrend)
                    df.loc[df.index[i], 'supertrend_direction'] = 1
            else:  # 이전이 하락 트렌드
                if curr_close > upper_band:
                    df.loc[df.index[i], 'supertrend'] = lower_band
                    df.loc[df.index[i], 'supertrend_direction'] = 1
                else:
                    df.loc[df.index[i], 'supertrend'] = min(upper_band, prev_supertrend)
                    df.loc[df.index[i], 'supertrend_direction'] = -1

        return df

    except Exception as e:
        if logger:
            logger.error(f"SuperTrend 계산 Failed: {e}")
        return None


def find_golden_cross(df: pd.DataFrame, ma1_col: str, ma2_col: str, recent_n: int = 30, logger=None) -> bool:
    """
    골든크로스 탐지 함수 (최근 n봉 내에서)

    Args:
        df: 데이터프레임
        ma1_col: 빠른 이동평균 Column명
        ma2_col: 느린 이동평균 Column명
        recent_n: 최근 몇 봉을 검사할지
        logger: 로거 인스턴스 (선택)

    Returns:
        골든크로스 발생 여부
    """
    try:
        if df is None or len(df) < 2:
            return False

        # 최근 n봉만 검사
        check_length = min(recent_n, len(df))
        recent_df = df.tail(check_length)

        if len(recent_df) < 2:
            return False

        # 각 인접한 캔들 쌍에서 골든크로스 찾기
        for i in range(len(recent_df) - 1):
            curr_idx = i
            next_idx = i + 1

            curr_row = recent_df.iloc[curr_idx]
            next_row = recent_df.iloc[next_idx]

            # 모든 값이 유효한지 Confirm
            if (pd.notna(curr_row[ma1_col]) and pd.notna(curr_row[ma2_col]) and
                pd.notna(next_row[ma1_col]) and pd.notna(next_row[ma2_col])):

                # 골든크로스: 이전봉에서 ma1 < ma2, 다음봉에서 ma1 > ma2
                if (curr_row[ma1_col] < curr_row[ma2_col] and
                    next_row[ma1_col] > next_row[ma2_col]):
                    return True

        return False

    except Exception as e:
        if logger:
            logger.error(f"골든크로스 탐지 Error: {e}")
        return False


def find_dead_cross(df: pd.DataFrame, ma1_col: str, ma2_col: str, recent_n: int = 20, logger=None) -> bool:
    """
    데드크로스 탐지 함수 (최근 n봉 내에서)

    Args:
        df: 데이터프레임
        ma1_col: 빠른 이동평균 Column명
        ma2_col: 느린 이동평균 Column명
        recent_n: 최근 몇 봉을 검사할지
        logger: 로거 인스턴스 (선택)

    Returns:
        데드크로스 발생 여부
    """
    try:
        if df is None or len(df) < 2:
            return False

        # 최근 n봉만 검사
        check_length = min(recent_n, len(df))
        recent_df = df.tail(check_length)

        if len(recent_df) < 2:
            return False

        # 각 인접한 캔들 쌍에서 데드크로스 찾기
        for i in range(len(recent_df) - 1):
            curr_idx = i
            next_idx = i + 1

            curr_row = recent_df.iloc[curr_idx]
            next_row = recent_df.iloc[next_idx]

            # 모든 값이 유효한지 Confirm
            if (pd.notna(curr_row[ma1_col]) and pd.notna(curr_row[ma2_col]) and
                pd.notna(next_row[ma1_col]) and pd.notna(next_row[ma2_col])):

                # 데드크로스: 이전봉에서 ma1 > ma2, 다음봉에서 ma1 < ma2
                if (curr_row[ma1_col] > curr_row[ma2_col] and
                    next_row[ma1_col] < next_row[ma2_col]):
                    return True

        return False

    except Exception as e:
        if logger:
            logger.error(f"데드크로스 탐지 Error: {e}")
        return False


def format_condition_result(condition_code: str, result: bool, extra_info: str = "") -> str:
    """
    조건 체크 결과를 상세하게 포맷팅

    Args:
        condition_code: 조건 Code (C1, C2A, D1 등)
        result: 조건 충족 여부
        extra_info: Add Info (선택)

    Returns:
        포맷팅된 결과 문자열
    """
    condition_info = STRATEGY_CONDITION_DETAILS.get(condition_code, {
        'name': condition_code,
        'description': '알 수 없는 조건',
        'detail': ''
    })

    status = "✅" if result else "❌"
    name = condition_info['name']
    description = condition_info['description']

    result_line = f"      {status} {name}: {description}"

    if extra_info:
        result_line += f" ({extra_info})"

    return result_line
