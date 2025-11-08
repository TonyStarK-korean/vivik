@echo off
chcp 65001 > nul
echo ====================================================================
echo VPS Config 파일 업로드
echo ====================================================================
echo.

REM VPS 정보 입력
set /p VPS_USER="VPS 사용자명 (예: root): "
set /p VPS_IP="VPS IP 주소: "
set /p VPS_PATH="프로젝트 경로 (기본: ~/vivik): "

if "%VPS_PATH%"=="" set VPS_PATH=~/vivik

echo.
echo ====================================================================
echo 업로드 정보
echo ====================================================================
echo VPS 주소: %VPS_USER%@%VPS_IP%
echo 경로: %VPS_PATH%
echo.

REM 현재 디렉토리의 config 파일들
set BINANCE_CONFIG="%~dp0binance_config.py"
set TELEGRAM_CONFIG="%~dp0telegram_config.py"

echo 업로드할 파일:
echo - binance_config.py
echo - telegram_config.py
echo.

pause

echo.
echo 📤 업로드 중...
echo.

REM SCP로 업로드
scp %BINANCE_CONFIG% %VPS_USER%@%VPS_IP%:%VPS_PATH%/
if errorlevel 1 (
    echo ❌ binance_config.py 업로드 실패
    pause
    exit /b 1
)
echo ✅ binance_config.py 업로드 완료

scp %TELEGRAM_CONFIG% %VPS_USER%@%VPS_IP%:%VPS_PATH%/
if errorlevel 1 (
    echo ❌ telegram_config.py 업로드 실패
    pause
    exit /b 1
)
echo ✅ telegram_config.py 업로드 완료

echo.
echo ====================================================================
echo ✅ 모든 파일 업로드 완료!
echo ====================================================================
echo.

REM 봇 재시작 여부 확인
set /p RESTART="VPS에서 봇을 재시작하시겠습니까? (y/n): "

if /i "%RESTART%"=="y" (
    echo.
    echo 🚀 봇 재시작 중...
    ssh %VPS_USER%@%VPS_IP% "cd %VPS_PATH% && pkill -f one_minute_surge_entry_strategy.py; sleep 2; nohup python3 one_minute_surge_entry_strategy.py > trading_bot.log 2>&1 & echo '봇 시작됨 (PID: '$!')'"
    echo.
    echo ✅ 봇 재시작 완료
    echo.
    echo 로그 확인:
    echo ssh %VPS_USER%@%VPS_IP%
    echo cd %VPS_PATH%
    echo tail -f trading_bot.log
) else (
    echo.
    echo 수동으로 봇을 재시작하려면:
    echo ssh %VPS_USER%@%VPS_IP%
    echo cd %VPS_PATH%
    echo pkill -f one_minute_surge_entry_strategy.py
    echo nohup python3 one_minute_surge_entry_strategy.py ^> trading_bot.log 2^>^&1 ^&
    echo tail -f trading_bot.log
)

echo.
pause
