"""Summarise GeM bids in site/data.json (after research/rebuild_site.py --gem)."""
import collections
import json
import pathlib

d = json.loads((pathlib.Path(__file__).parent.parent / "site" / "data.json").read_text(encoding="utf-8"))
gem = [t for t in d["tenders"] if t.get("source") == "gem" and t["status"] == "active"]
print(len(gem), "GeM active of", len(d["tenders"]))
print("decisions:", collections.Counter(t["analysis"]["decision"] for t in gem))
print("no district:", sum(not t["districts"] for t in gem))
print("districts:", collections.Counter(x for t in gem for x in t["districts"]).most_common(12))
print("personal:", collections.Counter(x for t in gem for x in t["personal"]))
print("types:", collections.Counter(t["detail"].get("tender_type") for t in gem))
for t in sorted(gem, key=lambda t: -t["analysis"]["relevance"])[:12]:
    a = t["analysis"]
    print(f'{a["relevance"]:3} {t["id"]} | {t["title"][:70]} | {",".join(t["districts"])} | {t["closing"]} | {a["reason"][:80]}')
picks = d["briefing"]["picks"]
print("briefing picks:", [(p["tender_id"], p["title"][:40]) for p in picks])
for s in d["briefing"]["personal"]:
    print(s["id"], [(p["tender_id"], p["title"][:40]) for p in s["top"]])
