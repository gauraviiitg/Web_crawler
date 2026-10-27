import sys

from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
soup = BeautifulSoup(open(sys.argv[1], encoding="utf-8").read(), "lxml")

print("CSS classes on td:", sorted({c for td in soup.find_all("td") for c in td.get("class", [])}))
print()
for cap in soup.find_all("td", class_="td_caption"):
    val = cap.find_next_sibling("td")
    if val is not None:
        print(f"{cap.get_text(' ', strip=True)!r:60} = {val.get_text(' ', strip=True)[:200]!r}")

print("\nALL LINKS IN CONTENT:")
for a in soup.find_all("a", href=True):
    h = a["href"]
    if "page=Front" in h and "service=page" in h:
        continue
    print(repr(a.get_text(" ", strip=True))[:80], "|", a.get("id"), "|", h[:170])
