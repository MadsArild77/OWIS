# Offshore Wind Intelligence Platform (MVP)

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

- Fetch news sources: `python -m owis.jobs.run_news_fetch`
- Process news raw items: `python -m owis.jobs.run_news_processing`
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

## Deploy on the web (Render)

1. Go to [Render Dashboard](https://dashboard.render.com) and click **New +** -> **Blueprint**.
2. Connect your GitHub repo `MadsArild77/OWIS`.
3. Render will detect `render.yaml` automatically.
4. Click **Apply** to deploy.
5. When deployment is done, open the public URL from the Render service.

Default public routes:

- `/news` (frontend)
- `/opportunities` (frontend)
- `/health`

Optional after deploy:

- Add `OPENAI_API_KEY` in Render environment variables.
- Set `OWI_AI_ENABLED=true` to turn on AI enrichment.

Note: free-tier disk is ephemeral, so SQLite/source-file changes can reset on restart.

## Railway note

Railway deploy uses Dockerfile to ensure Python/pip are always available in build/runtime.