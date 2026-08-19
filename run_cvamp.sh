#!/bin/bash
echo "============================================"
echo "  CVAmp - Crude Viewer Amplifier"
echo "============================================"
echo

cd "$(dirname "$0")"

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 not installed."
    exit 1
fi

if ! python3 -c "import playwright" &> /dev/null; then
    echo "[INFO] Installing dependencies..."
    pip3 install playwright==1.43.0 psutil toml sv-ttk python-dateutil
    python3 -m playwright install chromium
fi

if [ ! -f "proxy/proxy_list.txt" ]; then
    echo "[INFO] No proxy file found. Running without proxies."
    mkdir -p proxy
    touch proxy/proxy_list.txt
fi

echo "[INFO] Starting CVAmp GUI..."
python3 main_gui.py
