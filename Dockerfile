FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY owis/requirements.txt /app/owis/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r /app/owis/requirements.txt

COPY . /app

ENV OWI_DB_PATH=/data/owi.db
ENV OWI_NEWS_SOURCES=owis/modules/news/registry/sources.yaml

CMD ["python", "-m", "owis.scripts.run_server"]
