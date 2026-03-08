from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from owis.core.storage.db import init_db
from owis.modules.news.collectors.rss_fetcher import fetch_rss_items
from owis.modules.news.collectors.scrape_fetcher import fetch_scrape_items
from owis.modules.news.processing.pipeline import process_raw_item
from owis.modules.news.registry.source_discovery import (
    dedupe_sources,
    import_sources_from_text,
    load_source_registry,
    set_source_enabled,
    update_source,
)
from owis.modules.news.storage.repository import NewsRepository

router = APIRouter(prefix="/api/news", tags=["news"])
repo = NewsRepository()


class ImportSourcesRequest(BaseModel):
    text: str


class ToggleSourceRequest(BaseModel):
    index: int
    enabled: bool


class UpdateSourceRequest(BaseModel):
    index: int
    name: str | None = None
    homepage: str | None = None
    type: str | None = None
    url: str | None = None
    enabled: bool | None = None
    priority: str | None = None
    geography_tags: list[str] | None = None

@router.get("/latest")
def latest(limit: int = 20):
    return repo.latest(limit)


@router.get("/top-signals")
def top_signals(limit: int = 20):
    return repo.top_signals(limit)


@router.get("/linkedin-candidates")
def linkedin_candidates(limit: int = 20):
    return repo.linkedin_candidates(limit)


@router.get("/item/{item_id}")
def item(item_id: int):
    found = repo.get_item(item_id)
    if not found:
        raise HTTPException(status_code=404, detail="News item not found")
    return found


@router.get("/sources")
def list_sources():
    return [{"index": i, **s} for i, s in enumerate(load_source_registry())]


@router.post("/sources/import-text")
def import_sources(payload: ImportSourcesRequest):
    added = import_sources_from_text(payload.text)
    return {"added_count": len(added), "added": added}


@router.post("/sources/toggle")
def toggle_source(payload: ToggleSourceRequest):
    updated = set_source_enabled(payload.index, payload.enabled)
    if not updated:
        raise HTTPException(status_code=404, detail="Source not found")
    return updated


@router.post("/sources/update")
def edit_source(payload: UpdateSourceRequest):
    updates = payload.model_dump(exclude_none=True)
    index = updates.pop("index")
    updated = update_source(index=index, updates=updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Source not found")
    return updated


@router.post("/sources/dedupe")
def run_dedupe():
    return dedupe_sources()


@router.post("/run/fetch-process")
def run_fetch_process():
    init_db()

    fetched_items = [*fetch_rss_items(), *fetch_scrape_items()]
    inserted = 0
    for item in fetched_items:
        if repo.upsert_raw_item(item):
            inserted += 1

    raws = repo.list_unprocessed_raw(limit=200)
    processed = 0
    for raw in raws:
        result = process_raw_item(raw)
        repo.save_processed_item(result)
        repo.mark_raw_processed(raw["id"])
        processed += 1

    return {
        "fetched_candidates": len(fetched_items),
        "new_raw_items": inserted,
        "processed_items": processed,
    }
