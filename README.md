# Web_crawler

Daily crawler for Rajasthan government tenders ([eproc.rajasthan.gov.in](https://eproc.rajasthan.gov.in/nicgep/app)).
Every morning a GitHub Actions job collects active tenders, de-duplicates them against
`data/tenders.json`, classifies each new tender with a free LLM (Gemini or Groq), decides
whether it is worth reading, and publishes the report on GitHub Pages.

**Report:** https://gauraviiitg.github.io/Web_crawler/

## How it works

1. `crawler/gepnic.py` reads the public "Tenders by Organisation" pages (no captcha) and each
   tender's detail page in the same session.
2. `crawler/store.py` de-duplicates by Tender ID (e.g. `2026_CEPWD_604884_4`). Only new or
   changed tenders get their details fetched and analysed; changes (corrigenda) are recorded.
3. `crawler/analyse.py` sends new tenders in batches of 8 to a free LLM for a summary, sector,
   work type, relevance score, risk flags and a decision (`worth_reading` / `maybe` / `skip`).
   Providers are tried in order: Google Gemini (`gemini-3.8-flash`), then Groq
   (`openai/gpt-oss-120b`). Keyword rules are used until the LLM has analysed a tender.
   Judging follows the company profile in `config/settings.yaml` (eligibility, cash to bid,
   blockers), with English and Hindi text.
4. `crawler/briefing.py` writes the daily "Top picks for us" section shown at the top of the
   site: a ranked shortlist with why, risks and the next step, in English and Hindi (one LLM
   call; a template briefing is used without a key).
5. The site has an English/हिंदी toggle, and `?id=<TenderID>` links open a tender directly.
6. **Personalised** sections (`personalised:` in `config/settings.yaml`, e.g. "Photocopy &
   printing") are matched by keywords and by the LLM on every run. Matching tenders get a
   relevance boost, a ★ badge, their own list under the "Personalised" tab, and a summary in
   the daily briefing. Add a section by copying the photocopy block with new keywords.
   `?section=<id>` links open a section directly.

## LLM setup (free)

Add at least one key as a repository secret (Settings → Secrets and variables → Actions):

- `GEMINI_API_KEY` — create at https://aistudio.google.com/apikey
- `GROQ_API_KEY` — create at https://console.groq.com/keys

Or from a terminal: `gh secret set GEMINI_API_KEY -R gauraviiitg/Web_crawler` (paste the key when asked).
4. `crawler/report.py` writes `site/data.json`; `web/` holds the static page that renders it.

The schedule is in `.github/workflows/daily.yml` (03:00 UTC = 08:30 IST, so the report is ready
by 09:00 IST). Run it manually from the Actions tab with "Run workflow".

## Customise

Edit `config/settings.yaml` → `profile` to describe the tenders you care about (sectors,
locations, value range). The LLM uses it to decide what is worth reading.

## Run locally

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m pytest -q tests
.venv\Scripts\python -m crawler.main --max-orgs 3 --no-llm
```

Then serve `site/` (e.g. `python -m http.server -d site`) and open http://localhost:8000.

Tender documents (PDF/BOQ) are captcha-protected on the portal and are not downloaded; open a
tender on the portal with its Tender ID to read them. See `PLAN.txt` for the research notes.
