from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4
from typing import Any, Callable
from fastapi import HTTPException
from owis.core.storage.db import get_conn
from owis.modules.news.registry.source_discovery import load_source_registry, rediscover_rss_for_sources, source_health_report
from types import SimpleNamespace


_JOB_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="owis-news-job")


_JOBS: dict[str, dict[str, Any]] = {}


_JOBS_LOCK = Lock()


def _job_snapshot(job_id: str) -> dict[str, Any]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return dict(job)


def _update_job(job_id: str, **updates: Any) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job.update(updates)
        job["updated_at"] = datetime.now(timezone.utc).isoformat()


def _source_progress_from_registry(detail: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    registry = load_source_registry()
    sources = registry.get("sources", []) if isinstance(registry, dict) else registry
    for source in sources:
        if source.get("enabled") is False or not source.get('_collection_enabled', True):
            continue
        rows.append(
            {
                "source": source.get("name") or "Unknown",
                "type": source.get("type") or "source",
                "status": "pending",
                "detail": detail,
            }
        )
    return rows


def _mark_sources_active(rows: list[dict[str, Any]], active_index: int, done_detail: str = "Checked") -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        next_row = dict(row)
        if idx < active_index:
            next_row["status"] = "done"
            next_row["detail"] = next_row.get("detail_done") or done_detail
        elif idx == active_index:
            next_row["status"] = "active"
            next_row["detail"] = "Working..."
        else:
            next_row["status"] = next_row.get("status") or "pending"
        updated.append(next_row)
    return updated


def _complete_sources_from_report(report: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in report:
        error = row.get("error")
        items = int(row.get("items") or 0)
        filtered = int(row.get("filtered") or 0)
        rows.append(
            {
                **row,
                "status": "error" if error else "done",
                "detail": (f"error={error}" if error else f"items={items} | filtered={filtered}"),
            }
        )
    return rows


def _create_job(operation: str, payload: dict[str, Any], request_factory: Callable[..., Any] | None = None) -> str:
    """API callers supply their request model; internal callers supply prepared values."""
    job_id = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "id": job_id,
            "operation": operation,
            "status": "queued",
            "percent": 1,
            "step": "Queued",
            "source_progress": [],
            "result": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
    _JOB_EXECUTOR.submit(_run_job, job_id, operation, payload, request_factory)
    return job_id


def _run_job(job_id: str, operation: str, payload: dict[str, Any], request_factory: Callable[..., Any] | None = None) -> None:
    from owis.modules.news.processing.fetch_process import _run_fetch_process
    from owis.modules.news.processing.match_review import _run_match_review
    from owis.modules.news.processing.retention import _run_retention_archive
    from owis.modules.news.processing.item_view import enrich_article

    try:
        request = (request_factory or SimpleNamespace)(**payload)
        if operation == "fetch_process":
            _run_fetch_process(request, job_id=job_id)
            return

        if operation == "enrich_one":
            _update_job(job_id,status="running",percent=10,step="Henter kildegrunnlag")
            enrich_article(int(payload['item_id']))
            _update_job(job_id,status="completed",percent=100,step="Casebeskrivelse oppdatert",result={'updated':[payload['item_id']]})
            return
        if operation == "enrich_backfill":
            from owis.modules.news.processing.content import enrichment_eligible
            with get_conn() as c:
                rows=[dict(r) for r in c.execute("""SELECT r.*,p.id AS processed_id FROM news_raw_items r
                    JOIN news_processed_items p ON p.raw_item_id=r.id
                    LEFT JOIN news_case_versions v ON v.processed_id=p.id
                    WHERE COALESCE(v.version,0)<2 ORDER BY COALESCE(r.published_at,r.fetched_at) DESC LIMIT 300""")]
            selected=[r for r in rows if enrichment_eligible(r)[0]][:max(1,min(5,int(payload.get('limit',5))))]
            completed=[];errors=[]
            for index,raw in enumerate(selected):
                _update_job(job_id,status="running",percent=10+index*15,step=f"Expanding story {index+1}/{len(selected)}")
                try:
                    enrich_article(raw['processed_id'])
                    completed.append(raw['processed_id'])
                except Exception as exc:errors.append({'id':raw['processed_id'],'error':type(exc).__name__})
            _update_job(job_id,status="completed",percent=100,step="Expansion complete",result={'updated':completed,'errors':errors})
            return

        if operation == "rediscover_rss":
            _update_job(
                job_id,
                status="running",
                percent=8,
                step="Checking source homepages and RSS candidates...",
                source_progress=_source_progress_from_registry("Queued for RSS discovery"),
            )
            result = rediscover_rss_for_sources(
                only_scrape=bool(payload.get("only_scrape", False)),
                with_debug=bool(payload.get("with_debug", True)),
            )
            details = result.get("details") if isinstance(result, dict) else []
            if isinstance(details, list):
                rows = [
                    {
                        "source": row.get("source_name") or row.get("homepage") or "Unknown",
                        "type": "rss",
                        "status": "error" if row.get("homepage_error") else "done",
                        "detail": f"status={row.get('status') or 'checked'} | candidates={row.get('candidate_count') or 0}",
                        "error": row.get("homepage_error") or "",
                    }
                    for row in details
                ]
            else:
                rows = []
            _update_job(
                job_id,
                status="completed",
                percent=100,
                step="RSS discovery completed.",
                source_progress=rows,
                result=result,
            )
            return

        if operation == "source_health":
            _update_job(
                job_id,
                status="running",
                percent=8,
                step="Checking enabled sources...",
                source_progress=_source_progress_from_registry("Queued for health check"),
            )
            items = source_health_report(only_enabled=bool(payload.get("only_enabled", True)))
            rows = [
                {
                    "source": row.get("source") or "Unknown",
                    "type": "health",
                    "status": "done" if row.get("status") == "healthy" else "error",
                    "detail": f"status={row.get('status') or 'unknown'}{(' | ' + str(row.get('detail'))) if row.get('detail') else ''}",
                    "error": "" if row.get("status") == "healthy" else row.get("detail") or row.get("status") or "issue",
                }
                for row in items
            ]
            _update_job(
                job_id,
                status="completed",
                percent=100,
                step="Source health completed.",
                source_progress=rows,
                result={"items": items},
            )
            return

        if operation == "match_review":
            _run_match_review(request, job_id=job_id)
            return

        if operation == "retention_archive":
            _run_retention_archive(request, job_id=job_id)
            return

        _update_job(job_id, status="failed", error=f"Unknown operation: {operation}", step="Job failed")
    except Exception as ex:
        _update_job(
            job_id,
            status="failed",
            error=f"{ex.__class__.__name__}: {ex}",
            step="Job failed before completion.",
        )
