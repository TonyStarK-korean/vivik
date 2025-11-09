# -*- coding: utf-8 -*-
"""
텔레그램 봇 알림 시스템
진입 알림, 계좌 상태 보고 등 기능 제공
"""

import requests
import json
import time
import os
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

class TelegramBot:
    def __init__(self, bot_token: str = None, chat_id: str = None):
        """
        텔레그램 봇 초기화

        Args:
            bot_token: 텔레그램 봇 토큰 (BotFather에서 생성)
            chat_id: 메시지를 받을 채팅방 ID
        """
        # 실제 설정 값 사용, 플레이스홀더 값 검증
        self.bot_token = bot_token or "YOUR_BOT_TOKEN_HERE"
        self.chat_id = chat_id or "YOUR_CHAT_ID_HERE"
        
        # 플레이스홀더 값 검증
        if self.bot_token == "YOUR_BOT_TOKEN_HERE" or self.chat_id == "YOUR_CHAT_ID_HERE":
            print("[WARN] 텔레그램 설정이 플레이스홀더 값입니다. telegram_config.py 설정을 확인하세요.")

        # 텔레그램 API URL
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

        # 마지막 알림 시간 추적 (스팸 방지)
        self.last_alert_time = {}

        # 📊 메시지 히스토리 저장 설정
        self.message_log_dir = Path("data/telegram_history")
        self.message_log_dir.mkdir(parents=True, exist_ok=True)
        self.message_log_file = self.message_log_dir / f"messages_{datetime.now().strftime('%Y%m%d')}.jsonl"

        print(f"[Telegram Bot] 초기화 완료")
        print(f"  봇 토큰: {self.bot_token[:10]}...")
        print(f"  채팅 ID: {self.chat_id}")
        print(f"  메시지 로그: {self.message_log_file}")
    
    def send_message(self, message: str, parse_mode: str = "HTML", event_type: str = None, symbol: str = None, metadata: dict = None) -> bool:
        """
        텔레그램 메시지 전송 (히스토리 저장 포함)

        Args:
            message: 전송할 메시지
            parse_mode: 메시지 파싱 모드 (HTML, Markdown)
            event_type: 이벤트 타입 (entry, dca, exit, position_alert 등)
            symbol: 심볼명
            metadata: 추가 메타데이터

        Returns:
            bool: 전송 성공 여부
        """
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }

            # 즉시 전송을 위한 설정
            response = requests.post(url, json=payload, timeout=5)

            if response.status_code == 200:
                # 📊 메시지 히스토리 저장
                self._log_message(message, event_type, symbol, metadata)
                return True
            else:
                # 에러는 로그 파일에만 기록 (콘솔 출력 제거)
                import logging
                logging.error(f"Telegram API Error {response.status_code}: {response.text}")
                return False

        except Exception as e:
            # 에러는 로그 파일에만 기록 (콘솔 출력 제거)
            import logging
            logging.error(f"Telegram send error: {e}")
            return False

    def _log_message(self, message: str, event_type: str = None, symbol: str = None, metadata: dict = None):
        """메시지 히스토리를 JSONL 형식으로 저장"""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type or "general",
                "symbol": symbol,
                "message": message,
                "metadata": metadata or {}
            }

            # JSONL 형식으로 추가 (한 줄에 하나의 JSON)
            with open(self.message_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

        except Exception as e:
            print(f"[Telegram] 메시지 로그 저장 실패: {e}")
    
    def send_entry_alert(self, symbol: str, entry_price: float, position_amount: float, 
                        leverage: int, total_value: float, conditions: List[str]) -> bool:
        """
        진입 알림 메시지 전송
        
        Args:
            symbol: 심볼명
            entry_price: 진입가
            position_amount: 포지션 크기 (USDT)
            leverage: 레버리지
            total_value: 총 포지션 가치
            conditions: 충족된 조건들
            
        Returns:
            bool: 전송 성공 여부
        """
        # 스팸 방지: 같은 심볼 5분 이내 중복 알림 차단
        now = time.time()
        if symbol in self.last_alert_time:
            if now - self.last_alert_time[symbol] < 300:  # 5분
                return False
        
        self.last_alert_time[symbol] = now
        
        # 진입 시간
        entry_time = datetime.now().strftime("%H:%M:%S")
        
        # 조건 문자열 생성
        conditions_str = ", ".join(conditions)
        
        message = f"""
🚀 <b>[자동 진입 알림]</b>

📊 <b>심볼:</b> {symbol}/USDT:USDT
💰 <b>진입가:</b> ${entry_price:.4f}
📈 <b>포지션:</b> ${position_amount:.2f} ({leverage}x)
💎 <b>총 가치:</b> ${total_value:,.2f}
⏰ <b>진입 시간:</b> {entry_time}

✅ <b>충족 조건:</b>
{conditions_str}

🎯 <b>전략:</b> ULTRA_SURGE_1M_STRATEGY
📱 <b>상태:</b> 포지션 진입 완료
        """
        
        return self.send_message(message.strip())
    
    def send_account_status(self, total_balance: float, used_balance: float, 
                          free_balance: float, positions: List[Dict], 
                          total_pnl: float, scan_count: int = 0) -> bool:
        """
        계좌 상태 보고 메시지 전송
        
        Args:
            total_balance: 총 잔고
            used_balance: 사용 중 잔고
            free_balance: 가용 잔고
            positions: 포지션 리스트
            total_pnl: 총 손익
            scan_count: 스캔된 심볼 수
            
        Returns:
            bool: 전송 성공 여부
        """
        current_time = datetime.now().strftime("%H:%M:%S")
        
        # 포지션 정보 생성
        if positions:
            position_lines = []
            for pos in positions:
                symbol = pos.get('symbol', 'N/A')
                side = pos.get('side', 'N/A')
                pnl_pct = pos.get('pnl_pct', 0)
                pnl_usd = pos.get('pnl_usd', 0)
                
                pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"
                position_lines.append(f"  {pnl_emoji} {symbol}: {side} {pnl_pct:+.1f}% (${pnl_usd:+.2f})")
            
            positions_str = "\n".join(position_lines)
        else:
            positions_str = "  📭 포지션 없음"
        
        # 총 손익 이모지
        pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
        
        message = f"""
📊 <b>[계좌 상태 보고]</b>

💰 <b>잔고 정보:</b>
  • 총 잔고: ${total_balance:,.2f}
  • 사용 중: ${used_balance:,.2f}
  • 가용 잔고: ${free_balance:,.2f}

📈 <b>포지션 ({len(positions)}개):</b>
{positions_str}

{pnl_emoji} <b>총 손익:</b> ${total_pnl:+.2f}

📡 <b>스캔 상태:</b>
  • 스캔된 심볼: {scan_count}개
  • 보고 시간: {current_time}

🤖 <b>전략:</b> ULTRA_SURGE_1M_STRATEGY
        """
        
        return self.send_message(message.strip())
    
    def send_scan_summary(self, scan_results: Dict) -> bool:
        """
        스캔 결과 요약 전송
        
        Args:
            scan_results: 스캔 결과 딕셔너리
                - primary_count: 1차 스캔 통과 수
                - strong_count: 진입임박 수
                - partial_count: 일부충족 수
                - strong_symbols: 진입임박 심볼들
                
        Returns:
            bool: 전송 성공 여부
        """
        current_time = datetime.now().strftime("%H:%M:%S")
        
        primary_count = scan_results.get('primary_count', 0)
        strong_count = scan_results.get('strong_count', 0)
        partial_count = scan_results.get('partial_count', 0)
        strong_symbols = scan_results.get('strong_symbols', [])
        
        message = f"""
🔍 <b>[스캔 결과 요약]</b>

📈 <b>1차 스캔:</b> {primary_count}개 통과
🎯 <b>진입임박:</b> {strong_count}개
⚠️ <b>일부충족:</b> {partial_count}개

📊 <b>진입임박 심볼:</b>
"""
        
        if strong_symbols:
            for symbol_info in strong_symbols[:5]:  # 최대 5개만 표시
                symbol = symbol_info.get('symbol', 'N/A')
                conditions = symbol_info.get('conditions', 0)
                message += f"  🎯 {symbol}: {conditions}/6 조건\n"
            
            if len(strong_symbols) > 5:
                message += f"  ... 외 {len(strong_symbols) - 5}개\n"
        else:
            message += "  📭 없음\n"
        
        message += f"""
⏰ <b>스캔 시간:</b> {current_time}
🤖 <b>전략:</b> ULTRA_SURGE_1M_STRATEGY
        """
        
        return self.send_message(message.strip())
    
    def send_error_alert(self, error_message: str, context: str = "") -> bool:
        """
        오류 알림 전송
        
        Args:
            error_message: 오류 메시지
            context: 오류 발생 컨텍스트
            
        Returns:
            bool: 전송 성공 여부
        """
        current_time = datetime.now().strftime("%H:%M:%S")
        
        message = f"""
🚨 <b>[오류 알림]</b>

❌ <b>오류:</b> {error_message}

📍 <b>발생 위치:</b> {context}
⏰ <b>발생 시간:</b> {current_time}

🤖 <b>전략:</b> ULTRA_SURGE_1M_STRATEGY
        """
        
        return self.send_message(message.strip())
    
    def test_connection(self) -> bool:
        """
        텔레그램 봇 연결 테스트
        
        Returns:
            bool: 연결 성공 여부
        """
        test_message = f"""
✅ <b>[봇 연결 테스트]</b>

🤖 Ultra Surge 1M Strategy 텔레그램 봇이 정상 작동 중입니다.

⏰ 테스트 시간: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        """
        
        return self.send_message(test_message.strip())

# 텔레그램 봇 설정 방법 안내
TELEGRAM_SETUP_GUIDE = """
=== 텔레그램 봇 설정 방법 ===

1. BotFather에서 봇 생성:
   - 텔레그램에서 @BotFather 검색
   - /newbot 명령어로 봇 생성
   - 봇 토큰 복사

2. Chat ID 확인:
   - 봇과 채팅 시작
   - 아무 메시지 전송
   - https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   - 위 URL에서 chat.id 확인

3. 코드 설정:
   - bot_token과 chat_id를 실제 값으로 변경
   - 또는 환경변수 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 설정

4. 테스트:
   - TelegramBot().test_connection() 실행
"""

if __name__ == "__main__":
    print(TELEGRAM_SETUP_GUIDE)
    
    # 테스트 실행
    bot = TelegramBot()
    if bot.test_connection():
        print("✅ 텔레그램 봇 연결 성공!")
    else:
        print("❌ 텔레그램 봇 연결 실패!")