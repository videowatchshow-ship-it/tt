# -*- coding: utf-8 -*-
# CVAmp headless pipeline runner — validates and spawns in parallel, auto-replaces dead instances.
# Usage: python run_bot.py https://www.youtube.com/watch?v=VIDEO_ID [count]
import sys, os, time, threading, random, logging, queue

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "")

from concurrent.futures import ThreadPoolExecutor, as_completed
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
]

lock = threading.Lock()
stats = {"alive": 0, "watching": 0, "failed": 0, "total_spawned": 0}
ready_queue = queue.Queue()  # validated proxies ready to spawn


def load_proxies():
    if not os.path.exists(PROXY_FILE):
        log.error(f"프록시 파일 없음: {PROXY_FILE}")
        return []
    with open(PROXY_FILE) as f:
        proxies = [line.strip() for line in f if line.strip()]
    log.info(f"프록시 {len(proxies)}개 로드됨")
    return proxies


def validate_proxy_real(proxy_str, test_url, timeout=15):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=CHROMIUM_ARGS,
                proxy={"server": f"http://{proxy_str}"},
            )
            ctx = browser.new_context(
                viewport={"width": 800, "height": 600},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            )
            page = ctx.new_page()
            page.add_init_script("navigator.webdriver = false;")
            page.goto(test_url, timeout=timeout * 1000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            has_player = page.query_selector("ytd-player, #movie_player, video")
            browser.close()
            if has_player:
                return proxy_str
    except Exception:
        pass
    return None


def validator_thread(target_url, target_count, stop_event):
    """백그라운드 검증 스레드: 계속 프록시를 검증해서 ready_queue에 넣음"""
    used = set()
    while not stop_event.is_set():
        proxies = load_proxies()
        if not proxies:
            log.warning("프록시 파일 비어있음, 10초 후 재시도")
            time.sleep(10)
            continue

        random.shuffle(proxies)
        fresh = [p for p in proxies if p not in used]
        if not fresh:
            log.info("모든 프록시 사용됨, used 초기화 후 재시도")
            used.clear()
            fresh = proxies[:]
            random.shuffle(fresh)

        for batch_start in range(0, len(fresh), 200):
            if stop_event.is_set():
                return
            batch = fresh[batch_start:batch_start + 200]
            log.info(f"[검증기] {len(batch)}개 검증 시작 (큐 대기: {ready_queue.qsize()}, alive: {stats['alive']})")

            with ThreadPoolExecutor(max_workers=25) as ex:
                futures = {ex.submit(validate_proxy_real, p, target_url): p for p in batch}
                for fut in as_completed(futures):
                    result = fut.result()
                    if result and result not in used:
                        used.add(result)
                        ready_queue.put(result)
                        log.info(f"  ✓ 검증 통과: {result} (큐: {ready_queue.qsize()})")

            # alive가 목표 이상이면 검증 속도 줄임
            if stats["alive"] >= target_count:
                time.sleep(15)


def run_viewer(proxy_str, target_url, instance_id):
    try:
        with sync_playwright() as p:
            launch_opts = {
                "headless": True,
                "args": CHROMIUM_ARGS + ["--window-position=0,0"],
            }
            if proxy_str:
                launch_opts["proxy"] = {"server": f"http://{proxy_str}"}

            browser = p.chromium.launch(**launch_opts)
            major = browser.version.split(".")[0]
            ctx = browser.new_context(
                viewport={"width": 800, "height": 600},
                user_agent=f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36",
            )
            page = ctx.new_page()
            page.add_init_script("navigator.webdriver = false;")

            page.goto("https://www.youtube.com/", timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            dismiss_consent(page)

            now_ms = str(int(time.time() * 1000))
            far_future = str(int(time.time() * 1000) + 365 * 86400 * 1000)
            quality_val = '{"data":"{\\"quality\\":144,\\"previousQuality\\":144}","expiration":' + far_future + ',"creation":' + now_ms + '}'
            page.evaluate(f"window.localStorage.setItem('yt-player-quality', '{quality_val}');")

            page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            dismiss_consent(page)

            try:
                page.wait_for_selector("ytd-player, #movie_player, video", timeout=30000)
            except Exception:
                log.warning(f"[#{instance_id}] 플레이어 못 찾음")

            page.wait_for_timeout(2000)

            try:
                if page.evaluate('(() => { const p = document.querySelector("div#movie_player"); return p && p.classList.contains("paused-mode"); })()'):
                    page.keyboard.press("Space")
            except Exception:
                pass

            with lock:
                stats["alive"] += 1
                stats["total_spawned"] += 1
            log.info(f"[#{instance_id}] 시작됨 (proxy: {proxy_str}) | alive={stats['alive']} watching={stats['watching']}")

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
        log.warning(f"[#{instance_id}] 실패: {str(e)[:80]}")
    finally:
        with lock:
            stats["alive"] = max(0, stats["alive"] - 1)
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
                page.wait_for_timeout(1500)
                return
        except Exception:
            pass


def main():
    if len(sys.argv) < 2:
        print("사용법: python run_bot.py <YouTube_URL> [목표_수]")
        print("예: python run_bot.py https://www.youtube.com/watch?v=QfDaqmb_1Zg 100")
        sys.exit(1)

    target_url = sys.argv[1]
    if "/@" in target_url and "/live" not in target_url:
        target_url = target_url.rstrip("/") + "/live"
        log.info(f"채널 URL 감지 → 라이브 URL로 변환: {target_url}")
    target_count = int(sys.argv[2]) if len(sys.argv) > 2 else 100

    log.info(f"=== CVAmp 파이프라인 봇 시작 ===")
    log.info(f"URL: {target_url}")
    log.info(f"목표: {target_count}명")

    proxies = load_proxies()
    if not proxies:
        log.error("프록시가 없습니다. 먼저 proxy_updater.py를 실행하세요.")
        sys.exit(1)
    log.info(f"프록시 {len(proxies)}개 준비됨")

    stop_event = threading.Event()

    # 검증 스레드 시작 (백그라운드에서 계속 검증)
    vt = threading.Thread(target=validator_thread, args=(target_url, target_count, stop_event), daemon=True)
    vt.start()
    log.info("검증 스레드 시작됨 — 검증과 스폰이 동시 진행됩니다")

    # 스폰 루프: ready_queue에서 꺼내서 바로 스폰
    next_id = 0
    try:
        while True:
            # 목표 미달이면 빠르게 스폰, 달성이면 교체만
            need = target_count - stats["alive"]
            if need <= 0:
                time.sleep(5)
                log.info(f"[상태] alive={stats['alive']} watching={stats['watching']} failed={stats['failed']} total={stats['total_spawned']} | 목표 달성, 대기 중")
                continue

            try:
                proxy = ready_queue.get(timeout=5)
            except queue.Empty:
                log.info(f"[상태] alive={stats['alive']} watching={stats['watching']} failed={stats['failed']} | 검증 대기 중... (need {need})")
                continue

            next_id += 1
            t = threading.Thread(target=run_viewer, args=(proxy, target_url, next_id), daemon=True)
            t.start()

            if next_id % 5 == 0:
                log.info(f"[스폰] #{next_id} | alive={stats['alive']} watching={stats['watching']} need={need}")

            time.sleep(1.0)

    except KeyboardInterrupt:
        log.info("사용자 중단 (Ctrl+C)")
        stop_event.set()


if __name__ == "__main__":
    main()
