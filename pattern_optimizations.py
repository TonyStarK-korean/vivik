# -*- coding: utf-8 -*-
"""
Pattern Optimization Functions
Vectorized helper functions for MA480 pullback strategy pattern detection
"""

import numpy as np
import pandas as pd
from typing import Optional, Union


def find_golden_cross_vectorized(
    df: pd.DataFrame,
    fast_ma_col: str, 
    slow_ma_col: str, 
    recent_n: int = 334
) -> bool:
    """
    Vectorized golden cross detection
    
    Args:
        df: DataFrame with OHLCV and indicator data
        fast_ma_col: Fast moving average column name
        slow_ma_col: Slow moving average column name  
        recent_n: Number of periods to look back
        
    Returns:
        True if golden cross found within recent_n periods, False otherwise
    """
    if df is None or len(df) < 2:
        return False
        
    # Check if columns exist
    if fast_ma_col not in df.columns or slow_ma_col not in df.columns:
        return False
        
    # Get the data for the specified period
    look_back = min(recent_n, len(df))
    recent_df = df.tail(look_back)
    
    if len(recent_df) < 2:
        return False
        
    # Check for golden cross: previous period fast <= slow, current period fast > slow
    # Need to compare consecutive valid rows, so iterate through dataframe
    for i in range(1, len(recent_df)):
        prev_row = recent_df.iloc[i-1]
        curr_row = recent_df.iloc[i]

        # Check if both values are valid (not NaN) for both periods
        if (pd.notna(prev_row[fast_ma_col]) and pd.notna(prev_row[slow_ma_col]) and
            pd.notna(curr_row[fast_ma_col]) and pd.notna(curr_row[slow_ma_col])):

            # Golden cross: previous fast <= slow, current fast > slow
            if prev_row[fast_ma_col] <= prev_row[slow_ma_col] and curr_row[fast_ma_col] > curr_row[slow_ma_col]:
                return True

    return False


def find_dead_cross_vectorized(
    df: pd.DataFrame,
    fast_ma_col: str, 
    slow_ma_col: str, 
    recent_n: int = 334
) -> bool:
    """
    Vectorized dead cross detection
    
    Args:
        df: DataFrame with OHLCV and indicator data
        fast_ma_col: Fast moving average column name
        slow_ma_col: Slow moving average column name
        recent_n: Number of periods to look back
        
    Returns:
        True if dead cross found within recent_n periods, False otherwise
    """
    if df is None or len(df) < 2:
        return False
        
    # Check if columns exist
    if fast_ma_col not in df.columns or slow_ma_col not in df.columns:
        return False
        
    # Get the data for the specified period
    look_back = min(recent_n, len(df))
    recent_df = df.tail(look_back)
    
    if len(recent_df) < 2:
        return False
        
    # Check for dead cross: previous period fast >= slow, current period fast < slow
    # Need to compare consecutive valid rows, so iterate through dataframe
    for i in range(1, len(recent_df)):
        prev_row = recent_df.iloc[i-1]
        curr_row = recent_df.iloc[i]

        # Check if both values are valid (not NaN) for both periods
        if (pd.notna(prev_row[fast_ma_col]) and pd.notna(prev_row[slow_ma_col]) and
            pd.notna(curr_row[fast_ma_col]) and pd.notna(curr_row[slow_ma_col])):

            # Dead cross: previous fast >= slow, current fast < slow
            if prev_row[fast_ma_col] >= prev_row[slow_ma_col] and curr_row[fast_ma_col] < curr_row[slow_ma_col]:
                return True

    return False


