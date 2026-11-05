from owis.modules.news.processing.content import prepare
from datetime import datetime, timedelta, timezone
import logging
import time
import os
from typing import Any
from owis.core.config.settings import NEWS_RETENTION_DAYS
from owis.core.storage.db import init_db
from owis.modules.news.collectors.rss_fetcher import fetch_rss_items_with_report
from owis.modules.news.collectors.scrape_fetcher import fetch_article_preview, fetch_scrape_items_with_report
from owis.modules.news.processing.pipeline import process_raw_item
from types import SimpleNamespace
from owis.modules.news.processing.jobs import _update_job, _source_progress_from_registry, _complete_sources_from_report
from owis.modules.news.processing.collections import _build_collections
from owis.modules.news.processing.after_fetch import run_case_accounts_after_fetch, run_coverage_after_fetch, run_matching_after_fetch
from owis.modules.news.processing.item_view import _parse_iso_datetime, _attach_metadata, _filter_domain
from owis.modules.news.processing.retention import _run_retention_archive
from owis.modules.news.storage.repository import NewsRepository


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


def _clock() -> float:
    return time.monotonic()


def _fetch_minutes() -> float:
    try:
        return max(1.0, float(os.getenv("OWI_FETCH_MAX_MINUTES", "10")))
    except ValueError:
        return 10.0


def _run_fetch_process(payload: Any, job_id: str | None = None) -> dict[str, Any]:
    """Fetch, process, group and search coverage within OWI_FETCH_MAX_MINUTES.

    Processing gets the first half of the time, grouping until 85 % and coverage
    search the rest. Whatever is not reached waits for the next run instead of
    keeping this one going.
    """
    init_db()
    started = _clock()
    budget = _fetch_minutes() * 60
    timings: dict[str, float] = {}
    phase_start = started

    def lap(name: str) -> None:
        nonlocal phase_start
        now = _clock()
        timings[name] = round(now - phase_start, 1)
        phase_start = now

    days_back = max(1, int(payload.days_back or 7))
    threshold = datetime.now(timezone.utc) - timedelta(days=days_back)
    if job_id:
        _update_job(
            job_id,
            status="running",
            percent=5,
            step=f"Preparing fetch pipeline (days_back={days_back})...",
            source_progress=_source_progress_from_registry("Queued for fetch"),
        )

    if job_id:
        _update_job(job_id, percent=14, step="Fetching RSS sources...")
    phase_start = _clock()
    rss_items, rss_report = fetch_rss_items_with_report()
    if job_id:
        _update_job(
            job_id,
            percent=38,
            step="RSS fetch completed. Fetching scrape sources...",
            source_progress=_complete_sources_from_report(rss_report),
        )
    scrape_items, scrape_report = fetch_scrape_items_with_report()
    source_report = [*rss_report, *scrape_report]
    fetched_items_all = [*rss_items, *scrape_items]
    if job_id:
        _update_job(
            job_id,
            percent=54,
            step=f"Fetched {len(fetched_items_all)} candidate items. Filtering by date...",
            source_progress=_complete_sources_from_report(source_report),
        )

    # Scraped articles come without a publication time; read it from the article page once.
    from owis.modules.news.collectors.dates import backfill, fill_new
    from owis.modules.news.collectors.scrape_fetcher import fetch_article_preview
    dated_new = fill_new(fetched_items_all, fetch_article_preview)
    dated_old = backfill(fetch_article_preview)

    fetched_items: list[dict[str, Any]] = []
    dropped_old = 0
    for item in fetched_items_all:
        published = _parse_iso_datetime(item.get("published_at"))
        if published and published < threshold:
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
    if job_id:
        _update_job(job_id, percent=64, step=f"Stored {inserted} new raw items. Loading processing queue...")

    lap("collect")
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
    total_raws = max(len(raws), 1)
    deferred_items = 0
    for index, raw in enumerate(raws):
        if _clock() > started + budget * 0.5:
            deferred_items = len(raws) - index  # left unprocessed; the next run picks them up
            break
        if job_id:
            pct = 66 + min(20, int((processed / total_raws) * 20))
            _update_job(job_id, percent=pct, step=f"AI processing item {processed + processing_errors + 1}/{len(raws)}...")
        try:
            result = process_raw_item(prepare(raw))
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
    if job_id:
        _update_job(job_id, percent=88, step="Updating source health state...")
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

    if job_id:
        _update_job(job_id, percent=92, step="Grouping coverage of the same story across sources...")
    lap("process")
    matching_result = run_matching_after_fetch(deadline=started + budget * 0.8)
    lap("matching")
    case_result = run_case_accounts_after_fetch(deadline=started + budget * 0.9)
    lap("cases")
    if job_id:
        _update_job(job_id, percent=93, step="Looking for other outlets' coverage of important single-source stories...")
    coverage_result = run_coverage_after_fetch(deadline=started + budget)
    lap("coverage")
    try:
        from owis.modules.news.registry.source_advisor import refresh_learned_weights
        refresh_learned_weights()
    except Exception:
        logging.getLogger(__name__).exception("Updating learned source weights failed")
    collection_items = _filter_domain(_attach_metadata(repo.latest(limit=300)), "offshore_wind")
    if job_id:
        _update_job(job_id, percent=94, step="Refreshing collection preview...")
    collections = _build_collections(
        items=collection_items,
        overrides=repo.list_collection_overrides(),
        masters=repo.list_collection_masters(),
        limit=8,
        items_per_collection=3,
    )
    if job_id:
        _update_job(job_id, percent=97, step="Applying retention archive policy...")
    retention_result = _run_retention_archive(
        SimpleNamespace(days=NEWS_RETENTION_DAYS, limit=1000),
        job_id=None,
    )

    result = {
        "fetched_candidates": len(fetched_items),
        "dropped_old_items": dropped_old,
        "days_back": days_back,
        "new_raw_items": inserted,
        "queued_for_processing": queued_for_processing,
        "processed_items": processed,
        "processed_new_items": processed_new_items,
        "processed_backlog_items": processed_backlog_items,
        "processing_errors": processing_errors,
        "processing_error_samples": processing_error_samples,
        "deferred_items": deferred_items,
        "dated_articles": dated_new + dated_old,
        "timings_seconds": {**timings, "total": round(_clock() - started, 1)},
        "source_report": source_report,
        "source_health": health_rows,
        "collection_preview": collections,
        "retention": retention_result,
        "matching": matching_result,
        "coverage": coverage_result,
        "cases": case_result,
    }
    logging.getLogger(__name__).info(
        "Fetch finished: new=%s processed=%s deferred=%s errors=%s timings=%s",
        inserted, processed, deferred_items, processing_errors, result["timings_seconds"])
    if job_id:
        step = "Fetch, processing and UI refresh completed."
        if deferred_items or (matching_result or {}).get("deferred_pairs"):
            step = "Time limit reached; the rest continues in the next fetch."
        _update_job(job_id, status="completed", percent=100, step=step, result=result)
    return result
