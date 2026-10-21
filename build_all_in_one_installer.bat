@echo off
title HEART Studio - Build All-in-One Installer
echo ===============================================================================
echo   HEART Framework: Standalone All-in-One Packaging Pipeline
echo   Project ID: J26-SE-334
echo ===============================================================================
echo.
echo Executing PowerShell packaging automation...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_installer.ps1"
echo.
pause
