"""Time detail-page fetches and test whether detail links survive a fresh session."""
import re
import sys
import time

import requests
import urllib3
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
urllib3.disable_warnings()
BASE = "https://eproc.rajasthan.gov.in"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"


def sess():
    s = requests.Session()
    s.verify = False
    s.headers["User-Agent"] = UA
    return s


s = sess()
soup = BeautifulSoup(s.get(BASE + "/nicgep/app?page=FrontEndTendersByOrganisation&service=page", timeout=60).text, "lxml")
links = [a["href"] for a in soup.find_all("a", href=re.compile("DirectLink"))]
org = links[3]
soup = BeautifulSoup(s.get(BASE + org, timeout=60).text, "lxml")
dets = [a["href"] for a in soup.find_all("a", href=re.compile("FrontEndViewTender"))][:15]

times = []
for d in dets:
    t0 = time.time()
    html = s.get(BASE + d, timeout=60).text
    times.append(time.time() - t0)
    tid = re.search(r"\d{4}_[A-Z0-9]+_\d+_\d+", html)
    time.sleep(1)
print(f"{len(times)} detail fetches, avg {sum(times)/len(times):.2f}s, max {max(times):.2f}s")

fresh = sess()
html = fresh.get(BASE + dets[0], timeout=60).text
print("fresh-session detail works:", "Tender Reference Number" in html)
html = fresh.get(BASE + org, timeout=60).text
print("fresh-session org link works:", "FrontEndViewTender" in html)

print("robots.txt:", requests.get(BASE + "/robots.txt", verify=False, timeout=30, headers={"User-Agent": UA}).status_code)