def check_high_vs_open_vectorized(
    df: pd.DataFrame,
    min_increase_pct: float = 30.0,
    recent_n: int = 200
) -> bool:
    """
    Vectorized check for high vs open price increase within lookback periods
    
    Args:
        df: DataFrame with OHLCV data
        min_increase_pct: Minimum increase percentage required
        recent_n: Number of periods to look back
        
    Returns:
        True if condition is met, False otherwise
    """
    if df is None or len(df) < recent_n:
        return False
        
    # Check required columns
    required_cols = ['high', 'open', 'close']
    if not all(col in df.columns for col in required_cols):
        return False
        
    # Get recent data
    recent_df = df.tail(recent_n)
    
    high_arr = recent_df['high'].values
    open_arr = recent_df['open'].values
    close_arr = recent_df['close'].values
    
    # Remove NaN values
    valid_mask = ~(np.isnan(high_arr) | np.isnan(open_arr) | np.isnan(close_arr))
    if not np.any(valid_mask):
        return False
        
    high_clean = high_arr[valid_mask]
    open_clean = open_arr[valid_mask]
    close_clean = close_arr[valid_mask]
    
    # Avoid division by zero
    non_zero_mask = open_clean != 0
    if not np.any(non_zero_mask):
        return False
    
    # Calculate percentage increase from open to high
    pct_increases = ((high_clean[non_zero_mask] - open_clean[non_zero_mask]) / open_clean[non_zero_mask]) * 100
    
    # Check if any period meets the criteria and has positive close > open
    positive_candles = close_clean[non_zero_mask] > open_clean[non_zero_mask]
    
    return np.any((pct_increases >= min_increase_pct) & positive_candles)


def check_gap_within_threshold_vectorized(
    df: pd.DataFrame,
    col1: str,
    col2: str, 
    threshold_pct: float = 1.0,
    recent_n: int = 1
) -> bool:
    """
    Vectorized check if gap between two values is within threshold percentage
    
    Args:
        df: DataFrame with data
        col1: First column name
        col2: Second column name
        threshold_pct: Threshold percentage for gap
        recent_n: Number of periods to check
        
    Returns:
        True if gap is within threshold, False otherwise
    """
    if df is None or len(df) == 0:
        return False
        
    if col1 not in df.columns or col2 not in df.columns:
        return False
        
    recent_df = df.tail(recent_n)
    val1 = recent_df[col1].values
    val2 = recent_df[col2].values
    
    # Remove NaN values
    valid_mask = ~(np.isnan(val1) | np.isnan(val2))
    if not np.any(valid_mask):
        return False
        
    val1_clean = val1[valid_mask]
    val2_clean = val2[valid_mask]
    
    # Avoid division by zero
    non_zero_mask = val2_clean != 0
    if not np.any(non_zero_mask):
        return False
        
    # Calculate percentage gaps
    gap_pcts = np.abs((val1_clean[non_zero_mask] - val2_clean[non_zero_mask]) / val2_clean[non_zero_mask]) * 100
    
    return np.any(gap_pcts <= threshold_pct)


def check_value_comparison_vectorized(
    df: pd.DataFrame,
    col1: str,
    col2: str,
    operator: str = '>',
    recent_n: int = 1
) -> bool:
    """
    Vectorized value comparison with various operators
    
    Args:
        df: DataFrame with data
        col1: First column name
        col2: Second column name
        operator: Comparison operator ('>', '<', '>=', '<=', '==', '!=')
        recent_n: Number of periods to check
        
    Returns:
        True if comparison condition is met, False otherwise
    """
    if df is None or len(df) == 0:
        return False
        
    if col1 not in df.columns or col2 not in df.columns:
        return False
        
    recent_df = df.tail(recent_n)
    val1 = recent_df[col1].values
    val2 = recent_df[col2].values
    
    # Remove NaN values
    valid_mask = ~(np.isnan(val1) | np.isnan(val2))
    if not np.any(valid_mask):
        return False
        
    val1_clean = val1[valid_mask]
    val2_clean = val2[valid_mask]
    
    # Perform comparison
    if operator == '>':
        results = val1_clean > val2_clean
    elif operator == '<':
        results = val1_clean < val2_clean
    elif operator == '>=':
        results = val1_clean >= val2_clean
    elif operator == '<=':
        results = val1_clean <= val2_clean
    elif operator == '==':
        results = val1_clean == val2_clean
    elif operator == '!=':
        results = val1_clean != val2_clean
    else:
        return False
    
    return np.any(results)