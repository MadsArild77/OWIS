from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from owis.core.config.settings import (
    NOTION_API_KEY,
    NOTION_OPPORTUNITIES_DB_ID,
    NOTION_VERSION,
    OPPORTUNITIES_ACTIVE_PROFILES,
    OPPORTUNITIES_DAYS_BACK,
    OPPORTUNITIES_ENABLED_SOURCES,
    OPPORTUNITIES_NOTION_EXPORT_ENABLED,
    TED_API_KEY,
)
from owis.core.notion.opportunities_export import OpportunitiesNotionExporter
from owis.core.storage.db import init_db
from owis.modules.opportunities.collectors.dealengine_fetchers import (
    fetch_dealengine_style_notices_with_report,
)
from owis.modules.opportunities.processing.pipeline import process_raw_item
from owis.modules.opportunities.registry.profile_loader import load_profile_bundle
from owis.modules.opportunities.storage.repository import OpportunitiesRepository


router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])
repo = OpportunitiesRepository()


class RunOpportunitiesRequest(BaseModel):
    days_back: int | None = None
    sources: list[str] | None = None
    profiles: list[str] | None = None
    export_notion: bool = False
    notion_limit: int = 50
    notion_dry_run: bool = False


class ExportNotionRequest(BaseModel):
    limit: int = 50
    mode: str = "high_relevance"
    dry_run: bool = False


@router.get("/latest")
def latest(limit: int = 20):
    return repo.latest(limit)


@router.get("/upcoming-deadlines")
def upcoming_deadlines(limit: int = 20):
    return repo.upcoming_deadlines(limit)


@router.get("/high-relevance")
def high_relevance(limit: int = 20):
    return repo.high_relevance(limit)


@router.get("/item/{item_id}")
def item(item_id: int):
    found = repo.get_item(item_id)
    if not found:
        raise HTTPException(status_code=404, detail="Opportunity item not found")
    return found


def _build_exporter() -> OpportunitiesNotionExporter:
    if not OPPORTUNITIES_NOTION_EXPORT_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="Notion export disabled. Set OWI_OPP_NOTION_EXPORT_ENABLED=true.",
        )

    if not NOTION_API_KEY or not NOTION_OPPORTUNITIES_DB_ID:
        raise HTTPException(
            status_code=400,
            detail="Missing Notion config. Set NOTION_API_KEY and NOTION_OPPORTUNITIES_DB_ID (or OWI_NOTION_OPPORTUNITIES_DB_ID).",
        )

    return OpportunitiesNotionExporter(
        api_key=NOTION_API_KEY,
        database_id=NOTION_OPPORTUNITIES_DB_ID,
        notion_version=NOTION_VERSION,
    )


@router.post("/export/notion")
def export_to_notion(payload: ExportNotionRequest):
    init_db()

    mode = (payload.mode or "high_relevance").strip().lower()
    if mode == "latest":
        items = repo.latest(limit=max(1, payload.limit))
    elif mode in {"high", "high_relevance", "high-relevance"}:
        items = repo.high_relevance(limit=max(1, payload.limit))
    elif mode in {"deadlines", "upcoming_deadlines", "upcoming-deadlines"}:
        items = repo.upcoming_deadlines(limit=max(1, payload.limit))
    else:
        raise HTTPException(status_code=400, detail="Invalid mode. Use latest, high_relevance, or upcoming_deadlines.")

    exporter = _build_exporter()

    try:
        result = exporter.export_items(
            items=items,
            max_items=max(1, payload.limit),
            dry_run=payload.dry_run,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Notion export failed: {exc.__class__.__name__}: {exc}")

    return {
        "mode": mode,
        "items_selected": len(items),
        **result,
    }


@router.post("/run/fetch-process")
def run_fetch_process(payload: RunOpportunitiesRequest):
    init_db()

    selected_profiles = [
        profile.strip().upper()
        for profile in (payload.profiles or OPPORTUNITIES_ACTIVE_PROFILES)
        if profile.strip()
    ]
    selected_sources = [
        source.strip().upper()
        for source in (payload.sources or OPPORTUNITIES_ENABLED_SOURCES)
        if source.strip()
    ]
    days_back = payload.days_back if payload.days_back and payload.days_back > 0 else OPPORTUNITIES_DAYS_BACK

    profile_bundle = load_profile_bundle(active_profiles=selected_profiles)
    if not profile_bundle.get("by_company"):
        raise HTTPException(
            status_code=400,
            detail="No active opportunity profiles loaded. Check OWI_OPPORTUNITIES_PROFILES and profile names.",
        )

    fetched_items, source_report = fetch_dealengine_style_notices_with_report(
        profile_bundle=profile_bundle,
        enabled_sources=selected_sources,
        days_back=days_back,
        ted_api_key=TED_API_KEY,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for item in fetched_items:
        if not item.get("fetched_at"):
            item["fetched_at"] = now_iso
        if repo.upsert_raw_item(item):
            inserted += 1

    raws = repo.list_unprocessed_raw(limit=300)
    processed = 0
    rejected = 0

    for raw in raws:
        result = process_raw_item(
            raw,
            profile_bundle=profile_bundle,
            active_profiles=selected_profiles,
        )
        if result is None:
            repo.mark_raw_rejected(raw["id"])
            rejected += 1
            continue

        repo.save_processed_item(result)
        repo.mark_raw_processed(raw["id"])
        processed += 1

    notion_export: dict | None = None
    if payload.export_notion:
        exporter = _build_exporter()
        export_items = repo.high_relevance(limit=max(1, payload.notion_limit))
        notion_export = exporter.export_items(
            items=export_items,
            max_items=max(1, payload.notion_limit),
            dry_run=payload.notion_dry_run,
        )

    return {
        "fetched_candidates": len(fetched_items),
        "new_raw_items": inserted,
        "processed_items": processed,
        "rejected_items": rejected,
        "active_profiles": selected_profiles,
        "enabled_sources": selected_sources,
        "days_back": days_back,
        "source_report": source_report,
        "notion_export": notion_export,
    }