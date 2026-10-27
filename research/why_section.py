"""Show which keyword text made tenders match a personalised section.

Usage: python research/why_section.py <section_id> <tender_id> [<tender_id> ...]
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from crawler.analyse import section_matchers  # noqa: E402

cfg = yaml.safe_load((ROOT / "config/settings.yaml").read_text(encoding="utf-8"))
rx = section_matchers(cfg["personalised"])[sys.argv[1]]
tenders = json.loads((ROOT / "data/tenders.json").read_text(encoding="utf-8"))["tenders"]
for tid in sys.argv[2:]:
    r = tenders[tid]
    d = r.get("detail") or {}
    for field in ("title", "description", "product_category", "sub_category"):
        text = str((d if field != "title" else r).get(field) or "")
        for m in rx.finditer(text):
            print(f"{tid} [{field}] ...{text[max(0, m.start() - 40):m.end() + 40]}...  -> {m.group(0)!r}")
