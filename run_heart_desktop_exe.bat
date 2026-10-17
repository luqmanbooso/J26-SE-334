@echo off
title HEART - Unified Mobile Robustness Platform Studio
echo ===============================================================================
echo   HEART: Unified Mobile Robustness Platform Studio (Standalone Desktop App)
echo   4-Pillar Integrated Research Suite: Environment, Biometry, Vision, Self-Healing
echo   Project ID: J26-SE-334
echo ===============================================================================
echo.
echo Launching native standalone Windows executable...
cd /d "%~dp0dist\HEART_Studio_v4"
if exist "HEART_Studio_v4.exe" (
    start "" "HEART_Studio_v4.exe"
) else (
    cd /d "%~dp0"
    python heart_desktop_app.py
)
exit

