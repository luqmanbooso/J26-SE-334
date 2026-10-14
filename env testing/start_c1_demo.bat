@echo off
title HEART Framework - Environmental Perturbation Studio
echo ===============================================================================
echo   HEART Framework: Context-Aware Environmental Perturbation Engine
echo   Project ID: J26-SE-334
echo ===============================================================================
echo.
echo [1/2] Starting Python FastAPI REST Engine on Port 8001...
start "HEART Engine Backend (Port 8001)" cmd /k "cd /d "%~dp0" && python server.py"

echo.
echo [2/2] Launching Native Desktop Application Studio...
start "" "%~dp0..\run_heart_desktop_exe.bat"

echo.
echo [OK] Environmental Perturbation Engine Studio is now online!
echo      - Backend REST API Docs: http://127.0.0.1:8001/docs
echo.
pause
