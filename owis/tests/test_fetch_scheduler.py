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


def test_fetches_every_interval_during_the_day(jobs):
    morning = datetime(2026, 10, 6, 6, 0, tzinfo=timezone.utc)      # 08:00 in Oslo
    assert scheduler.tick(morning)
    assert not scheduler.tick(morning.replace(hour=7))              # within three hours: already claimed
    assert scheduler.tick(morning.replace(hour=9))
    assert jobs == [("fetch_process", {"days_back": 2, "since_last": False})] * 2


def test_no_fetch_at_night_while_running_or_when_disabled(jobs, monkeypatch):
    assert not scheduler.tick(datetime(2026, 10, 6, 1, 0, tzinfo=timezone.utc))   # 03:00 in Oslo
    monkeypatch.setattr(scheduler, "_fetch_running", lambda: True)
    assert not scheduler.tick(datetime(2026, 10, 6, 8, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(scheduler, "_fetch_running", lambda: False)
    monkeypatch.setenv("OWI_SCHEDULED_FETCH_ENABLED", "false")
    assert not scheduler.tick(datetime(2026, 10, 6, 8, 0, tzinfo=timezone.utc))
    assert jobs == []
