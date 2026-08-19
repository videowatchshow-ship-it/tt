#!/bin/bash
echo "============================================"
echo "  CVAmp (Crude Viewer Amplifier) Launcher"
echo "============================================"
echo

cd "$(dirname "$0")"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 is not installed."
    echo "Install with: sudo apt install python3 python3-pip (Ubuntu/Debian)"
    echo "         or: brew install python (macOS)"
    exit 1
fi

# Check dependencies
if ! python3 -c "import playwright" &> /dev/null; then
    echo "[INFO] Installing dependencies..."
    pip3 install playwright==1.43.0 psutil toml sv-ttk python-dateutil
    echo "[INFO] Installing Playwright Chromium..."
    python3 -m playwright install chromium
fi

# Check proxy
if [ ! -f "proxy/proxy_list.txt" ] || [ ! -s "proxy/proxy_list.txt" ]; then
    echo "[WARNING] proxy/proxy_list.txt is missing or empty."
    echo "Add proxies in format: ip:port:username:password"
    echo
fi

echo "[INFO] Starting CVAmp..."
python3 main_gui.py
