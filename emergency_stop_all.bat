@echo off
echo ========================================
echo 비상 중단: 모든 파이썬 거래 프로그램 종료
echo ========================================

echo 현재 실행 중인 파이썬 프로세스:
tasklist | findstr python.exe

echo.
echo 모든 파이썬 프로세스를 종료합니다...
taskkill /f /im python.exe

echo.
echo 종료 후 확인:
tasklist | findstr python.exe

echo.
echo ========================================
echo 비상 중단 완료!
echo 바이낸스 IP 밴 해제까지 최소 30분 대기하세요
echo 해제 예상 시간: 01:50 이후
echo ========================================
pause