"""Client for GeM BidPlus (bidplus.gem.gov.in) public bid search.

Uses the public "advance search" by consignee location (no login, no captcha):
  GET  /advance-search          -> session cookie + csrf token
  POST /city-list-adv           -> consignee cities of a state
  POST /search-bids (con)       -> open bids delivered to a state / city, 10 per page
Bid documents are public PDFs at /showbidDocument/<b_id>.
"""
from __future__ import annotations

import json
import logging
import re
import time

import requests

from .gepnic import USER_AGENT, ListingRow, clean

log = logging.getLogger(__name__)

BASE = "https://bidplus.gem.gov.in"
CSRF_RE = re.compile(r"csrf_bd_gem_nk'\s*:\s*'([0-9a-f]+)'")
SERVICE_RE = re.compile(r"\bservices?\b|\bhiring\b|\bmanpower\b|\boutsourc", re.I)
PAGE_SIZE = 10


def first(doc: dict, key: str):
    v = doc.get(key)
    return v[0] if isinstance(v, list) and v else v


def _date(value: str | None) -> str | None:
    """GeM stores IST wall-clock time with a 'Z' suffix (its site formats it as UTC)."""
    return value[:16] if value else None


class GemClient:
    def __init__(self, delay: float = 0.5, timeout: int = 60, max_pages: int = 400):
        self.delay, self.timeout, self.max_pages = delay, timeout, max_pages
        self.request_count = 0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "X-Requested-With": "XMLHttpRequest",
                                     "Referer": f"{BASE}/advance-search"})
        self.token = ""

    def _refresh(self) -> None:
        html = self.session.get(f"{BASE}/advance-search", timeout=self.timeout).text
        self.request_count += 1
        m = CSRF_RE.search(html)
        if not m:
            raise RuntimeError("GeM advance-search page has no csrf token")
        self.token = m.group(1)

    def _post(self, path: str, data: dict) -> str:
        for attempt in range(3):
            if not self.token:
                self._refresh()
            time.sleep(self.delay)
            try:
                r = self.session.post(f"{BASE}/{path}", data={**data, "csrf_bd_gem_nk": self.token}, timeout=self.timeout)
                self.request_count += 1
                if r.status_code == 200 or (r.status_code == 404 and '"No data found"' in r.text):
                    return r.text
                log.warning("GeM %s HTTP %s for %s: %s", path, r.status_code, data, r.text[:200].replace("\n", " "))
            except requests.RequestException as exc:
                log.warning("GeM %s failed: %s", path, exc)
            self.token = ""
            time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"GeM {path} failed 3 times")

    def cities(self, state: str) -> list[str]:
        data = json.loads(self._post("city-list-adv", {"state_name": state}))
        return sorted({c["city_name"].strip() for c in data.get("data") or [] if (c.get("city_name") or "").strip()})

    def search(self, state: str, city: str = "", page: int = 1) -> tuple[int, list[dict]]:
        payload = {"searchType": "con", "state_name_con": state, "city_name_con": city,
                   "bidEndFromCon": "", "bidEndToCon": "", "page": page}
        data = json.loads(self._post("search-bids", {"payload": json.dumps(payload)}))
        if data.get("code") == 404:
            return 0, []
        if data.get("code") != 200:
            raise RuntimeError(f"GeM search-bids returned code {data.get('code')}")
        resp = (data.get("response") or {}).get("response") or {}
        return int(resp.get("numFound") or 0), resp.get("docs") or []

    def bids(self, state: str, city: str = "") -> list[dict]:
        found, docs = self.search(state, city, 1)
        out = list(docs)
        pages = min(-(-found // PAGE_SIZE), self.max_pages)
        for page in range(2, pages + 1):
            out += self.search(state, city, page)[1]
        if len(out) < found and pages < self.max_pages:
            log.warning("GeM %s/%s: expected %d bids, got %d", state, city or "*", found, len(out))
        return out

    def state_bids(self, state: str) -> tuple[list[tuple[dict, list[str]]], dict]:
        """All open bids with a consignee in `state`, each with the consignee cities it was found under."""
        stats = {"cities": 0, "listed": 0, "complete": False}
        total, _ = self.search(state)
        by_id: dict[str, tuple[dict, set[str]]] = {}
        for city in self.cities(state):
            for doc in self.bids(state, city):
                bid = by_id.setdefault(str(first(doc, "b_id")), (doc, set()))
                bid[1].add(city.title())
            stats["cities"] += 1
        if len(by_id) < total:
            for doc in self.bids(state):
                by_id.setdefault(str(first(doc, "b_id")), (doc, set()))
        stats["listed"] = len(by_id)
        stats["state_total"] = total
        stats["complete"] = len(by_id) >= 0.97 * total
        return [(doc, sorted(cities)) for doc, cities in by_id.values()], stats


def to_row(doc: dict, cities: list[str]) -> tuple[ListingRow, dict]:
    b_id = first(doc, "b_id")
    number = clean(first(doc, "b_bid_number"))
    title = clean(first(doc, "b_category_name") or first(doc, "bd_category_name"))
    ministry = clean(first(doc, "ba_official_details_minName"))
    dept = clean(first(doc, "ba_official_details_deptName"))
    kind = {1: "Bid", 2: "Reverse Auction", 5: "Direct Reverse Auction"}.get(first(doc, "b_bid_type"), "Bid")
    pdf = f"{BASE}/showbidDocument/{b_id}"
    row = ListingRow(
        tender_id=number, title=title, ref_no="", org_chain="||".join(x for x in (ministry, dept) if x),
        published=_date(first(doc, "final_start_date_sort")), closing=_date(first(doc, "final_end_date_sort")),
        opening=None, link=pdf, organisation=dept or ministry, source="gem",
    )
    detail = {
        "title": title,
        "tender_category": "Services" if SERVICE_RE.search(title) else "Goods",
        "tender_type": kind + (" (Rate Contract)" if first(doc, "is_rc_bid") == 1 else ""),
        "location": ", ".join(cities),
        "quantity": first(doc, "b_total_quantity"),
        "ministry": ministry,
        "department": dept,
        "limited_tender": "Yes" if first(doc, "ba_is_limited_tendering") == 1 else "No",
        "global_tender": "Yes" if first(doc, "ba_is_global_tendering") == 1 else "No",
        "published": row.published,
        "bid_end": row.closing,
        "pdf_url": pdf,
    }
    return row, {k: v for k, v in detail.items() if v not in (None, "")}
