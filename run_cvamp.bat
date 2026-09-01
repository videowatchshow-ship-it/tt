@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title CVAmp Launcher
echo ============================================
echo   CVAmp - Crude Viewer Amplifier
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

python -c "import playwright" >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing dependencies...
    pip install playwright==1.43.0 psutil toml sv-ttk python-dateutil
    python -m playwright install chromium
)

if not exist "proxy" mkdir proxy
if not exist "proxy\proxy_list.txt" type nul > proxy\proxy_list.txt

echo [OK] Launching CVAmp GUI...
python main_gui.py
if errorlevel 1 (
    echo [ERROR] See cvamp.log for details.
    pause
)
