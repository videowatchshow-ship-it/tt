@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title CVAmp Viewer Bot Launcher
echo ============================================
echo   CVAmp - Original GUI YouTube Bot
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11.x
    echo https://www.python.org/downloads/
    echo "Add Python to PATH" check required.
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

REM Check Chrome
where chrome >nul 2>&1
if errorlevel 1 (
    if not exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
        if not exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
            echo [WARNING] Chrome not detected. CVAmp requires Google Chrome.
            echo https://www.google.com/chrome/
            echo.
        )
    )
)

REM Check proxy file
if not exist "proxy\proxy_list.txt" (
    echo [ERROR] proxy\proxy_list.txt not found!
    echo Create the file and add proxies: ip:port:username:password
    pause
    exit /b 1
)

echo CVAmp starting. Please wait for GUI...
echo.
python main_gui.py
if errorlevel 1 (
    echo.
    echo [ERROR] CVAmp crashed. Check cvamp.log for details.
    pause
)
