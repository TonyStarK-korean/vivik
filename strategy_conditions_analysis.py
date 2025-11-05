# -*- coding: utf-8 -*-
"""
전략 조건 분석 - 확률 높은 조건 식별
"""

def analyze_strategy_conditions():
    """전략 조건들 분석"""
    print("=== 전체 전략 조건 분석 ===")
    
    strategies = {
        "전략A": {
            "name": "1분봉-3분봉-15분봉 조합전략",
            "conditions": [
                "1분봉 300봉 이내 MA80-MA480 골든크로스",
                "1분봉 MA80-MA480 이격도 1% 이상", 
                "1분봉 200봉 이내 BB200-BB480 골든크로스 OR 이격도 2% 이내",
                "1분봉 200봉 이내 MA20-MA80 데드크로스 and (ma20<ma80 or ma5<ma80)",
                "1분봉 매수타점(30봉이내 1봉전 MA5-MA20 골든크로스 AND 30봉이내 MA5<MA80 AND 10봉이내 MA1-MA5 골든크로스)",
                "일봉상 100봉 이내 시가대비 고가 15% 이상 캔들 1회 이상",
                "3분봉 통합조건: (MA80<MA480 and 40봉이내 BB80상한선 돌파) OR 300봉이내 MA80-MA480 골든크로스",
                "15분봉 MA80<MA480",
                "5분봉 SuperTrend(10-3) 진입 시그널"
            ],
            "difficulty": "극도로 높음 (9개 조건 AND)",
            "probability": "매우 낮음"
        },
        
        "전략B": {
            "name": "3분봉 2번째 전략",
            "conditions": [
                "일봉상 시가대비고가 50%이하",
                "120봉이내 BB80-BB600 골든크로스 OR 이격도 3%이내",
                "60봉이내 MA20-BB600 골든크로스 OR 현재 MA20>BB600",
                "MA20>BB600 상단선 and MA20-BB600 이격도 2%이상",
                "60봉이내 시가대비고가 3~20% 1회이상",
                "30봉이내 3연속양봉 AND 30봉이내 (MA5우하향 AND 1봉전MA5돌파)",
                "5분봉 SuperTrend(10-3) 진입 시그널"
            ],
            "difficulty": "높음 (7개 조건 AND)",
            "probability": "낮음"
        },
        
        "전략C": {
            "name": "3분봉 3번째 시세초입포착전략",
            "conditions": [
                "60봉이내 BB200상단선(표준편차2)-BB480상단선(표준편차1.5) 골든크로스",
                "20봉이내 MA5-MA20 데드크로스 AND 5봉이내 MA1-MA5 골든크로스",
                "5분봉 SuperTrend(10-3) 진입 시그널"
            ],
            "difficulty": "중간 (3개 조건 AND)",
            "probability": "중간"
        },
        
        "전략D": {
            "name": "5분봉 초입 초강력타점",
            "conditions": [
                "60봉이내 MA80-MA480 골든크로스",
                "200봉이내 (MA480이 10연속 이상 우하향 AND BB200상단선이 MA480을 골든크로스)",
                "5봉이내 MA5-MA20 골든크로스"
            ],
            "difficulty": "중간 (3개 조건 AND)",
            "probability": "중간"
        }
    }
    
    print("\n=== 전략별 조건 분석 ===")
    for strategy_key, strategy in strategies.items():
        print(f"\n{strategy_key}: {strategy['name']}")
        print(f"난이도: {strategy['difficulty']}")
        print(f"성공 확률: {strategy['probability']}")
        print("조건들:")
        for i, condition in enumerate(strategy['conditions'], 1):
            print(f"  {i}. {condition}")
    
    print("\n=== 문제점 분석 ===")
    
    problems = {
        "MA480 의존성": [
            "MA480 데이터 부족 (21/480개만 유효)",
            "대부분의 MA480 관련 조건이 실패",
            "영향받는 조건: 전략A(2개), 전략B(1개), 전략D(2개)"
        ],
        
        "과도한 조건 수": [
            "전략A: 9개 조건 AND (성공 확률 극히 낮음)",
            "전략B: 7개 조건 AND (성공 확률 낮음)",
            "모든 조건을 동시에 만족하기 어려움"
        ],
        
        "엄격한 수치 조건": [
            "일봉 15% 이상 급등 (현재 시장에서 드물음)",
            "시가대비고가 3~20% (변동성 낮은 시장에서 어려움)",
            "MA 이격도 조건들이 현재 시장 상황과 맞지 않음"
        ],
        
        "SuperTrend 의존성": [
            "모든 전략이 SuperTrend 조건 포함",
            "트렌드 전환이 없으면 모든 전략 실패",
            "현재 시장이 횡보하면 신호 없음"
        ]
    }
    
    for problem, details in problems.items():
        print(f"\n{problem}:")
        for detail in details:
            print(f"  - {detail}")
    
    print("\n=== 개선 방안 (확률 높은 조건 위주) ===")
    
    improvements = {
        "즉시 개선 (확률 중심)": [
            "전략D를 메인으로 활용 (3개 조건으로 가장 단순)",
            "전략C를 보조로 활용 (3개 조건으로 단순)",
            "전략A, B는 일시 비활성화 (조건 너무 많음)",
            "MA480 → MA200으로 대체",
            "일봉 15% → 10%로 완화",
            "시가대비고가 3~20% → 2~15%로 완화"
        ],
        
        "조건 단순화": [
            "전략당 최대 3-4개 조건으로 제한",
            "OR 조건 추가로 유연성 확보",
            "핵심 조건만 남기고 부가 조건 제거",
            "SuperTrend 조건을 선택적으로 적용"
        ],
        
        "데이터 문제 해결": [
            "MA480 대신 사용 가능한 MA200 활용",
            "일봉 데이터 요구량 축소",
            "WebSocket 실시간 데이터 우선 활용",
            "API 의존성 최소화"
        ]
    }
    
    for category, items in improvements.items():
        print(f"\n{category}:")
        for item in items:
            print(f"  - {item}")
    
    print("\n=== 추천 수정 사항 ===")
    print("1. 전략D (5분봉 초강력타점)만 활성화")
    print("2. MA480 → MA200 변경")  
    print("3. 일봉 조건 완화 (15% → 10%)")
    print("4. SuperTrend 조건 선택적 적용")
    print("5. 나머지 전략들은 시장 활성화 시까지 비활성화")

if __name__ == "__main__":
    analyze_strategy_conditions()