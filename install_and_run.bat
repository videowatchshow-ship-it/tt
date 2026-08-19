@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title CVAmp Setup

echo ============================================
echo   CVAmp - Auto Installer
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Downloading Python 3.11.9 installer...
    echo.
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python_installer.exe'"
    if not exist "%TEMP%\python_installer.exe" (
        echo Download failed. Install manually:
        echo https://www.python.org/downloads/release/python-3119/
        pause
        exit /b 1
    )
    echo Installing Python... Please wait...
    "%TEMP%\python_installer.exe" /passive InstallAllUsers=0 PrependPath=1 Include_test=0
    echo.
    echo Python installed. CLOSE THIS WINDOW AND DOUBLE-CLICK install_and_run.bat AGAIN.
    pause
    exit /b 0
)

python --version
echo.

REM Install dependencies
echo Checking dependencies...
python -c "import playwright" >nul 2>&1
if errorlevel 1 (
    echo Installing packages...
    pip install playwright==1.43.0 psutil toml sv-ttk python-dateutil
    echo Installing Chromium browser...
    python -m playwright install chromium
    echo.
)

REM Create proxy folder
if not exist "proxy" mkdir proxy
if not exist "proxy\proxy_list.txt" type nul > proxy\proxy_list.txt

echo ============================================
echo   Starting CVAmp GUI...
echo ============================================
echo.
python main_gui.py
if errorlevel 1 (
    echo.
    echo Something went wrong. Check cvamp.log
    pause
)
