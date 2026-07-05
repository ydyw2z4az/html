from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import random
import time
import os
import requests
import selenium
from datetime import datetime, timezone, timedelta

try:
    from selenium.webdriver.chrome.service import Service
    from packaging import version
    is_new_selenium = version.parse(selenium.__version__) >= version.parse("4.6.0")
except:
    is_new_selenium = False

# === CONFIG ===
GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "unknown")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "unknown-repo")
BOT_LABEL = os.environ.get("BOT_LABEL", GITHUB_REPO)  # fallback ke nama repo
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://172.232.228.16:3000")
try:
    START_HOUR = int(os.environ.get("START_HOUR", "0") or "0")
except:
    START_HOUR = 0
try:
    STOP_HOUR = int(os.environ.get("STOP_HOUR", "24") or "24")
except:
    STOP_HOUR = 24

HEARTBEAT_EVERY = 15  # kirim tiap 15 detik biar lebih live
WIB = timezone(timedelta(hours=7))
start_time = datetime.now(WIB)

def send_heartbeat(status, hashrate="0", error_msg=""):
    try:
        requests.post(
            f"{DASHBOARD_URL}/api/heartbeat",
            json={
                "bot_label": BOT_LABEL,
                "github_username": GITHUB_USERNAME,
                "github_repo": GITHUB_REPO,
                "status": status,
                "hashrate": hashrate,
                "error": error_msg,
                "uptime": format_uptime(),
                "schedule": f"{START_HOUR}:00-{STOP_HOUR}:00" if STOP_HOUR < 24 else "24/7",
                "timestamp": datetime.now(WIB).strftime("%d/%m/%Y %H:%M:%S WIB")
            },
            timeout=10
        )
    except Exception as e:
        print(f"[{BOT_LABEL}][!] Heartbeat error: {e}")

def is_within_schedule():
    if STOP_HOUR >= 24 and START_HOUR <= 0:
        return True
    h = datetime.now(WIB).hour
    if START_HOUR < STOP_HOUR:
        return START_HOUR <= h < STOP_HOUR
    return h >= START_HOUR or h < STOP_HOUR

def format_uptime():
    delta = datetime.now(WIB) - start_time
    h, r = divmod(int(delta.total_seconds()), 3600)
    m, s = divmod(r, 60)
    return f"{h}j {m}m {s}s"

# === Chrome Setup ===
chrome_driver_path = "/usr/local/bin/chromedriver"
chrome_options = Options()
for arg in [
    "--enable-javascript","--headless=new","--no-sandbox","--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled","--disable-infobars","--disable-extensions",
    "--disable-gpu","--disable-dev-tools","--no-default-browser-check","--no-first-run",
    "--disable-web-security","--disable-notifications","--disable-popup-blocking",
    "--ignore-certificate-errors","--disable-logging","--log-level=3"
]:
    chrome_options.add_argument(arg)
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)
chrome_options.add_experimental_option("detach", True)

driver = None

try:
    print(f"[{BOT_LABEL}] @{GITHUB_USERNAME}/{GITHUB_REPO} -> {DASHBOARD_URL}")
    send_heartbeat("starting")

    while not is_within_schedule():
        print(f"[{BOT_LABEL}] Waiting for schedule...")
        send_heartbeat("waiting")
        time.sleep(60)

    if is_new_selenium:
        driver = webdriver.Chrome(service=Service(chrome_driver_path), options=chrome_options)
    else:
        driver = webdriver.Chrome(executable_path=chrome_driver_path, options=chrome_options)

    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});window.chrome={runtime:{}};"
    })

    base_url = "https://webminer.pages.dev?algorithm=cwm_minotaurx&host=minotaurx.sea.mine.zpool.ca&port=7019&worker=XbwZSCiazX5A3Hbm1tZhWFVzpwy5cRPXcJ&password=c%3DDASH&workers=4"
    driver.get(base_url)
    time.sleep(random.uniform(3, 5))

    start_time = datetime.now(WIB)
    errs = 0
    n = 0

    while True:
        if not is_within_schedule():
            send_heartbeat("stopped")
            break

        try:
            hr = driver.find_element(By.CSS_SELECTOR, "span#hashrate strong").text
            n += 1
            errs = 0
            print(f"[{BOT_LABEL}] {hr} | #{n}")
            send_heartbeat("mining", hr)
        except Exception as e:
            errs += 1
            print(f"[{BOT_LABEL}][!] err#{errs}: {e}")
            send_heartbeat("error", "0", str(e)[:80])
            if errs >= 5:
                try:
                    driver.refresh()
                    time.sleep(random.uniform(5, 8))
                    errs = 0
                except:
                    pass

        time.sleep(HEARTBEAT_EVERY)

except Exception as e:
    print(f"[{BOT_LABEL}][!] CRASH: {e}")
    try:
        send_heartbeat("crashed", "0", str(e)[:120])
    except:
        pass
finally:
    if driver:
        driver.quit()
