# Web_crawler

Daily crawler for Rajasthan government tenders from two portals:
[eproc.rajasthan.gov.in](https://eproc.rajasthan.gov.in/nicgep/app) and
[GeM BidPlus](https://bidplus.gem.gov.in/all-bids) (bids delivered in Rajasthan).
Every morning a GitHub Actions job collects open tenders, de-duplicates them against
`data/tenders.json`, tags each one with keyword rules, decides whether it is worth reading,
and publishes the report on GitHub Pages.

**Report:** https://gauraviiitg.github.io/Web_crawler/

## How it works

1. `crawler/gepnic.py` reads the eProc "Tenders by Organisation" pages (no captcha) and each
   tender's detail page in the same session.
2. `crawler/gem.py` reads GeM's public advance search by consignee location (state
   `RAJASTHAN`, then each consignee city, which gives the district). Each GeM bid links to its
   public bid PDF (`/showbidDocument/<id>`, no login or captcha). GeM refuses connections
   from GitHub's cloud runners, so `.github/workflows/gem.yml` runs on the owner's PC
   (self-hosted runner, label `gem`, started at logon by a Windows scheduled task) at 03:00 IST
   or from the site's "↻ Refresh GeM" button. It commits `data/gem_bids.json` and starts the
   daily job, which merges the snapshot if it is less than 36 hours old. If the PC is off, the
   run waits until it is back online.
3. `crawler/store.py` de-duplicates by Tender ID (e.g. `2026_CEPWD_604884_4`) or GeM bid
   number (e.g. `GEM/2026/B/8123892`); each record keeps its `source` so one portal's crawl
   never closes the other's tenders. Changes (corrigenda) are recorded.
4. `crawler/analyse.py` tags every open tender with keyword rules: sector, work type, cash to
   bid, blockers for a new company, relevance and a decision (`worth_reading` / `maybe` /
   `skip`), in English and Hindi, following the profile in `config/settings.yaml`.
   The LLM step is switched off (`llm.enabled: false`); the code is kept and can be turned back
   on with that flag plus a `GEMINI_API_KEY` / `GROQ_API_KEY` secret.
5. `crawler/briefing.py` builds the "Today's picks" tab: a ranked shortlist of feasible
   tenders with why, risks and the next step.
6. The site has an English/हिंदी toggle, filters for district, portal (eProc / GeM),
   organisation, sector, decision and value, and `?id=<TenderID>` links open a tender directly.
7. **Personalised** sections (`personalised:` in `config/settings.yaml`, e.g. "Photocopy &
   printing") are matched by keywords on every run. Matching tenders get a relevance boost,
   a ★ badge, their own list under the "Personalised" tab, and a summary in Today's picks.
   `?section=<id>` links open a section directly.
8. `crawler/report.py` writes `site/data.json`; `web/` holds the static page that renders it.

Both workflows start at 03:00 IST (21:30 UTC) and have retry runs at 04:00, 05:00, 06:00 and
07:30 IST that skip themselves once that day's crawl succeeded; each crawl also retries up to 3
times inside a run, 5 minutes apart. Run them manually from the Actions tab with "Run workflow".

## Customise

Edit `config/settings.yaml` → `profile` (interests, locations, value range) and
`personalised` (keyword sections). `gem.enabled: false` turns the GeM crawl off.

## Run locally

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m pytest -q tests
.venv\Scripts\python -m crawler.main --max-orgs 3 --no-gem
```

Then serve `site/` (e.g. `python -m http.server -d site`) and open http://localhost:8000.

eProc tender documents (PDF/BOQ) are captcha-protected and are not downloaded; open a tender
on the portal with its Tender ID to read them. GeM bid PDFs are linked directly. See
`PLAN.txt` for the research notes.
