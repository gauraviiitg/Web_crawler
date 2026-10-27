"""Builds the static website (site/) published on GitHub Pages."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from .districts import district_names, districts_for

DETAIL_FIELDS = (
    "ref_no", "tender_type", "form_of_contract", "tender_category", "product_category",
    "sub_category", "contract_type", "covers", "payment_mode", "tender_value", "emd",
    "emd_percentage", "emd_exemption", "tender_fee", "processing_fee", "fee_exemption",
    "description", "pre_qualification", "remarks", "location", "pincode",
    "period_of_work_days", "bid_validity_days", "tenderer_class", "published", "doc_start",
    "doc_end", "clarification_end", "prebid_date", "prebid_place", "bid_start", "bid_end",
    "bid_opening", "bid_opening_place", "nit_documents", "work_documents",
    "authority_name", "authority_address",
)


def site_record(record: dict, related: list[str]) -> dict:
    detail = record.get("detail") or {}
    return {
        "id": record["tender_id"],
        "title": detail.get("title") or record.get("title"),
        "org": record.get("organisation"),
        "org_chain": record.get("org_chain"),
        "ref_no": record.get("ref_no"),
        "published": record.get("published"),
        "closing": record.get("closing"),
        "opening": record.get("opening"),
        "status": record.get("status"),
        "first_seen": record.get("first_seen"),
        "last_changed": record.get("last_changed"),
        "changes": record.get("changes", [])[-5:],
        "related": related,
        "value": detail.get("tender_value"),
        "emd": detail.get("emd"),
        "category": detail.get("tender_category"),
        "location": detail.get("location"),
        "detail": {k: detail.get(k) for k in DETAIL_FIELDS if detail.get(k) not in (None, "", [], "NA")},
        "analysis": record.get("analysis"),
        "personal": record.get("personal") or [],
        "districts": districts_for({**record, "title": detail.get("title") or record.get("title")}),
    }


def build_site(store, cfg: dict, run: dict, now: datetime, root: Path, briefing: dict | None = None) -> Path:
    site_dir = root / "site"
    if site_dir.exists():
        shutil.rmtree(site_dir)
    shutil.copytree(root / "web", site_dir)

    cutoff = (now - timedelta(days=cfg["site"].get("keep_closed_days", 7))).strftime("%Y-%m-%dT%H:%M")
    tenders = [
        site_record(r, store.related_tenders(r["tender_id"]))
        for r in store.tenders.values()
        if r.get("status") == "active" or (r.get("status_changed") or "") >= cutoff
    ]
    payload = {
        "title": cfg["site"]["title"],
        "portal": {"name": cfg["portal"]["name"], "url": cfg["portal"]["home_url"],
                   "org_url": cfg["portal"]["home_url"] + "?page=FrontEndTendersByOrganisation&service=page"},
        "generated_at": now.strftime("%Y-%m-%dT%H:%M"),
        "run": run,
        "runs": store.data.get("runs", [])[-14:],
        "briefing": briefing,
        "personalised": [{k: s.get(k) for k in ("id", "name_en", "name_hi")} for s in cfg.get("personalised") or []],
        "districts": district_names(),
        "tenders": tenders,
    }
    (site_dir / "data.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")
    return site_dir
