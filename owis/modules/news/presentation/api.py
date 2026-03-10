from collections import defaultdict
from datetime import datetime, timedelta, timezone
import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from owis.core.llm.client import AIClient
from owis.core.storage.db import init_db
from owis.modules.news.collectors.rss_fetcher import fetch_rss_items_with_report
from owis.modules.news.collectors.scrape_fetcher import fetch_scrape_items_with_report
from owis.modules.news.matching.service import (
    build_candidate_pairs,
    judge_pair,
    make_manual_collection_key,
    should_enqueue_review,
    window_start_iso,
)
from owis.modules.news.processing.domain_classifier import classify_domain_with_ai_fallback
from owis.modules.news.processing.pipeline import process_raw_item
from owis.modules.news.registry.source_discovery import (
    dedupe_sources,
    delete_source,
    import_sources_from_text,
    load_source_registry,
    rediscover_rss_for_sources,
    set_source_enabled,
    source_health_report,
    update_source,
)
from owis.modules.news.storage.repository import NewsRepository

router = APIRouter(prefix="/api/news", tags=["news"])
repo = NewsRepository()

_CLUSTER_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "into", "is", "it", "its", "new", "of", "on", "or", "the",
    "to", "with", "offshore", "wind", "project", "projects",
}
VALID_DOMAIN_BUCKETS = {"offshore_wind", "adjacent_energy", "other_energy", "all"}


class ImportSourcesRequest(BaseModel):
    text: str


class ToggleSourceRequest(BaseModel):
    index: int
    enabled: bool


class DeleteSourceRequest(BaseModel):
    index: int


class RediscoverRSSRequest(BaseModel):
    only_scrape: bool = True
    with_debug: bool = False


class SourceHealthRequest(BaseModel):
    only_enabled: bool = True


class RunFetchProcessRequest(BaseModel):
    days_back: int = 7
    since_last: bool = False


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


class MergeCollectionRequest(BaseModel):
    item_ids: list[int] = Field(default_factory=list)
    collection_key: str | None = None
    note: str | None = None


class UnmergeCollectionRequest(BaseModel):
    item_ids: list[int] = Field(default_factory=list)


class UpdateRelevanceRequest(BaseModel):
    item_ids: list[int] = Field(default_factory=list)
    relevance: str | None = None
    qualified: bool | None = None


class MatchRunRequest(BaseModel):
    lookback_items: int = 350
    days_window: int = 7
    top_k: int = 8
    domain_bucket: str = "offshore_wind"


class MatchReviewDecisionRequest(BaseModel):
    pair_id: int
    decision: str
    actor: str | None = None


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


def _parse_iso_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in str(value).split(",") if x.strip()]


def _clean_source_filter(source_name: str | None) -> str | None:
    if source_name is None:
        return None
    cleaned = str(source_name).strip()
    return cleaned or None


def _normalize_domain_bucket(domain_bucket: str | None, default: str = "offshore_wind") -> str:
    raw = str(domain_bucket or default).strip().lower().replace("-", "_")
    if raw not in VALID_DOMAIN_BUCKETS:
        raise HTTPException(status_code=400, detail="Invalid domain_bucket")
    return raw


def _relevance_status(value: int | None) -> str:
    if value is None:
        return "unrated"
    return "relevant" if int(value) == 1 else "non_relevant"


