from datetime import datetime
from pathlib import Path

import pytest

from crawler.analyse import _validate, rule_analysis
from crawler.gepnic import (
    ListingRow, SessionExpired, parse_amount, parse_date, parse_detail, parse_org_list,
    parse_org_tenders,
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
              "closing": "2026-10-28T10:00", "detail": {"tender_category": "Works", "payment_mode": "Offline"}}
    profile = {"interests": ["water supply and pipelines"], "locations": ["Jodhpur"]}
    a = rule_analysis(record, profile, datetime(2026, 10, 27, 9))
    assert a["sector"] == "Water & Sanitation"
    assert a["source"] == "rules"
    assert "re-tender" in a["risk_flags"]

    v = _validate({"decision": "Worth Reading", "relevance": "180", "sector": "Bogus"}, datetime(2026, 10, 27), "m")
    assert v["decision"] == "worth_reading" and v["relevance"] == 100 and v["sector"] == "Other"
