"""Check pagination on a big organisation and timing of detail fetches."""
import re
import sys
import time

import requests
import urllib3
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
urllib3.disable_warnings()
BASE = "https://eproc.rajasthan.gov.in"
s = requests.Session()
s.verify = False
s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"


def soup_of(url):
    t0 = time.time()
    r = s.get(url if url.startswith("http") else BASE + url, timeout=90)
    return BeautifulSoup(r.text, "lxml"), time.time() - t0, r.text


soup, _, _ = soup_of("/nicgep/app?page=FrontEndTendersByOrganisation&service=page")
orgs = []
for tr in soup.find_all("tr"):
    tds = tr.find_all("td", recursive=False)
    a = tr.find("a", href=re.compile("DirectLink"))
    if len(tds) == 3 and a and tds[0].get_text(strip=True).isdigit():
        orgs.append((tds[1].get_text(strip=True), int(tds[2].get_text(strip=True)), a["href"]))
print("org pager?", [a.get_text(strip=True) for a in soup.find_all("a", id=re.compile("link|Next", re.I)) if a.get_text(strip=True) in ("Next", ">", ">>", "2")])
big = max(orgs, key=lambda o: o[1])
print("biggest org:", big[0], big[1])

soup, dt, raw = soup_of(big[2])
page = 1
seen = []
while True:
    rows = soup.find_all("a", href=re.compile("FrontEndViewTender"))
    ids = []
    for a in rows:
        tr = a.find_parent("tr")
        m = re.search(r"\[(\d{4}_[A-Z0-9]+_\d+_\d+)\]", tr.get_text(" ", strip=True))
        ids.append(m.group(1) if m else None)
    seen += ids
    print(f"page {page}: {len(rows)} rows ({dt:.1f}s) first={ids[:1]}")
    nxt = soup.find("a", id=re.compile("linkFwd|loadNext", re.I)) or soup.find("a", string=re.compile(r"^\s*(Next|>)\s*$"))
    if page == 1:
        open("big_org_p1.html", "w", encoding="utf-8").write(raw)
        print("  candidate pager anchors:", [(a.get("id"), a.get_text(strip=True)) for a in soup.find_all("a") if a.get("id") and re.search("link|page|next|fwd", a.get("id"), re.I)][:15])
    if not nxt or page >= 40:
        break
    soup, dt, raw = soup_of(nxt["href"])
    page += 1
print("total rows collected:", len(seen), "unique ids:", len(set(seen)), "expected:", big[1])
