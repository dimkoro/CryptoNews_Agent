@echo off
chcp 65001 >nul
TITLE Update Libraries
color 0B
echo ====================================================
echo    UPDATING LIBRARIES (Sync with requirements.txt)
echo ====================================================
echo.
echo [1] Updating pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
echo.
echo [2] Installing dependencies...
".venv\Scripts\pip" install -r requirements.txt
echo.
echo [3] Cleaning up...
".venv\Scripts\pip" uninstall -y aiogram
echo.
echo DONE!
pause