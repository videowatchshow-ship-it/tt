import datetime
import json
import logging
import time

from dateutil.relativedelta import relativedelta

from cvamp import utils
from cvamp.instance import Instance

logger = logging.getLogger(__name__)


class Unknown(Instance):
    site_name = "UNKNOWN"
    site_url = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def todo_every_loop(self):
        self.page.keyboard.press("Tab")

    def update_status(self):
        pass

    def todo_after_spawn(self):
        self.goto_with_retry(self.target_url)
        self.page.wait_for_timeout(1000)


class Chzzk(Instance):
    site_name = "CHZZK"
    site_url = "chzzk.naver.com"

    local_storage = {"live-player-video-track": r"""{"label":"360p","kind":"low-latency","width":640,"height":360}"""}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status_info = {}

    def todo_every_loop(self):
        try:
            self.page.click("button.btn_skip", timeout=100)
        except:
            pass

    def update_status(self):
        html = self.page.evaluate('document.querySelector("div#live_player_layout").innerHTML')
        if "pzp-pc--live" in html:
            if "pzp-pc--loading" not in html:
                self.status = utils.InstanceStatus.WATCHING
                return
        self.status = utils.InstanceStatus.BUFFERING

    def todo_after_spawn(self):
        self.goto_with_retry("https://chzzk.naver.com/category")

        self.page.wait_for_timeout(1000)

        for key, value in self.local_storage.items():
            tosend = """window.localStorage.setItem('{key}','{value}');""".format(key=key, value=value)
            self.page.evaluate(tosend)

        self.goto_with_retry(self.target_url)

        self.page.wait_for_selector("#live_player_layout", timeout=30000)
        self.page.wait_for_timeout(1000)
        self.page.keyboard.press("f")

        self.page.set_viewport_size(
            {
                "width": self.location_info["width"],
                "height": self.location_info["height"],
            }
        )

        self.status = utils.InstanceStatus.INITIALIZED

    def todo_after_load(self):
        self.page.wait_for_selector("#live_player_layout", timeout=30000)
        self.page.wait_for_timeout(1000)
        self.page.keyboard.press("f")


