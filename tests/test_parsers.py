from datetime import datetime
from pathlib import Path

import pytest

from crawler.analyse import (
    _validate, analyse_tenders, match_sections, parse_llm_json, rule_analysis, section_matchers,
)
from crawler.briefing import build_briefing
from crawler.districts import STATEWIDE, districts_for
from crawler.gepnic import (
    TENDER_ID_RE, ListingRow, SessionExpired, parse_amount, parse_date, parse_detail,
    parse_org_list, parse_org_tenders,
)
from crawler.store import Store, family_key

FIXTURES = Path(__file__).parent / "fixtures"
NOW = "2026-10-27T09:00"


def read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_helpers():
    assert parse_date("13-Oct-2026 03:00 PM") == "2026-10-13T15:00"
    assert parse_date("NA") is None
    assert parse_amount("15,00,000") == 1500000
    assert parse_amount("NA") is None
    assert family_key("2026_CEPWD_604884_4") == "2026_CEPWD_604884"
    assert TENDER_ID_RE.search("[TN-2206][2026_JdVVN_603006_1]").group(0) == "2026_JdVVN_603006_1"


def test_org_list():
    orgs = parse_org_list(read("org_list.html"))
    assert len(orgs) == 90
    assert sum(o.count for o in orgs) == 2149
    assert all("DirectLink" in o.link for o in orgs)


def test_org_tenders_all_rows_on_one_page():
    rows = parse_org_tenders(read("org_tenders.html"), "PWD - CE AND AS")
    assert len(rows) == 720
    assert len({r.tender_id for r in rows}) == 720
    first = rows[0]
    assert first.tender_id == "2026_CEPWD_604884_4"
    assert first.title and not first.title.startswith("[")
    assert first.closing and first.published and first.opening
    assert "FrontEndViewTender" in first.link


def test_detail():
    d = parse_detail(read("tender_detail.html"))
    assert d["tender_id"] == "2026_AGRIC_603900_1"
    assert d["ref_no"] == "ENIT 02/2026-27/3746-47 Chittorgarh"
    assert d["tender_value"] == 1500000
    assert d["emd"] == 30000
    assert d["tender_fee"] == 1000
    assert d["tender_category"] == "Goods"
    assert d["location"] == "Chittorgarh"
    assert d["pincode"] == "312001"
    assert d["bid_end"] == "2026-10-28T11:00"
    assert "Tendernotice_1.pdf" in d["nit_documents"]
    assert "BOQ_1071057.xls" in d["work_documents"]


def test_detail_rejects_non_detail_page():
    with pytest.raises(SessionExpired):
        parse_detail(read("org_list.html"))


def row(**kw):
    base = dict(tender_id="2026_TEST_1_1", title="Road work Jaipur", ref_no="NIT 1",
                org_chain="PWD", published="2026-10-20T10:00", closing="2026-11-05T18:00",
                opening="2026-11-06T11:00", link="x", organisation="PWD")
    base.update(kw)
    return ListingRow(**base)


def test_dedup_lifecycle(tmp_path):
    store = Store(tmp_path / "t.json")
    r = row()
    detail = {"tender_id": r.tender_id, "title": r.title, "tender_value": 100000.0, "bid_end": r.closing}
    assert store.classify(r) == "new"
    assert store.upsert(r, detail, NOW) == "new"
    store.save()

    store = Store(tmp_path / "t.json")
    assert store.classify(r) == "unchanged"

    moved = row(closing="2026-11-10T18:00")
    assert store.classify(moved) == "changed"
    assert store.upsert(moved, dict(detail, bid_end=moved.closing), "2026-10-28T09:00") == "updated"
    rec = store.tenders[r.tender_id]
    assert rec["changes"][-1]["fields"] == ["bid_end"]
    assert rec["first_seen"] == NOW

    retender = row(tender_id="2026_TEST_1_2")
    store.upsert(retender, dict(detail, tender_id="2026_TEST_1_2"), NOW)
    assert store.related_tenders("2026_TEST_1_2") == ["2026_TEST_1_1"]

    counts = store.mark_missing({"2026_TEST_1_2"}, "2026-11-11T09:00")
    assert counts == {"closed": 1, "removed": 0}


def test_rule_analysis_and_validation():
    record = {"tender_id": "2026_X_1_2", "title": "Laying pipeline for water supply in Jodhpur",
              "closing": "2026-10-28T10:00", "lots_in_group": 3,
              "detail": {"tender_category": "Works", "payment_mode": "Offline"}}
    profile = {"interests": ["water supply and pipelines"], "locations": ["Jodhpur"]}
    a = rule_analysis(record, profile, datetime(2026, 10, 27, 9))
    assert a["sector"] == "Water & Sanitation"
    assert a["source"] == "rules"
    assert "one lot of many" in a["risk_flags"]

    fenced = '```json\n{"results": [{"tender_id": "A", "decision": "skip"}]}\n```'
    assert parse_llm_json(fenced) == [{"tender_id": "A", "decision": "skip"}]

    v = _validate({"decision": "Worth Reading", "relevance": "180", "sector": "Bogus"}, datetime(2026, 10, 27), "m")
    assert v["decision"] == "worth_reading" and v["relevance"] == 100 and v["sector"] == "Other"
    assert v["upfront_cost_inr"] is None and v["blockers"] == []


