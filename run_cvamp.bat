@echo off
title CVAmp Viewer Bot Launcher
echo ============================================
echo   CVAmp (Crude Viewer Amplifier) Launcher
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.11.x from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

REM Check if dependencies are installed
python -c "import playwright" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    pip install playwright==1.43.0 psutil toml sv-ttk python-dateutil
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
    echo [INFO] Installing Playwright Chromium browser...
    python -m playwright install chromium
    if errorlevel 1 (
        echo [ERROR] Failed to install Playwright browser.
        pause
        exit /b 1
    )
)

REM Check Chrome
where chrome >nul 2>&1
if errorlevel 1 (
    if not exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
        if not exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
            echo [WARNING] Google Chrome not detected. CVAmp requires Chrome.
            echo Please install Chrome from https://www.google.com/chrome/
            echo.
        )
    )
)

REM Check proxy file
if not exist "proxy\proxy_list.txt" (
    echo [WARNING] proxy\proxy_list.txt not found or empty.
    echo Please add your HTTP proxies in format: ip:port:username:password
    echo.
)

echo [INFO] Starting CVAmp...
echo.
cd /d "%~dp0"
python main_gui.py
if errorlevel 1 (
    echo.
    echo [ERROR] CVAmp exited with an error. Check cvamp.log for details.
    pause
)
