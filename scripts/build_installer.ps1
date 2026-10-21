# ===============================================================================
# HEART Studio - Automated Installer & Standalone Bundle Builder
# ===============================================================================
param(
    [switch]$SkipDownloadAdb = $false
)

$ErrorActionPreference = "Continue"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "   HEART Studio: All-in-One Standalone Installer Packaging Pipeline" -ForegroundColor Cyan
Write-Host "===============================================================================" -ForegroundColor Cyan

# Helper to verify functional python runtime
function Test-PythonExecutable {
    param($cmd)
    try {
        $out = & $cmd -c "import sys; print(sys.executable)" 2>$null
        return ($LASTEXITCODE -eq 0 -and $out)
    } catch {
        return $false
    }
}

# 1. Ensure Google Platform-Tools (ADB) are available for bundling
$PlatformToolsDir = Join-Path $RepoRoot "platform-tools"
if (-not (Test-Path (Join-Path $PlatformToolsDir "adb.exe")) -and -not $SkipDownloadAdb) {
    Write-Host "[1/5] Downloading official Google standalone platform-tools (ADB)..." -ForegroundColor Yellow
    $ZipPath = Join-Path $RepoRoot "platform-tools.zip"
    $AdbUrl = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
    Invoke-WebRequest -Uri $AdbUrl -OutFile $ZipPath
    Expand-Archive -Path $ZipPath -DestinationPath $RepoRoot -Force
    Remove-Item $ZipPath -Force
    Write-Host "      ADB tools downloaded and unpacked to: $PlatformToolsDir" -ForegroundColor Green
} else {
    Write-Host "[1/5] Platform-tools directory already verified." -ForegroundColor Green
}

# 2. Verify / Auto-Install Python 3.11 via Winget or UV
Write-Host "[2/5] Checking Python 3 runtime..." -ForegroundColor Yellow
$pyPath = "python"
$localVenv = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if ((Test-Path $localVenv) -and (Test-PythonExecutable $localVenv)) {
    $pyPath = $localVenv
    $pyDir = Split-Path $localVenv
    $env:Path = "$pyDir;$env:Path"
} elseif (-not (Test-PythonExecutable $pyPath)) {
    # Check common install locations first
    $pyCands = @(
        "$env:APPDATA\uv\python\cpython-3.11-windows-x86_64-none\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "C:\Program Files\Python311\python.exe",
        "C:\Program Files\Python312\python.exe",
        "C:\Program Files\Python310\python.exe"
    )
    foreach ($cand in $pyCands) {
        if ((Test-Path $cand) -and (Test-PythonExecutable $cand)) {
            $pyPath = $cand
            $pyDir = Split-Path $cand
            $scriptsDir = Join-Path $pyDir "Scripts"
            $env:Path = "$pyDir;$scriptsDir;$env:Path"
            break
        }
    }
}

if (-not (Test-PythonExecutable $pyPath)) {
    Write-Host "      Checking uv Python package manager..." -ForegroundColor Yellow
    $uvExe = "$HOME\.local\bin\uv.exe"
    if (-not (Test-Path $uvExe)) {
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    }
    if (Test-Path $uvExe) {
        & $uvExe python install 3.11
        & $uvExe venv $RepoRoot\.venv --python 3.11
        $localVenv = Join-Path $RepoRoot ".venv\Scripts\python.exe"
        if (Test-Path $localVenv) {
            $pyPath = $localVenv
            $pyDir = Split-Path $localVenv
            $env:Path = "$pyDir;$env:Path"
        }
    }
}

if (-not (Test-PythonExecutable $pyPath)) {
    Write-Host "      Python not found. Auto-installing Python 3.11 via winget..." -ForegroundColor Yellow
    winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
    Start-Sleep -Seconds 3

    # Refresh PATH from system and check locations
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $pyCands = @(
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "C:\Program Files\Python311\python.exe"
    )
    foreach ($cand in $pyCands) {
        if (Test-Path $cand) {
            $pyPath = $cand
            $pyDir = Split-Path $cand
            $scriptsDir = Join-Path $pyDir "Scripts"
            $env:Path = "$pyDir;$scriptsDir;$env:Path"
            break
        }
    }
}

$pyVer = & $pyPath --version 2>&1
Write-Host "      Using: $pyVer ($pyPath)" -ForegroundColor Green

# 3. Install PyInstaller & dependencies
Write-Host "[3/5] Installing PyInstaller and application build dependencies..." -ForegroundColor Yellow
& $pyPath -m pip install --upgrade pip
& $pyPath -m pip install --upgrade pyinstaller customtkinter pillow pyyaml psutil requests fastapi uvicorn pydantic

# 4. Compile Standalone Application via PyInstaller spec
Write-Host "[4/5] Compiling standalone executable via PyInstaller spec..." -ForegroundColor Yellow
taskkill /F /IM adb.exe 2>$null
taskkill /F /IM HEART_Studio.exe 2>$null
Start-Sleep -Milliseconds 500
Remove-Item -Path (Join-Path $RepoRoot "dist\HEART_Studio") -Recurse -Force -ErrorAction SilentlyContinue

& $pyPath -m PyInstaller --noconfirm HEART_Studio.spec

# Copy local platform-tools into dist folder so ADB works out of the box
$DistPlatformTools = Join-Path $RepoRoot "dist\HEART_Studio\platform-tools"
if (Test-Path $PlatformToolsDir) {
    Copy-Item -Path $PlatformToolsDir -Destination $DistPlatformTools -Recurse -Force
    Write-Host "      Copied bundled ADB tools into dist package." -ForegroundColor Green
}

# 5. Check / Auto-Install Inno Setup Compiler (ISCC.exe)
Write-Host "[5/5] Generating single-click Setup installer..." -ForegroundColor Yellow
$foundIscc = $null
$cands = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
foreach ($c in $cands) {
    if ($c -and (Test-Path $c)) {
        $foundIscc = $c
        break
    }
}

if (-not $foundIscc) {
    Write-Host "      Inno Setup not detected. Auto-installing Inno Setup via winget..." -ForegroundColor Yellow
    winget install JRSoftware.InnoSetup --silent --accept-package-agreements --accept-source-agreements
    Start-Sleep -Seconds 3
    foreach ($c in $cands) {
        if ($c -and (Test-Path $c)) {
            $foundIscc = $c
            break
        }
    }
}

if ($foundIscc) {
    Write-Host "      Compiling with Inno Setup: $foundIscc" -ForegroundColor Gray
    $IssScript = Join-Path $RepoRoot "installer\HEART_Studio_Installer.iss"
    & "$foundIscc" "$IssScript"
    Write-Host "`n===============================================================================" -ForegroundColor Green
    Write-Host " [SUCCESS] All-in-One Standalone Installer generated at:" -ForegroundColor Green
    Write-Host "   $(Join-Path $RepoRoot 'dist_installer\HEART_Studio_Setup_v1.0.exe')" -ForegroundColor Cyan
    Write-Host "===============================================================================`n" -ForegroundColor Green
} else {
    Write-Host "`n[NOTE] Standalone portable application compiled successfully in: dist\HEART_Studio\`n" -ForegroundColor Green
}
