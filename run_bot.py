# -*- coding: utf-8 -*-
# CVAmp turbo runner — sequential spawning to prevent OOM.
# Target: 200 watching viewers.
# Usage: python run_bot.py https://www.youtube.com/watch?v=VIDEO_ID [count]
import sys, os, time, threading, random, logging, queue, ctypes

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "")

from playwright.sync_api import sync_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("run_bot.log", encoding="utf-8"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
PROXY_FILE = os.path.join(HERE, "proxy", "proxy_list.txt")

CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--no-first-run",
    "--disable-blink-features=AutomationControlled",
    "--mute-audio",
    "--webrtc-ip-handling-policy=disable_non_proxied_udp",
    "--force-webrtc-ip-handling-policy",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-site-isolation-trials",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    "--disable-extensions",
    "--disable-component-extensions-with-background-pages",
    "--disable-default-apps",
    "--disable-breakpad",
    "--disable-hang-monitor",
    "--disable-prompt-on-repost",
    "--disable-sync",
    "--disable-translate",
    "--metrics-recording-only",
    "--no-default-browser-check",
    "--js-flags=--max-old-space-size=128",
]

lock = threading.Lock()
stats = {"alive": 0, "watching": 0, "failed": 0, "total_spawned": 0}

proxy_queue = queue.Queue()
stop_event = threading.Event()

# 동시 스폰 중인 인스턴스 수 제한 (OOM 방지)
spawn_semaphore = threading.Semaphore(5)


def get_free_memory_gb():
    try:
        if sys.platform == "win32":
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return stat.ullAvailPhys / (1024 ** 3)
        else:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) / (1024 ** 2)
    except Exception:
        pass
    return 99.0


def load_proxies():
    if not os.path.exists(PROXY_FILE):
        return []
    with open(PROXY_FILE) as f:
        return [line.strip() for line in f if line.strip()]


def proxy_feeder():
    while not stop_event.is_set():
        proxies = load_proxies()
        if not proxies:
            time.sleep(5)
            continue
        random.shuffle(proxies)
        for p in proxies:
            if stop_event.is_set():
                return
            proxy_queue.put(p)
        time.sleep(1)


