# Offshore Wind Intelligence Platform (MVP)

MVP implementing Foundation + News module v1 from your spec.

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r owis/requirements.txt`
3. Run API:
   - `uvicorn owis.apps.api.main:app --reload`
4. Open frontend:
   - `http://127.0.0.1:8000/news`


## Preview mode (one command)

Run from repo root:

- `powershell -ExecutionPolicy Bypass -File owis/scripts/preview.ps1`

This opens `http://127.0.0.1:8000/news` and starts the API with reload.
## Jobs

- Fetch RSS + scrape sources: `python -m owis.jobs.run_news_fetch`
- Process raw items: `python -m owis.jobs.run_news_processing`

## API endpoints

- `GET /api/news/latest`
- `GET /api/news/top-signals`
- `GET /api/news/item/{id}`
- `GET /api/news/linkedin-candidates`
- `GET /api/news/sources`
- `POST /api/news/sources/import-text`

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

## Source Input UX

In `/news`, paste one source per line, for example:

- `Recharge - https://www.rechargenews.com`
- `https://windeurope.org`

Importer tries RSS autodiscovery first; if no feed is found, source is added as `scrape`.



