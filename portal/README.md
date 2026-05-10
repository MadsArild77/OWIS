# NorthernBlue Portal

Simple standalone landing page for app links such as MarketingHub, OWIS, Opportunities, and Umamu.

## Local run

From `portal/`:

- `python server.py`

Then open:

- `http://127.0.0.1:8080/`
- `http://127.0.0.1:8080/health`

## Environment variables

- `PORTAL_TITLE`
- `PORTAL_INTRO`
- `PORTAL_MARKETINGHUB_URL`
- `PORTAL_OWIS_URL`
- `PORTAL_OPPORTUNITIES_URL`
- `PORTAL_UMAMU_URL`

## Railway

Create a separate Railway service and set its root directory to `portal`.
The service uses `portal/Dockerfile` and exposes `/health` for health checks.