def run_viewer(proxy_str, target_url, instance_id):
    success = False
    try:
        spawn_semaphore.acquire()
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=CHROMIUM_ARGS + ["--window-position=0,0"],
                proxy={"server": f"http://{proxy_str}"},
            )
            spawn_semaphore.release()
            released = True

            major = browser.version.split(".")[0]
            ctx = browser.new_context(
                viewport={"width": 640, "height": 360},
                user_agent=f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36",
            )
            page = ctx.new_page()
            page.add_init_script("navigator.webdriver = false;")

            page.goto("https://www.youtube.com/", timeout=15000, wait_until="domcontentloaded")
            page.wait_for_timeout(1000)
            dismiss_consent(page)

            now_ms = str(int(time.time() * 1000))
            far_future = str(int(time.time() * 1000) + 365 * 86400 * 1000)
            quality_val = '{"data":"{\\"quality\\":144,\\"previousQuality\\":144}","expiration":' + far_future + ',"creation":' + now_ms + '}'
            page.evaluate(f"window.localStorage.setItem('yt-player-quality', '{quality_val}');")

            page.goto(target_url, timeout=25000, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            dismiss_consent(page)

            try:
                page.wait_for_selector("ytd-player, #movie_player, video", timeout=15000)
            except Exception:
                browser.close()
                return

            page.wait_for_timeout(1000)

            try:
                if page.evaluate('(() => { const p = document.querySelector("div#movie_player"); return p && p.classList.contains("paused-mode"); })()'):
                    page.keyboard.press("Space")
            except Exception:
                pass

            with lock:
                stats["alive"] += 1
                stats["total_spawned"] += 1
            success = True
            log.info(f"[#{instance_id}] ✓ alive (proxy: {proxy_str}) | alive={stats['alive']} watching={stats['watching']}")

            last_resume = 0
            watching = False
            while True:
                page.wait_for_timeout(10000)

                try:
                    page.click("button.ytp-ad-skip-button-modern", timeout=100)
                except Exception:
                    pass

                if page.query_selector('div.html5-video-player:not(.playing-mode)'):
                    page.keyboard.press("Space")

                dismiss_consent(page)

                try:
                    cur = int(page.evaluate('''() => {
                        const el = document.querySelector(".ytp-progress-bar");
                        return el ? el.getAttribute("aria-valuenow") : 0;
                    }'''))
                except Exception:
                    cur = 0

                was_watching = watching
                if cur > last_resume:
                    last_resume = cur
                    watching = True
                else:
                    watching = False

                if watching and not was_watching:
                    with lock:
                        stats["watching"] += 1
                    log.info(f"[#{instance_id}] ▶ watching | alive={stats['alive']} watching={stats['watching']}")
                elif not watching and was_watching:
                    with lock:
                        stats["watching"] = max(0, stats["watching"] - 1)

    except Exception as e:
        log.debug(f"[#{instance_id}] fail: {str(e)[:60]}")
        if not locals().get("released"):
            spawn_semaphore.release()
    finally:
        if success:
            with lock:
                stats["alive"] = max(0, stats["alive"] - 1)
        with lock:
            stats["failed"] += 1


def dismiss_consent(page):
    for sel in [
        'button[aria-label="Accept all"]',
        'button[aria-label="Accept the use of cookies and other data for the purposes described"]',
        'form[action="https://consent.youtube.com/save"] button',
    ]:
        try:
            btn = page.query_selector(sel)
            if btn:
                btn.click()
                page.wait_for_timeout(1000)
                return
        except Exception:
            pass


def main():
    if len(sys.argv) < 2:
        print("사용법: python run_bot.py <YouTube_URL> [목표_수]")
        sys.exit(1)

    target_url = sys.argv[1]
    if "/@" in target_url and "/live" not in target_url:
        target_url = target_url.rstrip("/") + "/live"
        log.info(f"채널 URL → 라이브: {target_url}")
    target_watching = int(sys.argv[2]) if len(sys.argv) > 2 else 200

    log.info(f"=== CVAmp 순차 스폰 모드 ===")
    log.info(f"URL: {target_url}")
    log.info(f"목표: 시청자 {target_watching}명")

    proxies = load_proxies()
    if not proxies:
        log.error("프록시 없음. proxy_updater.py 먼저 실행.")
        sys.exit(1)
    log.info(f"프록시 {len(proxies)}개 준비됨")

    ft = threading.Thread(target=proxy_feeder, daemon=True)
    ft.start()

    t0 = time.time()

    # 동시 스폰 최대 5개 (세마포어), 1초 간격으로 새 스레드 생성
    # MAX_ALIVE 제한으로 메모리 보호
    MAX_ALIVE = min(target_watching * 2, 400)
    SPAWN_DELAY = 1.0  # 새 인스턴스 간 1초 대기
    iid = 0

    log.info(f"순차 모드: 1초 간격 스폰, 동시 초기화 최대 5개, alive 상한 {MAX_ALIVE}")

    try:
        while True:
            elapsed = round(time.time() - t0)

            if stats["watching"] >= target_watching:
                log.info(f"[{elapsed}s] ★ 목표 달성! watching={stats['watching']}/{target_watching} alive={stats['alive']} failed={stats['failed']}")
                time.sleep(10)
                continue

            if stats["alive"] >= MAX_ALIVE:
                log.info(f"[{elapsed}s] alive 상한 ({stats['alive']}), watching={stats['watching']}/{target_watching} 대기...")
                time.sleep(5)
                continue

            free_mem = get_free_memory_gb()
            if free_mem < 2.0:
                log.warning(f"[{elapsed}s] 메모리 부족 ({free_mem:.1f}GB), 스폰 일시정지...")
                time.sleep(10)
                continue

            try:
                proxy = proxy_queue.get(timeout=2)
            except queue.Empty:
                continue

            iid += 1
            t = threading.Thread(target=run_viewer, args=(proxy, target_url, iid), daemon=True)
            t.start()

            if iid % 20 == 0:
                log.info(f"[{elapsed}s] 스폰 #{iid} | alive={stats['alive']} watching={stats['watching']}/{target_watching} failed={stats['failed']} mem={free_mem:.1f}GB")

            time.sleep(SPAWN_DELAY)

            if elapsed > 420 and stats["watching"] < target_watching:
                log.warning(f"[{elapsed}s] 7분 초과! watching={stats['watching']}/{target_watching}")

    except KeyboardInterrupt:
        log.info("사용자 중단 (Ctrl+C)")
        stop_event.set()


if __name__ == "__main__":
    main()
