@echo off
chcp 65001 >nul
TITLE CryptoNews Agent v17.4
color 0A
echo ====================================================
echo    CRYPTONEWS AGENT v17.4 (Stable)
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
