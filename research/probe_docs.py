"""Probe document downloads on a tender detail page (same session as navigation)."""
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


def get(url, **kw):
    r = s.get(url if url.startswith("http") else BASE + url, timeout=90, **kw)
    r.raise_for_status()
    return r


soup = BeautifulSoup(get("/nicgep/app?page=FrontEndTendersByOrganisation&service=page").text, "lxml")
org_link = soup.find("a", href=re.compile("DirectLink"))["href"]
soup = BeautifulSoup(get(org_link).text, "lxml")
det = [a["href"] for a in soup.find_all("a", href=re.compile("FrontEndViewTender"))]
print("detail links on org page:", len(det))
soup = BeautifulSoup(get(det[0]).text, "lxml")

for label, sel in [("NIT", {"id": "docDownoad"}), ("WorkItem", {"id": re.compile(r"^DirectLink_9")}), ("Zip", {"id": "DirectLink_8"})]:
    a = soup.find("a", **({"id": sel["id"]}))
    if not a:
        print(label, "no link")
        continue
    r = get(a["href"], allow_redirects=True)
    ct = r.headers.get("Content-Type")
    cd = r.headers.get("Content-Disposition")
    print(f"\n{label}: status={r.status_code} type={ct} disp={cd} bytes={len(r.content)}")
    if "html" in (ct or ""):
        page = BeautifulSoup(r.text, "lxml")
        txt = re.sub(r"\s+", " ", page.get_text(" "))
        i = txt.find("aptcha")
        print("  HTML; captcha mentioned:", i >= 0, "|", txt[max(0, i - 300): i + 300] if i >= 0 else txt[2000:2600])
        for img in page.find_all("img"):
            if "aptcha" in (img.get("id", "") + img.get("src", "")):
                print("  captcha img:", img.get("id"), img.get("src", "")[:80])
        open(f"doc_{label}.html", "w", encoding="utf-8").write(r.text)
    else:
        fn = f"doc_{label}.bin"
        open(fn, "wb").write(r.content)
        print("  saved", fn, r.content[:8])
