"""Regular news collection.

Many feeds list only their latest 10-20 items, so collecting only when someone
presses the button loses stories. This fetches at fixed hours of the day
(Europe/Oslo), by default 08, 12, 15, 18 and 21, after the 06:00 morning
report. Each run fetches only what is new since the last fetch. A database
claim per hour prevents duplicate runs across restarts and workers; if the
server was down, only the latest missed hour of the day is caught up.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from threading import Event, Thread
from zoneinfo import ZoneInfo

from owis.core.storage.db import get_conn

logger = logging.getLogger(__name__)
OSLO = ZoneInfo("Europe/Oslo")
DEFAULT_HOURS = "8,12,15,18,21"


def schedule_info() -> dict:
    try:
        hours = sorted({int(h) for h in os.getenv("OWI_FETCH_HOURS", DEFAULT_HOURS).split(",") if h.strip()} & set(range(24)))
    except ValueError:
        hours = [int(h) for h in DEFAULT_HOURS.split(",")]
    return {
        "enabled": os.getenv("OWI_SCHEDULED_FETCH_ENABLED", "true").lower() in {"1", "true", "yes"},
        "hours": hours,
        "timezone": "Europe/Oslo",
    }


def claim(day: str, hour: int, now: datetime) -> bool:
    """Atomically take one hour's slot; False if another process already took it."""
    with get_conn() as conn:
        cursor = conn.execute('INSERT OR IGNORE INTO news_registry_meta(key, value) VALUES(?, ?)',
                              (f"scheduled_fetch:{day}:{hour:02d}", now.isoformat()))
        return cursor.rowcount > 0


def _fetch_running() -> bool:
    from owis.modules.news.presentation import api
    with api._JOBS_LOCK:
        return any(j["operation"] == "fetch_process" and j["status"] in {"queued", "running"} for j in api._JOBS.values())


def tick(now: datetime | None = None) -> bool:
    info = schedule_info()
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(OSLO)
    passed = [h for h in info["hours"] if h <= local.hour]
    if not info["enabled"] or not passed or _fetch_running():
        return False
    if not claim(local.date().isoformat(), passed[-1], now):
        return False
    from owis.modules.news.presentation import api
    api._create_job("fetch_process", {"days_back": 2, "since_last": True})
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
            stop.wait(60)

    if schedule_info()["enabled"]:
        Thread(target=loop, name="owis-fetch-clock", daemon=True).start()
    return stop
