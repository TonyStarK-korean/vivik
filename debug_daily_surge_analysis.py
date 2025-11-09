#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daily Surge Condition Debug Analysis Tool

1% daily surge가 차단되는 이유를 분석하는 디버깅 도구
현실적으로 1% 일봉 급등이 60일 동안 한 번도 없는 것은 데이터 이슈 가능성 높음
"""

import ccxt
import pandas as pd
import numpy as np
import datetime
import json
from binance_config import *

class DailySurgeDebugger:
    def __init__(self):
        """디버거 초기화"""
        print("🔍 Daily Surge Condition Debugger 초기화 중...")
        
        try:
            self.exchange = ccxt.binance({
                'apiKey': API_KEY,
                'secret': SECRET_KEY,
                'timeout': 30000,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future',  # 선물 거래
                    'recvWindow': 60000,
                },
                'sandbox': False,  # 실제 거래소 사용
            })
            print("✅ Binance 연결 성공")
        except Exception as e:
            print(f"❌ Binance 연결 실패: {e}")
            self.exchange = None
    
    def get_daily_data(self, symbol, days=65):
        """일봉 데이터 조회 (1% 급등 분석용)"""
        try:
            # 선물 심볼로 변환 (BTCUSDT → BTC/USDT:USDT)
            if '/' not in symbol:
                formatted_symbol = f"{symbol[:-4]}/{symbol[-4:]}:USDT"
            else:
                formatted_symbol = symbol
            
            print(f"🔍 {formatted_symbol} 일봉 데이터 조회 중... ({days}일간)")
            
            # 현재 시간에서 days만큼 이전부터 조회
            since = int((datetime.datetime.now() - datetime.timedelta(days=days)).timestamp()) * 1000
            
            ohlcv = self.exchange.fetch_ohlcv(formatted_symbol, '1d', since=since, limit=days)
            
            if not ohlcv:
                print(f"❌ {formatted_symbol}: 데이터 없음")
                return None
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            print(f"✅ {formatted_symbol}: {len(df)}개 일봉 데이터 조회 성공")
            return df
            
        except Exception as e:
            print(f"❌ {formatted_symbol}: 데이터 조회 실패 - {e}")
            return None
    
    def analyze_daily_surge_reality_check(self, symbol):
        """1% 일봉 급등 현실성 체크 (60일간 급등 분석)"""
        print(f"\n{'='*60}")
        print(f"🚀 {symbol} - 1% 일봉 급등 현실성 분석")
        print(f"{'='*60}")
        
        df = self.get_daily_data(symbol, 65)
        if df is None:
            return None
        
        # 최근 60일 분석
        recent_60 = df.tail(60)
        
        surge_analysis = {
            'symbol': symbol,
            'total_days': len(recent_60),
            'data_quality': {},
            'surge_stats': {},
            'surge_details': []
        }
        
        # 1. 데이터 품질 체크
        print(f"\n📊 데이터 품질 분석:")
        
        # NaN 체크
        nan_count = recent_60[['open', 'high', 'low', 'close']].isnull().sum().sum()
        print(f"- NaN 값: {nan_count}개")
        surge_analysis['data_quality']['nan_count'] = int(nan_count)
        
        # 0 또는 음수 체크
        zero_negative = (recent_60[['open', 'high', 'low', 'close']] <= 0).sum().sum()
        print(f"- 0/음수 값: {zero_negative}개")
        surge_analysis['data_quality']['zero_negative'] = int(zero_negative)
        
        # 가격 범위 체크
        price_stats = {
            'open_range': [float(recent_60['open'].min()), float(recent_60['open'].max())],
            'high_range': [float(recent_60['high'].min()), float(recent_60['high'].max())],
            'low_range': [float(recent_60['low'].min()), float(recent_60['low'].max())],
            'close_range': [float(recent_60['close'].min()), float(recent_60['close'].max())]
        }
        print(f"- 시가 범위: ${price_stats['open_range'][0]:.4f} ~ ${price_stats['open_range'][1]:.4f}")
        print(f"- 고가 범위: ${price_stats['high_range'][0]:.4f} ~ ${price_stats['high_range'][1]:.4f}")
        surge_analysis['data_quality']['price_stats'] = price_stats
        
        # 2. 급등 분석
        print(f"\n🚀 급등 패턴 분석:")
        
        surges = []
        max_surge = 0
        surge_days = 0
        
        for i, row in recent_60.iterrows():
            open_price = row['open']
            high_price = row['high']
            date_str = row['datetime'].strftime('%Y-%m-%d')
            
            if open_price > 0:
                surge_pct = ((high_price - open_price) / open_price) * 100
                max_surge = max(max_surge, surge_pct)
                
                surge_detail = {
                    'date': date_str,
                    'open': float(open_price),
                    'high': float(high_price),
                    'surge_pct': float(surge_pct)
                }
                surges.append(surge_detail)
                
                if surge_pct >= 1.0:
                    surge_days += 1
                    print(f"  ✅ {date_str}: {surge_pct:.2f}% (O:{open_price:.4f}, H:{high_price:.4f})")
        
        # 급등 통계
        surge_analysis['surge_stats'] = {
            'max_surge': float(max_surge),
            'surge_days_1pct': surge_days,
            'surge_days_2pct': len([s for s in surges if s['surge_pct'] >= 2.0]),
            'surge_days_3pct': len([s for s in surges if s['surge_pct'] >= 3.0]),
            'surge_days_5pct': len([s for s in surges if s['surge_pct'] >= 5.0]),
            'avg_surge': float(np.mean([s['surge_pct'] for s in surges])),
            'median_surge': float(np.median([s['surge_pct'] for s in surges]))
        }
        surge_analysis['surge_details'] = sorted(surges, key=lambda x: x['surge_pct'], reverse=True)[:20]  # Top 20
        
        print(f"\n📈 급등 통계:")
        print(f"- 최대 급등: {surge_analysis['surge_stats']['max_surge']:.2f}%")
        print(f"- 1%+ 급등일: {surge_analysis['surge_stats']['surge_days_1pct']}일 / {len(recent_60)}일")
        print(f"- 2%+ 급등일: {surge_analysis['surge_stats']['surge_days_2pct']}일")
        print(f"- 3%+ 급등일: {surge_analysis['surge_stats']['surge_days_3pct']}일")
        print(f"- 5%+ 급등일: {surge_analysis['surge_stats']['surge_days_5pct']}일")
        print(f"- 평균 급등: {surge_analysis['surge_stats']['avg_surge']:.2f}%")
        print(f"- 중간값 급등: {surge_analysis['surge_stats']['median_surge']:.2f}%")
        
        # 3. 현실성 판정
        print(f"\n🤔 현실성 판정:")
        if surge_analysis['surge_stats']['surge_days_1pct'] == 0:
            if surge_analysis['surge_stats']['max_surge'] < 0.1:
                print(f"❌ 극심한 데이터 이슈: 최대 급등 {surge_analysis['surge_stats']['max_surge']:.3f}%")
                print("   → OHLC 데이터가 올바르지 않거나 극도로 안정적인 자산")
            else:
                print(f"⚠️ 특이한 패턴: 최대 급등 {surge_analysis['surge_stats']['max_surge']:.2f}%")
                print("   → 하락장이거나 극도로 안정적인 기간")
        else:
            print(f"✅ 정상적인 변동성: {surge_analysis['surge_stats']['surge_days_1pct']}일 1%+ 급등")
        
        return surge_analysis
    
    def analyze_multiple_symbols(self, symbols):
        """여러 심볼 대량 분석"""
        print(f"\n{'='*80}")
        print(f"🔍 {len(symbols)}개 심볼 1% 급등 조건 대량 분석")
        print(f"{'='*80}")
        
        results = []
        problem_symbols = []
        
        for i, symbol in enumerate(symbols, 1):
            print(f"\n[{i}/{len(symbols)}] 분석 중: {symbol}")
            
            try:
                analysis = self.analyze_daily_surge_reality_check(symbol)
                if analysis:
                    results.append(analysis)
                    
                    # 문제 심볼 식별
                    if analysis['surge_stats']['surge_days_1pct'] == 0:
                        problem_symbols.append({
                            'symbol': symbol,
                            'max_surge': analysis['surge_stats']['max_surge'],
                            'avg_surge': analysis['surge_stats']['avg_surge']
                        })
                        
            except Exception as e:
                print(f"❌ {symbol} 분석 실패: {e}")
        
        # 종합 리포트
        print(f"\n{'='*80}")
        print(f"📊 종합 분석 리포트")
        print(f"{'='*80}")
        
        total_analyzed = len(results)
        problem_count = len(problem_symbols)
        
        print(f"- 총 분석 심볼: {total_analyzed}개")
        print(f"- 1% 급등 없는 심볼: {problem_count}개 ({problem_count/total_analyzed*100:.1f}%)")
        
        if problem_symbols:
            print(f"\n🚨 문제 심볼 리스트:")
            for prob in problem_symbols:
                print(f"  - {prob['symbol']}: 최대 {prob['max_surge']:.2f}%, 평균 {prob['avg_surge']:.2f}%")
        
        # JSON 저장
        report_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'total_analyzed': total_analyzed,
            'problem_count': problem_count,
            'problem_rate': problem_count/total_analyzed*100 if total_analyzed > 0 else 0,
            'detailed_results': results,
            'problem_symbols': problem_symbols
        }
        
        with open('daily_surge_analysis_report.json', 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 상세 리포트 저장: daily_surge_analysis_report.json")
        
        return results, problem_symbols

if __name__ == "__main__":
    # 테스트 심볼들 (문제가 될 가능성이 있는 심볼들)
    test_symbols = [
        'BTCUSDT',    # 메이저 코인
        'ETHUSDT',    # 메이저 코인
        'ADAUSDT',    # 알트코인
        'SOLUSDT',    # 핫한 코인
        'DOGEUSDT',   # 밈코인
        'XRPUSDT',    # 전통 알트
        'BNBUSDT',    # 거래소 코인
        'AVAXUSDT',   # L1 코인
        'LINKUSDT',   # DeFi 코인
        'DOTUSDT',    # 파라체인
    ]
    
    debugger = DailySurgeDebugger()
    
    if debugger.exchange is None:
        print("❌ 거래소 연결 실패 - 프로그램 종료")
        exit(1)
    
    # 단일 심볼 상세 분석 (예시)
    print("🔍 단일 심볼 상세 분석 예시:")
    debugger.analyze_daily_surge_reality_check('BTCUSDT')
    
    # 대량 분석
    print("\n" + "="*80)
    print("🔍 대량 심볼 분석 시작...")
    results, problems = debugger.analyze_multiple_symbols(test_symbols)
    
    print(f"\n✅ 분석 완료!")
    print(f"📊 총 {len(results)}개 심볼 분석, {len(problems)}개 문제 심볼 발견")