#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
빈 결과 분석 스크립트 - 왜 모든 카테고리가 비어있는지 분석
"""

import os
import sys

# 스크립트 디렉토리 추가
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

def analyze_current_market_conditions():
    """현재 시장 상황 분석"""
    print("=== 빈 결과 원인 분석 ===")
    print()
    
    print("📊 현재 상황 요약:")
    print("- 티커 수집: 246개 심볼 성공")
    print("- 하이브리드 처리: WebSocket(134) + 캐시(0) + API(850)")
    print("- 모든 분류 카테고리가 비어있음")
    print()
    
    print("🔍 가능한 원인들:")
    print()
    
    print("1. 📈 시장 상황 요인:")
    print("   - 현재 시간대에 급등 조건을 만족하는 코인이 없음")
    print("   - 전체적으로 횡보 또는 하락장 상황")
    print("   - 변동성이 낮은 시간대 (아시아 시간대 등)")
    print()
    
    print("2. 🎯 전략 조건 엄격성:")
    print("   전략C (3분봉 시세 초입 포착):")
    print("   - 조건1: 200봉이내 BB200상단선-BB480상단선 골든크로스")
    print("   - 조건2: MA5-MA20 데드크로스 후 MA1-MA5 골든크로스")
    print("   - 조건3: 5분봉 SuperTrend(10-3) 진입 시그널")
    print()
    
    print("   전략D (5분봉 초입 초강력 타점):")
    print("   - 조건1: 15분봉 MA80<MA480")
    print("   - 조건2: 5분봉 SuperTrend(10-3) 진입 시그널")
    print("   - 조건3: 60봉이내 MA80-MA480 골든크로스")
    print("   - 조건4: 700봉이내 복합 조건")
    print("   - 조건5: 20봉이내 MA5-MA20 골든크로스")
    print()
    
    print("3. 📊 데이터 품질 이슈:")
    print("   - WebSocket 데이터 부족 (실시간 스트림 시작 직후)")
    print("   - MA/BB 지표 계산을 위한 충분한 히스토리 부족")
    print("   - 일부 타임프레임 데이터 누락")
    print()
    
    print("4. ⚙️ 기술적 이슈:")
    print("   - 심볼 형식 변환 문제")
    print("   - 조건 체크 로직 오류")
    print("   - 지표 계산 오류")
    print()
    
    print("💡 권장 해결 방안:")
    print()
    
    print("1. 📉 조건 완화 테스트:")
    print("   - 임시로 조건 수를 줄여서 테스트")
    print("   - 개별 조건별 통과율 확인")
    print("   - 가장 제한적인 조건 식별")
    print()
    
    print("2. 🕒 시간대별 분석:")
    print("   - 다른 시간대에 테스트 (미국/유럽 시장 시간)")
    print("   - 변동성이 높은 시간대 확인")
    print("   - 과거 성공 사례 시간대 분석")
    print()
    
    print("3. 📊 개별 심볼 상세 분석:")
    print("   - 인기 코인 3-5개 수동 분석")
    print("   - 각 조건별 통과/실패 이유 확인")
    print("   - 임계값 조정 가능성 검토")
    print()
    
    print("4. 🔧 시스템 검증:")
    print("   - WebSocket 데이터 품질 확인")
    print("   - 지표 계산 정확성 검증")
    print("   - 과거 성공 사례 재현 테스트")
    print()

def suggest_immediate_actions():
    """즉시 실행 가능한 액션 제안"""
    print("⚡ 즉시 실행 권장 액션:")
    print()
    
    print("1. 🧪 조건 완화 테스트:")
    print("   - 전략C에서 조건 1개만 적용해서 테스트")
    print("   - 전략D에서 조건 2-3개만 적용해서 테스트")
    print("   - SuperTrend 조건만으로 필터링 테스트")
    print()
    
    print("2. 📈 인기 코인 수동 분석:")
    print("   - BTC, ETH, BNB 같은 주요 코인 개별 분석")
    print("   - 각 조건별 상세 로그 확인")
    print("   - 어떤 조건에서 막히는지 파악")
    print()
    
    print("3. 🕐 시간대 고려:")
    print("   - 현재는 한국 시간 기준 저녁 시간대")
    print("   - 미국 시장 오픈 시간대(밤 11시-새벽 6시) 재테스트")
    print("   - 유럽 시장 시간대(오후 4시-밤 12시) 테스트")
    print()
    
    print("4. 📊 과거 데이터 검증:")
    print("   - 과거 성공했던 시점의 데이터로 재테스트")
    print("   - 전략 조건이 실제로 작동하는지 백테스트")
    print()

def market_timing_analysis():
    """시장 타이밍 분석"""
    from datetime import datetime
    
    current_time = datetime.now()
    hour = current_time.hour
    
    print("🕐 현재 시간대 분석:")
    print(f"현재 시간: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    if 0 <= hour < 6:
        market_status = "미국 장 마감 후 ~ 아시아 장 오픈 전 (저변동성)"
    elif 6 <= hour < 9:
        market_status = "아시아 장 오픈 초기 (중간 변동성)"
    elif 9 <= hour < 15:
        market_status = "아시아 장 활성 시간 (중간 변동성)"
    elif 15 <= hour < 18:
        market_status = "아시아 장 마감 ~ 유럽 장 오픈 (중간 변동성)"
    elif 18 <= hour < 23:
        market_status = "유럽 장 활성 시간 (높은 변동성)"
    else:
        market_status = "미국 장 오픈 시간 (최고 변동성)"
    
    print(f"시장 상태: {market_status}")
    print()
    
    if "저변동성" in market_status or "중간 변동성" in market_status:
        print("💡 추천: 급등 조건을 만족하는 코인이 적을 수 있는 시간대입니다.")
        print("   - 유럽/미국 시장 시간대에 재테스트 권장")
        print("   - 또는 조건을 일시적으로 완화하여 테스트")
    else:
        print("💡 현재는 변동성이 높은 시간대입니다.")
        print("   - 시스템 조건이 너무 엄격할 가능성")
        print("   - 개별 조건 분석 필요")

def main():
    print("빈 결과 원인 분석 및 해결방안")
    print("=" * 50)
    print()
    
    analyze_current_market_conditions()
    print()
    market_timing_analysis()
    print()
    suggest_immediate_actions()
    print()
    
    print("🎯 결론:")
    print("현재 모든 카테고리가 비어있는 것은 정상적인 상황일 수 있습니다.")
    print("전략 조건이 매우 엄격하게 설계되어 있어, 시장 상황에 따라")
    print("조건을 만족하는 코인이 없을 수 있습니다.")
    print()
    print("권장사항:")
    print("1. 다른 시간대에 재테스트")
    print("2. 조건 완화하여 디버깅")
    print("3. 개별 조건별 통과율 분석")
    print("4. 과거 성공 사례와 비교 분석")

if __name__ == "__main__":
    main()