def _attach_relevance(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = [int(item.get("id") or 0) for item in items if int(item.get("id") or 0) > 0]
    mapping = repo.list_relevance_map(ids)

    out: list[dict[str, Any]] = []
    for item in items:
        item_copy = dict(item)
        item_id = int(item_copy.get("id") or 0)
        item_copy["relevance_status"] = _relevance_status(mapping.get(item_id))
        out.append(item_copy)
    return out

def _attach_domain_data(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = [int(item.get("id") or 0) for item in items if int(item.get("id") or 0) > 0]
    domain_map = repo.list_domain_map(ids)

    out: list[dict[str, Any]] = []
    for item in items:
        row = dict(item)
        item_id = int(row.get("id") or 0)
        existing = domain_map.get(item_id)
        if existing:
            row["domain_bucket"] = existing.get("domain_bucket")
            row["domain_confidence"] = float(existing.get("domain_confidence") or 0.0)
            out.append(row)
            continue

        bucket, confidence = classify_domain_with_ai_fallback(
            title=str(row.get("title") or ""),
            summary=str(row.get("summary") or ""),
            themes=str(row.get("theme_tags") or ""),
        )
        repo.upsert_domain_classification(item_id, bucket, confidence)
        row["domain_bucket"] = bucket
        row["domain_confidence"] = confidence
        out.append(row)

    return out


def _attach_metadata(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _attach_domain_data(_attach_relevance(items))


def _filter_domain(items: list[dict[str, Any]], domain_bucket: str) -> list[dict[str, Any]]:
    if domain_bucket == "all":
        return items
    return [x for x in items if str(x.get("domain_bucket") or "other_energy") == domain_bucket]


def _parse_relevance_payload(payload: UpdateRelevanceRequest) -> int | None:
    if payload.relevance is None:
        if payload.qualified is None:
            raise HTTPException(status_code=400, detail="Provide relevance: relevant/non_relevant/unrated.")
        return 1 if bool(payload.qualified) else 0

    value = str(payload.relevance).strip().lower()
    if value in {"relevant", "yes", "true", "1"}:
        return 1
    if value in {"non_relevant", "non-relevant", "irrelevant", "no", "false", "0"}:
        return 0
    if value in {"unrated", "none", "clear", "reset"}:
        return None

    raise HTTPException(status_code=400, detail="Invalid relevance. Use relevant, non_relevant, or unrated.")


def _title_cluster_key(item: dict[str, Any]) -> str:
    title = str(item.get("title") or "").lower()
    tokens = re.findall(r"[a-z0-9]{3,}", title)
    significant = [token for token in tokens if token not in _CLUSTER_STOPWORDS]
    if not significant:
        return f"item{int(item.get('id') or 0)}"
    return "-".join(significant[:5])


def _default_collection_key(item: dict[str, Any]) -> str:
    themes = _split_csv(item.get("theme_tags"))
    geos = _split_csv(item.get("geography_tags"))
    theme = themes[0] if themes else "general_news"
    geo = geos[0] if geos else "Global"
    title_key = _title_cluster_key(item)
    return f"auto:{theme}|{geo}|{title_key}"

def _build_collections(
    items: list[dict],
    overrides: dict[int, dict],
    limit: int,
    items_per_collection: int,
) -> list[dict]:
    groups: dict[str, dict] = {}

    for item in items:
        processed_id = int(item.get("id") or 0)
        override = overrides.get(processed_id)
        collection_key = (override or {}).get("collection_key") or _default_collection_key(item)

        group = groups.get(collection_key)
        if group is None:
            group = {
                "collection_key": collection_key,
                "is_manual": collection_key.startswith("manual:"),
                "article_count": 0,
                "top_signal_score": 0,
                "signal_score_sum": 0,
                "latest_published_at": None,
                "themes": defaultdict(int),
                "geographies": defaultdict(int),
                "items": [],
            }
            groups[collection_key] = group

        score = int(item.get("signal_score") or 0)
        group["article_count"] += 1
        group["top_signal_score"] = max(group["top_signal_score"], score)
        group["signal_score_sum"] += score

        published = item.get("published_at") or item.get("processed_at")
        if not group["latest_published_at"] or str(published) > str(group["latest_published_at"]):
            group["latest_published_at"] = published

        themes = _split_csv(item.get("theme_tags"))
        geographies = _split_csv(item.get("geography_tags"))

        for theme in themes:
            group["themes"][theme] += 1
        for geo in geographies:
            group["geographies"][geo] += 1

        group["items"].append(
            {
                "id": processed_id,
                "title": item.get("title") or "Untitled",
                "source_name": item.get("source_name") or "Unknown",
                "article_url": item.get("article_url") or "",
                "signal_score": score,
                "published_at": item.get("published_at"),
                "relevance_status": str(item.get("relevance_status") or "unrated"),
                "domain_bucket": str(item.get("domain_bucket") or "other_energy"),
                "is_manual_override": bool(override),
            }
        )

    result: list[dict] = []
    for group in groups.values():
        item_rows = sorted(
            group["items"],
            key=lambda x: (int(x.get("signal_score") or 0), str(x.get("published_at") or "")),
            reverse=True,
        )

        top_themes = sorted(group["themes"].items(), key=lambda x: x[1], reverse=True)
        top_geos = sorted(group["geographies"].items(), key=lambda x: x[1], reverse=True)
        avg_score = round(group["signal_score_sum"] / max(group["article_count"], 1), 1)

        result.append(
            {
                "collection_key": group["collection_key"],
                "is_manual": group["is_manual"],
                "article_count": group["article_count"],
                "top_signal_score": group["top_signal_score"],
                "avg_signal_score": avg_score,
                "latest_published_at": group["latest_published_at"],
                "primary_theme": top_themes[0][0] if top_themes else "general_news",
                "primary_geography": top_geos[0][0] if top_geos else "Global",
                "items": item_rows[: max(items_per_collection, 1)],
            }
        )

    result.sort(
        key=lambda x: (int(x.get("article_count") or 0), int(x.get("top_signal_score") or 0), str(x.get("latest_published_at") or "")),
        reverse=True,
    )
    return result[: max(limit, 1)]


@router.get("/latest")
def latest(limit: int = 20, source_name: str | None = None, domain_bucket: str = "offshore_wind"):
    bucket = _normalize_domain_bucket(domain_bucket)
    rows = repo.latest(limit=max(limit * 5, limit), source_name=_clean_source_filter(source_name))
    rows = _filter_domain(_attach_metadata(rows), bucket)
    return rows[: max(limit, 1)]


@router.get("/top-signals")
def top_signals(limit: int = 20, source_name: str | None = None, domain_bucket: str = "offshore_wind"):
    bucket = _normalize_domain_bucket(domain_bucket)
    rows = repo.top_signals(limit=max(limit * 5, limit), source_name=_clean_source_filter(source_name))
    rows = _filter_domain(_attach_metadata(rows), bucket)
    return rows[: max(limit, 1)]


@router.get("/linkedin-candidates")
def linkedin_candidates(limit: int = 20, source_name: str | None = None, domain_bucket: str = "offshore_wind"):
    bucket = _normalize_domain_bucket(domain_bucket)
    rows = repo.linkedin_candidates(limit=max(limit * 5, limit), source_name=_clean_source_filter(source_name))
    rows = _filter_domain(_attach_metadata(rows), bucket)
    return rows[: max(limit, 1)]

@router.post("/items/relevance")
def update_item_relevance(payload: UpdateRelevanceRequest):
    item_ids = sorted({int(x) for x in payload.item_ids if int(x) > 0})
    if not item_ids:
        raise HTTPException(status_code=400, detail="Provide at least 1 item id.")

    found_items = repo.list_processed_by_ids(item_ids)
    if len(found_items) != len(item_ids):
        raise HTTPException(status_code=404, detail="One or more selected items were not found.")

    relevance = _parse_relevance_payload(payload)
    updated = repo.set_relevance(item_ids, relevance=relevance)
    status_value = _relevance_status(relevance)
    for item_id in item_ids:
        repo.log_learning_feedback(
            feedback_type="relevance",
            feedback_value=status_value,
            processed_id=item_id,
        )
    return {"updated_count": updated, "relevance_status": status_value}


@router.post("/items/qualification")
def update_item_qualification(payload: UpdateRelevanceRequest):
    return update_item_relevance(payload)


@router.get("/item/{item_id}")
def item(item_id: int):
    found = repo.get_item(item_id)
    if not found:
        raise HTTPException(status_code=404, detail="News item not found")
    return _attach_metadata([found])[0]


@router.get("/collections")
def list_collections(
    limit: int = 20,
    items_per_collection: int = 5,
    lookback_items: int = 400,
    source_name: str | None = None,
    domain_bucket: str = "offshore_wind",
):
    init_db()
    bucket = _normalize_domain_bucket(domain_bucket)
    items = repo.latest(limit=max(lookback_items, 1), source_name=_clean_source_filter(source_name))
    items = _filter_domain(_attach_metadata(items), bucket)
    overrides = repo.list_collection_overrides()
    collections = _build_collections(items, overrides, limit=limit, items_per_collection=items_per_collection)
    return {"items": collections}


@router.post("/collections/merge")
def merge_collections(payload: MergeCollectionRequest):
    init_db()
    item_ids = [int(x) for x in payload.item_ids if int(x) > 0]
    if len(item_ids) < 2:
        raise HTTPException(status_code=400, detail="Select at least 2 items to merge.")

    found_items = repo.list_processed_by_ids(item_ids)
    if len(found_items) != len(item_ids):
        raise HTTPException(status_code=404, detail="One or more selected items were not found.")

    provided_key = (payload.collection_key or "").strip()
    collection_key = provided_key or f"manual:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    updated = repo.set_collection_overrides(item_ids, collection_key=collection_key, note=payload.note)
    for item_id in item_ids:
        repo.log_learning_feedback(
            feedback_type="merge",
            feedback_value=collection_key,
            processed_id=item_id,
        )
    return {
        "updated_count": updated,
        "collection_key": collection_key,
    }


@router.post("/collections/unmerge")
def unmerge_collections(payload: UnmergeCollectionRequest):
    init_db()
    item_ids = [int(x) for x in payload.item_ids if int(x) > 0]
    if not item_ids:
        raise HTTPException(status_code=400, detail="Provide at least 1 item to unmerge.")

    removed = repo.clear_collection_overrides(item_ids)
    for item_id in item_ids:
        repo.log_learning_feedback(
            feedback_type="unmerge",
            feedback_value="automatic_grouping",
            processed_id=item_id,
        )
    return {
        "updated_count": removed,
        "message": "Selected items reverted to automatic grouping.",
    }

@router.post("/match/run")
def run_match_review(payload: MatchRunRequest):
    init_db()
    bucket = _normalize_domain_bucket(payload.domain_bucket)
    since_iso = window_start_iso(payload.days_window)

    items = repo.list_processed_since(since_iso=since_iso, limit=max(payload.lookback_items, 50))
    items = _filter_domain(_attach_domain_data(items), bucket)

    candidates = build_candidate_pairs(items, days_window=payload.days_window, top_k=payload.top_k)
    ai = AIClient()

    enqueued = 0
    reviewed = 0
    fallback_count = 0

    for left, right, heuristic_score in candidates:
        judgement = judge_pair(ai=ai, item_a=left, item_b=right, heuristic_score=heuristic_score)
        reviewed += 1
        if judgement.get("fallback"):
            fallback_count += 1

        if not should_enqueue_review(judgement):
            continue

        repo.upsert_match_review_pair(
            item_a_id=int(left.get("id") or 0),
            item_b_id=int(right.get("id") or 0),
            ai_same_story=str(judgement.get("same_story") or "no"),
            ai_confidence=float(judgement.get("confidence") or 0.0),
            reason_short=str(judgement.get("reason_short") or ""),
            overlap_entities=[str(x) for x in (judgement.get("overlap_entities") or [])],
            overlap_timeframe=str(judgement.get("overlap_timeframe") or ""),
        )
        enqueued += 1

    return {
        "checked_pairs": reviewed,
        "enqueued_pairs": enqueued,
        "fallback_pairs": fallback_count,
        "domain_bucket": bucket,
        "lookback_items": len(items),
    }


@router.get("/match-review")
def list_match_review(status: str = "pending", domain_bucket: str = "offshore_wind", limit: int = 30):
    if status not in {"pending", "accepted", "rejected"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    bucket = _normalize_domain_bucket(domain_bucket)
    items = repo.list_match_review_pairs(status=status, domain_bucket=bucket, limit=limit)
    return {"items": items}


@router.post("/match-review/decide")
def decide_match_review(payload: MatchReviewDecisionRequest):
    decision = str(payload.decision or "").strip().lower()
    if decision not in {"accept", "reject"}:
        raise HTTPException(status_code=400, detail="decision must be accept or reject")

    existing = repo.get_match_review_pair(payload.pair_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Pair not found")

    updated = repo.decide_match_review_pair(pair_id=payload.pair_id, decision=decision, actor=payload.actor)
    if updated <= 0:
        raise HTTPException(status_code=404, detail="Pair not found")

    item_ids = [int(existing.get("item_a_id") or 0), int(existing.get("item_b_id") or 0)]
    if decision == "accept":
        collection_key = make_manual_collection_key()
        repo.set_collection_overrides(item_ids, collection_key=collection_key, note="accepted_from_match_review")

    repo.log_learning_feedback(
        feedback_type="match_review_decision",
        feedback_value=decision,
        pair_id=payload.pair_id,
        actor=payload.actor,
    )

    return {
        "updated_count": updated,
        "pair_id": payload.pair_id,
        "decision": decision,
    }

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


@router.post("/sources/delete")
def remove_source(payload: DeleteSourceRequest):
    removed = delete_source(payload.index)
    if not removed:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"removed": removed}


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


@router.get("/sources/health-state")
def source_health_state():
    return {"items": repo.list_source_health_states()}


@router.get("/ai/status")
def ai_status(probe: bool = False):
    ai = AIClient()
    return ai.status(with_probe=bool(probe))

@router.post("/run/fetch-process")
def run_fetch_process(payload: RunFetchProcessRequest):
    init_db()

    days_back = max(1, int(payload.days_back or 7))
    threshold = datetime.now(timezone.utc) - timedelta(days=days_back)

    since_last = bool(payload.since_last)
    checkpoint_dt: datetime | None = None
    if since_last:
        checkpoint = repo.latest_raw_checkpoint()
        checkpoint_dt = _parse_iso_datetime(checkpoint) if checkpoint else None

    rss_items, rss_report = fetch_rss_items_with_report()
    scrape_items, scrape_report = fetch_scrape_items_with_report()
    source_report = [*rss_report, *scrape_report]
    fetched_items_all = [*rss_items, *scrape_items]

    fetched_items: list[dict[str, Any]] = []
    dropped_old = 0
    for item in fetched_items_all:
        published = _parse_iso_datetime(item.get("published_at"))
        if published and published < threshold:
            dropped_old += 1
            continue
        if since_last and checkpoint_dt and published and published <= checkpoint_dt:
            dropped_old += 1
            continue
        fetched_items.append(item)

    inserted = 0
    inserted_raw_ids: list[int] = []
    for item in fetched_items:
        new_raw_id = repo.upsert_raw_item_get_id(item)
        if new_raw_id is not None:
            inserted += 1
            inserted_raw_ids.append(int(new_raw_id))

    inserted_id_set = {int(x) for x in inserted_raw_ids}
    raws_new = repo.list_unprocessed_raw_by_ids(inserted_raw_ids)
    backlog_candidates = repo.list_unprocessed_raw(limit=200)
    backlog_raws = [r for r in backlog_candidates if int(r.get("id") or 0) not in inserted_id_set]
    raws = [*raws_new, *backlog_raws]

    queued_for_processing = len(raws)
    processed = 0
    processed_new_items = 0
    processed_backlog_items = 0
    processing_errors = 0
    processing_error_samples: list[str] = []
    for raw in raws:
        try:
            result = process_raw_item(raw)
            repo.save_processed_item(result)
            repo.mark_raw_processed(raw["id"])
            processed += 1
            if int(raw.get("id") or 0) in inserted_id_set:
                processed_new_items += 1
            else:
                processed_backlog_items += 1
        except Exception as ex:
            processing_errors += 1
            if len(processing_error_samples) < 5:
                rid = int(raw.get("id") or 0)
                processing_error_samples.append(f"raw_id={rid}: {ex.__class__.__name__}: {ex}")
            continue

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

    collection_items = _filter_domain(_attach_metadata(repo.latest(limit=300)), "offshore_wind")
    collections = _build_collections(
        items=collection_items,
        overrides=repo.list_collection_overrides(),
        limit=8,
        items_per_collection=3,
    )

    return {
        "fetched_candidates": len(fetched_items),
        "dropped_old_items": dropped_old,
        "days_back": days_back,
        "since_last": since_last,
        "new_raw_items": inserted,
        "queued_for_processing": queued_for_processing,
        "processed_items": processed,
        "processed_new_items": processed_new_items,
        "processed_backlog_items": processed_backlog_items,
        "processing_errors": processing_errors,
        "processing_error_samples": processing_error_samples,
        "source_report": source_report,
        "source_health": health_rows,
        "collection_preview": collections,
    }

