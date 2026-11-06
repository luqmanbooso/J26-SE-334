@echo off
title HEART - Context-Aware Environmental Perturbation Engine Studio
echo ===============================================================================
echo   HEART: Environmental Perturbation Engine Studio (Standalone Desktop Application)
echo   Automated Multi-Factor Mobile Robustness ^& Fault Injection Platform
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
