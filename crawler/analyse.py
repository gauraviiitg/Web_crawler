"""Tender classification and decision-making.

Primary: a free-tier LLM (Gemini, then Groq) via OpenAI-compatible APIs; keys come from
repository secrets (GEMINI_API_KEY, GROQ_API_KEY).
Fallback: keyword rules, so every tender always has a classification. Rule results are
replaced by LLM results on a later run when free-tier quota is available.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime

import requests

log = logging.getLogger(__name__)

SECTORS = [
    "Roads & Bridges", "Buildings & Civil", "Water & Sanitation", "Irrigation",
    "Power & Electrical", "Renewable Energy", "IT & Telecom", "Healthcare & Medical",
    "Education", "Agriculture", "Transport & Vehicles", "Security & Police",
    "Housekeeping & Manpower", "Consultancy", "Mining & Minerals", "Urban Development",
    "Other",
]
WORK_TYPES = ["Construction", "Supply", "Service", "Maintenance", "Consultancy", "Rate Contract", "Other"]
DECISIONS = ["worth_reading", "maybe", "skip"]
# Bump when the prompt or profile logic changes so stored LLM analyses are redone.
PROMPT_VERSION = "newco-3"
GENERIC_WORDS = {"works", "work", "services", "service", "supply", "hardware", "equipment", "and",
                 "goods", "items", "material", "supplies", "miscellaneous"}

SECTOR_KEYWORDS = {
    "Roads & Bridges": ["road", "bridge", "highway", "culvert", "bt ", "patch repair", "mdr", "odr", "pavement"],
    "Buildings & Civil": ["building", "construction of", "boundary wall", "renovation", "hospital at", "school building", "civil work"],
    "Water & Sanitation": ["pipeline", "water supply", "tubewell", "tube well", "sewer", "drain", "phed", "ro plant", "handpump"],
    "Irrigation": ["canal", "irrigation", "dam", "anicut", "ignp", "watershed"],
    "Power & Electrical": ["electrical", "transformer", "substation", "kv ", "feeder", "cable", "vvnl", "rrvpn", "rrvun", "lighting"],
    "Renewable Energy": ["solar", "renewable", "photovoltaic", "wind"],
    "IT & Telecom": ["computer", "software", "server", "network", "cctv", "it ", "laptop", "printer", "website", "data centre"],
    "Healthcare & Medical": ["medical", "hospital", "drug", "medicine", "surgical", "x-ray", "laboratory", "rmscl", "health"],
    "Education": ["school", "college", "university", "education", "text book"],
    "Agriculture": ["agricultur", "soil", "seed", "fertili", "dairy", "milk", "animal"],
    "Transport & Vehicles": ["vehicle", "bus", "taxi", "hiring of", "tyre", "rsrtc"],
    "Housekeeping & Manpower": ["housekeeping", "manpower", "cleaning", "security guard", "outsourc"],
    "Consultancy": ["consultan", "dpr", "survey", "design and supervision"],
    "Mining & Minerals": ["mining", "mineral", "rsmml"],
    "Urban Development": ["development authority", "uit", "smart city", "municipal", "nagar"],
}

SYSTEM_PROMPT = """You are an expert analyst of Indian government tenders (Rajasthan eProcurement).
For each tender, decide whether THIS reader can realistically bid and win, given the reader
profile. Judge feasibility first, interest second. Be concrete and brief.

Rajasthan rules to apply (RTPP Act 2012 / Rules 2013 and state notifications):
- Works (civil/electrical construction) need contractor registration of the stated
  tenderer class (D/C/B/A/AA); a new company cannot have it -> skip unless class is ALL
  and the job is really a supply.
- Startups registered with iStart Rajasthan get relaxation in prior experience and prior
  turnover and exemption from bid security (EMD) for GOODS and SERVICES up to Rs 1 crore,
  when the tender says "EMD exemption allowed: Yes".
- Micro & small enterprises of Rajasthan (Udyam) pay 50%% of the tender document fee,
  bid security 0.5%% instead of 2%%, and performance security 1%% for supply of goods.
