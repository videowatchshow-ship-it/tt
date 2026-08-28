# -*- coding: utf-8 -*-
# CVAmp turbo runner — skip pre-validation, spawn directly, replace failures instantly.
# Target: 100 alive viewers within 7 minutes.
# Usage: python run_bot.py https://www.youtube.com/watch?v=VIDEO_ID [count]
import sys, os, time, threading, random, logging, queue

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

# proxy feeder
proxy_queue = queue.Queue()
stop_event = threading.Event()


def load_proxies():
    if not os.path.exists(PROXY_FILE):
        return []
    with open(PROXY_FILE) as f:
        return [line.strip() for line in f if line.strip()]


def proxy_feeder():
    """끊임없이 프록시를 proxy_queue에 공급"""
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
    """스폰 즉시 시도. 실패하면 바로 리턴 (교체 대상)"""
    success = False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=CHROMIUM_ARGS + ["--window-position=0,0"],
                proxy={"server": f"http://{proxy_str}"},
            )
            major = browser.version.split(".")[0]
            ctx = browser.new_context(
                viewport={"width": 640, "height": 360},
                user_agent=f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36",
            )
            page = ctx.new_page()
            page.add_init_script("navigator.webdriver = false;")

            # youtube 홈 → localStorage 설정 → 타겟 이동
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
                    log.info(f"[#{instance_id}] ▶ 시청 중 | alive={stats['alive']} watching={stats['watching']}")
                elif not watching and was_watching:
                    with lock:
                        stats["watching"] = max(0, stats["watching"] - 1)

    except Exception as e:
        log.debug(f"[#{instance_id}] fail: {str(e)[:60]}")
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


def spawner_wave(target_url, target_count, wave_size):
    """wave_size개를 동시에 스폰 시도. 성공한 것만 살아남음."""
    threads = []
    for i in range(wave_size):
        try:
            proxy = proxy_queue.get(timeout=2)
        except queue.Empty:
            break
        iid = stats["total_spawned"] + stats["failed"] + i + 1
        t = threading.Thread(target=run_viewer, args=(proxy, target_url, iid), daemon=True)
        t.start()
        threads.append(t)
    return threads


def main():
    if len(sys.argv) < 2:
        print("사용법: python run_bot.py <YouTube_URL> [목표_수]")
        print("예: python run_bot.py https://www.youtube.com/watch?v=QfDaqmb_1Zg 100")
        sys.exit(1)

    target_url = sys.argv[1]
    if "/@" in target_url and "/live" not in target_url:
        target_url = target_url.rstrip("/") + "/live"
        log.info(f"채널 URL → 라이브: {target_url}")
    target_watching = int(sys.argv[2]) if len(sys.argv) > 2 else 200

    log.info(f"=== CVAmp TURBO 모드 ===")
    log.info(f"URL: {target_url}")
    log.info(f"목표: 시청자 {target_watching}명 (7분 내)")

    proxies = load_proxies()
    if not proxies:
        log.error("프록시 없음. proxy_updater.py 먼저 실행.")
        sys.exit(1)
    log.info(f"프록시 {len(proxies)}개 준비됨")

    # 프록시 공급 스레드
    ft = threading.Thread(target=proxy_feeder, daemon=True)
    ft.start()

    t0 = time.time()

    # 전략: 웨이브 방식으로 대량 동시 스폰
    # 무료 프록시 성공률 ~5% → 100개 성공하려면 ~2000개 시도
    # 동시 50개씩 웨이브, 각 웨이브 사이 3초 대기
    # 50개 × 40웨이브 = 2000개 시도, 40 × 3초 = 120초 + 스폰시간 ~5분 = 총 ~7분

    WAVE_SIZE = 30  # 동시 스폰 수 (안전하게)
    WAVE_PAUSE = 10  # 웨이브 사이 대기 — 이전 웨이브 실패분 정리 시간
    MAX_ALIVE = target_watching * 3

    log.info(f"웨이브 모드: {WAVE_SIZE}개씩 동시 스폰, alive 상한 {MAX_ALIVE}")

    try:
        wave = 0
        while True:
            elapsed = round(time.time() - t0)

            if stats["watching"] >= target_watching:
                log.info(f"[{elapsed}s] ★ 목표 달성! watching={stats['watching']}/{target_watching} alive={stats['alive']} failed={stats['failed']}")
                time.sleep(10)
                continue

            if stats["alive"] >= MAX_ALIVE:
                log.info(f"[{elapsed}s] alive 상한 도달 ({stats['alive']}), watching={stats['watching']}/{target_watching} 대기 중...")
                time.sleep(5)
                continue

            wave += 1
            alive_room = MAX_ALIVE - stats["alive"]
            spawn_count = min(WAVE_SIZE, alive_room)
            log.info(f"[{elapsed}s] 웨이브 #{wave}: {spawn_count}개 스폰 | alive={stats['alive']} watching={stats['watching']}/{target_watching} failed={stats['failed']}")

            spawner_wave(target_url, target_watching, spawn_count)
            time.sleep(WAVE_PAUSE)

            if elapsed > 420 and stats["watching"] < target_watching:
                log.warning(f"[{elapsed}s] 7분 초과! watching={stats['watching']}/{target_watching}")

    except KeyboardInterrupt:
        log.info("사용자 중단 (Ctrl+C)")
        stop_event.set()


if __name__ == "__main__":
    main()
