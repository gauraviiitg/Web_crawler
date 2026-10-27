"""Daily pipeline: crawl -> de-duplicate -> fetch details -> analyse -> build site.

Usage:
  python -m crawler.main                 # full run
  python -m crawler.main --max-orgs 3    # quick test on the first 3 organisations
  python -m crawler.main --no-llm        # skip the LLM (rule-based analysis only)
  python -m crawler.main --no-gem        # skip GeM
  python -m crawler.main --gem-snapshot data/gem_bids.json   # only fetch GeM bids (needs an Indian IP)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from .analyse import analyse_tenders
from .briefing import build_briefing
from .gem import GemClient, load_snapshot, save_snapshot
from .gem import first as gem_first
from .gem import to_row as gem_row
from .gepnic import GepnicClient, SessionExpired
from .report import build_site
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))
log = logging.getLogger("crawler")


MAX_CONSECUTIVE_DETAIL_FAILURES = 5


def crawl(client: GepnicClient, store: Store, now_str: str, max_orgs: int | None) -> dict:
    stats = {"organisations": 0, "listed": 0, "new": 0, "updated": 0, "unchanged": 0,
             "detail_errors": 0, "details_disabled": False, "complete": False}
    seen: set[str] = set()
    consecutive_failures = 0
    orgs = client.organisations()
    if max_orgs:
        orgs = orgs[:max_orgs]
    log.info("%d organisations, %d tenders advertised", len(orgs), sum(o.count for o in orgs))

    for org in orgs:
        rows = client.org_tenders(org)
        stats["organisations"] += 1
        stats["listed"] += len(rows)
        if len(rows) < org.count:
            log.warning("%s: expected %d tenders, parsed %d", org.name, org.count, len(rows))
        for row in rows:
            seen.add(row.tender_id)
            kind = store.classify(row)
            if kind == "unchanged":
                store.touch(row, now_str)
                stats["unchanged"] += 1
                continue
            detail = None
            for attempt in range(2):
                if stats["details_disabled"]:
                    break
                try:
                    detail = client.tender_detail(row)
                    consecutive_failures = 0
                    break
                except (SessionExpired, RuntimeError) as exc:
                    log.warning("detail %s failed (%s); refreshing session", row.tender_id, exc)
                    fresh = {r.tender_id: r for r in client.reload_org(org.name)}
                    if row.tender_id not in fresh:
                        break
                    row = fresh[row.tender_id]
            if detail is None:
                stats["detail_errors"] += 1
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_DETAIL_FAILURES and not stats["details_disabled"]:
                    stats["details_disabled"] = True
                    log.error("portal refuses tender detail pages; continuing with listing data only")
            outcome = store.upsert(row, detail, now_str)
            stats[outcome] = stats.get(outcome, 0) + 1
        log.info("%-60s listed=%-4d new=%d updated=%d", org.name[:60], len(rows), stats["new"], stats["updated"])

    stats["complete"] = max_orgs is None
    if stats["complete"]:
        stats.update(store.mark_missing(seen, now_str))
    return stats


def crawl_gem(client: GemClient, store: Store, now_str: str, state: str) -> dict:
    bids, stats = client.state_bids(state)
    return merge_gem(bids, stats, store, now_str, state)


def merge_gem(bids: list, stats: dict, store: Store, now_str: str, state: str) -> dict:
    stats = {**stats, "new": 0, "updated": 0, "unchanged": 0, "cancelled": 0}
    seen: set[str] = set()
    for doc, cities in bids:
        if gem_first(doc, "b_status") in (3, 5):
            stats["cancelled"] += 1
            continue
        row, detail = gem_row(doc, cities)
        seen.add(row.tender_id)
        outcome = store.upsert(row, detail, now_str)
        stats[outcome] = stats.get(outcome, 0) + 1
    if stats["complete"]:
        stats.update(store.mark_missing(seen, now_str, source="gem"))
    else:
        stats.update(store.expire(now_str, source="gem"))
    log.info("GeM %s: %s", state, stats)
    return stats


def done_today(portal: str, data_path: Path, snapshot_path: Path, now: datetime) -> bool:
    """True if a complete crawl of `portal` already succeeded today (IST); retry runs then skip."""
    today = now.strftime("%Y-%m-%d")
    if portal == "gem":
        if not snapshot_path.exists():
            return False
        snap = json.loads(snapshot_path.read_text(encoding="utf-8"))
        return snap.get("fetched_at", "")[:10] == today and bool((snap.get("stats") or {}).get("complete"))
    if not data_path.exists():
        return False
    runs = json.loads(data_path.read_text(encoding="utf-8")).get("runs") or []
    return any(r.get("started", "")[:10] == today and r.get("status") == "ok" and (r.get("crawl") or {}).get("complete")
               for r in runs)


def gem_snapshot(gem_cfg: dict, path: Path, attempts: int = 3, wait_seconds: int = 300) -> int:
    """Fetch GeM bids, retrying a failed or incomplete crawl; keeps the most complete result."""
    best = None
    for attempt in range(1, attempts + 1):
        gem = GemClient(delay=gem_cfg.get("request_delay_seconds", 0.5), timeout=gem_cfg.get("timeout_seconds", 60))
        try:
            bids, stats = gem.state_bids(gem_cfg.get("state", "RAJASTHAN"))
            stats["requests"] = gem.request_count
            if best is None or len(bids) > len(best[0]):
                best = (bids, stats)
            if stats["complete"]:
                break
            log.warning("GeM attempt %d incomplete: %s", attempt, stats)
        except Exception:
            log.exception("GeM attempt %d failed", attempt)
        if attempt < attempts:
            time.sleep(wait_seconds)
    if not best or not best[0]:
        return 1
    now_str = datetime.now(IST).strftime("%Y-%m-%dT%H:%M")
    save_snapshot(path, best[0], best[1], now_str)
    log.info("GeM snapshot: %d bids -> %s (%s)", len(best[0]), path, best[1])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-orgs", type=int, default=None)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--no-gem", action="store_true", help="skip the GeM BidPlus crawl")
    parser.add_argument("--only-gem", action="store_true", help="skip the eProc crawl (testing)")
    parser.add_argument("--gem-snapshot", metavar="PATH", help="only fetch GeM bids and save them to PATH")
    parser.add_argument("--done-today", choices=("eproc", "gem"),
                        help="only report (to $GITHUB_OUTPUT) whether today's crawl of that portal succeeded")
    parser.add_argument("--data", default=str(ROOT / "data" / "tenders.json"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=sys.stdout)
    cfg = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    now = datetime.now(IST).replace(tzinfo=None)
    now_str = now.strftime("%Y-%m-%dT%H:%M")
    started = time.time()
    gem_cfg = cfg.get("gem") or {}
    if args.done_today:
        done = done_today(args.done_today, Path(args.data), ROOT / gem_cfg.get("snapshot", "data/gem_bids.json"), now)
        log.info("%s already crawled successfully today: %s", args.done_today, done)
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
                fh.write(f"done={'true' if done else 'false'}\n")
        return 0
    if args.gem_snapshot:
        return gem_snapshot(gem_cfg, Path(args.gem_snapshot))
    store = Store(Path(args.data))
    portal = cfg["portal"]
    client = GepnicClient(portal["base_url"], delay=portal.get("request_delay_seconds", 0.5),
                          timeout=portal.get("timeout_seconds", 60), verify_tls=portal.get("verify_tls", False))

    run = {"started": now_str, "status": "ok", "error": None}
    attempts = portal.get("crawl_attempts", 3)
    for attempt in range(1, attempts + 1):
        try:
            if not args.only_gem:
                run["crawl"] = crawl(client, store, now_str, args.max_orgs)
            run.update(status="ok", error=None, attempts=attempt)
            break
        except Exception as exc:  # keep yesterday's data and still publish the site
            log.exception("crawl attempt %d failed", attempt)
            run["status"] = "crawl_failed"
            run["error"] = f"{type(exc).__name__}: {exc}"[:500]
            run["attempts"] = attempt
            if attempt < attempts:
                time.sleep(portal.get("retry_wait_seconds", 300))
                client = GepnicClient(portal["base_url"], delay=portal.get("request_delay_seconds", 0.5),
                                      timeout=portal.get("timeout_seconds", 60), verify_tls=portal.get("verify_tls", False))
    run["requests"] = client.request_count

    if gem_cfg.get("enabled") and not args.no_gem:
        state = gem_cfg.get("state", "RAJASTHAN")
        try:
            if gem_cfg.get("live"):
                gem = GemClient(delay=gem_cfg.get("request_delay_seconds", 0.5), timeout=gem_cfg.get("timeout_seconds", 60))
                run["gem"] = crawl_gem(gem, store, now_str, state)
                run["gem"]["requests"] = gem.request_count
            else:
                snap = load_snapshot(ROOT / gem_cfg["snapshot"], now, gem_cfg.get("max_age_hours", 36))
                run["gem"] = merge_gem(*snap, store, now_str, state) if snap else {
                    "error": f"no fresh GeM snapshot ({gem_cfg['snapshot']}); run the 'GeM bids (this PC)' workflow"}
                if not snap:
                    store.expire(now_str, source="gem")
        except Exception as exc:  # GeM problems must not block the eProc report
            log.exception("GeM step failed")
            run["gem"] = {"error": f"{type(exc).__name__}: {exc}"[:500]}

    if args.no_llm:
        cfg["llm"]["providers"] = []
    run["analysis"] = analyse_tenders(store.tenders, cfg, now)
    briefing = build_briefing(store.tenders, cfg, now)
    run["briefing"] = {"source": briefing["source"], "picks": len(briefing["picks"])}
    run["pruned"] = store.prune(now, cfg["site"].get("prune_closed_days", 60))
    run["active"] = sum(1 for r in store.tenders.values() if r.get("status") == "active")
    run["duration_seconds"] = round(time.time() - started)
    store.add_run(run)
    store.save()
    build_site(store, cfg, run, now, ROOT, briefing)
    log.info("run summary: %s", run)
    return 0 if run["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
