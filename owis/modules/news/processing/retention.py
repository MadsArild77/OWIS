from datetime import datetime, timedelta, timezone
from typing import Any
from owis.core.config.settings import NEWS_HIGH_SIGNAL_MIN_SCORE, NEWS_HIGH_SIGNAL_RETENTION_DAYS, NEWS_RETENTION_DAYS
from owis.core.storage.db import init_db
from owis.modules.news.processing.jobs import _update_job
from owis.modules.news.storage.repository import NewsRepository


repo = NewsRepository()


def _retention_cutoff(days: int | None = None) -> tuple[int, str]:
    retention_days = int(days or NEWS_RETENTION_DAYS or 90)
    retention_days = max(1, min(retention_days, 3650))
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    return retention_days, cutoff.isoformat()


def _run_retention_archive(payload: Any, job_id: str | None = None) -> dict[str, Any]:
    init_db()
    retention_days, cutoff_iso = _retention_cutoff(payload.days)
    if job_id:
        _update_job(
            job_id,
            status="running",
            percent=10,
            step=f"Archiving unprotected articles older than {retention_days} days...",
        )
    high_days, high_cutoff_iso = _retention_cutoff(max(retention_days, NEWS_HIGH_SIGNAL_RETENTION_DAYS))
    result = repo.archive_old_unprotected_items(cutoff_iso=cutoff_iso, limit=max(1, int(payload.limit or 1000)),
                                                high_signal_cutoff_iso=high_cutoff_iso,
                                                high_signal_min_score=NEWS_HIGH_SIGNAL_MIN_SCORE)
    summary = repo.archive_summary()
    payload_out = {
        **result,
        **summary,
        "retention_days": retention_days,
        "cutoff": cutoff_iso,
        "high_signal_retention_days": high_days,
        "high_signal_min_score": NEWS_HIGH_SIGNAL_MIN_SCORE,
        "mode": "archive_url_tags_then_purge_full_text",
    }
    if job_id:
        _update_job(
            job_id,
            status="completed",
            percent=100,
            step=f"Retention archive completed. archived={result.get('archived', 0)}",
            result=payload_out,
        )
    return payload_out
