# Offshore Wind Intelligence Platform (MVP)

[Til dokumentasjonsoversikten](../DOCUMENTATION.md)

MVP implementing Foundation + News module v1, and a DealEngine-bridged Opportunities starter module.

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r owis/requirements.txt`
3. Run API:
   - `uvicorn owis.apps.api.main:app --reload`
4. Open frontend:
   - `http://127.0.0.1:8000/news`
   - `http://127.0.0.1:8000/opportunities`

## Preview mode (one command)

Run from repo root:

- `powershell -ExecutionPolicy Bypass -File owis/scripts/preview.ps1`

This opens `http://127.0.0.1:8000/news` and starts the API with reload.

## Jobs

Morning report and policy outlook: see [MORNING_REPORT.md](../MORNING_REPORT.md).
Automatic 06:00 Europe/Oslo runs are enabled with `OWI_MORNING_REPORT_ENABLED=true`.
The server must be running. Manual generation is available in the News page.

- Fetch news sources: `python -m owis.jobs.run_news_fetch`
- Process news raw items: `python -m owis.jobs.run_news_processing`
- Generate today's morning report: `python -m owis.jobs.run_morning_report`
- Fetch opportunities (DealEngine-style sources): `python -m owis.jobs.run_opportunities_fetch`
- Process opportunity raw items: `python -m owis.jobs.run_opportunities_processing`
- Export opportunities to Notion: `python -m owis.jobs.run_opportunities_notion_export`

## API endpoints

### News

- `GET /api/news/latest`
- `GET /api/news/top-signals`
- `GET /api/news/item/{id}`
- `GET /api/news/linkedin-candidates`
- `GET /api/news/sources`
- `POST /api/news/sources/import-text`
- `POST /api/news/sources/toggle`
- `POST /api/news/sources/update`
- `POST /api/news/sources/dedupe`
- `POST /api/news/sources/rediscover-rss`
- `POST /api/news/run/fetch-process`

### Opportunities

- `GET /api/opportunities/latest`
- `GET /api/opportunities/upcoming-deadlines`
- `GET /api/opportunities/high-relevance`
- `GET /api/opportunities/item/{id}`
- `POST /api/opportunities/run/fetch-process`
- `POST /api/opportunities/export/notion`

### eInnsyn (read-only from Notion)

