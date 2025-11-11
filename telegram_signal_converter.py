# -*- coding: utf-8 -*-
"""
📱➡️📊 텔레그램 봇 메시지 히스토리 → 거래 신호 로그 변환기
텔레그램 봇의 JSONL 히스토리를 거래 로깅 시스템에 연동

주요 기능:
1. 텔레그램 메시지 파싱 및 분석
2. 거래 신호 자동 추출 (진입/청산/DCA)
3. 실시간 모니터링 및 자동 변환
4. 중복 방지 및 무결성 검증
"""

import json
import os
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import threading
import logging
from dataclasses import dataclass

# 거래 로깅 시스템 연동
try:
    from strategy_integration_patch import (
        log_entry_signal, log_exit_signal, log_dca_signal, log_custom_signal,
        TRADING_LOGGER_AVAILABLE
    )
    HAS_LOGGER = True
except ImportError:
    print("⚠️ strategy_integration_patch.py 없음 - 로깅 기능 비활성화")
    HAS_LOGGER = False

@dataclass
class ParsedTelegramSignal:
    """파싱된 텔레그램 신호"""
    timestamp: str
    message_type: str  # entry, exit, dca, status, scan
    symbol: str
    strategy: str = None
    price: float = 0.0
    quantity: float = 0.0
    leverage: float = 10.0
    pnl_percent: float = 0.0
    status: str = ""
    conditions: List[str] = None
    metadata: Dict = None
    
    def __post_init__(self):
        if self.conditions is None:
            self.conditions = []
        if self.metadata is None:
            self.metadata = {}

