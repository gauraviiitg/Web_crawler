"""List active tenders related to photocopy / printing / scanning work."""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from crawler.analyse import _days_left  # noqa: E402

PAT = re.compile(
    r"photo ?cop|photostat|xerox|\bcopier|duplicat(?:ing|or)|\bprint(?:ing|er|ers|ed)?\b|toner|cartridge|"
    r"\bscann(?:ing|er)|digiti[sz]|\bbinding|laminat|\bflex\b|banner|a4 paper|copy paper|stationery printing",
    re.I,
)
tenders = json.loads((ROOT / "data/tenders.json").read_text(encoding="utf-8"))["tenders"]
now = datetime(2026, 10, 27, 19)
rows = []
for r in tenders.values():
    d = r.get("detail") or {}
    if r.get("status") != "active":
        continue
    text = " ".join(str(x) for x in (r.get("title"), d.get("description"), d.get("product_category"), d.get("sub_category")) if x)
    m = PAT.findall(text)
    if m:
        a = r.get("analysis") or {}
        rows.append((r["closing"] or "", r, d, a, sorted({x.lower() for x in m})))
rows.sort(key=lambda x: x[0])
for closing, r, d, a, m in rows:
    days = _days_left(closing, now)
    print(f"{r['tender_id']:22} {closing} ({days:4.1f}d) {d.get('tender_category') or '-':8} "
          f"Rs{(d.get('tender_value') or 0)/1e5:6.1f}L EMD{(d.get('emd') or 0):>8.0f} ex={d.get('emd_exemption') or '-':3} "
          f"{(d.get('location') or '')[:14]:14} {a.get('decision','-'):13} {m} | {(r.get('title') or '')[:90]}")
print(len(rows), "matches")
