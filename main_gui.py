import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

def check_and_install():
    missing = []
    for mod in ["playwright", "psutil", "toml", "sv_ttk", "dateutil"]:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)

    if missing:
        print("[SETUP] Installing dependencies...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "playwright==1.43.0", "psutil", "toml", "sv-ttk", "python-dateutil"
        ])
        print("[SETUP] Installing Chromium browser...")
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("[SETUP] Done! Restarting...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    proxy_dir = os.path.join(os.getcwd(), "proxy")
    if not os.path.exists(proxy_dir):
        os.makedirs(proxy_dir)
    proxy_file = os.path.join(proxy_dir, "proxy_list.txt")
    if not os.path.exists(proxy_file):
        open(proxy_file, "w").close()

check_and_install()

from cvamp.gui import GUI
from cvamp.manager import InstanceManager

SPAWNER_THREAD_COUNT = 3
CLOSER_THREAD_COUNT = 10
PROXY_FILE_NAME = "proxy_list.txt"
HEADLESS = True
AUTO_RESTART = False
SPAWN_INTERVAL_SECONDS = 2

manager = InstanceManager(
    spawn_thread_count=SPAWNER_THREAD_COUNT,
    delete_thread_count=CLOSER_THREAD_COUNT,
    headless=HEADLESS,
    auto_restart=AUTO_RESTART,
    proxy_file_name=PROXY_FILE_NAME,
    spawn_interval_seconds=SPAWN_INTERVAL_SECONDS,
)

print("Available proxies", len(manager.proxies.proxy_list))
print("Available window locations", len(manager.screen.spawn_locations))

GUI(manager).run()
