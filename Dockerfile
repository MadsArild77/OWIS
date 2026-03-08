FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY owis/requirements.txt /app/owis/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r /app/owis/requirements.txt

COPY . /app

ENV OWI_DB_PATH=/tmp/owi.db
ENV OWI_NEWS_SOURCES=owis/modules/news/registry/sources.yaml

CMD ["sh", "-c", "python -m uvicorn owis.apps.api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
