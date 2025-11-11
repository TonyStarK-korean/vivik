# -*- coding: utf-8 -*-
"""
🔥 DCA 시스템 간소화 패치
기존 DCA(1차/2차) 제거하고 불타기 시스템만 유지
손절선 고정: 초기 진입가 기준 -3%
"""

def disable_dca_messages(dca_manager):
    """DCA 관련 메시지 비활성화"""
    
    # 1. DCA 주문 누락 경고 메시지 비활성화
    original_check_dca = getattr(dca_manager, 'check_dca_triggers', None)
    if original_check_dca:
        def dummy_check_dca(symbol, current_price):
            """DCA 트리거 체크 비활성화"""
            return None
        dca_manager.check_dca_triggers = dummy_check_dca
    
    # 2. DCA 관련 로깅 비활성화
    original_log = dca_manager.logger.warning
    def filtered_log(message, *args, **kwargs):
        """DCA 관련 경고 메시지 필터링"""
        if any(keyword in str(message) for keyword in ['DCA 주문 누락', '1차 DCA', '2차 DCA', 'DCA order', 'DCA limit']):
            return  # DCA 관련 메시지는 무시
        return original_log(message, *args, **kwargs)
    
    dca_manager.logger.warning = filtered_log
    
    print("✅ DCA 관련 메시지 비활성화 완료")

def verify_stop_loss_logic(dca_manager):
    """손절 로직 확인 및 수정"""
    
    # 손절선 고정 설정 확인
    if hasattr(dca_manager, 'config'):
        dca_manager.config['stop_loss_fixed'] = -0.03  # 초기 진입가 기준 -3% 고정
        dca_manager.config['stop_loss_never_change'] = True
        print("✅ 손절선 고정 설정 업데이트: 초기 진입가 기준 -3%")
    
    # 기존 stop loss 체크 함수 오버라이드
    def check_fixed_stop_loss(position, current_price):
        """초기 진입가 기준 -3% 고정 손절 체크"""
        if not position or not hasattr(position, 'initial_entry_price'):
            return None
            
        # 초기 진입가 기준 수익률 계산
        current_profit = (current_price - position.initial_entry_price) / position.initial_entry_price
        
        # -3% 손절선 체크
        if current_profit <= -0.03:
            return {
                'trigger': True,
                'type': 'fixed_stop_loss',
                'profit_pct': current_profit * 100,
                'stop_loss_pct': -3.0,
                'initial_price': position.initial_entry_price,
                'current_price': current_price,
                'message': f"손절선 고정 트리거: 초기진입가 ${position.initial_entry_price:.6f} 대비 {current_profit*100:.2f}%"
            }
        
        return None
    
    # 메서드 교체
    dca_manager.check_fixed_stop_loss = check_fixed_stop_loss
    print("✅ 손절 로직 업데이트: 초기 진입가 기준 -3% 고정")

def apply_pyramid_only_system(dca_manager):
    """불타기 시스템만 활성화"""
    
    # DCA 관련 설정 비활성화
    if hasattr(dca_manager, 'config'):
        dca_manager.config['dca_enabled'] = False
        dca_manager.config['pyramid_enabled'] = True
        
        # 기존 DCA 트리거 비활성화
        dca_manager.config['first_dca_trigger'] = 999.0   # 실행되지 않도록
        dca_manager.config['second_dca_trigger'] = 999.0  # 실행되지 않도록
        
        print("✅ DCA 시스템 비활성화, 불타기 시스템만 활성화")

if __name__ == "__main__":
    print("🔧 DCA 시스템 간소화 패치 스크립트")
    print("이 패치는 다음을 수행합니다:")
    print("1. DCA 주문 누락 경고 메시지 제거")
    print("2. 손절선 고정: 초기 진입가 기준 -3%")  
    print("3. 불타기 시스템만 활성화")
    print("4. 기존 DCA(1차/2차) 시스템 비활성화")