"""Regular news collection.

Many feeds list only their latest 10-20 items, so collecting only when someone
presses the button loses stories. This fetches every few hours during the day
(Europe/Oslo). A database claim prevents duplicate runs across restarts and
workers, and a run is skipped while another fetch is in progress.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from zoneinfo import ZoneInfo

from owis.core.storage.db import get_conn

logger = logging.getLogger(__name__)
OSLO = ZoneInfo("Europe/Oslo")
_CLAIM_KEY = "scheduled_fetch_last"


def schedule_info() -> dict:
    def number(name, default):
        try:
            return int(os.getenv(name, default))
        except ValueError:
            return int(default)
    return {
        "enabled": os.getenv("OWI_SCHEDULED_FETCH_ENABLED", "true").lower() in {"1", "true", "yes"},
        "interval_hours": max(1, number("OWI_FETCH_INTERVAL_HOURS", "3")),
        "first_hour": number("OWI_FETCH_FIRST_HOUR", "7"),   # after the 06:00 morning report
        "last_hour": number("OWI_FETCH_LAST_HOUR", "22"),
        "timezone": "Europe/Oslo",
    }


def claim(now: datetime, interval_hours: int) -> bool:
    """Atomically take the next slot; returns False if a run happened within the interval."""
    threshold = (now - timedelta(hours=interval_hours) + timedelta(minutes=5)).isoformat()
    with get_conn() as conn:
        cursor = conn.execute('''INSERT INTO news_registry_meta(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value WHERE news_registry_meta.value < ?''',
                              (_CLAIM_KEY, now.isoformat(), threshold))
        return cursor.rowcount > 0


def _fetch_running() -> bool:
    from owis.modules.news.presentation import api
    with api._JOBS_LOCK:
        return any(j["operation"] == "fetch_process" and j["status"] in {"queued", "running"} for j in api._JOBS.values())


def tick(now: datetime | None = None) -> bool:
    info = schedule_info()
    now = now or datetime.now(timezone.utc)
    hour = now.astimezone(OSLO).hour
    if not info["enabled"] or not (info["first_hour"] <= hour <= info["last_hour"]) or _fetch_running():
        return False
    if not claim(now, info["interval_hours"]):
        return False
    from owis.modules.news.presentation import api
    api._create_job("fetch_process", {"days_back": 2, "since_last": False})
    logger.info("Scheduled news fetch started")
    return True


def start_scheduler() -> Event:
    stop = Event()

    def loop():
        while not stop.is_set():
            try:
                tick()
            except Exception:
                logger.exception("Scheduled news fetch failed")
            stop.wait(300)

    if schedule_info()["enabled"]:
        Thread(target=loop, name="owis-fetch-clock", daemon=True).start()
    return stop
