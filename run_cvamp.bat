@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title CVAmp Viewer Bot
echo ============================================
echo   CVAmp - Crude Viewer Amplifier
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11.x
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Install dependencies if missing
python -c "import playwright" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    pip install playwright==1.43.0 psutil toml sv-ttk python-dateutil
    if errorlevel 1 (
        echo [ERROR] pip install failed.
        pause
        exit /b 1
    )
    echo [INFO] Installing Playwright Chromium...
    python -m playwright install chromium
    if errorlevel 1 (
        echo [ERROR] Playwright install failed.
        pause
        exit /b 1
    )
)

if not exist "proxy\proxy_list.txt" (
    echo [INFO] No proxy file found. Running without proxies.
    if not exist "proxy" mkdir proxy
    type nul > proxy\proxy_list.txt
)

echo [INFO] Starting CVAmp GUI...
echo.
python main_gui.py
if errorlevel 1 (
    echo.
    echo [ERROR] CVAmp crashed. Check cvamp.log
    pause
)
