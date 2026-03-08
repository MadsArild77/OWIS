# Offshore Wind Intelligence Platform (MVP)

MVP implementing Foundation + News module v1 from your spec.

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r platform/requirements.txt`
3. Run API:
   - `uvicorn platform.apps.api.main:app --reload`

## Jobs

- Fetch RSS items: `python -m platform.jobs.run_news_fetch`
- Process raw items: `python -m platform.jobs.run_news_processing`

## API endpoints

- `GET /api/news/latest`
- `GET /api/news/top-signals`
- `GET /api/news/item/{id}`
- `GET /api/news/linkedin-candidates`