class TelegramSignalConverter:
    """텔레그램 신호 변환기"""
    
    def __init__(self):
        self.telegram_dir = Path("data/telegram_history")
        self.processed_file = Path("data/telegram_processed.json")
        
        # 처리 상태 관리
        self.processed_messages = self.load_processed_state()
        
        # 정규식 패턴들
        self.patterns = self._init_patterns()
        
        # 모니터링 설정
        self.running = False
        self.monitor_thread = None
        
        print(f"[Telegram Converter] 초기화 완료")
        print(f"  히스토리 디렉토리: {self.telegram_dir}")
        print(f"  처리상태 파일: {self.processed_file}")
        print(f"  거래 로거 연동: {'SUCCESS' if HAS_LOGGER else 'FAILED'}")
    
    def _init_patterns(self) -> Dict[str, re.Pattern]:
        """메시지 파싱용 정규식 패턴 초기화"""
        return {
            # 진입 알림 패턴
            'entry': re.compile(r'🚀.*\[자동 진입 알림\]', re.DOTALL),
            'symbol': re.compile(r'📊.*심볼:.*?([A-Z]+)(?:/USDT)?', re.IGNORECASE),
            'entry_price': re.compile(r'💰.*진입가:.*?\$([0-9,]+\.?[0-9]*)', re.IGNORECASE),
            'position_amount': re.compile(r'📈.*포지션:.*?\$([0-9,]+\.?[0-9]*)', re.IGNORECASE),
            'leverage_info': re.compile(r'📈.*포지션:.*?\(([0-9]+)x\)', re.IGNORECASE),
            'total_value': re.compile(r'💎.*총 가치:.*?\$([0-9,]+\.?[0-9]*)', re.IGNORECASE),
            'conditions_list': re.compile(r'✅.*충족 조건:.*?\n(.*?)(?=\n🎯|\n📱|$)', re.DOTALL),
            
            # 계좌 상태 패턴
            'account_status': re.compile(r'📊.*\[계좌 상태 보고\]', re.DOTALL),
            'total_balance': re.compile(r'총 잔고:.*?\$([0-9,]+\.?[0-9]*)', re.IGNORECASE),
            'position_pnl': re.compile(r'([A-Z]+):.*?([+-][0-9\.]+)%.*?\(\$([+-][0-9,\.]+)\)', re.IGNORECASE),
            'total_pnl': re.compile(r'총 손익:.*?\$([+-][0-9,\.]+)', re.IGNORECASE),
            
            # 스캔 결과 패턴
            'scan_summary': re.compile(r'🔍.*\[스캔 결과 요약\]', re.DOTALL),
            'scan_counts': re.compile(r'1차 스캔:.*?([0-9]+)개.*?진입임박:.*?([0-9]+)개.*?일부충족:.*?([0-9]+)개', re.DOTALL),
            'scan_symbols': re.compile(r'🎯 ([A-Z]+):.*?([0-9]+)/[0-9]+ conditions', re.IGNORECASE),
            
            # 오류 알림 패턴
            'error_alert': re.compile(r'🚨.*\[오류 알림\]', re.DOTALL),
            'error_message': re.compile(r'❌.*오류:.*?(.*?)(?=\n📍|\n⏰|$)', re.DOTALL),
            
            # DCA/불타기 관련 패턴 (향후 확장용)
            'dca_pattern': re.compile(r'(불타기|DCA|추가.*?매수)', re.IGNORECASE),
            'exit_pattern': re.compile(r'(청산|익절|손절|exit)', re.IGNORECASE),
            
            # 가격 및 수치 추출
            'price_pattern': re.compile(r'\$([0-9,]+\.?[0-9]*)', re.IGNORECASE),
            'percentage_pattern': re.compile(r'([+-]?[0-9]+\.?[0-9]*)%', re.IGNORECASE),
        }
    
    def load_processed_state(self) -> Dict:
        """처리된 메시지 상태 로드"""
        if self.processed_file.exists():
            try:
                with open(self.processed_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Converter] 처리상태 로드 실패: {e}")
        
        return {
            'last_processed_date': '',
            'processed_message_ids': [],
            'total_converted': 0,
            'last_update': datetime.now().isoformat()
        }
    
    def save_processed_state(self):
        """처리된 메시지 상태 저장"""
        try:
            self.processed_messages['last_update'] = datetime.now().isoformat()
            with open(self.processed_file, 'w', encoding='utf-8') as f:
                json.dump(self.processed_messages, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Converter] 처리상태 저장 실패: {e}")
    
    def parse_telegram_message(self, message_data: Dict) -> Optional[ParsedTelegramSignal]:
        """텔레그램 메시지를 파싱하여 거래 신호로 변환"""
        try:
            timestamp = message_data.get('timestamp', '')
            message_text = message_data.get('message', '')
            event_type = message_data.get('event_type', 'general')
            symbol = message_data.get('symbol', '')
            metadata = message_data.get('metadata', {})
            
            # 메시지 타입 감지
            if self.patterns['entry'].search(message_text):
                return self._parse_entry_message(timestamp, message_text, metadata)
            elif self.patterns['account_status'].search(message_text):
                return self._parse_account_status(timestamp, message_text, metadata)
            elif self.patterns['scan_summary'].search(message_text):
                return self._parse_scan_summary(timestamp, message_text, metadata)
            elif self.patterns['error_alert'].search(message_text):
                return self._parse_error_alert(timestamp, message_text, metadata)
            else:
                # 기타 메시지는 일반 신호로 처리
                return self._parse_general_message(timestamp, message_text, event_type, symbol, metadata)
            
        except Exception as e:
            print(f"[Converter] 메시지 파싱 실패: {e}")
            return None
    
    def _parse_entry_message(self, timestamp: str, message: str, metadata: Dict) -> Optional[ParsedTelegramSignal]:
        """진입 알림 메시지 파싱"""
        try:
            # 심볼 추출
            symbol_match = self.patterns['symbol'].search(message)
            symbol = symbol_match.group(1) if symbol_match else 'UNKNOWN'
            
            # 진입가 추출
            price_match = self.patterns['entry_price'].search(message)
            price = float(price_match.group(1).replace(',', '')) if price_match else 0.0
            
            # 포지션 크기 추출
            position_match = self.patterns['position_amount'].search(message)
            position_amount = float(position_match.group(1).replace(',', '')) if position_match else 0.0
            
            # 레버리지 추출
            leverage_match = self.patterns['leverage_info'].search(message)
            leverage = float(leverage_match.group(1)) if leverage_match else 10.0
            
            # 총 가치 추출
            total_value_match = self.patterns['total_value'].search(message)
            total_value = float(total_value_match.group(1).replace(',', '')) if total_value_match else 0.0
            
            # 수량 계산 (포지션 크기 / 진입가)
            quantity = position_amount / price if price > 0 else 0.0
            
            # 조건들 추출
            conditions_match = self.patterns['conditions_list'].search(message)
            conditions = []
            if conditions_match:
                conditions_text = conditions_match.group(1).strip()
                conditions = [line.strip() for line in conditions_text.split('\n') if line.strip()]
            
            # 전략 추정 (조건 수에 따라)
            strategy = self._estimate_strategy_from_conditions(conditions)
            
            return ParsedTelegramSignal(
                timestamp=timestamp,
                message_type='entry',
                symbol=symbol,
                strategy=strategy,
                price=price,
                quantity=quantity,
                leverage=leverage,
                status='진입완료',
                conditions=conditions,
                metadata={
                    **metadata,
                    'position_amount': position_amount,
                    'total_value': total_value,
                    'source': 'telegram_entry_alert'
                }
            )
            
        except Exception as e:
            print(f"[Converter] 진입 메시지 파싱 실패: {e}")
            return None
    
    def _parse_account_status(self, timestamp: str, message: str, metadata: Dict) -> Optional[ParsedTelegramSignal]:
        """계좌 상태 메시지 파싱"""
        try:
            # 총 잔고 추출
            balance_match = self.patterns['total_balance'].search(message)
            total_balance = float(balance_match.group(1).replace(',', '')) if balance_match else 0.0
            
            # 총 PnL 추출
            pnl_match = self.patterns['total_pnl'].search(message)
            total_pnl = float(pnl_match.group(1).replace(',', '')) if pnl_match else 0.0
            
            # 포지션별 PnL 추출
            position_pnls = []
            for match in self.patterns['position_pnl'].finditer(message):
                symbol = match.group(1)
                pnl_percent = float(match.group(2))
                pnl_usd = float(match.group(3).replace(',', ''))
                position_pnls.append({
                    'symbol': symbol,
                    'pnl_percent': pnl_percent,
                    'pnl_usd': pnl_usd
                })
            
            return ParsedTelegramSignal(
                timestamp=timestamp,
                message_type='status',
                symbol='ACCOUNT',
                status='계좌상태',
                metadata={
                    **metadata,
                    'total_balance': total_balance,
                    'total_pnl': total_pnl,
                    'position_pnls': position_pnls,
                    'source': 'telegram_account_status'
                }
            )
            
        except Exception as e:
            print(f"[Converter] 계좌상태 메시지 파싱 실패: {e}")
            return None
    
    def _parse_scan_summary(self, timestamp: str, message: str, metadata: Dict) -> Optional[ParsedTelegramSignal]:
        """스캔 결과 메시지 파싱"""
        try:
            # 스캔 카운트 추출
            counts_match = self.patterns['scan_counts'].search(message)
            primary_count = int(counts_match.group(1)) if counts_match else 0
            strong_count = int(counts_match.group(2)) if counts_match else 0
            partial_count = int(counts_match.group(3)) if counts_match else 0
            
            # 진입임박 심볼들 추출
            strong_symbols = []
            for match in self.patterns['scan_symbols'].finditer(message):
                symbol = match.group(1)
                conditions = int(match.group(2))
                strong_symbols.append({
                    'symbol': symbol,
                    'conditions': conditions
                })
            
            return ParsedTelegramSignal(
                timestamp=timestamp,
                message_type='scan',
                symbol='SCAN_RESULT',
                status='스캔완료',
                metadata={
                    **metadata,
                    'primary_count': primary_count,
                    'strong_count': strong_count,
                    'partial_count': partial_count,
                    'strong_symbols': strong_symbols,
                    'source': 'telegram_scan_summary'
                }
            )
            
        except Exception as e:
            print(f"[Converter] 스캔결과 메시지 파싱 실패: {e}")
            return None
    
    def _parse_error_alert(self, timestamp: str, message: str, metadata: Dict) -> Optional[ParsedTelegramSignal]:
        """오류 알림 메시지 파싱"""
        try:
            # 오류 메시지 추출
            error_match = self.patterns['error_message'].search(message)
            error_text = error_match.group(1).strip() if error_match else 'Unknown error'
            
            return ParsedTelegramSignal(
                timestamp=timestamp,
                message_type='error',
                symbol='ERROR',
                status='오류발생',
                metadata={
                    **metadata,
                    'error_message': error_text,
                    'source': 'telegram_error_alert'
                }
            )
            
        except Exception as e:
            print(f"[Converter] 오류알림 메시지 파싱 실패: {e}")
            return None
    
    def _parse_general_message(self, timestamp: str, message: str, event_type: str, symbol: str, metadata: Dict) -> Optional[ParsedTelegramSignal]:
        """기타 메시지 파싱"""
        try:
            # DCA/불타기 패턴 검사
            if self.patterns['dca_pattern'].search(message):
                message_type = 'dca'
                status = '불타기실행'
            elif self.patterns['exit_pattern'].search(message):
                message_type = 'exit'
                status = '청산실행'
            else:
                message_type = 'general'
                status = '일반메시지'
            
            # 가격 정보 추출 시도
            price_matches = self.patterns['price_pattern'].findall(message)
            price = float(price_matches[0].replace(',', '')) if price_matches else 0.0
            
            # 퍼센트 정보 추출 시도
            pct_matches = self.patterns['percentage_pattern'].findall(message)
            pnl_percent = float(pct_matches[0]) if pct_matches else 0.0
            
            return ParsedTelegramSignal(
                timestamp=timestamp,
                message_type=message_type,
                symbol=symbol or 'UNKNOWN',
                price=price,
                pnl_percent=pnl_percent,
                status=status,
                metadata={
                    **metadata,
                    'original_event_type': event_type,
                    'message_text': message[:200],  # 처음 200자만 저장
                    'source': 'telegram_general'
                }
            )
            
        except Exception as e:
            print(f"[Converter] 일반 메시지 파싱 실패: {e}")
            return None
    
    def _estimate_strategy_from_conditions(self, conditions: List[str]) -> str:
        """조건들로부터 전략 추정"""
        if not conditions:
            return 'UNKNOWN'
        
        condition_text = ' '.join(conditions).upper()
        
        # A전략 키워드: 3분봉, 바닥, MA5-MA80, BB80-BB480
        if any(keyword in condition_text for keyword in ['3분', 'MA5', 'BB80', 'MA80', '바닥']):
            return 'A'
        
        # B전략 키워드: 15분봉, 급등초입, MA5-MA20, BB200
        elif any(keyword in condition_text for keyword in ['15분', 'MA20', 'BB200', '급등초입']):
            return 'B'
        
        # C전략 키워드: 30분봉, 급등맥점, MA480
        elif any(keyword in condition_text for keyword in ['30분', 'MA480', '급등맥점']):
            return 'C'
        
        # 조건 수에 따른 추정
        elif len(conditions) >= 5:
            return 'A'  # A전략이 5개 조건
        elif len(conditions) >= 3:
            return 'B'  # B전략이 6개 조건이지만 복잡한 조건
        else:
            return 'C'  # C전략이 2+3개 조건
    
    def convert_signal_to_trading_log(self, signal: ParsedTelegramSignal) -> bool:
        """파싱된 신호를 거래 로그로 변환"""
        if not HAS_LOGGER:
            return False
        
        try:
            if signal.message_type == 'entry':
                log_entry_signal(
                    symbol=signal.symbol,
                    strategy=signal.strategy or 'TG',
                    price=signal.price,
                    quantity=signal.quantity,
                    leverage=signal.leverage,
                    metadata={
                        **signal.metadata,
                        'telegram_source': True,
                        'conditions_met': signal.conditions
                    }
                )
                return True
                
            elif signal.message_type == 'exit':
                # 청산의 경우 진입가가 필요하지만 텔레그램 메시지에서는 얻기 어려움
                # 커스텀 로그로 기록
                log_custom_signal(
                    symbol=signal.symbol,
                    strategy='TG_EXIT',
                    action='EXIT',
                    price=signal.price,
                    quantity=signal.quantity,
                    status=signal.status,
                    metadata={
                        **signal.metadata,
                        'telegram_source': True,
                        'pnl_percent': signal.pnl_percent
                    }
                )
                return True
                
            elif signal.message_type == 'dca':
                log_dca_signal(
                    symbol=signal.symbol,
                    price=signal.price,
                    quantity=signal.quantity,
                    stage='TG_DCA',
                    leverage=signal.leverage,
                    metadata={
                        **signal.metadata,
                        'telegram_source': True
                    }
                )
                return True
                
            else:
                # 기타 신호들은 커스텀 로그로 기록
                log_custom_signal(
                    symbol=signal.symbol,
                    strategy='TELEGRAM',
                    action=signal.message_type.upper(),
                    price=signal.price,
                    quantity=signal.quantity,
                    status=signal.status,
                    metadata={
                        **signal.metadata,
                        'telegram_source': True
                    }
                )
                return True
            
        except Exception as e:
            print(f"[Converter] 거래 로그 변환 실패: {e}")
            return False
    
    def process_telegram_files(self, date_str: str = None) -> int:
        """텔레그램 히스토리 파일들 처리"""
        if not self.telegram_dir.exists():
            print(f"[Converter] 텔레그램 디렉토리가 없습니다: {self.telegram_dir}")
            return 0
        
        processed_count = 0
        
        # 처리할 파일 목록 구성
        if date_str:
            files_to_process = [self.telegram_dir / f"messages_{date_str}.jsonl"]
        else:
            files_to_process = list(self.telegram_dir.glob("messages_*.jsonl"))
        
        for file_path in files_to_process:
            if not file_path.exists():
                continue
            
            try:
                count = self._process_single_file(file_path)
                processed_count += count
                print(f"[Converter] {file_path.name}: {count}개 메시지 처리")
                
            except Exception as e:
                print(f"[Converter] 파일 처리 실패 {file_path.name}: {e}")
        
        # 처리 상태 저장
        self.processed_messages['total_converted'] += processed_count
        self.save_processed_state()
        
        return processed_count
    
    def _process_single_file(self, file_path: Path) -> int:
        """단일 텔레그램 히스토리 파일 처리"""
        processed_count = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        message_data = json.loads(line)
                        message_id = f"{file_path.name}:{line_num}"
                        
                        # 중복 처리 방지
                        if message_id in self.processed_messages['processed_message_ids']:
                            continue
                        
                        # 메시지 파싱
                        signal = self.parse_telegram_message(message_data)
                        if signal is None:
                            continue
                        
                        # 거래 로그로 변환
                        if self.convert_signal_to_trading_log(signal):
                            self.processed_messages['processed_message_ids'].append(message_id)
                            processed_count += 1
                            
                            print(f"  [SUCCESS] {signal.symbol} {signal.message_type} @ ${signal.price:.4f}")
                        
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        print(f"  [ERROR] 라인 {line_num} 처리 실패: {e}")
                        continue
                        
        except Exception as e:
            print(f"[Converter] 파일 읽기 실패: {e}")
        
        return processed_count
    
    def start_monitoring(self, interval: int = 10):
        """텔레그램 히스토리 실시간 모니터링 시작"""
        if self.running:
            print("[Converter] 이미 모니터링 중입니다")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, args=(interval,), daemon=True)
        self.monitor_thread.start()
        
        print(f"[Converter] 실시간 모니터링 시작 (간격: {interval}초)")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()
        print("[Converter] 모니터링 중지")
    
    def _monitoring_loop(self, interval: int):
        """모니터링 루프"""
        last_check = datetime.now()
        
        while self.running:
            try:
                # 오늘 날짜 파일 처리
                today_str = datetime.now().strftime('%Y%m%d')
                today_file = self.telegram_dir / f"messages_{today_str}.jsonl"
                
                if today_file.exists() and today_file.stat().st_mtime > last_check.timestamp():
                    count = self._process_single_file(today_file)
                    if count > 0:
                        print(f"[Converter] 실시간 처리: {count}개 메시지")
                        self.save_processed_state()
                
                last_check = datetime.now()
                time.sleep(interval)
                
            except Exception as e:
                print(f"[Converter] 모니터링 오류: {e}")
                time.sleep(interval)
    
    def get_conversion_stats(self) -> Dict:
        """변환 통계 조회"""
        return {
            'total_converted': self.processed_messages.get('total_converted', 0),
            'processed_files': len(set(mid.split(':')[0] for mid in self.processed_messages.get('processed_message_ids', []))),
            'last_update': self.processed_messages.get('last_update', ''),
            'monitoring_active': self.running
        }

