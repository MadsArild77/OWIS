from datetime import datetime, timezone

import pytest

from owis.core.storage import db
from owis.modules.news.processing import fetch_scheduler as scheduler
from owis.modules.news.presentation import api


@pytest.fixture
def jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "sched.db"))
    db.init_db()
    monkeypatch.setenv("OWI_SCHEDULED_FETCH_ENABLED", "true")
    created = []
    monkeypatch.setattr(api, "_create_job", lambda op, payload: created.append((op, payload)) or "job")
    return created


def test_fetches_since_last_at_fixed_hours(jobs):
    day = datetime(2026, 10, 6, tzinfo=timezone.utc)                # Oslo is UTC+2
    assert not scheduler.tick(day.replace(hour=5, minute=59))       # 07:59: no slot yet
    assert scheduler.tick(day.replace(hour=6))                      # 08:00
    assert not scheduler.tick(day.replace(hour=7))                  # 09:00: 08 slot already taken
    assert scheduler.tick(day.replace(hour=10, minute=30))          # 12:30
    assert not scheduler.tick(day.replace(hour=11))
    assert jobs == [("fetch_process", {"days_back": 2, "since_last": True})] * 2


def test_only_the_latest_missed_hour_is_caught_up(jobs, monkeypatch):
    monkeypatch.setenv("OWI_FETCH_HOURS", "8,12,15")
    assert scheduler.tick(datetime(2026, 10, 6, 14, tzinfo=timezone.utc))   # 16:00, server was down since morning
    assert not scheduler.tick(datetime(2026, 10, 6, 14, 1, tzinfo=timezone.utc))
    assert len(jobs) == 1


def test_no_fetch_at_night_while_running_or_when_disabled(jobs, monkeypatch):
    assert not scheduler.tick(datetime(2026, 10, 6, 1, 0, tzinfo=timezone.utc))   # 03:00 in Oslo
    monkeypatch.setattr(scheduler, "_fetch_running", lambda: True)
    assert not scheduler.tick(datetime(2026, 10, 6, 8, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(scheduler, "_fetch_running", lambda: False)
    monkeypatch.setenv("OWI_SCHEDULED_FETCH_ENABLED", "false")
    assert not scheduler.tick(datetime(2026, 10, 6, 8, 0, tzinfo=timezone.utc))
    assert jobs == []
