"""Daily "top picks for us" briefing: ranks feasible tenders and writes advice in English + Hindi.

The LLM (same free providers as the per-tender analysis) writes the text in one request;
without a key, or if the call fails, a template briefing is built from the analysis data.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

import requests

from .analyse import QuotaExhausted, _days_left, llm_clients, profile_text, tender_prompt_view, upfront_cost

log = logging.getLogger(__name__)

BRIEFING_PROMPT = """You are a government-tender advisor for the company described below.
From the candidate tenders (already filtered for feasibility), pick the best first bids and
write a short, practical daily briefing, like a consultant's note to the owner.

How to rank: realistic to win and deliver for a new company with no experience and no cash
(loan only after winning) > Jaipur location > rate contract (supply on demand) > low cash to
bid (fees + EMD; EMD exemption for iStart startups, 0.5%% EMD and half fee for Udyam MSEs) >
common items buyable from Jaipur wholesalers on credit > enough days to prepare.
Mention concrete risks: stock funding for one-shot supply, short delivery, offline payment
(original EMD/fee instruments must reach the office before the deadline), licences, slow payment.

Answer ONLY with JSON:
{"headline_en": "<1 sentence: what matters today>",
 "headline_hi": "<same in simple Hindi>",
 "picks": [{"tender_id": "<copy exactly>", "rank": <1..N>,
            "why_en": "<max 35 words>", "why_hi": "<same in Hindi>",
            "risks_en": ["<max 3 short risks>"], "risks_hi": ["<same in Hindi>"],
            "next_step_en": "<the single next action, max 20 words>", "next_step_hi": "<same in Hindi>"}],
 "advice_en": ["<max 4 short general tips for this week>"],
 "advice_hi": ["<same in Hindi>"]}
