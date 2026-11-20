"""Daily tender collection (D34).

Fetches and processes tenders once a day at OWI_OPP_FETCH_TIME (04:30
Europe/Oslo by default), before the 06:00 morning report lists new tenders.
Before each run, listed tenders are checked against the current profiles, so a
tightened profile also removes earlier matches; saved tenders are kept. A
database claim per day prevents duplicate runs across restarts and workers.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from threading import Event, Thread
from zoneinfo import ZoneInfo

from owis.core.config.settings import OPPORTUNITIES_ACTIVE_PROFILES
from owis.core.storage.db import get_conn
from owis.modules.opportunities.processing.pipeline import process_raw_item
from owis.modules.opportunities.registry.profile_loader import load_profile_bundle
from owis.modules.opportunities.storage.repository import OpportunitiesRepository

logger = logging.getLogger(__name__)
OSLO = ZoneInfo("Europe/Oslo")


def schedule_info() -> dict:
    try:
        hour, minute = (int(part) for part in os.getenv("OWI_OPP_FETCH_TIME", "04:30").split(":"))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError
    except ValueError:
        hour, minute = 4, 30
    return {"enabled": os.getenv("OWI_OPP_SCHEDULED_FETCH_ENABLED", "true").lower() in {"1", "true", "yes"},
            "time": f"{hour:02d}:{minute:02d}", "timezone": "Europe/Oslo"}


def claim(day: str, now: datetime) -> bool:
    with get_conn() as conn:
        cursor = conn.execute("INSERT OR IGNORE INTO news_registry_meta(key, value) VALUES(?, ?)",
                              (f"scheduled_opportunities:{day}", now.isoformat()))
        return cursor.rowcount > 0


def reclassify(repo: OpportunitiesRepository | None = None) -> int:
    repo = repo or OpportunitiesRepository()
    profiles = [p.strip().upper() for p in OPPORTUNITIES_ACTIVE_PROFILES if p.strip()]
    bundle = load_profile_bundle(active_profiles=profiles)
    if not bundle.get("by_company"):
        return 0
    removed = 0
    for raw in repo.processed_raw_items():
        if raw["state"] != "saved" and process_raw_item(raw, profile_bundle=bundle, active_profiles=profiles) is None:
            repo.remove_processed(raw["id"])
            removed += 1
    return removed


def run() -> dict:
    from owis.modules.opportunities.presentation.api import RunOpportunitiesRequest, run_fetch_process
    removed = reclassify()
    result = run_fetch_process(RunOpportunitiesRequest())
    logger.info("Scheduled tender run: %s removed by current profiles, %s new, %s matched",
                removed, result["new_raw_items"], result["processed_items"])
    return {"removed": removed, **result}


def tick(now: datetime | None = None) -> bool:
    info = schedule_info()
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(OSLO)
    if not info["enabled"] or local.strftime("%H:%M") < info["time"]:
        return False
    if not claim(local.date().isoformat(), now):
        return False
    run()
    return True


def start_scheduler() -> Event:
    stop = Event()

    def loop():
        # A deploy can change the profiles; clean the list right away instead of at the next run.
        try:
            reclassify()
        except Exception:
            logger.exception("Checking listed tenders against the profiles failed")
        while not stop.is_set():
            try:
                tick()
            except Exception:
                logger.exception("Scheduled tender run failed")
            stop.wait(60)

    if schedule_info()["enabled"]:
        Thread(target=loop, name="owis-opportunities-clock", daemon=True).start()
    return stop
