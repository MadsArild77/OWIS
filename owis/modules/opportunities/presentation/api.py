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
from owis.modules.opportunities.collectors.open_data import SOURCE_NAMES
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


@router.get("/sources")
def sources():
    init_db()
    runs = repo.latest_source_runs()
    result = []
    for source, name in SOURCE_NAMES.items():
        run = runs.get(source)
        status = "Not run yet" if run is None else ("OK" if run["status"] == "ok" else f"Failed: {run.get('error') or 'Unknown error'}")
        result.append({"source": source, "name": name, "status": status,
                       "enabled": source in OPPORTUNITIES_ENABLED_SOURCES,
                       "started_at": run["started_at"] if run else None,
                       "completed_at": run["completed_at"] if run else None,
                       "fetched": run["fetched"] if run else 0,
                       "new": run["new_items"] if run else 0,
                       "filtered": run["filtered"] if run else 0})
    return result


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
    unknown_sources = set(selected_sources) - SOURCE_NAMES.keys()
    if unknown_sources:
        raise HTTPException(status_code=400, detail="Unknown opportunity source")
    days_back = payload.days_back if payload.days_back and payload.days_back > 0 else OPPORTUNITIES_DAYS_BACK

    profile_bundle = load_profile_bundle(active_profiles=selected_profiles)
    if not profile_bundle.get("by_company"):
        raise HTTPException(
            status_code=400,
            detail="No active opportunity profiles loaded. Check OWI_OPPORTUNITIES_PROFILES and profile names.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    fetched_items, source_report = fetch_dealengine_style_notices_with_report(
        profile_bundle=profile_bundle,
        enabled_sources=selected_sources,
        days_back=days_back,
        ted_api_key=TED_API_KEY,
        since_by_source={} if payload.days_back else repo.successful_source_starts(),
        until=now_iso,
    )

    reports = {entry["source"]: entry for entry in source_report}
    new_notice_ids = set()
    inserted = 0
    for item in fetched_items:
        if not item.get("fetched_at"):
            item["fetched_at"] = now_iso
        if repo.upsert_raw_item(item):
            inserted += 1
            new_notice_ids.add(item["id"])
            entry = reports.get(item["source"])
            if entry is not None:
                entry["new_items"] = entry.get("new_items", 0) + 1
        else:
            entry = reports.get(item["source"])
            if entry is not None:
                entry["filtered"] = entry.get("filtered", 0) + 1

    processed = 0
    rejected = 0
    while raws := repo.list_unprocessed_raw(limit=300):
        for raw in raws:
            result = process_raw_item(raw, profile_bundle=profile_bundle, active_profiles=selected_profiles)
            if result is None:
                repo.mark_raw_rejected(raw["id"])
                rejected += 1
                entry = reports.get(raw["source_name"])
                if entry is not None and raw["notice_id"] in new_notice_ids:
                    entry["filtered"] = entry.get("filtered", 0) + 1
                continue
            repo.save_processed_item(result)
            repo.mark_raw_processed(raw["id"])
            processed += 1

    completed_at = datetime.now(timezone.utc).isoformat()
    for entry in source_report:
        repo.save_source_run(entry, started_at=now_iso, completed_at=completed_at)

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