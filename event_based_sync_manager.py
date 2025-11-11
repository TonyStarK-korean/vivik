# -*- coding: utf-8 -*-
"""
🔄 이벤트 기반 동기화 매니저
메인 전략과 대시보드 간 실시간 동기화를 위한 이벤트 시스템

주요 기능:
1. 거래 실행 시 즉시 알림
2. DCA 포지션 변경 이벤트 감지
3. 파일 감시를 통한 자동 동기화
4. 이벤트 큐 및 배치 처리
5. 실시간 알림 시스템

이벤트 유형:
- POSITION_OPENED: 새 포지션 진입
- POSITION_CLOSED: 포지션 청산
- DCA_TRIGGERED: DCA 추가매수 실행
- POSITION_UPDATED: 포지션 정보 업데이트
- SIGNAL_GENERATED: 새 신호 발생
"""

import json
import time
import threading
import queue
import hashlib
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import logging

class EventType(Enum):
    """이벤트 유형"""
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed" 
    DCA_TRIGGERED = "dca_triggered"
    POSITION_UPDATED = "position_updated"
    SIGNAL_GENERATED = "signal_generated"
    FILE_UPDATED = "file_updated"
    ACCOUNT_UPDATED = "account_updated"

@dataclass
class SyncEvent:
    """동기화 이벤트"""
    event_type: str
    symbol: str
    data: Dict
    timestamp: str
    priority: int = 1  # 1=높음, 2=보통, 3=낮음