- Processing fee (RISL) is never exempt; tender fee only if "fee exemption allowed: Yes".
- Items that need a licence or authorisation are hard for a new company: drugs and medicines
  (drug licence), medical/lab equipment and reagents (OEM authorisation), electrical
  equipment for discoms/power plants (approved vendor lists, type tests), manpower supply
  (labour licence, EPF/ESI), security (PSARA licence).
- Rate contracts (supply on demand over a year) need little upfront stock; one-shot supplies
  with short delivery need the bidder to fund all stock until payment (30-90 days).
- At least 5 days are needed to obtain a Class 3 DSC, enrol on the portal and prepare a bid.

Answer ONLY with JSON:
{"results": [{
  "tender_id": "<copy exactly>",
  "summary": "<plain-English summary, max 35 words: what, where, for whom>",
  "summary_hi": "<the same summary in simple Hindi (Devanagari)>",
  "sector": "<one of SECTORS>",
  "work_type": "<one of WORK_TYPES>",
  "decision": "worth_reading | maybe | skip",
  "relevance": <integer 0-100: how good a first tender this is for the reader>,
  "reason": "<max 30 words: why this decision, citing the deciding rule>",
  "reason_hi": "<the same reason in simple Hindi (Devanagari)>",
  "upfront_cost_inr": <integer estimate of cash needed to submit the bid as an iStart startup / Udyam MSE (fees + any EMD), excluding stock>,
  "blockers": ["<max 3 things the reader probably lacks, e.g. 'contractor class C registration', 'drug licence', 'OEM authorisation', 'past supply orders'>"],
  "risk_flags": ["<short flags e.g. 'closes in 2 days', 'high EMD', 'value not disclosed', 'vague scope', 'stock funding needed', 'one lot of many'>"],
  "key_requirements": ["<max 3 short items the bidder must have/do, from the data given>"],
  "tags": ["<max 5 short keywords>"],
  "personal_sections": ["<ids of the PERSONALISED SECTIONS (listed below) this tender belongs to; [] if none>"]
}]}
SECTORS: %s
WORK_TYPES: %s""" % (", ".join(SECTORS), ", ".join(WORK_TYPES))

LICENSED_RE = re.compile(
    r"drug|medicine|pharma|surgical|suture|reagent|kit|implant|graft|x-ray|radiograph|anesthesia|"
    r"pesticide|insecticide|fungicide|herbicide|emulsifiable|malathion|fertili[sz]er|"
    r"laborator|lab items|blood bag|transformer|surge arrester|kv |switchyard|insulator|meter|"
    r"manpower|man power|placement agenc|security guard|scada|spares? for|bearing|ball tube mill|"
    r"tester|injection set|test set|hospital use|dental|medical|machine|installation|commissioning|"
    r"refrigerant|fire extinguisher|ghee|food grade|fuses|sensors|energy audit|rent out|leasing",
    re.I,
)
WORKS_RE = re.compile(
    r"construction|renovation|conversion of|repair|civil work|beautification|handling and transport|"
    r"transportation work|laying|boring",
    re.I,
)


def _days_left(closing: str | None, now: datetime) -> float | None:
    if not closing:
        return None
    try:
        return (datetime.strptime(closing, "%Y-%m-%dT%H:%M") - now).total_seconds() / 86400
    except ValueError:
        return None


def tender_prompt_view(record: dict, now: datetime) -> dict:
    d = record.get("detail") or {}
    days = _days_left(record.get("closing"), now)
    view = {
        "tender_id": record["tender_id"],
        "full_details_available": bool(d),
        "reference_no": d.get("ref_no") or record.get("ref_no"),
        "title": d.get("title") or record.get("title"),
        "description": (d.get("description") or "")[:600],
        "organisation": d.get("org_chain") or record.get("org_chain"),
        "category": d.get("tender_category"),
        "product_category": d.get("product_category"),
        "sub_category": d.get("sub_category"),
        "tender_type": d.get("tender_type"),
        "contract_form": d.get("form_of_contract"),
        "value_inr": d.get("tender_value"),
        "emd_inr": d.get("emd"),
        "emd_percentage": d.get("emd_percentage"),
        "emd_exemption_allowed": d.get("emd_exemption"),
        "tender_fee_inr": d.get("tender_fee"),
        "processing_fee_inr": d.get("processing_fee"),
        "fee_exemption_allowed": d.get("fee_exemption"),
        "location": d.get("location"),
        "period_days": d.get("period_of_work_days"),
        "pre_qualification": (d.get("pre_qualification") or "")[:300],
        "tenderer_class": d.get("tenderer_class"),
        "payment_mode": d.get("payment_mode"),
        "days_left_to_bid": round(days, 1) if days is not None else None,
        "other_lots_with_same_number": record.get("lots_in_group"),
        "documents": (d.get("nit_documents") or []) + (d.get("work_documents") or []),
    }
    return {k: v for k, v in view.items() if v not in (None, "", [], "NA")}


def profile_text(profile: dict) -> str:
    parts = [profile.get("description", "").strip()]
    if profile.get("interests"):
        parts.append("Interests: " + ", ".join(profile["interests"]))
    if profile.get("locations"):
        parts.append("Preferred locations: " + ", ".join(profile["locations"]))
    if profile.get("base_location"):
        parts.append(f"Based in: {profile['base_location']}")
    if "experience_years" in profile:
        parts.append(f"Past government contract experience: {profile['experience_years']} years")
    if "budget_inr" in profile:
        parts.append(f"Cash available before first payment: Rs {profile['budget_inr']:,}")
    if profile.get("min_value_inr"):
        parts.append(f"Minimum tender value: Rs {profile['min_value_inr']:,}")
    if profile.get("max_value_inr"):
        parts.append(f"Preferred maximum tender value: Rs {profile['max_value_inr']:,}")
    if profile.get("min_days_left"):
        parts.append(f"Needs at least {profile['min_days_left']} days before the bid deadline")
    return "\n".join(p for p in parts if p)


def sections_text(sections: list[dict]) -> str:
    return "\n".join(f"- {s['id']}: {s['name_en']}. {' '.join(s.get('description', '').split())}" for s in sections)


def section_matchers(sections: list[dict]) -> dict[str, re.Pattern]:
    """Keywords match whole words (optional plural); a keyword starting with "re:" is a raw regex."""
    def part(k: str) -> str:
        return k[3:] if k.startswith("re:") else r"\s*".join(map(re.escape, k.split()))

    return {
        s["id"]: re.compile(r"\b(?:%s)(?:s|es)?\b" % "|".join(part(k) for k in s["keywords"]), re.I)
        for s in sections if s.get("keywords")
    }


def match_sections(record: dict, matchers: dict[str, re.Pattern]) -> list[str]:
    d = record.get("detail") or {}
    text = " ".join(str(x) for x in (record.get("title"), d.get("title"), d.get("description"),
                                     d.get("product_category"), d.get("sub_category")) if x)
    return [sid for sid, rx in matchers.items() if rx.search(text)]


def upfront_cost(d: dict, startup: bool = True) -> float:
    """Cash to submit a bid as an iStart startup (EMD exempt) / Udyam MSE (50% fee, 0.5% EMD)."""
    fee = 0 if (d.get("fee_exemption") or "").lower() == "yes" else (d.get("tender_fee") or 0) / 2
    emd = d.get("emd") or 0
    if startup and (d.get("emd_exemption") or "").lower() == "yes":
        emd = 0
    elif emd and (d.get("emd_percentage") or "").startswith("2"):
        emd = emd / 4
    return round(fee + (d.get("processing_fee") or 0) + emd)


def feasibility_blockers(record: dict, profile: dict, now: datetime) -> list[tuple[str, str]]:
    """Hard reasons a new, zero-experience company cannot bid, as (English, Hindi) pairs."""
    d = record.get("detail") or {}
    if profile.get("experience_years", 1) > 0:
        return []
    blockers = []
    category = (d.get("tender_category") or "").lower()
    tclass = (d.get("tenderer_class") or "ALL").upper()
    text = " ".join(str(x) for x in (record.get("title"), d.get("description"), d.get("product_category"),
                                     d.get("sub_category")) if x)
    if category == "works" or WORKS_RE.search(text):
        blockers.append(("works / labour contract (needs contractor registration or fleet)",
                         "निर्माण / श्रम कार्य (ठेकेदार पंजीकरण या वाहन चाहिए)"))
    if tclass not in ("ALL", ""):
        blockers.append((f"needs {d.get('tenderer_class')} registration",
                         f"{d.get('tenderer_class')} पंजीकरण आवश्यक"))
    value = d.get("tender_value") or 0
    if value > 1e7:
        blockers.append(("above Rs 1 crore (no startup relaxation)", "₹1 करोड़ से अधिक (स्टार्टअप छूट नहीं)"))
    elif profile.get("max_value_inr") and value > 2 * profile["max_value_inr"]:
        blockers.append(("too large for a first order (stock funding)", "पहले ऑर्डर के लिए बहुत बड़ा (माल हेतु पूंजी)"))
    if LICENSED_RE.search(text):
        blockers.append(("licence / OEM authorisation likely needed", "लाइसेंस / निर्माता अधिकार-पत्र संभवतः आवश्यक"))
    if d and upfront_cost(d) > profile.get("max_upfront_inr", float("inf")):
        blockers.append((f"about Rs {upfront_cost(d):,} cash needed to bid",
                         f"बोली के लिए लगभग ₹{upfront_cost(d):,} नकद चाहिए"))
    days = _days_left(record.get("closing"), now)
    if days is not None and days < profile.get("min_days_left", 0):
        blockers.append((f"only {max(days, 0):.0f} days left", f"केवल {max(days, 0):.0f} दिन शेष"))
    if record.get("source") == "gem":
        if "Reverse Auction" in (d.get("tender_type") or ""):
            blockers.append(("reverse auction: only sellers who qualified in the bid",
                             "रिवर्स ऑक्शन: केवल बोली में योग्य विक्रेता"))
        if d.get("limited_tender") == "Yes":
            blockers.append(("limited tender: invited sellers only", "सीमित निविदा: केवल आमंत्रित विक्रेता"))
        if d.get("global_tender") == "Yes":
            blockers.append(("global tender", "वैश्विक निविदा"))
    return blockers


def rule_analysis(record: dict, profile: dict, now: datetime, personal: list[tuple[str, str]] = ()) -> dict:
    """personal: (English, Hindi) names of the personalised sections this tender matches."""
    d = record.get("detail") or {}
    text = " ".join(
        str(x) for x in (record.get("title"), d.get("description"), d.get("product_category"),
                         d.get("sub_category"), record.get("org_chain"))
        if x
    ).lower() + " "
    scores = {s: sum(k in text for k in kws) for s, kws in SECTOR_KEYWORDS.items()}
    sector = max(scores, key=scores.get) if max(scores.values()) else "Other"
    category = (d.get("tender_category") or "").lower()
    work_type = {"goods": "Supply", "services": "Service", "works": "Construction"}.get(category, "Other")
    try:
        period = int(d.get("period_of_work_days") or 0)
    except ValueError:
        period = 0
    if "rate contract" in text or (category == "goods" and period >= 300):
        work_type = "Rate Contract"
    elif "maintenance" in text or "repair" in text:
        work_type = "Maintenance"

    interests = [i.lower() for i in profile.get("interests", [])]
    locations = [l.lower() for l in profile.get("locations", [])]
    hits = [
        i for i in interests
        if any(re.search(rf"\b{re.escape(w)}", text) for w in i.split() if len(w) > 3 and w not in GENERIC_WORDS)
    ]
    place = f"{d.get('location') or ''} {d.get('authority_address') or ''}".lower()
    loc_hit = any(l in place for l in locations)
    days = _days_left(record.get("closing"), now)
    flags = []
    if days is not None and days < 3:
        flags.append(f"closes in {max(days, 0):.0f} days")
    if not d:
        flags.append("details not fetched yet")
    elif record.get("source") == "gem":
        flags.append("GeM: value, EMD and eligibility are in the bid PDF")
    elif not d.get("tender_value"):
        flags.append("value not disclosed")
    if record.get("lots_in_group"):
        flags.append("one lot of many")
    if (d.get("payment_mode") or "").lower() == "offline":
        flags.append("offline payment")

    blockers = feasibility_blockers(record, profile, now)
    if personal:
        large = [b for b in blockers if b[0].startswith("too large")]
        blockers = [b for b in blockers if b not in large]
        flags += ["large contract: needs capital for machines/staff/stock" for _ in large[:1]]
    cost = upfront_cost(d) if d else None
    max_value = profile.get("max_value_inr") or 0
    if blockers:
        relevance = 0
    else:
        relevance = (40 + 15 * min(len(hits), 2) + (20 if loc_hit else -10 if locations else 0)
                     + (10 if work_type == "Rate Contract" else 0)
                     + (10 if cost is not None and cost <= 2000 else 0)
                     - (15 if max_value and (d.get("tender_value") or 0) > max_value else 0)
                     + (15 if personal else 0))
        relevance = max(0, min(100, relevance))
    decision = "worth_reading" if relevance >= 70 else "maybe" if relevance >= 45 else "skip"
    base = profile.get("base_location", "")
    if blockers:
        reason = "Not feasible yet: " + "; ".join(en for en, _ in blockers)
        reason_hi = "अभी संभव नहीं: " + "; ".join(hi for _, hi in blockers)
    else:
        parts = [
            ("personalised: " + ", ".join(en for en, _ in personal),
             "व्यक्तिगत: " + ", ".join(hi for _, hi in personal)) if personal else None,
            ("in " + base, base + " में") if loc_hit else None,
            ("matches " + ", ".join(hits), "रुचि से मेल: " + ", ".join(hits)) if hits else None,
            ("rate contract", "दर अनुबंध (रेट कॉन्ट्रैक्ट)") if work_type == "Rate Contract" else None,
            (f"upfront about Rs {cost:,}", f"शुरुआती खर्च लगभग ₹{cost:,}") if cost is not None else None,
        ]
        parts = [p for p in parts if p]
        reason = ", ".join(en for en, _ in parts) or "goods/services open to all bidders"
        reason_hi = ", ".join(hi for _, hi in parts) or "सभी बोलीदाताओं के लिए खुली सामग्री/सेवा"
    title = record.get("title") or d.get("title") or ""
    return {
        "summary": title[:200],
        "sector": sector,
        "work_type": work_type,
        "decision": decision,
        "relevance": relevance,
        "reason": reason[:300],
        "reason_hi": reason_hi[:300],
        "upfront_cost_inr": cost,
        "blockers": [en for en, _ in blockers][:3],
        "blockers_hi": [hi for _, hi in blockers][:3],
        "risk_flags": flags,
        "key_requirements": [],
        "tags": hits[:5],
        "source": "rules",
        "analysed_at": now.strftime("%Y-%m-%dT%H:%M"),
    }


class QuotaExhausted(Exception):
    pass


class LLMClient:
    """OpenAI-compatible chat-completions client for one provider (Gemini, Groq, ...)."""

    def __init__(self, provider: dict, api_key: str):
        self.name = provider["name"]
        self.endpoint = provider["endpoint"]
        self.models = list(provider["models"])
        self.delay = provider.get("seconds_between_requests", 5)
        self.max_requests = provider.get("max_requests_per_run", 100)
        self.json_mode = provider.get("json_mode", True)
        self.api_key = api_key
        self.requests_made = 0
        self.model_in_use = self.models[0]

    def complete(self, messages: list[dict]) -> str:
        if self.requests_made >= self.max_requests:
            raise QuotaExhausted(f"{self.name}: per-run request budget used")
        for _ in range(4):
            time.sleep(self.delay)
            self.requests_made += 1
            body = {"model": self.model_in_use, "messages": messages, "temperature": 0.2}
            if self.json_mode:
                body["response_format"] = {"type": "json_object"}
            response = requests.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=180,
                allow_redirects=False,
            )
            if response.status_code == 200:
                try:
                    content = response.json()["choices"][0]["message"]["content"]
                except (ValueError, KeyError, IndexError, TypeError) as exc:
                    raise RuntimeError(
                        f"{self.name}: unexpected response ({exc}); content-type="
                        f"{response.headers.get('Content-Type')} body={response.text[:300]!r}"
                    ) from exc
                if not content:
                    raise RuntimeError(f"{self.name}: empty content: {response.text[:300]!r}")
                return content
            if response.status_code == 429:
                retry_after = int(float(response.headers.get("retry-after", "30") or 30))
                if retry_after > 120 or "day" in response.text.lower():
                    if self._next_model():
                        continue
                    raise QuotaExhausted(f"{self.name}: daily quota reached ({response.text[:150]})")
                log.warning("%s rate limited, sleeping %ss", self.name, retry_after)
                time.sleep(retry_after)
                continue
            if response.status_code == 400 and self.json_mode and "response_format" in response.text:
                log.warning("%s does not accept JSON mode; retrying without it", self.name)
                self.json_mode = False
                continue
            if response.status_code in (400, 404) and "model" in response.text.lower() and self._next_model():
                continue
            if response.status_code in (401, 403):
                raise QuotaExhausted(f"{self.name}: key rejected ({response.status_code} {response.text[:200]})")
            log.warning("%s call failed %s: %s", self.name, response.status_code, response.text[:300])
        raise RuntimeError(f"{self.name}: call failed after retries")

    def _next_model(self) -> bool:
        idx = self.models.index(self.model_in_use)
        if idx + 1 < len(self.models):
            self.model_in_use = self.models[idx + 1]
            log.info("switching LLM model to %s", self.model_in_use)
            return True
        return False


def parse_llm_json(content: str) -> list[dict]:
    """Parse the model's JSON answer, tolerating code fences or text around it."""
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in LLM answer: {content[:300]!r}")
    data = json.loads(text[start:end + 1])
    results = data.get("results", data if isinstance(data, list) else [])
    return results if isinstance(results, list) else []


