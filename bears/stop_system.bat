@echo off
echo Stopping Wildlife Monitoring System...

taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM streamlit.exe /T 2>nul

echo.
echo System stopped!
pause