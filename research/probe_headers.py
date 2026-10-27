"""Try browser-like header variants for the detail page."""
import re
import sys
import time

import requests
import urllib3
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
urllib3.disable_warnings()
BASE = "https://eproc.rajasthan.gov.in"
BROWSER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}


def attempt(label, home_first, referer, delay):
    s = requests.Session()
    s.verify = False
    s.headers.update(BROWSER)
    if home_first:
        s.get(BASE + "/nicgep/app", timeout=60)
        time.sleep(delay)
    org_list_url = BASE + "/nicgep/app?page=FrontEndTendersByOrganisation&service=page"
    html = s.get(org_list_url, timeout=60, headers={"Referer": BASE + "/nicgep/app"} if referer else {}).text
    time.sleep(delay)
    org = BASE + BeautifulSoup(html, "lxml").find("a", href=re.compile("DirectLink"))["href"]
    html = s.get(org, timeout=60, headers={"Referer": org_list_url} if referer else {}).text
    time.sleep(delay)
    det = BASE + BeautifulSoup(html, "lxml").find("a", href=re.compile("FrontEndViewTender"))["href"]
    html = s.get(det, timeout=60, headers={"Referer": org} if referer else {}).text
    print(f"{label:35} ok={'td_caption' in html} expired={'has expired' in html} len={len(html)}")


attempt("plain", False, False, 0.5)
attempt("referer", False, True, 0.5)
attempt("home first + referer", True, True, 1)
attempt("home first + referer + slow", True, True, 3)
