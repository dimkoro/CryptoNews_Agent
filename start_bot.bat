@echo off
chcp 65001 >nul
TITLE CryptoNews Agent v16.3.1
color 0A
echo ====================================================
echo    CRYPTONEWS AGENT v16.3.1 (Stable Release)
echo ====================================================
echo.
echo [1] Checking environment...
if not exist .env (
    echo [ERROR] .env file not found!
    pause
    exit
)
echo [OK] Environment ready.
echo.
echo [2] Starting Bot Core...
echo.
".venv\Scripts\python.exe" run.py
echo.
echo [STOP] Bot stopped.
pause