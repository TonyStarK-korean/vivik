@echo off
echo ========================================
echo 서버 업로드용 파일 압축 중...
echo ========================================
echo.

REM 필수 파일 목록
set FILES=^
one_minute_surge_entry_strategy.py ^
binance_config.py ^
telegram_bot.py ^
telegram_config.py ^
pattern_optimizations.py ^
binance_websocket_kline_manager.py ^
improved_dca_position_manager.py ^
advanced_exit_system.py ^
basic_exit_system.py ^
optimized_2h_filter.py ^
dca_config.json ^
half_profit_exit_config.json ^
webhook_config.json ^
dca_positions.json ^
dca_limits.json ^
daily_stats.json ^
sent_notifications.json

echo 압축 파일 생성: binance-bot.zip
powershell Compress-Archive -Path %FILES% -DestinationPath binance-bot.zip -Force

echo.
echo ========================================
echo 완료! binance-bot.zip 파일이 생성되었습니다
echo ========================================
echo.
echo 이제 WinSCP로 이 파일을 서버에 업로드하세요
pause