- `GET /api/einnsyn/overview` (`?refresh=true` skips the 30-minute cache)
- `GET /api/einnsyn/case?ref=<eInnsyn case link or id>`: journal posts and open documents (read
  from eInnsyn's open API), the written account and related news
- `POST /api/einnsyn/case/account` `{ref}`: write the account now (AI)
- `GET /api/einnsyn/related?item_ids=..`: eInnsyn cases naming the projects/companies of news items
- `GET|POST|DELETE /api/einnsyn/case/chat`: the saved conversation about a case; `POST {ref, question}`
  answers from the journal posts and the most relevant open documents (PDF text via `pypdf`)
- Page: `/einnsyn`

## eInnsyn page config

The separate eInnsyn monitor (github.com/MadsArild77/eInnsyn) stores cases,
journal posts and search terms in Notion. OWIS only reads them; nothing is
written back, so Notion stays the source of truth. Set:

- `NOTION_API_KEY=...` (same integration as below)
- `OWI_EINNSYN_SAKER_DB_ID=...` (eInnsyn – Saker)
- `OWI_EINNSYN_LOGG_DB_ID=...` (eInnsyn – Logg)
- `OWI_EINNSYN_SOK_DB_ID=...` (eInnsyn – Søk)

Share the three databases with the Notion integration behind `NOTION_API_KEY`.
Without this the page shows what is missing.

## Opportunities DealEngine bridge config

The opportunities module uses local profiles and DealEngine-style source adapters (TED, Doffin, World Bank).

Optional environment variables:

- `OWI_OPP_ENABLED_SOURCES=TED,DOFFIN,WORLDBANK`
- `OWI_OPP_ACTIVE_PROFILES=AGR,MAV`
- `OWI_OPP_DAYS_BACK=30`
- `OWI_OPPORTUNITIES_PROFILES=owis/modules/opportunities/registry/profiles.yaml`
- `TED_API_KEY=...` (optional)

Optional Notion export variables:

- `OWI_OPP_NOTION_EXPORT_ENABLED=true`
- `NOTION_API_KEY=...`
- `NOTION_OPPORTUNITIES_DB_ID=...` or `OWI_NOTION_OPPORTUNITIES_DB_ID=...`
- `OWI_NOTION_VERSION=2022-06-28`

## Tests

- Run all tests: `pytest owis/tests -q`

## AI Layer (optional, provider-agnostic)

This project uses an OpenAI-compatible API pattern, so you can switch providers by config.

Set environment variables:

- `OWI_AI_ENABLED=true`
- `OWI_AI_PROVIDER=openai_compatible` (or `mistral`, `deepseek`)
- `OWI_AI_MODEL=...`
- `OWI_AI_BASE_URL=...`
- `OWI_AI_ENDPOINT=/chat/completions`
- `OWI_AI_INPUT_MAX_CHARS=3500`
- `OWI_AI_MAX_TOKENS=220`
- `OPENAI_API_KEY=...`

Cost control defaults:

- input truncation (`OWI_AI_INPUT_MAX_CHARS`)
- low `temperature`
- strict JSON output
- low `max_tokens`

If AI is disabled or unavailable, the pipeline automatically falls back to heuristic processing.

## Source Input UX (News)

In `/news`, paste one source per line, for example:

- `Recharge - https://www.rechargenews.com`
- `https://windeurope.org`

Importer tries RSS autodiscovery first; if no feed is found, source is added as `scrape`.

## Access protection

Set `OWI_ACCESS_PASSWORD` to require a login on every page and API route.
The browser asks for a username and password; the username is `owis` unless
`OWI_ACCESS_USER` is set. `/health` stays open for the Railway health check.
Without `OWI_ACCESS_PASSWORD` the app is open to anyone with the URL, and a
warning is logged on Railway at startup.

## Automatic collection, matching and coverage search

- `OWI_SCHEDULED_FETCH_ENABLED=true` (default): fetch new articles (not seen before, by URL) at the hours in
  `OWI_FETCH_HOURS` (`5,8,12,15,18,21`; the 06:00 morning report uses what the 05 fetch stored), Europe/Oslo. Set `false` to fetch only manually.
- After each fetch: event cards (`OWI_EVENT_CARDS_PER_RUN`, 150), story matching (`OWI_MATCH_MAX_PAIRS`, 300;
  auto-merge at `OWI_MATCH_AUTO_MERGE_CONFIDENCE`, 0.85), coverage search for important single-source stories
  (`OWI_GAP_SEARCHES_PER_RUN`, 5; `OWI_GAP_SEARCHES_PER_DAY`, 25; needs `TAVILY_API_KEY` or `BRAVE_SEARCH_API_KEY`)
  and learned source weights for the Source advisor.
- All web searches share one monthly budget: `OWI_SEARCH_MONTHLY_LIMIT` (1000, the Tavily free plan) with
  `OWI_SEARCH_RESEARCH_RESERVE` (100) kept for research you start. Automatic searches are paced over the month.

## Full text and time limits

- Full text is fetched per source in the way that has worked: OWIS's own request first, then
  Tavily Extract for sources that block it (needs `TAVILY_API_KEY`; 1 credit per page, counted
  as an automatic search). A method that keeps failing for a source is skipped, with one retry
  in ten. Paywalls are respected; the Source advisor shows the result per source.
- Relevant stories that still have only a teaser get a search for an open version elsewhere,
  whatever their score, up to `OWI_OPEN_SEARCHES_PER_DAY` (15).
- A fetch run stops after `OWI_FETCH_MAX_MINUTES` (10): processing gets the first half, story
  grouping until 85 % and coverage search the rest. What is not reached waits for the next run.
  Each run logs its timings (`Fetch finished: ... timings=...`).

## Retention

After each fetch, articles older than `OWI_NEWS_RETENTION_DAYS` (90) are archived:
title, link, tags and score stay in `news_article_archive`, while the full text, AI
summary, event card, cached embeddings and match judgements, and saved source texts
are deleted. Stories scoring at least `OWI_NEWS_HIGH_SIGNAL_MIN_SCORE` (70) are kept
until `OWI_NEWS_HIGH_SIGNAL_RETENTION_DAYS` (365). Stories you have researched,
merged, rated, drafted or reviewed are never archived. Morning reports are saved
copies and are kept.

## Deploy on Railway

Railway builds the `Dockerfile` and uses `railway.json` (start command and
`/health` check). OWIS needs a persistent volume that contains `OWI_DB_PATH`
(the Dockerfile default is `/data/owi.db`); startup is refused on Railway without it.

Recommended variables in each Railway environment:

- `OWI_ACCESS_PASSWORD` (and optionally `OWI_ACCESS_USER`)
- `OPENAI_API_KEY` and `OWI_AI_ENABLED=true` to turn on AI enrichment
- `OWI_MORNING_REPORT_ENABLED=true` for the 06:00 Europe/Oslo run

Routes: `/news`, `/opportunities` and `/health`.

At startup the app copies the database to `backups/startup-YYYY-MM-DD.db` next
to the database and keeps the 14 newest copies. These copies live on the same
volume, so they do not protect against losing the volume itself.