def main():
    """메인 실행 함수"""
    converter = TelegramSignalConverter()
    
    print("\n" + "="*60)
    print("[TELEGRAM CONVERTER] 텔레그램 메시지 -> 거래 신호 로그 변환기")
    print("="*60)
    
    try:
        # 기존 파일들 일괄 처리
        total_processed = converter.process_telegram_files()
        print(f"\n[SUCCESS] 일괄 처리 완료: {total_processed}개 메시지 변환")
        
        # 통계 출력
        stats = converter.get_conversion_stats()
        print(f"\n[STATS] 변환 통계:")
        print(f"  총 변환 메시지: {stats['total_converted']}개")
        print(f"  처리된 파일: {stats['processed_files']}개")
        print(f"  마지막 업데이트: {stats['last_update']}")
        
        # 실시간 모니터링 시작
        if total_processed > 0 or input("\n실시간 모니터링을 시작하시겠습니까? (y/n): ").lower() == 'y':
            converter.start_monitoring(interval=5)
            
            try:
                print("\n[MONITORING] 실시간 모니터링 중... (종료하려면 Ctrl+C)")
                while converter.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n[STOP] 모니터링 종료 중...")
                converter.stop_monitoring()
        
    except Exception as e:
        print(f"\n[ERROR] 오류 발생: {e}")
        
    print("\n[SUCCESS] 프로그램 종료")

if __name__ == "__main__":
    main()