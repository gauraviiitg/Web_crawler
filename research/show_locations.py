"""Check district mapping coverage on site/data.json (run research/rebuild_site.py first)."""
import collections
import json
import pathlib

d = json.loads((pathlib.Path(__file__).parent.parent / "site" / "data.json").read_text(encoding="utf-8"))
active = [t for t in d["tenders"] if t["status"] == "active"]
c = collections.Counter(x for t in active for x in t.get("districts") or ["(none)"])
print(len(active), "active;", c.most_common())
unmatched = collections.Counter(t.get("location") for t in active if not t.get("districts"))
print("unmatched locations:", unmatched.most_common(30))
multi = [(t["location"], t["districts"]) for t in active if len(t.get("districts") or []) > 1]
print("multi:", multi[:20])
