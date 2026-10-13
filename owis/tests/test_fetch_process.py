from datetime import datetime, timedelta, timezone

import pytest

from owis.core.storage import db
from owis.modules.news.presentation import api


def raw(url, published):
    return dict(source_name="Test", article_url=url, title_raw="Offshore wind contract", summary_raw="Grid.",
                content_raw="Grid.", content_hash=url, published_at=published,
                fetched_at=datetime.now(timezone.utc).isoformat())


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "fetch.db"))
    db.init_db()
    for name in ("run_matching_after_fetch", "run_coverage_after_fetch"):
        monkeypatch.setattr(api, name, lambda: {})
    monkeypatch.setattr(api, "process_raw_item", lambda item: {**item, "raw_item_id": item["id"]})
    monkeypatch.setattr(api.repo, "save_processed_item", lambda item: 1)
    monkeypatch.setattr(api, "_run_retention_archive", lambda *a, **k: {})
    monkeypatch.setattr(api, "_build_collections", lambda **k: [])
    feed = {"rss": [], "scrape": []}
    monkeypatch.setattr(api, "fetch_rss_items_with_report", lambda: (feed["rss"], []))
    monkeypatch.setattr(api, "fetch_scrape_items_with_report", lambda: (feed["scrape"], []))
    return feed


def test_date_only_and_late_listed_articles_are_not_dropped(pipeline):
    now = datetime.now(timezone.utc)
    pipeline["rss"] = [raw("https://a.example/newest", now.isoformat())]
    assert api._run_fetch_process(api.RunFetchProcessRequest(days_back=2))["new_raw_items"] == 1
    # A scraped story with only today's date, and a feed story published earlier than the newest stored one.
    pipeline["rss"] = [raw("https://a.example/newest", now.isoformat()),
                       raw("https://b.example/late", (now - timedelta(hours=3)).isoformat())]
    pipeline["scrape"] = [raw("https://c.example/dated", now.date().isoformat())]
    result = api._run_fetch_process(api.RunFetchProcessRequest(days_back=2, since_last=True))
    assert result["new_raw_items"] == 2   # the already stored article is skipped by URL
