@echo off
title HEART Framework - Component 1 Environmental Perturbation Studio
echo ===============================================================================
echo   HEART Framework: Component 1 - Environmental Perturbation Engine
echo   Student: G.L.S. Chanlaka (IT23151260) - Project ID: J26-SE-334
echo ===============================================================================
echo.
echo [1/2] Starting Component 1 Python FastAPI REST Engine on Port 8001...
start "HEART C1 Backend (Port 8001)" cmd /k "cd /d "%~dp0" && python server.py"

echo.
echo [2/2] Launching Frontend Web Studio...
start http://localhost:3000

echo.
echo [OK] Component 1 Environment Studio is now online!
echo      - Backend REST API Docs: http://127.0.0.1:8001/docs
echo      - Dashboard Studio:      http://localhost:3000
echo.
pause
