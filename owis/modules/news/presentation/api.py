from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from owis.core.storage.db import init_db
from owis.modules.news.collectors.rss_fetcher import fetch_rss_items_with_report
from owis.modules.news.collectors.scrape_fetcher import fetch_scrape_items_with_report
from owis.modules.news.processing.pipeline import process_raw_item
from owis.modules.news.registry.source_discovery import (
    dedupe_sources,
    import_sources_from_text,
    load_source_registry,
    rediscover_rss_for_sources,
    source_health_report,
    set_source_enabled,
    update_source,
)
from owis.modules.news.storage.repository import NewsRepository

router = APIRouter(prefix="/api/news", tags=["news"])
repo = NewsRepository()


def _base_health(items: int, error: str | None) -> tuple[int, str]:
    if error:
        return 0, "red"
    if items <= 0:
        return 1, "yellow"
    return 2, "green"


def _with_degradation_color(base_score: int, base_color: str, prev: dict | None, items: int) -> tuple[int, str, str]:
    reason = "ok"
    if base_color == "red":
        return base_score, base_color, "fetch_failed"
    if prev is None:
        return base_score, base_color, reason

    prev_score = int(prev.get("health_score") or 0)
    prev_items = int(prev.get("last_items") or 0)
    if items < prev_items:
        return min(base_score, 1), "yellow", "degraded_from_previous_fetch"
    if base_score < prev_score:
        return min(base_score, 1), "yellow", "health_score_regressed"
    return base_score, base_color, reason


class ImportSourcesRequest(BaseModel):
    text: str


class ToggleSourceRequest(BaseModel):
    index: int
    enabled: bool


class RediscoverRSSRequest(BaseModel):
    only_scrape: bool = True
    with_debug: bool = False


class SourceHealthRequest(BaseModel):
    only_enabled: bool = True


class UpdateSourceRequest(BaseModel):
    index: int
    name: str | None = None
    homepage: str | None = None
    type: str | None = None
    url: str | None = None
    enabled: bool | None = None
    priority: str | None = None
    geography_tags: list[str] | None = None
    auth: dict[str, object] | None = None
    manual_override: bool | None = None

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


@router.post("/sources/rediscover-rss")
def rediscover_rss(payload: RediscoverRSSRequest):
    return rediscover_rss_for_sources(only_scrape=payload.only_scrape, with_debug=payload.with_debug)


@router.post("/sources/health")
def source_health(payload: SourceHealthRequest):
    return {"items": source_health_report(only_enabled=payload.only_enabled)}


@router.post("/run/fetch-process")
def run_fetch_process():
    init_db()

    rss_items, rss_report = fetch_rss_items_with_report()
    scrape_items, scrape_report = fetch_scrape_items_with_report()
    source_report = [*rss_report, *scrape_report]
    fetched_items = [*rss_items, *scrape_items]

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

    health_rows: list[dict] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    for row in source_report:
        source_name = str(row.get("source") or "unknown")
        items = int(row.get("items") or 0)
        error = row.get("error")

        score, color = _base_health(items=items, error=error)
        prev = repo.get_source_health_state(source_name)
        score, color, reason = _with_degradation_color(score, color, prev, items)

        repo.upsert_source_health_state(
            source_name=source_name,
            health_score=score,
            health_color=color,
            last_items=items,
            last_error=(str(error) if error else None),
            updated_at=now_iso,
        )

        row["health"] = color
        row["health_reason"] = reason
        health_rows.append({"source": source_name, "health": color, "reason": reason, "items": items})

    return {
        "fetched_candidates": len(fetched_items),
        "new_raw_items": inserted,
        "processed_items": processed,
        "source_report": source_report,
        "source_health": health_rows,
    }