class FileWatcher:
    """파일 변경 감시기"""
    
    def __init__(self, callback: Callable):
        self.callback = callback
        self.watched_files = {}
        self.is_running = False
        self.watch_thread = None
        
    def add_file(self, file_path: str, event_type: str = "file_updated"):
        """감시할 파일 추가"""
        if os.path.exists(file_path):
            self.watched_files[file_path] = {
                'last_mtime': os.path.getmtime(file_path),
                'last_hash': self._calculate_file_hash(file_path),
                'event_type': event_type
            }
            
    def _calculate_file_hash(self, file_path: str) -> str:
        """파일 해시 계산"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return ""
    
    def _watch_files(self):
        """파일 감시 루프"""
        while self.is_running:
            for file_path, info in self.watched_files.items():
                try:
                    if not os.path.exists(file_path):
                        continue
                        
                    current_mtime = os.path.getmtime(file_path)
                    
                    # 수정 시간이 변경되었으면 해시 체크
                    if current_mtime > info['last_mtime']:
                        current_hash = self._calculate_file_hash(file_path)
                        
                        if current_hash != info['last_hash']:
                            # 파일이 실제로 변경됨
                            event = SyncEvent(
                                event_type=info['event_type'],
                                symbol="SYSTEM",
                                data={'file_path': file_path, 'change_time': current_mtime},
                                timestamp=datetime.now(timezone(timedelta(hours=9))).isoformat(),
                                priority=2
                            )
                            
                            self.callback(event)
                            
                            # 정보 업데이트
                            info['last_mtime'] = current_mtime
                            info['last_hash'] = current_hash
                            
                except Exception as e:
                    print(f"파일 감시 오류 {file_path}: {e}")
            
            time.sleep(1)  # 1초마다 체크
    
    def start(self):
        """파일 감시 시작"""
        if self.is_running:
            return
            
        self.is_running = True
        self.watch_thread = threading.Thread(target=self._watch_files, daemon=True)
        self.watch_thread.start()
        
    def stop(self):
        """파일 감시 중지"""
        self.is_running = False

class EventBasedSyncManager:
    """이벤트 기반 동기화 매니저"""
    
    def __init__(self):
        self.logger = self._setup_logger()
        
        # 이벤트 큐
        self.event_queue = queue.PriorityQueue()
        self.processing_thread = None
        self.is_running = False
        
        # 콜백 함수들
        self.event_callbacks = {}
        
        # 파일 감시기
        self.file_watcher = FileWatcher(self.emit_event)
        
        # 통계
        self.stats = {
            'events_processed': 0,
            'events_by_type': {},
            'last_event_time': None,
            'start_time': time.time()
        }
        
        # 이벤트 배치 처리
        self.batch_events = []
        self.batch_size = 10
        self.batch_timeout = 5  # 5초
        self.last_batch_time = time.time()
        
        self._setup_file_watchers()
        
    def _setup_logger(self):
        """로거 설정"""
        logger = logging.getLogger('EventSync')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def _setup_file_watchers(self):
        """파일 감시기 설정"""
        # DCA 포지션 파일
        self.file_watcher.add_file('dca_positions.json', 'position_updated')
        
        # 신호 로그 파일
        self.file_watcher.add_file('trading_signals.log', 'signal_generated')
        
        # 거래 이력 파일
        self.file_watcher.add_file('trade_history.json', 'position_updated')
        
        # 설정 파일들
        for pattern in ['*.json', '*.log']:
            for file_path in Path('.').glob(pattern):
                if file_path.name not in ['dca_positions.json', 'trade_history.json']:
                    self.file_watcher.add_file(str(file_path), 'file_updated')
    
    def register_callback(self, event_type: EventType, callback: Callable):
        """이벤트 콜백 등록"""
        if event_type not in self.event_callbacks:
            self.event_callbacks[event_type] = []
        
        self.event_callbacks[event_type].append(callback)
        self.logger.info(f"콜백 등록: {event_type.value}")
    
    def emit_event(self, event: SyncEvent):
        """이벤트 발생"""
        if not self.is_running:
            return
            
        try:
            # 우선순위 큐에 추가 (우선순위, 타임스탬프, 이벤트)
            priority_item = (event.priority, time.time(), event)
            self.event_queue.put(priority_item)
            
            # 통계 업데이트
            self.stats['events_processed'] += 1
            if event.event_type not in self.stats['events_by_type']:
                self.stats['events_by_type'][event.event_type] = 0
            self.stats['events_by_type'][event.event_type] += 1
            self.stats['last_event_time'] = event.timestamp
            
            self.logger.debug(f"이벤트 발생: {event.event_type} - {event.symbol}")
            
        except Exception as e:
            self.logger.error(f"이벤트 발생 오류: {e}")
    
    def _process_events(self):
        """이벤트 처리 루프"""
        while self.is_running:
            try:
                # 이벤트 대기 (타임아웃 1초)
                try:
                    priority, timestamp, event = self.event_queue.get(timeout=1)
                except queue.Empty:
                    # 배치 타임아웃 체크
                    if self.batch_events and (time.time() - self.last_batch_time) > self.batch_timeout:
                        self._process_batch()
                    continue
                
                # 배치에 추가
                self.batch_events.append(event)
                
                # 배치 크기 또는 타임아웃 체크
                if (len(self.batch_events) >= self.batch_size or 
                    (time.time() - self.last_batch_time) > self.batch_timeout):
                    self._process_batch()
                
            except Exception as e:
                self.logger.error(f"이벤트 처리 오류: {e}")
    
    def _process_batch(self):
        """배치 이벤트 처리"""
        if not self.batch_events:
            return
            
        try:
            self.logger.info(f"배치 처리: {len(self.batch_events)}개 이벤트")
            
            # 이벤트 유형별로 그룹핑
            grouped_events = {}
            for event in self.batch_events:
                event_type_enum = EventType(event.event_type)
                if event_type_enum not in grouped_events:
                    grouped_events[event_type_enum] = []
                grouped_events[event_type_enum].append(event)
            
            # 각 유형별로 콜백 실행
            for event_type, events in grouped_events.items():
                if event_type in self.event_callbacks:
                    for callback in self.event_callbacks[event_type]:
                        try:
                            callback(events)
                        except Exception as e:
                            self.logger.error(f"콜백 실행 오류 {event_type}: {e}")
            
            # 배치 초기화
            self.batch_events = []
            self.last_batch_time = time.time()
            
        except Exception as e:
            self.logger.error(f"배치 처리 오류: {e}")
    
    def start(self):
        """동기화 매니저 시작"""
        if self.is_running:
            return
            
        self.is_running = True
        
        # 이벤트 처리 스레드 시작
        self.processing_thread = threading.Thread(target=self._process_events, daemon=True)
        self.processing_thread.start()
        
        # 파일 감시기 시작
        self.file_watcher.start()
        
        self.logger.info("🔄 이벤트 기반 동기화 매니저 시작")
    
    def stop(self):
        """동기화 매니저 중지"""
        self.is_running = False
        
        # 남은 배치 처리
        if self.batch_events:
            self._process_batch()
        
        # 파일 감시기 중지
        self.file_watcher.stop()
        
        self.logger.info("🛑 이벤트 기반 동기화 매니저 중지")
    
    def get_stats(self) -> Dict:
        """통계 정보 반환"""
        runtime = time.time() - self.stats['start_time']
        
        return {
            'events_processed': self.stats['events_processed'],
            'events_by_type': self.stats['events_by_type'],
            'events_per_minute': round((self.stats['events_processed'] / runtime) * 60, 2) if runtime > 0 else 0,
            'last_event_time': self.stats['last_event_time'],
            'runtime_seconds': round(runtime, 1),
            'queue_size': self.event_queue.qsize(),
            'batch_pending': len(self.batch_events)
        }
    
    # 편의 메서드들
    def notify_position_opened(self, symbol: str, entry_data: Dict):
        """포지션 진입 알림"""
        event = SyncEvent(
            event_type=EventType.POSITION_OPENED.value,
            symbol=symbol,
            data=entry_data,
            timestamp=datetime.now(timezone(timedelta(hours=9))).isoformat(),
            priority=1
        )
        self.emit_event(event)
    
    def notify_position_closed(self, symbol: str, close_data: Dict):
        """포지션 청산 알림"""
        event = SyncEvent(
            event_type=EventType.POSITION_CLOSED.value,
            symbol=symbol,
            data=close_data,
            timestamp=datetime.now(timezone(timedelta(hours=9))).isoformat(),
            priority=1
        )
        self.emit_event(event)
    
    def notify_dca_triggered(self, symbol: str, dca_data: Dict):
        """DCA 실행 알림"""
        event = SyncEvent(
            event_type=EventType.DCA_TRIGGERED.value,
            symbol=symbol,
            data=dca_data,
            timestamp=datetime.now(timezone(timedelta(hours=9))).isoformat(),
            priority=1
        )
        self.emit_event(event)
    
    def notify_signal_generated(self, symbol: str, signal_data: Dict):
        """신호 생성 알림"""
        event = SyncEvent(
            event_type=EventType.SIGNAL_GENERATED.value,
            symbol=symbol,
            data=signal_data,
            timestamp=datetime.now(timezone(timedelta(hours=9))).isoformat(),
            priority=2
        )
        self.emit_event(event)


# 글로벌 인스턴스 (싱글톤 패턴)
_sync_manager = None

def get_sync_manager() -> EventBasedSyncManager:
    """글로벌 동기화 매니저 인스턴스 반환"""
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = EventBasedSyncManager()
    return _sync_manager

# 사용 예시
if __name__ == "__main__":
    def on_position_event(events):
        """포지션 이벤트 처리"""
        print(f"📊 포지션 이벤트 {len(events)}개 처리")
        for event in events:
            print(f"  - {event.symbol}: {event.event_type}")
    
    def on_signal_event(events):
        """신호 이벤트 처리"""
        print(f"📡 신호 이벤트 {len(events)}개 처리")
        for event in events:
            print(f"  - {event.symbol}: {event.data}")
    
    # 동기화 매니저 시작
    sync_manager = get_sync_manager()
    
    # 콜백 등록
    sync_manager.register_callback(EventType.POSITION_OPENED, on_position_event)
    sync_manager.register_callback(EventType.POSITION_CLOSED, on_position_event)
    sync_manager.register_callback(EventType.SIGNAL_GENERATED, on_signal_event)
    
    # 시작
    sync_manager.start()
    
    # 테스트 이벤트 발생
    sync_manager.notify_position_opened("BTCUSDT", {"price": 91000, "quantity": 0.1})
    sync_manager.notify_signal_generated("ETHUSDT", {"strategy": "A", "action": "BUY"})
    
    print("동기화 매니저 실행 중... 'q' 입력으로 종료")
    try:
        while True:
            user_input = input()
            if user_input.lower() == 'q':
                break
                
            # 통계 출력
            stats = sync_manager.get_stats()
            print(f"📊 통계: {json.dumps(stats, indent=2)}")
                
    except KeyboardInterrupt:
        pass
    
    sync_manager.stop()
    print("동기화 매니저 종료")