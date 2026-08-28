# -*- coding: utf-8 -*-
# CVAmp headless batch runner — validates proxies, spawns viewers, auto-replaces dead ones.
# Usage: python run_bot.py https://www.youtube.com/watch?v=VIDEO_ID [count]
import sys, os, time, threading, random, logging

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
dead_slots = []  # instance IDs that died and need replacement


def load_proxies():
    if not os.path.exists(PROXY_FILE):
        log.error(f"프록시 파일 없음: {PROXY_FILE}")
        log.error("먼저 python proxy_updater.py 를 실행하세요")
        return []
    with open(PROXY_FILE) as f:
        proxies = [line.strip() for line in f if line.strip()]
    log.info(f"프록시 {len(proxies)}개 로드됨")
    return proxies


def validate_proxy_real(proxy_str, test_url, timeout=20):
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
            page.wait_for_timeout(3000)

            has_player = page.query_selector("ytd-player, #movie_player, video")
            browser.close()
            if has_player:
                return proxy_str
    except Exception:
        pass
    return None


def validate_batch(proxies, test_url, max_workers=20):
    valid = []
    total = len(proxies)
    done = 0
    log.info(f"프록시 {total}개 YouTube 검증 중 (동시 {max_workers}개)...")

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(validate_proxy_real, p, test_url): p for p in proxies}
        for fut in as_completed(futures):
            done += 1
            result = fut.result()
            if result:
                valid.append(result)
                log.info(f"  ✓ 검증 통과: {result} ({len(valid)}개, {done}/{total})")
            elif done % 50 == 0:
                log.info(f"  검증 진행: {done}/{total}, 통과 {len(valid)}개")

    log.info(f"검증 완료: {len(valid)}/{total} 통과")
    return valid


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
            page.wait_for_timeout(2000)
            dismiss_consent(page)

            now_ms = str(int(time.time() * 1000))
            far_future = str(int(time.time() * 1000) + 365 * 86400 * 1000)
            quality_val = '{"data":"{\\"quality\\":144,\\"previousQuality\\":144}","expiration":' + far_future + ',"creation":' + now_ms + '}'
            page.evaluate(f"window.localStorage.setItem('yt-player-quality', '{quality_val}');")

            page.goto(target_url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            dismiss_consent(page)

            try:
                page.wait_for_selector("ytd-player, #movie_player, video", timeout=30000)
            except Exception:
                log.warning(f"[#{instance_id}] 플레이어 못 찾음, 계속 진행")

            page.wait_for_timeout(3000)

            try:
                if page.evaluate('(() => { const p = document.querySelector("div#movie_player"); return p && p.classList.contains("paused-mode"); })()'):
                    page.keyboard.press("Space")
            except Exception:
                pass

            with lock:
                stats["alive"] += 1
                stats["total_spawned"] += 1
            proxy_label = proxy_str or "direct"
            log.info(f"[#{instance_id}] 시작됨 (proxy: {proxy_label}) | alive={stats['alive']} watching={stats['watching']}")

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
        msg = str(e)[:80]
        log.warning(f"[#{instance_id}] 실패: {msg}")
    finally:
        with lock:
            stats["alive"] = max(0, stats["alive"] - 1)
            stats["failed"] += 1
            dead_slots.append(instance_id)


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
                page.wait_for_timeout(2000)
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

    log.info(f"=== CVAmp 헤드리스 봇 시작 ===")
    log.info(f"URL: {target_url}")
    log.info(f"목표: {target_count}명")

    all_proxies = load_proxies()
    if not all_proxies:
        log.error("프록시가 없습니다. 먼저 proxy_updater.py를 실행하세요.")
        sys.exit(1)

    random.shuffle(all_proxies)

    # 사용한 프록시 추적
    used_proxies = set()
    proxy_idx = [0]  # mutable for closure

    def get_fresh_proxies(count):
        """사용 안 한 프록시 가져오기, 다 쓰면 파일 다시 로드"""
        batch = []
        while len(batch) < count:
            if proxy_idx[0] >= len(all_proxies):
                log.info("프록시 전부 사용됨, 파일 다시 로드...")
                fresh = load_proxies()
                if not fresh:
                    break
                random.shuffle(fresh)
                all_proxies.clear()
                all_proxies.extend(fresh)
                used_proxies.clear()
                proxy_idx[0] = 0

            p = all_proxies[proxy_idx[0]]
            proxy_idx[0] += 1
            if p not in used_proxies:
                batch.append(p)
        return batch

    # 1단계: 초기 검증
    validated = []
    log.info(f"--- 1단계: 프록시 검증 (목표 {target_count}개) ---")
    while len(validated) < target_count:
        batch = get_fresh_proxies(200)
        if not batch:
            break
        new_valid = validate_batch(batch, target_url, max_workers=20)
        for p in new_valid:
            used_proxies.add(p)
        validated.extend(new_valid)
        log.info(f"검증 누적: {len(validated)}/{target_count}")
        if len(validated) >= target_count:
            break

    if not validated:
        log.error("검증 통과한 프록시가 하나도 없습니다.")
        sys.exit(1)

    validated = validated[:target_count]
    log.info(f"--- 2단계: {len(validated)}개 시청 인스턴스 생성 ---")

    # 2단계: 스폰
    next_id = [0]
    for proxy in validated:
        next_id[0] += 1
        t = threading.Thread(target=run_viewer, args=(proxy, target_url, next_id[0]), daemon=True)
        t.start()
        if next_id[0] % 10 == 0:
            log.info(f"생성 진행: {next_id[0]}/{len(validated)} | alive={stats['alive']} watching={stats['watching']}")
        time.sleep(1.3)

    log.info(f"=== 초기 스폰 완료: {len(validated)}개 ===")

    # 3단계: 모니터링 + 자동 교체
    try:
        while True:
            time.sleep(30)
            log.info(f"[상태] alive={stats['alive']} watching={stats['watching']} failed={stats['failed']} total={stats['total_spawned']}")

            # 죽은 슬롯 교체
            with lock:
                to_replace = len(dead_slots)
                dead_slots.clear()

            if to_replace > 0:
                log.info(f"--- 자동 교체: {to_replace}개 죽은 인스턴스 교체 시작 ---")
                batch = get_fresh_proxies(to_replace * 10)
                if batch:
                    new_valid = validate_batch(batch, target_url, max_workers=min(20, len(batch)))
                    for proxy in new_valid[:to_replace]:
                        used_proxies.add(proxy)
                        next_id[0] += 1
                        t = threading.Thread(target=run_viewer, args=(proxy, target_url, next_id[0]), daemon=True)
                        t.start()
                        time.sleep(1.3)
                    replaced = min(len(new_valid), to_replace)
                    log.info(f"교체 완료: {replaced}/{to_replace}개")
                else:
                    log.warning("교체할 프록시 없음")

    except KeyboardInterrupt:
        log.info("사용자 중단 (Ctrl+C)")


if __name__ == "__main__":
    main()
