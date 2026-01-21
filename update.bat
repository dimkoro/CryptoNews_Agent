@echo off
chcp 65001 >nul
TITLE Update Libraries
color 0B
echo ====================================================
echo    UPDATING LIBRARIES (Safe Mode)
echo ====================================================
echo.
echo [1] Updating core tools...
".venv\Scripts\python.exe" -m pip install --upgrade pip
echo.
echo [2] Updating AI and Telegram libs...
".venv\Scripts\pip" install --upgrade google-genai google-generativeai telethon aiogram aiohttp
echo.
echo [3] Cleaning up...
echo.
echo DONE! You can close this window.
pause