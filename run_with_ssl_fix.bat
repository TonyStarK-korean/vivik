@echo off
REM SSL 인증서 경로 설정
SET SSL_CERT_FILE=C:\Users\USER\AppData\Local\Programs\Python\Python310-32\lib\site-packages\certifi\cacert.pem
SET REQUESTS_CA_BUNDLE=C:\Users\USER\AppData\Local\Programs\Python\Python310-32\lib\site-packages\certifi\cacert.pem

echo ========================================
echo Binance Strategy (SSL Fixed)
echo ========================================
echo SSL_CERT_FILE: %SSL_CERT_FILE%
echo.

python one_minute_surge_entry_strategy.py

pause
