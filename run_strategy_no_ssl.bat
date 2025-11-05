@echo off
REM SSL 검증 완전 비활성화하여 전략 실행
SET PYTHONHTTPSVERIFY=0
SET CURL_CA_BUNDLE=
SET REQUESTS_CA_BUNDLE=
SET SSL_CERT_FILE=

echo ========================================
echo 바이낸스 전략 실행 (SSL 검증 비활성화)
echo ========================================
echo.

python one_minute_surge_entry_strategy.py

pause
