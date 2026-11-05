@echo off
title HEART Framework - Environmental Perturbation Demo Studio
echo ===============================================================================
echo   HEART Framework: Context-Aware Environmental Perturbation Engine
echo   One-Click Demo Video Recording Launcher
echo   Project ID: J26-SE-334
echo ===============================================================================
echo.

echo [1/3] Checking / Launching Android Emulator (Pixel_9_Pro)...
"%~dp0platform-tools\adb.exe" devices | findstr "emulator-5554" >nul
if %errorlevel% neq 0 (
    echo Starting Pixel 9 Pro Emulator with GPU acceleration...
    start "Pixel 9 Pro Emulator" "%USERPROFILE%\AppData\Local\Android\Sdk\emulator\emulator.exe" -avd Pixel_9_Pro -gpu host
) else (
    echo Android emulator is already connected!
)

echo.
echo [2/3] Starting FastAPI REST Engine on Port 8001...
start "HEART Engine Backend (Port 8001)" cmd /k "cd /d "%~dp0env testing" && python server.py"

echo.
echo [3/3] Launching Native Desktop Application Studio...
start "HEART Studio GUI" cmd /c "cd /d "%~dp0" && python heart_desktop_app.py"

echo.
echo ===============================================================================
echo [READY] All systems online for Demo Recording:
echo   - Android Emulator: emulator-5554
echo   - Backend REST Docs: http://127.0.0.1:8001/docs
echo   - Interactive Studio: heart_desktop_app.py
echo ===============================================================================
echo.
pause
