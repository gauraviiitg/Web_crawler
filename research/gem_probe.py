"""Probe GeM BidPlus public search: consignee-state search for Rajasthan, and the all-bids feed."""
import json
import re
import sys

import requests

BASE = "https://bidplus.gem.gov.in"
UA = {"User-Agent": "Mozilla/5.0 (research; tender digest)", "X-Requested-With": "XMLHttpRequest"}


def session(page: str):
    s = requests.Session()
    s.headers.update(UA)
    html = s.get(f"{BASE}/{page}", timeout=40).text
    token = re.search(r"csrf_bd_gem_nk'\s*:\s*'([0-9a-f]+)'", html).group(1)
    return s, token


def post(s, token, path, payload):
    r = s.post(f"{BASE}/{path}", data={"payload": json.dumps(payload), "csrf_bd_gem_nk": token},
               headers={"Referer": f"{BASE}/advance-search"}, timeout=60)
    return r.status_code, r.text


def show(label, code, text):
    print(f"--- {label}: HTTP {code}, {len(text)} bytes")
    try:
        data = json.loads(text)
    except ValueError:
        print(text[:400])
        return None
    resp = (data.get("response") or {}).get("response") or {}
    print("code", data.get("code"), "numFound", resp.get("numFound"), "docs", len(resp.get("docs") or []))
    return resp


def main():
    s, tok = session("advance-search")
    for state in sys.argv[1:] or ["RAJASTHAN", "Rajasthan"]:
        code, text = post(s, tok, "search-bids", {"searchType": "con", "state_name_con": state, "city_name_con": "",
                                                    "bidEndFromCon": "", "bidEndToCon": "", "page": 1})
        resp = show(f"con {state}", code, text)
        if resp and resp.get("docs"):
            doc = resp["docs"][0]
            print(json.dumps(doc, ensure_ascii=False, indent=1)[:3000])
            print("keys:", sorted(doc))
            break
    r = s.post(f"{BASE}/city-list-adv", data={"state_name": "RAJASTHAN", "csrf_bd_gem_nk": tok}, timeout=40)
    print("--- cities:", r.status_code, r.text[:600])


if __name__ == "__main__":
    main()
