"""Rank active tenders for the configured profile using the keyword rules (no LLM)."""
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crawler.analyse import rule_analysis  # noqa: E402

root = Path(__file__).resolve().parents[1]
profile = yaml.safe_load((root / "config/settings.yaml").read_text(encoding="utf-8"))["profile"]
tenders = json.loads((root / "data/tenders.json").read_text(encoding="utf-8"))["tenders"]
now = datetime(2026, 10, 27, 9)

rows = []
for rec in tenders.values():
    if rec.get("status") != "active":
        continue
    a = rule_analysis(rec, profile, now)
    rows.append((a, rec))

print(Counter(a["decision"] for a, _ in rows))
top = sorted((r for r in rows if r[0]["decision"] != "skip"), key=lambda r: -r[0]["relevance"])
for a, rec in top[:40]:
    d = rec.get("detail") or {}
    print(f"{a['relevance']:3} {a['decision']:13} {rec['tender_id']:22} {rec['closing']} "
          f"Rs{(d.get('tender_value') or 0)/1e5:6.1f}L cost={a['upfront_cost_inr']} "
          f"{(d.get('location') or '')[:12]:12} {(rec.get('title') or '')[:70]}")
