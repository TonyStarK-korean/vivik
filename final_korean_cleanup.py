# -*- coding: utf-8 -*-
"""
Final Korean Cleanup - Remove ALL remaining Korean characters
"""

import re
import os

FINAL_TRANSLATIONS = {
    "시도": "Attempt",
    "최종": "Final",
    "콜백": "Callback",
    "키": "Key",
    "메시지": "Message",
    "세션": "Session",
    "코드": "Code",
    "상황": "Situation",
    "경고메시지": "Warning message",
    "시간대": "Timezone",
    "상태": "Status",
    "알림": "Notification",
    "파일": "File",
    "로그": "Log",
    "설정": "Settings",
    "사용자": "User",
    "관리자": "Admin",
    "확인": "Confirm",
    "취소": "Cancel",
    "저장": "Save",
    "로드": "Load",
    "삭제": "Delete",
    "생성": "Create",
    "수정": "Modify",
    "조회": "Query",
    "등록": "Register",
    "해제": "Release",
    "업데이트": "Update",
    "동기화": "Sync",
    "변경": "Change",
    "추가": "Add",
    "제거": "Remove",
    "복구": "Recover",
    "백업": "Backup",
    "초기화": "Initialize",
    "재시작": "Restart",
    "종료": "Terminate",
    "실행": "Execute",
    "처리": "Process",
    "분석": "Analysis",
    "검증": "Verification",
    "테스트": "Test",
    "배포": "Deploy",
}

FILES = [
    "advanced_exit_system.py",
    "apply_websocket_user_data_stream.py",
    "basic_exit_system.py",
    "binance_rate_limiter.py",
    "binance_websocket_kline_manager.py",
    "bulk_websocket_kline_manager.py",
    "improved_dca_position_manager.py",
    "indicators.py",
    "one_minute_surge_entry_strategy.py",
    "tradingview_strategy_executor.py",
    "tradingview_webhook_server.py",
    "websocket_defense_system.py",
]

def has_korean(text):
    """Check if text contains Korean characters"""
    return bool(re.search(r'[\uAC00-\uD7A3]', text))

def translate_final(content):
    """Final Korean translation pass"""
    for korean, english in FINAL_TRANSLATIONS.items():
        korean_escaped = re.escape(korean)
        content = re.sub(korean_escaped, english, content)
    return content

def main():
    print("="*70)
    print("Final Korean Cleanup")
    print("="*70)

    for filename in FILES:
        filepath = os.path.join(os.getcwd(), filename)

        if not os.path.exists(filepath):
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        if has_korean(content):
            new_content = translate_final(content)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)

            # Count remaining Korean chars
            remaining = len(re.findall(r'[\uAC00-\uD7A3]', new_content))
            print(f"[PROC] {filename}: {remaining} Korean chars remaining")
        else:
            print(f"[OK] {filename}: No Korean chars")

    print("\n"+"="*70)
    print("DONE: Final cleanup complete")
    print("="*70)

if __name__ == "__main__":
    main()
