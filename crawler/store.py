"""Tender database (data/tenders.json) and de-duplication logic.

Unique key: the portal Tender ID, e.g. 2026_CEPWD_604884_4.
  - new      : Tender ID never seen          -> fetch detail + analyse
  - changed  : listing row changed (dates/title) or detail missing -> re-fetch detail;
               if the detail hash differs the tender is marked updated and re-analysed
  - unchanged: only last_seen is updated (no detail fetch, no LLM call)
Tenders missing from a complete crawl become "closed" (deadline passed) or "removed".
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

from .gepnic import ListingRow

LISTING_FIELDS = ("title", "ref_no", "published", "closing", "opening")
TRACKED_DETAIL_FIELDS = (
    "title", "description", "tender_value", "emd", "tender_fee", "bid_end", "bid_opening",
    "doc_end", "prebid_date", "location", "pre_qualification", "nit_documents", "work_documents",
)


def _hash(data: dict, fields: tuple[str, ...]) -> str:
    payload = json.dumps({f: data.get(f) for f in fields}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def family_key(tender_id: str) -> str:
    """2026_CEPWD_604884_4 -> 2026_CEPWD_604884 (groups re-tenders). GeM bid numbers stand alone."""
    return tender_id if tender_id.startswith("GEM/") else tender_id.rsplit("_", 1)[0]


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.data = {"version": 1, "tenders": {}, "runs": []}
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
            self.data.setdefault("runs", [])

    @property
    def tenders(self) -> dict:
        return self.data["tenders"]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def classify(self, row: ListingRow) -> str:
        record = self.tenders.get(row.tender_id)
        if record is None:
            return "new"
        if record.get("listing_hash") != _hash(asdict(row), LISTING_FIELDS) or not record.get("detail"):
            return "changed"
        return "unchanged"

    def touch(self, row: ListingRow, now: str) -> None:
        record = self.tenders[row.tender_id]
        record["last_seen"] = now
        record["status"] = "active"

    def upsert(self, row: ListingRow, detail: dict | None, now: str) -> str:
        """Store listing + detail. Returns 'new', 'updated' or 'unchanged'."""
        listing = {f: getattr(row, f) for f in LISTING_FIELDS}
        listing.update(organisation=row.organisation, org_chain=row.org_chain)
        record = self.tenders.get(row.tender_id)
        outcome = "unchanged"
        if record is None:
            record = {
                "tender_id": row.tender_id,
                "family": family_key(row.tender_id),
                "first_seen": now,
                "last_changed": now,
                "changes": [],
                "analysis": None,
            }
            self.tenders[row.tender_id] = record
            outcome = "new"
        record.update(listing)
        record["source"] = row.source
        record["listing_hash"] = _hash(asdict(row), LISTING_FIELDS)
        record["last_seen"] = now
        record["status"] = "active"
        if detail is not None:
            new_hash = _hash(detail, TRACKED_DETAIL_FIELDS)
            old_detail = record.get("detail") or {}
            if outcome != "new" and old_detail and record.get("detail_hash") != new_hash:
                changed = [f for f in TRACKED_DETAIL_FIELDS if old_detail.get(f) != detail.get(f)]
                record["changes"].append({"date": now, "fields": changed})
                record["last_changed"] = now
                record["analysis"] = None
                outcome = "updated"
            elif not old_detail:
                record["analysis"] = None  # re-analyse now that full details are available
            record["detail"] = detail
            record["detail_hash"] = new_hash
        return outcome

    def related_tenders(self, tender_id: str) -> list[str]:
        fam = family_key(tender_id)
        return sorted(t for t in self.tenders if t != tender_id and self.tenders[t].get("family") == fam)

    def mark_missing(self, seen_ids: set[str], now: str, source: str = "eproc") -> dict:
        """Close active tenders of `source` that a complete crawl of that source did not see."""
        counts = {"closed": 0, "removed": 0}
        for tender_id, record in self.tenders.items():
            if tender_id in seen_ids or record.get("status") != "active" or record.get("source", "eproc") != source:
                continue
            closing = record.get("closing")
            if closing and closing <= now:
                record["status"] = "closed"
                counts["closed"] += 1
            else:
                record["status"] = "removed"
                counts["removed"] += 1
            record["status_changed"] = now
        return counts

    def expire(self, now: str, source: str) -> dict:
        """Close active tenders of `source` whose deadline has passed (used after a partial crawl)."""
        closed = 0
        for record in self.tenders.values():
            if (record.get("status") == "active" and record.get("source", "eproc") == source
                    and record.get("closing") and record["closing"] <= now):
                record["status"] = "closed"
                record["status_changed"] = now
                closed += 1
        return {"closed": closed, "removed": 0}

    def prune(self, now: datetime, days: int) -> int:
        cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")
        stale = [
            t for t, r in self.tenders.items()
            if r.get("status") != "active" and (r.get("status_changed") or r.get("last_seen", "")) < cutoff
        ]
        for tender_id in stale:
            del self.tenders[tender_id]
        return len(stale)

    def add_run(self, run: dict, keep: int = 60) -> None:
        self.data["runs"] = (self.data["runs"] + [run])[-keep:]
