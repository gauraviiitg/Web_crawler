"""Rebuild site/ from data/tenders.json without crawling (rule analysis + briefing, no LLM unless keys set).

Works on a copy of the data so the committed file is not changed.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from crawler.analyse import analyse_tenders  # noqa: E402
from crawler.briefing import build_briefing  # noqa: E402
from crawler.report import build_site  # noqa: E402
from crawler.store import Store  # noqa: E402

cfg = yaml.safe_load((ROOT / "config/settings.yaml").read_text(encoding="utf-8"))
if "--llm" not in sys.argv:
    cfg["llm"]["providers"] = []
tmp = ROOT / "data" / "rebuild.tmp"
tmp.write_bytes((ROOT / "data/tenders.json").read_bytes())
store = Store(tmp)
now = datetime.now(timezone(timedelta(hours=5, minutes=30))).replace(tzinfo=None)
run = {"started": now.strftime("%Y-%m-%dT%H:%M"), "status": "ok", "error": None}
if "--gem" in sys.argv:
    import logging

    from crawler.gem import GemClient
    from crawler.main import crawl_gem
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr)
    gem = GemClient(delay=cfg["gem"].get("request_delay_seconds", 0.5))
    run["gem"] = crawl_gem(gem, store, now.strftime("%Y-%m-%dT%H:%M"), cfg["gem"]["state"])
    run["gem"]["requests"] = gem.request_count
run["analysis"] = analyse_tenders(store.tenders, cfg, now)
briefing = build_briefing(store.tenders, cfg, now)
build_site(store, cfg, run, now, ROOT, briefing)
tmp.unlink()
print(json.dumps(briefing, ensure_ascii=False, indent=1)[:3500])
