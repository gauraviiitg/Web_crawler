"""GeM probe 2: city filter, closed-bid mix, page size, bid PDF access."""
import json
import re
import time
from datetime import datetime, timezone

from gem_probe import BASE, post, session


def docs(resp):
    return ((json.loads(resp).get("response") or {}).get("response") or {})


def main():
    s, tok = session("advance-search")
    cities = s.post(f"{BASE}/city-list-adv", data={"state_name": "RAJASTHAN", "csrf_bd_gem_nk": tok}, timeout=40).json()["data"]
    names = [c["city_name"] for c in cities if c["city_name"]]
    print(len(names), "cities:", names)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ends = []
    for page in (1, 2, 50, 137):
        code, text = post(s, tok, "search-bids", {"searchType": "con", "state_name_con": "RAJASTHAN", "city_name_con": "",
                                                    "bidEndFromCon": "", "bidEndToCon": "", "page": page})
        r = docs(text)
        e = [d["final_end_date_sort"][0] for d in r.get("docs", [])]
        ends += e
        print("page", page, "start", r.get("start"), "n", len(e), "min end", min(e) if e else None, "max end", max(e) if e else None)
        time.sleep(1)
    print("closed among sampled:", sum(1 for x in ends if x < now), "/", len(ends))

    total = 0
    for city in names[:4]:
        code, text = post(s, tok, "search-bids", {"searchType": "con", "state_name_con": "RAJASTHAN", "city_name_con": city,
                                                    "bidEndFromCon": "", "bidEndToCon": "", "page": 1})
        r = docs(text)
        total += r.get("numFound") or 0
        print("city", city, r.get("numFound"), [d["b_category_name"][0][:50] for d in r.get("docs", [])[:3]])
        time.sleep(1)

    code, text = post(s, tok, "search-bids", {"searchType": "con", "state_name_con": "RAJASTHAN", "city_name_con": "",
                                                "bidEndFromCon": "", "bidEndToCon": "", "page": 1})
    d = docs(text)["docs"][0]
    bid = d["b_id"][0]
    r = s.get(f"{BASE}/showbidDocument/{bid}", timeout=60, stream=True)
    head = next(r.iter_content(8))
    print("pdf", r.status_code, r.headers.get("content-type"), r.headers.get("content-length"), head)


if __name__ == "__main__":
    main()
