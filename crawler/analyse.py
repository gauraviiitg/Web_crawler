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
GENERIC_WORDS = {"works", "work", "services", "service", "supply", "hardware", "equipment", "and"}

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
For each tender you receive, classify it and decide whether the reader should open the
tender documents, based on the reader profile. Be concrete and brief. Answer ONLY with JSON:
{"results": [{
  "tender_id": "<copy exactly>",
  "summary": "<plain-English summary, max 35 words: what, where, for whom>",
  "sector": "<one of SECTORS>",
  "work_type": "<one of WORK_TYPES>",
  "decision": "worth_reading | maybe | skip",
  "relevance": <integer 0-100 for the reader profile>,
  "reason": "<max 25 words: why this decision>",
  "risk_flags": ["<short flags e.g. 'closes in 2 days', 'high EMD', 'value not disclosed', 'vague scope', 'offline payment', 'one lot of many'>"],
  "key_requirements": ["<max 3 short items the bidder must have/do, from the data given>"],
  "tags": ["<max 5 short keywords>"]
}]}
SECTORS: %s
WORK_TYPES: %s""" % (", ".join(SECTORS), ", ".join(WORK_TYPES))


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
        "fee_inr": d.get("tender_fee"),
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
    if profile.get("min_value_inr"):
        parts.append(f"Minimum tender value: Rs {profile['min_value_inr']:,}")
    if profile.get("max_value_inr"):
        parts.append(f"Maximum tender value: Rs {profile['max_value_inr']:,}")
    return "\n".join(p for p in parts if p)


def rule_analysis(record: dict, profile: dict, now: datetime) -> dict:
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
    if "rate contract" in text:
        work_type = "Rate Contract"
    elif "maintenance" in text or "repair" in text:
        work_type = "Maintenance"

    interests = [i.lower() for i in profile.get("interests", [])]
    locations = [l.lower() for l in profile.get("locations", [])]
    hits = [
        i for i in interests
        if any(re.search(rf"\b{re.escape(w)}", text) for w in i.split() if len(w) > 3 and w not in GENERIC_WORDS)
    ]
    loc_hit = any(l in text or l in (d.get("location") or "").lower() for l in locations)
    days = _days_left(record.get("closing"), now)
    flags = []
    if days is not None and days < 3:
        flags.append(f"closes in {max(days, 0):.0f} days")
    if not d:
        flags.append("details not fetched yet")
    elif not d.get("tender_value"):
        flags.append("value not disclosed")
    if record.get("lots_in_group"):
        flags.append("one lot of many")
    if (d.get("payment_mode") or "").lower() == "offline":
        flags.append("offline payment")

    relevance = (30 * min(len(hits), 2) + (20 if loc_hit else 0) + (10 if d.get("tender_value") else 0)
                 + (10 if days is not None and days >= 5 else 0))
    if days is not None and days < 1:
        relevance = max(0, relevance - 30)
    decision = "worth_reading" if hits and relevance >= 70 else "maybe" if hits and relevance >= 40 else "skip"
    title = record.get("title") or d.get("title") or ""
    return {
        "summary": title[:200],
        "sector": sector,
        "work_type": work_type,
        "decision": decision,
        "relevance": relevance,
        "reason": ("Matches: " + ", ".join(hits)) if hits else "No profile keyword match (rule-based)",
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


def _validate(item: dict, now: datetime, model: str, full_details: bool = True) -> dict:
    decision = str(item.get("decision", "maybe")).strip().lower().replace(" ", "_")
    sector = item.get("sector") if item.get("sector") in SECTORS else "Other"
    work_type = item.get("work_type") if item.get("work_type") in WORK_TYPES else "Other"
    try:
        relevance = max(0, min(100, int(item.get("relevance", 0))))
    except (TypeError, ValueError):
        relevance = 0

    def str_list(value, limit):
        return [str(v)[:80] for v in value][:limit] if isinstance(value, list) else []

    return {
        "summary": str(item.get("summary", ""))[:400],
        "sector": sector,
        "work_type": work_type,
        "decision": decision if decision in DECISIONS else "maybe",
        "relevance": relevance,
        "reason": str(item.get("reason", ""))[:300],
        "risk_flags": str_list(item.get("risk_flags"), 6),
        "key_requirements": str_list(item.get("key_requirements"), 3),
        "tags": str_list(item.get("tags"), 5),
        "source": "llm",
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
    pending = [
        r for r in tenders.values()
        if r.get("status") == "active" and (r.get("analysis") or {}).get("source") != "llm"
    ]
    pending.sort(key=lambda r: (r.get("first_seen", ""), r.get("closing") or ""), reverse=True)

    for record in pending:
        record["analysis"] = rule_analysis(record, profile, now)
        stats["rules"] += 1

    clients = [
        LLMClient(p, os.environ[p["api_key_env"]])
        for p in cfg["llm"]["providers"]
        if os.environ.get(p["api_key_env"])
    ]
    if not clients:
        names = ", ".join(p["api_key_env"] for p in cfg["llm"]["providers"])
        stats["llm_error"] = f"no LLM API key set ({names}) - rule-based analysis only"
        stats["llm_pending"] = len(pending)
        return stats

    batch_size = cfg["llm"].get("batch_size", 8)
    system = SYSTEM_PROMPT + "\n\nREADER PROFILE:\n" + profile_text(profile)
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
                record["analysis"] = _validate(item, now, label, bool(record.get("detail")))
                stats["llm"] += 1
                stats["models"][label] = stats["models"].get(label, 0) + 1
        stats["model"] = label
    stats["llm_pending"] = sum(
        1 for r in tenders.values()
        if r.get("status") == "active" and (r.get("analysis") or {}).get("source") != "llm"
    )
    return stats
