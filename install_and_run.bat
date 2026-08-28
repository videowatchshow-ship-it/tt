@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title CVAmp

echo ============================================
echo   CVAmp - Auto Installer
echo ============================================
echo.
echo Current folder: %cd%
echo.

REM ---- Step 1: Check Python ----
echo [Step 1] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  !! Python is NOT installed !!
    echo.
    echo  Downloading Python 3.11.9 installer...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python_installer.exe'" 2>nul
    if not exist "%TEMP%\python_installer.exe" (
        echo  Download failed.
        echo  Please install Python manually from:
        echo  https://www.python.org/downloads/release/python-3119/
        echo  CHECK "Add python.exe to PATH" during install!
        echo.
        pause
        exit /b 1
    )
    echo  Installing Python...
    start /wait "" "%TEMP%\python_installer.exe" /passive InstallAllUsers=0 PrependPath=1 Include_test=0
    del "%TEMP%\python_installer.exe" >nul 2>&1
    echo.
    echo  !! Python installed. You MUST close this window and
    echo  !! double-click install_and_run.bat AGAIN.
    echo.
    pause
    exit /b 0
)
python --version
echo.

REM ---- Step 2: Install packages ----
echo [Step 2] Checking packages...
python -c "import playwright" >nul 2>&1
if errorlevel 1 (
    echo  Installing packages... please wait...
    pip install playwright==1.43.0 psutil toml sv-ttk python-dateutil
    if errorlevel 1 (
        echo  pip install FAILED.
        echo  Try running CMD as Administrator.
        pause
        exit /b 1
    )
    echo  Installing Chromium browser... please wait...
    python -m playwright install chromium
    if errorlevel 1 (
        echo  Chromium install FAILED.
        pause
        exit /b 1
    )
    echo  Done.
    echo.
)

REM ---- Step 3: Proxy folder ----
echo [Step 3] Checking proxy folder...
if not exist "proxy" mkdir proxy
if not exist "proxy\proxy_list.txt" type nul > proxy\proxy_list.txt
echo  OK
echo.

REM ---- Step 4: Launch ----
echo ============================================
echo  Launching CVAmp GUI...
echo ============================================
echo.
python main_gui.py
echo.
echo  CVAmp has closed.
echo.
pause
