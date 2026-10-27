"""Client and HTML parsers for NIC GePNIC eProcurement portals (e.g. eproc.rajasthan.gov.in).

Only pages that are public without a captcha are used:
  FrontEndTendersByOrganisation -> organisation list
  organisation DirectLink        -> all active tenders of that organisation
  FrontEndViewTender             -> tender details
DirectLink URLs are bound to the server session, so list -> detail navigation must
happen inside the same requests.Session.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime

import requests
import urllib3
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

TENDER_ID_RE = re.compile(r"\d{4}_[A-Za-z0-9]+_\d+_\d+")
DOC_RE = re.compile(r"^[^\s].*\.(?:pdf|xlsx?|docx?|zip|rar|dwg|jpe?g)$", re.I)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
ORG_LIST_PATH = "/nicgep/app?page=FrontEndTendersByOrganisation&service=page"


class SessionExpired(Exception):
    pass


@dataclass
class Organisation:
    name: str
    count: int
    link: str


@dataclass
class ListingRow:
    tender_id: str
    title: str
    ref_no: str
    org_chain: str
    published: str | None
    closing: str | None
    opening: str | None
    link: str = field(repr=False)
    organisation: str = ""
    source: str = "eproc"


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_date(value: str | None) -> str | None:
    """'13-Oct-2026 03:00 PM' -> '2026-10-13T15:00'."""
    value = clean(value)
    for fmt in ("%d-%b-%Y %I:%M %p", "%d-%b-%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            continue
    return None


def parse_amount(value: str | None) -> float | None:
    """'15,00,000' -> 1500000.0; 'NA' -> None."""
    digits = re.sub(r"[^\d.]", "", value or "")
    if not digits or digits == ".":
        return None
    try:
        return float(digits)
    except ValueError:
        return None


def parse_org_list(html: str) -> list[Organisation]:
    soup = BeautifulSoup(html, "lxml")
    orgs = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        link = tr.find("a", href=re.compile("DirectLink"))
        if len(tds) == 3 and link and clean(tds[0].get_text()).isdigit():
            count = clean(tds[2].get_text())
            orgs.append(
                Organisation(
                    name=clean(tds[1].get_text()),
                    count=int(count) if count.isdigit() else 0,
                    link=link["href"],
                )
            )
    return orgs


def parse_org_tenders(html: str, organisation: str = "") -> list[ListingRow]:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for link in soup.find_all("a", href=re.compile("FrontEndViewTender")):
        tr = link.find_parent("tr")
        tds = tr.find_all("td", recursive=False) if tr else []
        if len(tds) < 6:
            continue
        cell_text = clean(tds[4].get_text(" "))
        match = TENDER_ID_RE.search(cell_text)
        if not match:
            continue
        title = clean(link.get_text()).strip("[] ")
        rest = cell_text.replace(clean(link.get_text()), "", 1)
        rest = rest.replace(f"[{match.group(0)}]", "")
        ref_no = clean(rest).strip("[] ")
        rows.append(
            ListingRow(
                tender_id=match.group(0),
                title=title,
                ref_no=ref_no,
                org_chain=clean(tds[5].get_text(" ")),
                published=parse_date(tds[1].get_text()),
                closing=parse_date(tds[2].get_text()),
                opening=parse_date(tds[3].get_text()),
                link=link["href"],
                organisation=organisation,
            )
        )
    return rows


# caption (lower-cased, currency suffix removed) -> normalised key
DETAIL_KEYS = {
    "organisation chain": "org_chain",
    "tender reference number": "ref_no",
    "tender id": "tender_id",
    "tender type": "tender_type",
    "form of contract": "form_of_contract",
    "tender category": "tender_category",
    "no. of covers": "covers",
    "payment mode": "payment_mode",
    "allow two stage bidding": "two_stage_bidding",
    "tender fee": "tender_fee",
    "processing fee": "processing_fee",
    "tender fee exemption allowed": "fee_exemption",
    "emd amount": "emd",
    "emd exemption allowed": "emd_exemption",
    "emd percentage": "emd_percentage",
    "title": "title",
    "work description": "description",
    "nda/pre qualification": "pre_qualification",
    "independent external monitor/remarks": "remarks",
    "tender value": "tender_value",
    "product category": "product_category",
    "sub category": "sub_category",
    "contract type": "contract_type",
    "bid validity(days)": "bid_validity_days",
    "period of work(days)": "period_of_work_days",
    "location": "location",
    "pincode": "pincode",
    "pre bid meeting place": "prebid_place",
    "pre bid meeting address": "prebid_address",
    "pre bid meeting date": "prebid_date",
    "bid opening place": "bid_opening_place",
    "tenderer class": "tenderer_class",
    "published date": "published",
    "bid opening date": "bid_opening",
    "document download / sale start date": "doc_start",
    "document download / sale end date": "doc_end",
    "clarification start date": "clarification_start",
    "clarification end date": "clarification_end",
    "bid submission start date": "bid_start",
    "bid submission end date": "bid_end",
    "nit document": "nit_documents",
    "work item documents": "work_documents",
    "name": "authority_name",
    "address": "authority_address",
}
AMOUNT_KEYS = {"tender_fee", "processing_fee", "emd", "tender_value"}
DATE_KEYS = {
    "published", "bid_opening", "doc_start", "doc_end", "clarification_start",
    "clarification_end", "bid_start", "bid_end", "prebid_date",
}
DOC_KEYS = {"nit_documents", "work_documents"}


def _caption_key(caption: str) -> str:
    caption = clean(caption).lower()
    caption = re.sub(r"\s*in\s*₹\s*$", "", caption)
    return DETAIL_KEYS.get(caption, "")


def parse_detail(html: str) -> dict:
    """Return normalised tender detail fields. Raises SessionExpired if not a detail page."""
    soup = BeautifulSoup(html, "lxml")
    detail: dict = {}
    for caption in soup.find_all("td", class_="td_caption"):
        value_td = caption.find_next_sibling("td")
        key = _caption_key(caption.get_text())
        if not key or value_td is None or key in detail:
            continue
        raw = clean(value_td.get_text(" "))
        if key in AMOUNT_KEYS:
            detail[key] = parse_amount(raw)
        elif key in DATE_KEYS:
            detail[key] = parse_date(raw) or (None if raw in ("", "NA") else raw)
        elif key in DOC_KEYS:
            cells = (clean(td.get_text(" ")) for td in value_td.find_all(["td", "a"]))
            detail[key] = sorted({c for c in cells if DOC_RE.match(c) and len(c) < 150})
        else:
            detail[key] = raw
    if not detail.get("tender_id"):
        raise SessionExpired("detail page did not contain a Tender ID")
    return detail


class GepnicClient:
    def __init__(self, base_url: str, delay: float = 0.5, timeout: int = 60,
                 verify_tls: bool = False, retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.retries = retries
        self.request_count = 0
        if not verify_tls:
            urllib3.disable_warnings()
        self.new_session()

    def new_session(self) -> None:
        self.session = requests.Session()
        self.session.verify = self.verify_tls
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-IN,en;q=0.9"})

    def get(self, path: str) -> str:
        url = path if path.startswith("http") else self.base_url + path
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                time.sleep(self.delay)
                response = self.session.get(url, timeout=self.timeout)
                self.request_count += 1
                response.raise_for_status()
                return response.text
            except requests.RequestException as exc:
                last_error = exc
                wait = 5 * attempt
                log.warning("GET failed (attempt %d/%d): %s - retrying in %ds", attempt, self.retries, exc, wait)
                time.sleep(wait)
        raise RuntimeError(f"GET {url} failed after {self.retries} attempts: {last_error}")

    def organisations(self) -> list[Organisation]:
        orgs = parse_org_list(self.get(ORG_LIST_PATH))
        if not orgs:
            raise RuntimeError("organisation list is empty - page layout may have changed")
        return orgs

    def org_tenders(self, org: Organisation) -> list[ListingRow]:
        return parse_org_tenders(self.get(org.link), org.name)

    def tender_detail(self, row: ListingRow) -> dict:
        return parse_detail(self.get(row.link))

    def reload_org(self, org_name: str) -> list[ListingRow]:
        """Start a fresh session and re-open an organisation's tender list (fresh links)."""
        self.new_session()
        for org in self.organisations():
            if org.name == org_name:
                return self.org_tenders(org)
        return []
