@echo off
echo ================================================
echo  Wildlife Monitoring System - Startup
echo ================================================
echo.

echo [1/2] Starting Email Extractor...
start "Email Extractor" cmd /k "cd email_extractor && python WildlifePictureExtractor.py"

timeout /t 3 /nobreak > nul

echo [2/2] Starting Streamlit Web App...
start "Streamlit App" cmd /k "cd streamlit_app && python -m streamlit run map.py"

echo.
echo ================================================
echo  System gestartet!
echo  - Email Extractor: Laeuft im Hintergrund
echo  - Web App: http://localhost:8501
echo ================================================
pause