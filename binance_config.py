# 바이낸스 API 설정
class BinanceConfig:
    # API 키 설정
    API_KEY = "Ljyd55VX6OZEY3pdqM2KlJk8g5cHmRDmOs7HBwzPfby4Njfg7Vs24exv3nZrw1m3"
    SECRET_KEY = "Jl1hPQYfXcYfVijELwbejgHID9tLq3IXmtSkWxxtMLhtni8XvAJU1oV0ouREXbgE"
    SECRET = SECRET_KEY  # 호환성을 위한 별칭
    
    # 거래 설정
    LEVERAGE = 5  # 레버리지 (기본 5배)
    POSITION_SIZE_PCT = 5  # 포지션 크기 비율 (5%)
    
    # 안전 설정
    TESTNET = False  # True: 테스트넷, False: 실제 거래
    USE_TESTNET = TESTNET  # 호환성을 위한 별칭
    
    # API 제한 설정
    ENABLE_RATE_LIMIT = True
    
    @classmethod
    def get_config(cls):
        """API 설정 딕셔너리 반환"""
        return {
            'apiKey': cls.API_KEY,
            'secret': cls.SECRET_KEY,
            'sandbox': cls.TESTNET,
            'enableRateLimit': cls.ENABLE_RATE_LIMIT,
            'options': {
                'defaultType': 'swap'  # 선물 거래
            }
        }
    
    @classmethod
    def get_api_credentials(cls):
        """API 자격증명 반환"""
        return {
            'apiKey': cls.API_KEY,
            'secret': cls.SECRET_KEY,
            'sandbox': cls.TESTNET,
            'enableRateLimit': cls.ENABLE_RATE_LIMIT
        }
    
    @classmethod
    def validate_config(cls):
        """API 설정 유효성 검증"""
        try:
            # API 키와 시크릿 키가 설정되어 있는지 확인
            if not cls.API_KEY or not cls.SECRET_KEY:
                return False, "API 키 또는 시크릿 키가 설정되지 않았습니다"
            
            # 키 길이 검증 (바이낸스 API 키는 보통 64자)
            if len(cls.API_KEY) < 10 or len(cls.SECRET_KEY) < 10:
                return False, "API 키 또는 시크릿 키가 너무 짧습니다"
            
            return True, "API 설정이 유효합니다"
            
        except Exception as e:
            return False, f"설정 검증 중 오류: {e}"