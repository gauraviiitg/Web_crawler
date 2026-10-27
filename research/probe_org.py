"""Probe: org list -> one org's tender list -> one tender detail page."""
import re
import sys

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings()
BASE = "https://eproc.rajasthan.gov.in"
s = requests.Session()
s.verify = False
s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"


def get(url):
    r = s.get(url if url.startswith("http") else BASE + url, timeout=60)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml"), r.text


def table_rows(soup, table_id=None):
    tbl = soup.find("table", id=table_id) if table_id else None
    out = []
    for tr in (tbl or soup).find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all("td", recursive=False)]
        links = [a["href"] for a in tr.find_all("a", href=True)]
        if cells:
            out.append((cells, links))
    return out


soup, raw = get("/nicgep/app?page=FrontEndTendersByOrganisation&service=page")
open("org_list.html", "w", encoding="utf-8").write(raw)
orgs = []
for tr in soup.find_all("tr"):
    tds = tr.find_all("td", recursive=False)
    a = tr.find("a", href=re.compile("DirectLink"))
    if len(tds) == 3 and a and tds[0].get_text(strip=True).isdigit():
        orgs.append((tds[1].get_text(strip=True), int(tds[2].get_text(strip=True)), a["href"]))
print("orgs:", len(orgs), "total tenders:", sum(o[1] for o in orgs))
for o in orgs[:5]:
    print("  ", o[0], o[1])

idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
name, cnt, link = orgs[idx]
print("\n### ORG:", name, cnt)
soup, raw = get(link)
open("org_tenders.html", "w", encoding="utf-8").write(raw)
detail_links = []
for cells, links in table_rows(soup):
    if cells and cells[0].rstrip(".").isdigit() and len(cells) >= 5:
        print(cells)
        detail_links += [l for l in links if "DirectLink" in l]
print("pager links:", [a.get_text(strip=True) for a in soup.find_all("a", id=re.compile("linkFwd|loadNext|Next", re.I))])

if detail_links:
    soup, raw = get(detail_links[0])
    open("tender_detail.html", "w", encoding="utf-8").write(raw)
    print("\n### DETAIL")
    for cells, links in table_rows(soup):
        line = " | ".join(c for c in cells if c)
        if line and len(line) < 400:
            print(line)
    print("\nDOC LINKS:")
    for a in soup.find_all("a", href=True):
        if "DirectLink" in a["href"] or a["href"].lower().endswith(".pdf"):
            print(a.get_text(strip=True), "->", a["href"][:160])