Include at most %d picks, best first. Use only the given tender IDs."""

ADVICE_EN = [
    "Bid with your own small cash (fees + EMD); apply for the loan in parallel and use the work order to get it sanctioned.",
    "Prefer rate contracts: you buy stock only when an order arrives.",
    "Download the NIT and BOQ, check experience/turnover clauses and quote the startup/MSE relaxation if needed.",
    "For 'Offline' payment tenders, deliver the original fee/EMD instruments to the office before the deadline.",
]
ADVICE_HI = [
    "बोली अपने थोड़े पैसों (शुल्क + ईएमडी) से लगाएँ; ऋण के लिए साथ-साथ आवेदन करें और कार्यादेश मिलने पर स्वीकृत कराएँ।",
    "दर अनुबंध (रेट कॉन्ट्रैक्ट) चुनें: माल तभी खरीदना होता है जब ऑर्डर आए।",
    "एनआईटी और बीओक्यू डाउनलोड करें, अनुभव/टर्नओवर शर्तें जाँचें और ज़रूरत हो तो स्टार्टअप/एमएसई छूट का हवाला दें।",
    "'ऑफलाइन' भुगतान वाले टेंडर में शुल्क/ईएमडी के मूल दस्तावेज़ अंतिम तिथि से पहले कार्यालय में जमा करें।",
]


def candidates(tenders: dict, profile: dict, now: datetime, limit: int) -> list[dict]:
    rank = {"worth_reading": 0, "maybe": 1}
    pool = []
    for r in tenders.values():
        a = r.get("analysis") or {}
        days = _days_left(r.get("closing"), now)
        if (r.get("status") != "active" or a.get("decision") not in rank or a.get("blockers")
                or days is None or days < 1):
            continue
        pool.append(r)
    pool.sort(key=lambda r: (rank[r["analysis"]["decision"]], -(r["analysis"].get("relevance") or 0),
                             r.get("closing") or ""))
    return pool[:limit]


def _fact_card(r: dict, now: datetime) -> dict:
    d = r.get("detail") or {}
    a = r.get("analysis") or {}
    days = _days_left(r.get("closing"), now)
    return {
        "tender_id": r["tender_id"],
        "title": d.get("title") or r.get("title"),
        "authority": d.get("authority_name") or r.get("organisation"),
        "location": d.get("location"),
        "value": d.get("tender_value"),
        "emd": d.get("emd"),
        "emd_exemption": d.get("emd_exemption"),
        "payment_mode": d.get("payment_mode"),
        "closing": r.get("closing"),
        "days_left": round(days, 1) if days is not None else None,
        "cash_to_bid": a.get("upfront_cost_inr") if a.get("upfront_cost_inr") is not None else (upfront_cost(d) if d else None),
        "work_type": a.get("work_type"),
        "decision": a.get("decision"),
        "relevance": a.get("relevance"),
        "is_new": (r.get("first_seen") or "")[:10] == now.strftime("%Y-%m-%d"),
    }


def _template(cards: list[dict], records: dict, now: datetime) -> dict:
    picks = []
    for i, c in enumerate(cards, 1):
        a = records[c["tender_id"]].get("analysis") or {}
        risks_en, risks_hi = [], []
        if c["work_type"] != "Rate Contract":
            risks_en.append("one-shot supply: stock must be funded until payment")
            risks_hi.append("एकमुश्त आपूर्ति: भुगतान तक माल की पूंजी लगानी होगी")
        if (c["payment_mode"] or "").lower() == "offline":
            risks_en.append("offline payment: original instruments due at the office before the deadline")
            risks_hi.append("ऑफलाइन भुगतान: मूल दस्तावेज़ अंतिम तिथि से पहले कार्यालय में")
        if c["days_left"] is not None and c["days_left"] < 5:
            risks_en.append(f"only {c['days_left']:.0f} days left")
            risks_hi.append(f"केवल {c['days_left']:.0f} दिन शेष")
        picks.append({
            **c, "rank": i,
            "why_en": a.get("reason", ""), "why_hi": a.get("reason_hi") or a.get("reason", ""),
            "risks_en": risks_en, "risks_hi": risks_hi,
            "next_step_en": "Download the NIT + BOQ on the portal and check eligibility; get wholesaler rates.",
            "next_step_hi": "पोर्टल से एनआईटी + बीओक्यू डाउनलोड करें, पात्रता जाँचें; थोक विक्रेता से दरें लें।",
        })
    new = sum(c["is_new"] for c in cards)
    return {
        "headline_en": f"{len(cards)} suitable tenders open ({new} new today)."
                       + (f" Nearest deadline: {cards[0]['closing'].replace('T', ' ')}." if cards else ""),
        "headline_hi": f"{len(cards)} उपयुक्त टेंडर खुले हैं (आज {new} नए)।",
        "picks": picks,
        "advice_en": ADVICE_EN,
        "advice_hi": ADVICE_HI,
        "source": "template",
    }


def _merge(llm: dict, cards: list[dict], top_n: int) -> dict:
    by_id = {c["tender_id"]: c for c in cards}
    picks = []
    for item in llm.get("picks") or []:
        card = by_id.get(str(item.get("tender_id", "")).strip())
        if card is None or any(p["tender_id"] == card["tender_id"] for p in picks) or len(picks) >= top_n:
            continue

        def text(key, limit=300):
            return str(item.get(key) or "")[:limit]

        def items(key):
            v = item.get(key)
            return [str(x)[:120] for x in v][:3] if isinstance(v, list) else []

        picks.append({**card, "rank": len(picks) + 1,
                      "why_en": text("why_en"), "why_hi": text("why_hi"),
                      "risks_en": items("risks_en"), "risks_hi": items("risks_hi"),
                      "next_step_en": text("next_step_en", 200), "next_step_hi": text("next_step_hi", 200)})
    if not picks:
        raise ValueError("LLM briefing contained no valid picks")

    def lines(key):
        v = llm.get(key)
        return [str(x)[:300] for x in v][:4] if isinstance(v, list) else []

    return {"headline_en": str(llm.get("headline_en") or "")[:300],
            "headline_hi": str(llm.get("headline_hi") or "")[:300],
            "picks": picks, "advice_en": lines("advice_en") or ADVICE_EN,
            "advice_hi": lines("advice_hi") or ADVICE_HI, "source": "llm"}


def build_briefing(tenders: dict, cfg: dict, now: datetime) -> dict:
    profile = cfg["profile"]
    top_n = cfg.get("briefing", {}).get("top_picks", 6)
    pool = candidates(tenders, profile, now, cfg.get("briefing", {}).get("candidates", 15))
    cards = [_fact_card(r, now) for r in pool]
    records = {r["tender_id"]: r for r in pool}
    briefing = None
    if cards:
        for client in llm_clients(cfg):
            try:
                messages = [
                    {"role": "system", "content": BRIEFING_PROMPT % top_n + "\n\nCOMPANY PROFILE:\n" + profile_text(profile)},
                    {"role": "user", "content": "Today is %s.\nCandidates:\n%s" % (now.strftime("%d %b %Y"), json.dumps(
                        [{**tender_prompt_view(r, now), "analysis_reason": r["analysis"].get("reason"),
                          "cash_to_bid_inr": c["cash_to_bid"], "work_type": c["work_type"]}
                         for r, c in zip(pool, cards)], ensure_ascii=False))},
                ]
                content = client.complete(messages)
                start, end = content.find("{"), content.rfind("}")
                briefing = _merge(json.loads(content[start:end + 1]), cards, top_n)
                briefing["model"] = f"{client.name}:{client.model_in_use}"
                break
            except (QuotaExhausted, RuntimeError, ValueError, KeyError, requests.RequestException) as exc:
                log.warning("briefing via %s failed: %s", client.name, exc)
    if briefing is None:
        briefing = _template(cards[:top_n], records, now)
    briefing["generated_at"] = now.strftime("%Y-%m-%dT%H:%M")
    briefing["candidates"] = len(cards)
    return briefing
