import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
db = json.load(open("data/tenders.json", encoding="utf-8"))["tenders"]
KEYS = ("org_chain", "ref_no", "tender_type", "form_of_contract", "tender_category", "product_category",
        "sub_category", "tender_value", "emd", "emd_percentage", "emd_exemption", "tender_fee",
        "processing_fee", "fee_exemption", "description", "pre_qualification", "remarks", "location",
        "period_of_work_days", "tenderer_class", "bid_end", "prebid_date", "nit_documents", "work_documents",
        "authority_name", "authority_address")
for tid in sys.argv[1:]:
    t = db[tid]
    d = t.get("detail") or {}
    print("=" * 100)
    print(tid, "|", d.get("title"))
    for k in KEYS:
        if d.get(k) not in (None, "", [], "NA"):
            print(f"  {k:20} {d[k]}")