def _validate(item: dict, now: datetime, model: str, full_details: bool = True,
              section_ids: tuple[str, ...] = ()) -> dict:
    decision = str(item.get("decision", "maybe")).strip().lower().replace(" ", "_")
    sector = item.get("sector") if item.get("sector") in SECTORS else "Other"
    work_type = item.get("work_type") if item.get("work_type") in WORK_TYPES else "Other"
    try:
        relevance = max(0, min(100, int(item.get("relevance", 0))))
    except (TypeError, ValueError):
        relevance = 0

    def str_list(value, limit):
        return [str(v)[:80] for v in value][:limit] if isinstance(value, list) else []

    try:
        cost = max(0, int(float(item.get("upfront_cost_inr"))))
    except (TypeError, ValueError):
        cost = None

    return {
        "summary": str(item.get("summary", ""))[:400],
        "summary_hi": str(item.get("summary_hi", ""))[:400],
        "sector": sector,
        "work_type": work_type,
        "decision": decision if decision in DECISIONS else "maybe",
        "relevance": relevance,
        "reason": str(item.get("reason", ""))[:300],
        "reason_hi": str(item.get("reason_hi", ""))[:300],
        "upfront_cost_inr": cost,
        "blockers": str_list(item.get("blockers"), 3),
        "risk_flags": str_list(item.get("risk_flags"), 6),
        "key_requirements": str_list(item.get("key_requirements"), 3),
        "tags": str_list(item.get("tags"), 5),
        "personal_sections": [s for s in str_list(item.get("personal_sections"), 5) if s in section_ids],
        "source": "llm",
        "prompt_version": prompt_version(section_ids),
        "basis": "full" if full_details else "listing",
        "model": model,
        "analysed_at": now.strftime("%Y-%m-%dT%H:%M"),
    }


