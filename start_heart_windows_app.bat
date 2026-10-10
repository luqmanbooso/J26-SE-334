@echo off
title HEART Mobile Robustness Testing Framework (Windows Enterprise Studio)
color 0b
echo =========================================================================
echo   HEART Mobile Robustness Testing Framework - Windows Desktop Edition
echo   Component 1: Context-Aware Environmental Perturbation Engine
echo   Student: Chanlaka G.L.S. (IT23151260) - Project ID: J26-SE-334
echo =========================================================================
echo.
echo [1/3] Checking Python runtime...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found on PATH. Please install Python 3.10+ to continue.
    pause
    exit /b 1
)

echo [2/3] Verifying pywebview Windows desktop dependencies...
python -c "import webview" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Installing pywebview desktop window runtime...
    pip install pywebview
)

echo [3/3] Launching HEART Windows Enterprise Desktop Studio...
cd /d "%~dp0"
python launch_windows_desktop.py

echo.
echo [DONE] Desktop session terminated.
pause
