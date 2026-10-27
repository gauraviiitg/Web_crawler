"""Screen active tenders for a brand-new, zero-budget, zero-experience company in Jaipur."""
import json
import re
import sys
from collections import Counter
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
NOW = datetime(2026, 10, 27, 19, 0)
db = json.load(open("data/tenders.json", encoding="utf-8"))["tenders"]

EXPERIENCE_RE = re.compile(r"experience|turnover|similar work|work order|completion certificate|class [a-d]|registered contractor", re.I)
JAIPUR_RE = re.compile(r"jaipur", re.I)


def days_left(t):
    try:
        return (datetime.strptime(t["closing"], "%Y-%m-%dT%H:%M") - NOW).total_seconds() / 86400
    except (TypeError, ValueError, KeyError):
        return None


rows = []
for t in db.values():
    if t.get("status") != "active":
        continue
    d = t.get("detail") or {}
    cat = (d.get("tender_category") or "").lower()
    value = d.get("tender_value")
    emd = d.get("emd") or 0
    fee = (d.get("tender_fee") or 0) + (d.get("processing_fee") or 0)
    dl = days_left(t)
    emd_exempt = (d.get("emd_exemption") or "").lower() == "yes"
    fee_exempt = (d.get("fee_exemption") or "").lower() == "yes"
    text = " ".join(str(d.get(k) or "") for k in ("title", "description", "pre_qualification", "remarks"))
    rows.append({
        "id": t["tender_id"], "org": t.get("organisation"), "title": d.get("title") or t.get("title"),
        "cat": cat, "value": value, "emd": emd, "fee": fee, "emd_exempt": emd_exempt, "fee_exempt": fee_exempt,
        "days": dl, "loc": d.get("location") or "", "jaipur": bool(JAIPUR_RE.search((d.get("location") or "") + " " + (t.get("org_chain") or ""))),
        "class": d.get("tenderer_class") or "", "pq": (d.get("pre_qualification") or "")[:160],
        "exp_mentioned": bool(EXPERIENCE_RE.search(text)), "product": d.get("product_category") or "",
        "sub": d.get("sub_category") or "", "period": d.get("period_of_work_days"), "form": d.get("form_of_contract"),
        "type": d.get("tender_type"), "closing": t.get("closing"), "chain": t.get("org_chain"),
    })

print("active:", len(rows))
print("category:", Counter(r["cat"] for r in rows))
print("EMD exemption allowed:", Counter(r["emd_exempt"] for r in rows))
print("fee exemption allowed:", Counter(r["fee_exempt"] for r in rows))
print("tenderer class:", Counter(r["class"] for r in rows).most_common(5))

stage = [r for r in rows if r["cat"] in ("goods", "services")]
print("\ngoods/services:", len(stage))
stage = [r for r in stage if r["days"] is not None and r["days"] >= 5]
print("  + >=5 days left:", len(stage))
stage = [r for r in stage if r["value"] is None or r["value"] <= 1e7]
print("  + value <= 1 Cr or undisclosed:", len(stage))
stage = [r for r in stage if r["class"].upper() in ("", "ALL")]
print("  + open to all tenderer classes:", len(stage))


def startup_cost(r):
    """Cash needed upfront as an iStart startup (EMD exempt for goods/services <= 1 Cr)."""
    return 0 if r["fee_exempt"] else r["fee"]


def mse_cost(r):
    emd = 0 if r["emd_exempt"] else (r["emd"] / 4 if r["emd"] else 0)  # 0.5% instead of 2%
    return (0 if r["fee_exempt"] else r["fee"] / 2) + emd


for r in stage:
    r["startup_cost"] = startup_cost(r)
    r["mse_cost"] = mse_cost(r)
    r["normal_cost"] = (0 if r["fee_exempt"] else r["fee"]) + (0 if r["emd_exempt"] else r["emd"])

print("\nupfront cost as normal bidder:", Counter(
    "<=2k" if r["normal_cost"] <= 2000 else "<=10k" if r["normal_cost"] <= 10000 else "<=50k" if r["normal_cost"] <= 50000 else ">50k"
    for r in stage))
print("jaipur:", sum(r["jaipur"] for r in stage))

json.dump(sorted(stage, key=lambda r: (not r["jaipur"], r["normal_cost"])),
          open("research/shortlist.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\nwrote research/shortlist.json")
