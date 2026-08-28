# -*- coding: utf-8 -*-
# CVAmp proxy collector + YouTube validation pipeline (batch mode)
# [0] Mass collect (10+ sources, 50k+) -> [1][2][3] YouTube batch validation -> [4] Accumulate -> [5] Loop
import urllib.request, json, os, re, time, ssl, random
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR  = os.path.join(HERE, "proxy")
OUT_FILE = os.path.join(OUT_DIR, "proxy_list.txt")

INTERVAL = 30
VALIDATE_TIMEOUT = 5
MAX_WORKERS = 500
BATCH = 5000
TARGET = 20000
REFRESH_RAW_EVERY = 3
TEST_URL = "https://www.youtube.com/generate_204"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
ipport_re = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})\b")
_BAD_PREFIXES = ("0.", "10.", "127.", "169.254.", "172.16.", "172.17.", "172.18.",
                  "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                  "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.",
                  "172.31.", "192.168.", "255.")

def _is_valid_proxy(ip_port):
    ip = ip_port.split(":")[0]
    if ip.startswith(_BAD_PREFIXES):
        return False
    parts = ip.split(".")
    return all(0 <= int(p) <= 255 for p in parts)
_ctx = ssl.create_default_context(); _ctx.check_hostname = False; _ctx.verify_mode = ssl.CERT_NONE

SOURCES = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/https.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/zloi-user/hideip.me/main/http.txt",
    "https://raw.githubusercontent.com/zloi-user/hideip.me/main/https.txt",
    "https://raw.githubusercontent.com/saisuiu/Lionkings-Http-Proxys-Proxies/main/free.txt",
    "https://raw.githubusercontent.com/HyperBeats/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/HyperBeats/proxy-list/main/https.txt",
    "https://raw.githubusercontent.com/rx443/proxy-list/main/online/http.txt",
    "https://raw.githubusercontent.com/rx443/proxy-list/main/online/https.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/http/http.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/https/https.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/http.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/https.txt",
    "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/https.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/http_proxies.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/https_proxies.txt",
    "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/proxylist-to/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/proxylist-to/proxy-list/main/https.txt",
    "https://raw.githubusercontent.com/ellerbrock/tor-exit-nodes-ips/master/http.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/US/data.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/JP/data.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/KR/data.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/SG/data.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/DE/data.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/GB/data.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/FR/data.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/NL/data.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CA/data.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/AU/data.txt",
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=https&timeout=10000&country=all",
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=US",
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=JP",
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=KR",
    "https://www.proxy-list.download/api/v1/get?type=http",
    "https://www.proxy-list.download/api/v1/get?type=https",
    "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc&protocols=http",
    "https://proxylist.geonode.com/api/proxy-list?limit=500&page=2&sort_by=lastChecked&sort_type=desc&protocols=http",
    "https://proxylist.geonode.com/api/proxy-list?limit=500&page=3&sort_by=lastChecked&sort_type=desc&protocols=http",
    "https://raw.githubusercontent.com/mertguvencli/http-proxy-list/main/proxy-list/data.txt",
    "https://raw.githubusercontent.com/UptimerBot/proxy-list/main/proxies/http.txt",
]


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")


def collect_raw():
    pool = set()
    for url in SOURCES:
        try:
            text = fetch(url)
            if "geonode.com" in url:
                try:
                    data = json.loads(text)
                    for item in data.get("data", []):
                        ip = item.get("ip", "")
                        port = item.get("port", "")
                        if ip and port:
                            pool.add(f"{ip}:{port}")
                    print(f"  [src] +{len(data.get('data',[]))} (json)  geonode.com")
                    continue
                except Exception:
                    pass
            cnt = 0
            for m in ipport_re.finditer(text):
                pool.add(f"{m.group(1)}:{m.group(2)}"); cnt += 1
            print(f"  [src] +{cnt:>6}  {url.split('/')[2]}")
        except Exception as e:
            print(f"  [src] FAIL {url.split('/')[2]}: {e}")
    pool = {p for p in pool if _is_valid_proxy(p)}
    return list(pool)


def validate(proxy):
    h = urllib.request.ProxyHandler({"http": f"http://{proxy}", "https": f"http://{proxy}"})
    opener = urllib.request.build_opener(h, urllib.request.HTTPSHandler(context=_ctx))
    try:
        r = opener.open(urllib.request.Request(TEST_URL, headers=HEADERS), timeout=VALIDATE_TIMEOUT)
        return proxy if r.status in (200, 204) else None
    except Exception:
        return None


def validate_many(proxies):
    ok = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for fut in as_completed([ex.submit(validate, p) for p in proxies]):
            r = fut.result()
            if r:
                ok.append(r)
    return ok


def write_file(proxies):
    os.makedirs(OUT_DIR, exist_ok=True)
    tmp = OUT_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(proxies) + "\n")
    os.replace(tmp, OUT_FILE)


def main():
    print(f"Proxy collector+validator started | target {TARGET} | interval {INTERVAL}s")
    validated = []
    raw_queue = []
    round_no = 0
    while True:
        t0 = time.time()
        round_no += 1
        if not raw_queue or round_no % REFRESH_RAW_EVERY == 1:
            print(f"[R{round_no}] Collecting raw proxies...")
            allraw = collect_raw()
            random.shuffle(allraw)
            have = set(validated)
            raw_queue = [p for p in allraw if p not in have]
            print(f"[R{round_no}] raw total {len(allraw)} (queue {len(raw_queue)})")

        validated = validate_many(validated) if validated else []
        if len(validated) < TARGET and raw_queue:
            batch = raw_queue[:BATCH]; raw_queue = raw_queue[BATCH:]
            newok = validate_many(batch)
            have = set(validated)
            validated += [p for p in newok if p not in have]
        validated = validated[:max(TARGET, len(validated))]
        write_file(validated)

        dt = round(time.time() - t0, 1)
        stamp = time.strftime("%H:%M:%S")
        print(f"[{stamp} R{round_no}] validated {len(validated)}/{TARGET} | queue {len(raw_queue)} | {dt}s")
        time.sleep(max(5, INTERVAL - dt))


if __name__ == "__main__":
    main()