class Youtube(Instance):
    site_name = "YOUTUBE"
    site_url = "youtube.com"
    cookie_css = ".eom-button-row.style-scope.ytd-consent-bump-v2-lightbox > ytd-button-renderer:nth-child(1) button"

    now_timestamp_ms = int(time.time() * 1000)
    next_year_timestamp_ms = int((datetime.datetime.now() + relativedelta(years=1)).timestamp() * 1000)
    local_storage = {
        "yt-player-quality": r"""{{"data":"{{\\"quality\\":144,\\"previousQuality\\":144}}","expiration":{0},"creation":{1}}}""".format(
            next_year_timestamp_ms, now_timestamp_ms
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def todo_every_loop(self):
        self._dismiss_consent()

        if self.page.query_selector('div.html5-video-player:not(.playing-mode)'):
            self.page.keyboard.press("Space")

        try:
            self.page.click("button.ytp-ad-skip-button-modern", timeout=100)
        except:
            pass

    def _dismiss_consent(self):
        for selector in [
            self.cookie_css,
            'button[aria-label="Accept all"]',
            'button[aria-label="Accept the use of cookies and other data for the purposes described"]',
            'form[action="https://consent.youtube.com/save"] button',
        ]:
            try:
                btn = self.page.query_selector(selector)
                if btn:
                    btn.click()
                    self.page.wait_for_timeout(2000)
                    return True
            except:
                pass
        return False

    def update_status(self):
        current_time = datetime.datetime.now()

        if not self.status_info:
            self.status_info = {
                "last_active_resume_time": 0,
                "last_active_timestamp": current_time - datetime.timedelta(seconds=10),
                "last_stream_id": None,
            }

        time_since_last_activity = current_time - self.status_info["last_active_timestamp"]
        if time_since_last_activity < datetime.timedelta(seconds=15):
            self.status = utils.InstanceStatus.WATCHING
            return

        try:
            current_resume_time = int(
                self.page.evaluate(
                    '''() => {
                const element = document.querySelector(".ytp-progress-bar");
                return element ? element.getAttribute("aria-valuenow") : 0;
            }'''
                )
            )
        except:
            self.status = utils.InstanceStatus.BUFFERING
            return

        if current_resume_time:
            if current_resume_time > self.status_info["last_active_resume_time"]:
                self.status_info["last_active_timestamp"] = current_time
                self.status_info["last_active_resume_time"] = current_resume_time
                self.status = utils.InstanceStatus.WATCHING
                return

        self.status = utils.InstanceStatus.BUFFERING

    def todo_after_spawn(self):
        self.goto_with_retry("https://www.youtube.com/")

        self.page.wait_for_timeout(2000)
        self._dismiss_consent()

        for key, value in self.local_storage.items():
            tosend = """window.localStorage.setItem('{key}','{value}');""".format(key=key, value=value)
            self.page.evaluate(tosend)

        self.goto_with_retry(self.target_url)

        self.page.wait_for_timeout(3000)
        self._dismiss_consent()

        try:
            self.page.wait_for_selector("ytd-player, #movie_player, video", timeout=30000)
        except:
            logger.warning(f"Instance {self.id}: player element not found, page may not have loaded")
            raise

        self.page.wait_for_timeout(5000)
        try:
            if self.page.evaluate("""(() => { const p = document.querySelector("div#movie_player"); return p && p.classList.contains('paused-mode'); })()"""):
                self.page.keyboard.press("Space")
        except:
            pass
        self.page.keyboard.press("f")
        self.status = utils.InstanceStatus.INITIALIZED


class Kick(Instance):
    site_name = "KICK"
    site_url = "kick.com"
    local_storage = {
        "agreed_to_mature_content": "true",
        "kick_cookie_accepted": "true",
        "kick_video_size": "160p",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def todo_every_loop(self):
        self.page.keyboard.press("Tab")

    def update_status(self):
        pass

    def todo_after_spawn(self):
        self.goto_with_retry("https://kick.com/terms-of-service")
        self.page.wait_for_timeout(5000)

        for key, value in self.local_storage.items():
            tosend = """window.localStorage.setItem('{key}','{value}');""".format(key=key, value=value)
            self.page.evaluate(tosend)

        self.goto_with_retry(self.target_url)
        self.page.wait_for_timeout(1000)
        if 'cloudflare' in self.page.content().lower():
            raise utils.CloudflareBlockException("Blocked by Cloudflare.")


class Twitch(Instance):
    site_name = "TWITCH"
    site_url = "twitch.tv"
    cookie_css = "button[data-a-target=consent-banner-accept]"
    local_storage = {
        "mature": "true",
        "video-muted": '{"default": "false"}',
        "volume": "0.5",
        "video-quality": '{"default": "160p30"}',
        "lowLatencyModeEnabled": "false",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def todo_after_load(self):
        self.page.wait_for_selector(".persistent-player", timeout=30000)
        self.page.wait_for_timeout(1000)
        self.page.keyboard.press("Alt+t")

    def update_status(self):
        current_time = datetime.datetime.now()
        if not self.status_info:
            self.status_info = {
                "last_active_resume_time": 0,
                "last_active_timestamp": current_time - datetime.timedelta(seconds=10),
                "last_stream_id": None,
            }

        # If the stream was active less than 10 seconds ago, it's still being watched
        time_since_last_activity = current_time - self.status_info["last_active_timestamp"]
        if time_since_last_activity < datetime.timedelta(seconds=10):
            self.status = utils.InstanceStatus.WATCHING
            return

        # Fetch the current resume time for the stream
        fetched_resume_times = self.page.evaluate("window.localStorage.getItem('livestreamResumeTimes');")
        if fetched_resume_times:
            resume_times_dict = json.loads(fetched_resume_times)
            current_stream_id = list(resume_times_dict.keys())[-1]
            current_resume_time = list(resume_times_dict.values())[-1]

            # If this is the first run, set the last stream id to current stream id
            if not self.status_info["last_stream_id"]:
                self.status_info["last_stream_id"] = current_stream_id

            # If the stream has restarted, reset last_active_resume_time
            if current_stream_id != self.status_info["last_stream_id"]:
                self.status_info["last_stream_id"] = current_stream_id
                self.status_info["last_active_resume_time"] = 0

            # If the current resume time has advanced past the last active resume time, update and set status to
            if current_resume_time > self.status_info["last_active_resume_time"]:
                self.status_info["last_active_timestamp"] = current_time
                self.status_info["last_active_resume_time"] = current_resume_time
                self.status = utils.InstanceStatus.WATCHING
                return

        # If none of the above conditions are met, the stream is buffering
        self.status = utils.InstanceStatus.BUFFERING

    def todo_after_spawn(self):
        self.goto_with_retry("https://www.twitch.tv/p/en/partners/")

        try:
            self.page.click(self.cookie_css, timeout=15000)
        except:
            logger.warning("Cookie consent banner not found/clicked.")

        for key, value in self.local_storage.items():
            tosend = """window.localStorage.setItem('{key}','{value}');""".format(key=key, value=value)
            self.page.evaluate(tosend)

        self.page.set_viewport_size(
            {
                "width": self.location_info["width"],
                "height": self.location_info["height"],
            }
        )

        self.goto_with_retry(self.target_url)
        self.page.wait_for_timeout(1000)
        self.page.wait_for_selector(".persistent-player", timeout=15000)
        self.page.keyboard.press("Alt+t")
        self.page.wait_for_timeout(1000)

        try:
            self.page.click(
                "button[data-a-target=content-classification-gate-overlay-start-watching-button]", timeout=3000
            )
        except:
            logger.info("Mature button not found/clicked.")

        self.status = utils.InstanceStatus.INITIALIZED
