"""Print each personalised section from the last site build (run rebuild_site.py first)."""
import json
from pathlib import Path

data = json.loads((Path(__file__).resolve().parents[1] / "site/data.json").read_text(encoding="utf-8"))
for s in data["briefing"]["personal"]:
    print(f"== {s['name_en']}: {s['open']} open, {s['new']} new | briefing top: {[p['tender_id'] for p in s['top']]}")
rows = [t for t in data["tenders"] if t["status"] == "active" and t.get("personal")]
rows.sort(key=lambda t: (-(t["analysis"].get("relevance") or 0), t["closing"] or ""))
for t in rows:
    a = t["analysis"]
    print(f"{a.get('relevance', 0):3} {a['decision']:13} {t['id']:22} {t['closing']} "
          f"{(t.get('location') or '')[:16]:16} | {a.get('reason', '')[:110]}")
