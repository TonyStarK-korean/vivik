@echo off
echo ========================================
echo Network Connection Test
echo ========================================
echo.

echo [1] Checking network connection...
ipconfig | findstr "IPv4"
echo.

echo [2] Testing internet (Google)...
ping -n 2 8.8.8.8
echo.

echo [3] Testing Binance API...
ping -n 2 api.binance.com
echo.

echo ========================================
echo If all tests passed, you're ready!
echo ========================================
pause
