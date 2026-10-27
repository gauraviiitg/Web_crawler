"""Debug session handling: print cookies and Set-Cookie per request."""
import re
import sys

import requests
import urllib3
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
urllib3.disable_warnings()
BASE = "https://eproc.rajasthan.gov.in"
s = requests.Session()
s.verify = False
s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"


def go(path, label):
    r = s.get(BASE + path, timeout=60, allow_redirects=False)
    print(f"{label}: {r.status_code} len={len(r.text)} set-cookie={r.headers.get('Set-Cookie')} loc={r.headers.get('Location')}")
    print("   jar:", {c.name: (c.value[:12], c.path, c.domain) for c in s.cookies})
    return r.text


html = go("/nicgep/app?page=FrontEndTendersByOrganisation&service=page", "orglist")
org = BeautifulSoup(html, "lxml").find("a", href=re.compile("DirectLink"))["href"]
html = go(org, "org")
det = BeautifulSoup(html, "lxml").find("a", href=re.compile("FrontEndViewTender"))
print("detail link:", det["href"] if det else None)
html = go(det["href"], "detail")
print("detail ok:", "td_caption" in html, "| expired:", "session in the client area has expired" in html)
print("ip check:", [requests.get("https://api.ipify.org", timeout=20).text for _ in range(4)])
