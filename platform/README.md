# Offshore Wind Intelligence Platform (MVP)

MVP implementing Foundation + News module v1 from your spec.

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r platform/requirements.txt`
3. Run API:
   - `uvicorn platform.apps.api.main:app --reload`
4. Open frontend:
   - `http://127.0.0.1:8000/news`

## Jobs

- Fetch RSS items: `python -m platform.jobs.run_news_fetch`
- Process raw items: `python -m platform.jobs.run_news_processing`

## API endpoints

- `GET /api/news/latest`
- `GET /api/news/top-signals`
- `GET /api/news/item/{id}`
- `GET /api/news/linkedin-candidates`

## Tests

- Run all tests: `pytest platform/tests -q`

## AI Layer (optional)

Set environment variables before running processing job:

- `OWI_AI_ENABLED=true`
- `OPENAI_API_KEY=...`
- Optional: `OWI_AI_MODEL=gpt-4o-mini`
- Optional: `OWI_AI_BASE_URL=https://api.openai.com/v1`

If AI is disabled or unavailable, the pipeline automatically falls back to heuristic processing.
