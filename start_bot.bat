@echo off
chcp 65001 >nul
TITLE CryptoNews Agent v15.9
color 0A
echo ====================================================
echo    CRYPTONEWS AGENT v15.9 (FINAL STABLE)
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