def analyse_tenders(tenders: dict, cfg: dict, now: datetime) -> dict:
    """Analyse active tenders lacking an LLM analysis. Mutates records; returns stats."""
    profile = cfg["profile"]
    stats = {"llm": 0, "rules": 0, "llm_error": None, "model": None}
    family_sizes: dict[str, int] = {}
    for r in tenders.values():
        if r.get("status") == "active":
            family_sizes[r.get("family")] = family_sizes.get(r.get("family"), 0) + 1
    for r in tenders.values():
        r["lots_in_group"] = family_sizes.get(r.get("family"), 1) - 1 or None
    sections = cfg.get("personalised") or []
    names = {s["id"]: (s["name_en"], s.get("name_hi") or s["name_en"]) for s in sections}
    matchers = section_matchers(sections)
    rule_sections = {
        r["tender_id"]: match_sections(r, matchers) for r in tenders.values() if r.get("status") == "active"
    }
    version = prompt_version(tuple(names))
    keep_llm = cfg["llm"].get("enabled", True)
    pending = [r for r in tenders.values()
               if r.get("status") == "active" and not (keep_llm and _llm_current(r, version))]
    pending.sort(key=lambda r: (r.get("first_seen", ""), r.get("closing") or ""), reverse=True)

    for record in pending:
        personal = [names[s] for s in rule_sections[record["tender_id"]]]
        record["analysis"] = rule_analysis(record, profile, now, personal)
        stats["rules"] += 1
    _analyse_llm(tenders, cfg, now, pending, stats, sections)
    for tid, ids in rule_sections.items():
        llm_ids = (tenders[tid].get("analysis") or {}).get("personal_sections") or []
        tenders[tid]["personal"] = sorted(set(ids) | set(llm_ids))
    stats["personalised"] = {
        sid: sum(sid in (tenders[t].get("personal") or []) for t in rule_sections) for sid in names
    }
    return stats