def test_new_company_feasibility():
    now = datetime(2026, 10, 27, 9)
    profile = {"experience_years": 0, "min_days_left": 5, "max_value_inr": 2500000,
               "interests": ["stationery"], "locations": ["Jaipur"]}
    goods = {"tender_category": "Goods", "tenderer_class": "ALL", "tender_value": 1800000,
             "emd": 36000, "emd_percentage": "2.00", "emd_exemption": "Yes", "tender_fee": 590,
             "processing_fee": 500, "fee_exemption": "No", "location": "Jaipur"}
    stationery = {"tender_id": "2026_DLB_1_1", "title": "Rate contract for stationery items",
                  "closing": "2026-11-02T13:00", "detail": goods}
    a = rule_analysis(stationery, profile, now)
    assert a["decision"] == "worth_reading" and a["blockers"] == []
    assert a["upfront_cost_inr"] == 795

    works = dict(stationery, detail=dict(goods, tender_category="Works", tenderer_class="Class C"))
    a = rule_analysis(works, profile, now)
    assert a["decision"] == "skip" and len(a["blockers"]) == 2

    drugs = dict(stationery, title="Supply of drugs and medicines")
    assert rule_analysis(drugs, profile, now)["decision"] == "skip"
    assert rule_analysis(works, profile, now)["reason_hi"].startswith("अभी संभव नहीं")


def test_personalised_sections():
    sections = [{"id": "photocopy", "name_en": "Photocopy & printing", "name_hi": "फोटोकॉपी",
                 "keywords": ["photostat", "photostate", "printer", "photo copy", "flex", "lamination"]}]
    m = section_matchers(sections)

    def rec(title, **detail):
        return {"tender_id": "2026_X_1_1", "title": title, "status": "active", "closing": "2026-11-05T18:00",
                "detail": detail}

    assert match_sections(rec("PHOTOSTATE WORK AT POLICE COMMISSIONERATE JAIPUR"), m) == ["photocopy"]
    assert match_sections(rec("Supply of printers"), m) == ["photocopy"]
    assert match_sections(rec("Photo  copy job work"), m) == ["photocopy"]
    assert match_sections(rec("Flexible pipe for water supply"), m) == []
    assert match_sections(rec("HDPE laminated kraft paper bag"), m) == []
    assert match_sections(rec("Annual contract", product_category="Photostat services"), m) == ["photocopy"]

    vehicles = section_matchers([{"id": "vehicles", "name_en": "Vehicle on hire", "keywords": [
        r"re:hir(?:e|ed|ing)\b.{0,40}?\b(?:vehicles?|cars?|tractors?|jcb)",
        r"re:(?:vehicles?|cars?|tankers?)\b.{0,25}?\b(?:on|for)\s+(?:hire|rent)", "innova"]}])
    assert match_sections(rec("Hiring of 2 nos. vehicles for the office"), vehicles) == ["vehicles"]
    assert match_sections(rec("Supply of water tanker on rent basis"), vehicles) == ["vehicles"]
    assert match_sections(rec("Garage cars", description="innova crysta on rent"), vehicles) == ["vehicles"]
    assert match_sections(rec("Maintenance of parks", sub_category="Water Tanker"), vehicles) == []
    assert match_sections(rec("Supply of vehicle tyres"), vehicles) == []

    tenders = {"2026_X_1_1": rec("Photostat work", tender_category="Services", tenderer_class="ALL")}
    cfg = {"profile": {"experience_years": 0}, "llm": {"providers": []}, "personalised": sections}
    stats = analyse_tenders(tenders, cfg, datetime(2026, 10, 27, 9))
    assert tenders["2026_X_1_1"]["personal"] == ["photocopy"]
    assert stats["personalised"] == {"photocopy": 1}
    assert "personalised: Photocopy & printing" in tenders["2026_X_1_1"]["analysis"]["reason"]


def test_districts():
    assert districts_for({"location": "ADA, Ajmer"}) == ["Ajmer"]
    assert districts_for({"location": "Dholpur and Bharatpur"}) == ["Bharatpur", "Dholpur"]
    assert districts_for({"location": "Nathdwara"}) == ["Rajsamand"]
    assert districts_for({"location": "Nagar Palika Mundawar", "detail": {"pincode": "301407"}}) == ["Alwar"]
    assert districts_for({"location": "All Rajasthan"}) == [STATEWIDE]
    assert districts_for({"location": "as per NIT", "org_chain": "PHED, Jaipur||ACE (Proj.) Bharathpur"}) == ["Bharatpur"]


def test_briefing_template_without_llm():
    now = datetime(2026, 10, 27, 9)
    cfg = {"profile": {"experience_years": 0, "min_days_left": 5, "interests": ["stationery"],
                       "locations": ["Jaipur"], "base_location": "Jaipur"},
           "llm": {"providers": []}, "briefing": {"top_picks": 2}}
    detail = {"tender_category": "Goods", "tenderer_class": "ALL", "tender_value": 1800000, "emd": 36000,
              "emd_exemption": "Yes", "tender_fee": 590, "processing_fee": 500, "location": "Jaipur",
              "payment_mode": "Offline"}
    tenders = {}
    for i, title in enumerate(["Rate contract for stationery", "Supply of canvas bags", "Construction of road"]):
        rec = {"tender_id": f"2026_X_{i}_1", "title": title, "status": "active", "closing": "2026-11-02T13:00",
               "first_seen": "2026-10-27T09:00", "detail": detail}
        rec["analysis"] = rule_analysis(rec, cfg["profile"], now)
        tenders[rec["tender_id"]] = rec
    b = build_briefing(tenders, cfg, now)
    assert b["source"] == "template" and b["candidates"] == 2
    assert [p["tender_id"] for p in b["picks"]] == ["2026_X_0_1", "2026_X_1_1"]
    assert b["picks"][0]["is_new"] and b["headline_hi"] and b["picks"][1]["risks_hi"]
