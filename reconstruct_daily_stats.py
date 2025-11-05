#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
일일 통계 재구성 스크립트
- DCA 포지션 파일과 실제 거래 내역을 기반으로 통계 재구성
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import os
from datetime import datetime, timezone, timedelta


def get_korea_time():
    """한국 시간 반환"""
    return datetime.now(timezone.utc) + timedelta(hours=9)


def load_dca_positions():
    """DCA 포지션 파일 로드"""
    try:
        with open('dca_positions.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"DCA 포지션 파일 로드 실패: {e}")
        return {}


def load_daily_stats():
    """일일 통계 파일 로드"""
    try:
        with open('daily_stats.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"일일 통계 파일 로드 실패: {e}")
        return {}


def save_daily_stats(stats):
    """일일 통계 파일 저장"""
    try:
        with open('daily_stats.json', 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=4, ensure_ascii=False)
        print("✅ 일일 통계 파일 저장 완료")
    except Exception as e:
        print(f"❌ 일일 통계 파일 저장 실패: {e}")


def reconstruct_stats():
    """통계 재구성 메인 함수"""
    print("=" * 60)
    print("📊 일일 통계 재구성 시작")
    print("=" * 60)
    
    # 현재 날짜 (KST 오전 9시 기준)
    kst_now = get_korea_time()
    if kst_now.hour < 9:
        current_trading_day = (kst_now - timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        current_trading_day = kst_now.strftime('%Y-%m-%d')
    
    print(f"거래일: {current_trading_day}")
    
    # DCA 포지션 로드
    dca_positions = load_dca_positions()
    print(f"DCA 포지션 수: {len(dca_positions)}개")
    
    # 오늘 청산된 포지션 찾기
    closed_today = []
    active_positions = []
    
    for symbol, position in dca_positions.items():
        # 포지션이 청산된 경우
        if position.get('current_stage') == 'closed' and not position.get('is_active', True):
            # updated_at 확인
            if position.get('updated_at'):
                try:
                    updated_str = position['updated_at']
                    if '+09:00' in updated_str:
                        updated_date = datetime.fromisoformat(updated_str.replace('+09:00', '')).date()
                    else:
                        updated_date = datetime.fromisoformat(updated_str.replace('Z', '+00:00'))
                        updated_date = (updated_date + timedelta(hours=9)).date()
                    
                    if updated_date == datetime.strptime(current_trading_day, '%Y-%m-%d').date():
                        closed_today.append((symbol, position))
                except Exception as e:
                    print(f"  ⚠️ {symbol} 날짜 파싱 실패: {e}")
        elif position.get('is_active', False):
            active_positions.append((symbol, position))
    
    print(f"\n📈 오늘 청산된 포지션: {len(closed_today)}개")
    print(f"📊 현재 활성 포지션: {len(active_positions)}개")
    
    # 통계 계산
    total_trades = len(closed_today)
    wins = 0
    losses = 0
    total_pnl = 0.0
    total_entry_amount = 0.0
    
    print("\n[청산된 포지션 상세]")
    for symbol, position in closed_today:
        # 수익률 계산
        max_profit_pct = position.get('max_profit_pct', 0.0)
        total_amount = position.get('total_amount_usdt', 0.0)
        
        # 수익금 계산
        profit_amount = total_amount * max_profit_pct
        total_pnl += profit_amount
        total_entry_amount += total_amount
        
        # 수익/손실 분류
        if max_profit_pct > 0:
            wins += 1
            result = "수익"
        else:
            losses += 1
            result = "손실"
        
        print(f"  {symbol}: {result} {max_profit_pct*100:+.2f}% (${profit_amount:+.2f}) - 투자금: ${total_amount:.2f}")
    
    # 승률 계산
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    
    print(f"\n📊 통계 요약:")
    print(f"  총 거래: {total_trades}회")
    print(f"  수익: {wins}회 | 손실: {losses}회")
    print(f"  승률: {win_rate:.1f}%")
    print(f"  총 손익: ${total_pnl:+.2f}")
    print(f"  총 투자금: ${total_entry_amount:.2f}")
    
    # Day ROE 계산
    day_roe = (total_pnl / total_entry_amount * 100) if total_entry_amount > 0 else 0.0
    print(f"  Day ROE: {day_roe:+.2f}%")
    
    # 기존 통계 파일 업데이트
    daily_stats = load_daily_stats()
    
    # 오늘 통계 업데이트
    daily_stats[current_trading_day] = {
        'date': current_trading_day,
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'total_entry_amount': total_entry_amount,
        'day_roe': day_roe,
        'trades_detail': []
    }
    
    # 상세 거래 내역 추가
    for symbol, position in closed_today:
        max_profit_pct = position.get('max_profit_pct', 0.0)
        total_amount = position.get('total_amount_usdt', 0.0)
        profit_amount = total_amount * max_profit_pct
        
        daily_stats[current_trading_day]['trades_detail'].append({
            'symbol': symbol,
            'profit_pct': max_profit_pct * 100,
            'profit_amount': profit_amount,
            'result': '수익' if max_profit_pct > 0 else '손실',
            'amount': total_amount
        })
    
    # 파일 저장
    save_daily_stats(daily_stats)
    
    print("\n✅ 통계 재구성 완료!")
    
    # 현재 활성 포지션의 미실현 손익 계산
    if active_positions:
        print("\n[현재 활성 포지션 미실현 손익]")
        total_unrealized_pnl = 0.0
        total_active_investment = 0.0
        
        for symbol, position in active_positions:
            current_profit_pct = position.get('current_profit_pct', 0.0)
            total_amount = position.get('total_amount_usdt', 0.0)
            unrealized_pnl = total_amount * current_profit_pct
            
            total_unrealized_pnl += unrealized_pnl
            total_active_investment += total_amount
            
            print(f"  {symbol}: {current_profit_pct*100:+.2f}% (${unrealized_pnl:+.2f}) - 투자금: ${total_amount:.2f}")
        
        print(f"\n총 미실현 손익: ${total_unrealized_pnl:+.2f}")
        print(f"총 활성 투자금: ${total_active_investment:.2f}")


if __name__ == '__main__':
    reconstruct_stats()