def _analyse_llm(tenders: dict, cfg: dict, now: datetime, pending: list[dict], stats: dict,
                 sections: list[dict]) -> dict:
    profile = cfg["profile"]
    section_ids = tuple(s["id"] for s in sections)

    clients = llm_clients(cfg)
    if not cfg["llm"].get("enabled", True):
        stats["llm_disabled"] = True
        return stats
    if not clients:
        names = ", ".join(p["api_key_env"] for p in cfg["llm"]["providers"])
        stats["llm_error"] = f"no LLM API key set ({names}) - rule-based analysis only"
        stats["llm_pending"] = len(pending)
        return stats

    batch_size = cfg["llm"].get("batch_size", 8)
    system = SYSTEM_PROMPT + "\n\nREADER PROFILE:\n" + profile_text(profile)
    if sections:
        system += ("\n\nPERSONALISED SECTIONS (the owner follows these closely; a tender in one of them "
                   "deserves a higher relevance if feasible):\n" + sections_text(sections))
    client = clients.pop(0)
    consecutive_failures = 0
    stats["models"] = {}
    stats["llm_requests"] = 0
    batches = [pending[i:i + batch_size] for i in range(0, len(pending), batch_size)]
    while batches and client is not None:
        batch = batches[0]
        payload = [tender_prompt_view(r, now) for r in batch]
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": "Today is %s.\nTenders:\n%s" % (
                now.strftime("%d %b %Y"), json.dumps(payload, ensure_ascii=False))},
        ]
        try:
            before = client.requests_made
            results = parse_llm_json(client.complete(messages))
            stats["llm_requests"] += client.requests_made - before
            consecutive_failures = 0
        except (QuotaExhausted, RuntimeError, ValueError, KeyError, requests.RequestException) as exc:
            log.warning("LLM batch failed: %s", exc)
            stats["llm_error"] = str(exc)[:300]
            consecutive_failures += 1
            if isinstance(exc, QuotaExhausted) or consecutive_failures >= 3:
                log.warning("giving up on %s for this run", client.name)
                client = clients.pop(0) if clients else None
                consecutive_failures = 0
            else:
                batches.pop(0)
            continue
        batches.pop(0)
        label = f"{client.name}:{client.model_in_use}"
        by_id = {r["tender_id"]: r for r in batch}
        for item in results:
            record = by_id.get(str(item.get("tender_id", "")).strip())
            if record is not None:
                record["analysis"] = _validate(item, now, label, bool(record.get("detail")), section_ids)
                stats["llm"] += 1
                stats["models"][label] = stats["models"].get(label, 0) + 1
        stats["model"] = label
    version = prompt_version(section_ids)
    stats["llm_pending"] = sum(
        1 for r in tenders.values() if r.get("status") == "active" and not _llm_current(r, version))
    return stats


def prompt_version(section_ids: tuple[str, ...]) -> str:
    """Changes when the prompt or the list of personalised sections changes."""
    return PROMPT_VERSION + (":" + ",".join(section_ids) if section_ids else "")


def _llm_current(record: dict, version: str) -> bool:
    a = record.get("analysis") or {}
    return a.get("source") == "llm" and a.get("prompt_version") == version


def llm_clients(cfg: dict) -> list[LLMClient]:
    if not cfg["llm"].get("enabled", True):
        return []
    return [LLMClient(p, os.environ[p["api_key_env"]]) for p in cfg["llm"]["providers"]
            if os.environ.get(p["api_key_env"])]
